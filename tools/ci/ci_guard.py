#!/usr/bin/env python3
"""CI guard for boundary enforcement (with ops/signals guardrail)."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

FORBIDDEN_PATHS = ["data/", "exports/"]
PROGRESS_LOG_PATHS = [
    "exports/progress/PROGRESS_LOG.jsonl",
]
LEGACY_MIRROR_PREFIXES = ["modules/garment/", "modules/fitting/"]
STATUS_PATHS = ["ops/STATUS.md", "STATUS.md"]
SIGNALS_PREFIX = "ops/signals/"
ABS_WIN_RE = re.compile(r"[A-Za-z]:\\")
ABS_USERS_RE = re.compile(r"\\\\Users\\\\", re.IGNORECASE)


class CheckResult:
    __slots__ = ("severity", "label", "message")

    def __init__(self, severity: str, label: str, message: str):
        self.severity = severity
        self.label = label
        self.message = message


def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def find_repo_root(start_dir: Optional[Path] = None) -> Optional[Path]:
    if start_dir is None:
        start_dir = Path.cwd()
    current = start_dir.resolve()
    while True:
        if (current / ".git").is_dir():
            return current
        if (current / "project_map.md").is_file():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _run_git(repo_root: Path, args: List[str]) -> Tuple[str, Optional[str]]:
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception as exc:
        return "", f"git error: {exc}"
    if result.returncode != 0:
        return "", (result.stderr or "git command failed").strip()
    return result.stdout, None


def get_changed_files(repo_root: Path, base_ref: str, head_ref: str) -> Tuple[List[str], Optional[str]]:
    stdout, err = _run_git(repo_root, ["diff", "--name-only", f"{base_ref}...{head_ref}"])
    if err:
        return [], f"git diff failed: {err}"
    return [line.strip() for line in stdout.splitlines() if line.strip()], None


def get_file_diff(repo_root: Path, file_path: str, base_ref: str, head_ref: str) -> Tuple[str, Optional[str]]:
    stdout, err = _run_git(repo_root, ["diff", "--unified=0", f"{base_ref}...{head_ref}", "--", file_path])
    if err:
        return "", f"git diff failed: {err}"
    return stdout, None


def parse_loose_copies(repo_root: Path) -> Dict[str, str]:
    """Best-effort parser for project_map loose-copy hints."""
    project_map = repo_root / "project_map.md"
    if not project_map.is_file():
        return {}

    loose_copies: Dict[str, str] = {}
    try:
        with open(project_map, encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if "=>" not in line:
                    continue
                left, right = line.split("=>", 1)
                root_file = left.strip().strip("-*` ").split()[-1]
                canonical = right.strip().strip("` ")
                if root_file and "/" not in root_file and canonical:
                    loose_copies[root_file] = canonical
    except Exception:
        return {}
    return loose_copies


def check_forbidden_paths(changed_files: List[str]) -> List[CheckResult]:
    results: List[CheckResult] = []
    violations = []
    for file_path in changed_files:
        if any(file_path.startswith(prefix) for prefix in FORBIDDEN_PATHS):
            violations.append(file_path)
    if violations:
        for path in violations:
            results.append(CheckResult(FAIL, "forbidden_path", f"{path} (local-only, no commit)"))
    else:
        results.append(CheckResult(PASS, "forbidden_paths", "No exports/data commits"))
    return results


def check_progress_log_append_only(repo_root: Path, changed_files: List[str],
                                   base_ref: str, head_ref: str) -> List[CheckResult]:
    results: List[CheckResult] = []
    log_files = [f for f in changed_files if any(f.endswith(log) for log in PROGRESS_LOG_PATHS)]
    if not log_files:
        results.append(CheckResult(PASS, "progress_log", "No PROGRESS_LOG changes"))
        return results

    for log_file in log_files:
        diff, err = get_file_diff(repo_root, log_file, base_ref, head_ref)
        if err:
            results.append(CheckResult(WARN, f"progress_log:{log_file}", f"Could not get diff: {err}"))
            continue
        deletions = [line for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")]
        if deletions:
            results.append(CheckResult(FAIL, f"progress_log:{log_file}",
                                       f"Append-only violation: {len(deletions)} deletion(s) detected"))
        else:
            results.append(CheckResult(PASS, f"progress_log:{log_file}", "Append-only OK (additions only)"))
    return results


def check_loose_copies(changed_files: List[str], loose_copies: Dict[str, str],
                       canonical_also_changed: Set[str]) -> List[CheckResult]:
    results: List[CheckResult] = []
    violations = []
    for file_path in changed_files:
        if file_path in loose_copies:
            canonical = loose_copies[file_path]
            if canonical in canonical_also_changed:
                results.append(CheckResult(WARN, f"loose_copy:{file_path}",
                                           f"Modified with canonical -> {canonical} (sync OK)"))
            else:
                violations.append((file_path, canonical))

    if violations:
        for copy, canonical in violations:
            results.append(CheckResult(FAIL, f"loose_copy:{copy}",
                                       f"Root copy modified -> use canonical: {canonical}"))
    else:
        if not any(f in loose_copies for f in changed_files):
            results.append(CheckResult(PASS, "loose_copies", "No root copies modified"))
    return results


def check_status_generated(changed_files: List[str]) -> List[CheckResult]:
    results: List[CheckResult] = []
    status_files = [f for f in changed_files if f in STATUS_PATHS]
    if status_files:
        for sf in status_files:
            results.append(CheckResult(WARN, f"status:{sf}",
                                       "Modified: ensure generated-only block not manually edited"))
    else:
        results.append(CheckResult(PASS, "status", "No STATUS.md changes"))
    return results


def check_legacy_mirror_changes(repo_root: Path, changed_files: List[str]) -> List[CheckResult]:
    """Fail on edits under legacy in-repo garment/fitting mirrors; allow deletions for cleanup."""
    results: List[CheckResult] = []
    touched = [p for p in changed_files if any(p.startswith(prefix) for prefix in LEGACY_MIRROR_PREFIXES)]
    if not touched:
        results.append(CheckResult(PASS, "legacy_mirror", "No legacy mirror changes"))
        return results

    still_present = [p for p in touched if (repo_root / p).exists()]
    removed = [p for p in touched if not (repo_root / p).exists()]

    if still_present:
        sample = ", ".join(still_present[:5])
        if len(still_present) > 5:
            sample += ", ..."
        results.append(
            CheckResult(
                FAIL,
                "legacy_mirror",
                (
                    "In-repo garment/fitting mirrors are deprecated; edit external lab repos instead "
                    f"(changed present paths: {sample})"
                ),
            )
        )
    if removed:
        results.append(
            CheckResult(
                WARN,
                "legacy_mirror",
                f"Legacy mirror cleanup detected (removed paths: {len(removed)})",
            )
        )
    return results


def check_signals_no_abs_windows_paths(repo_root: Path, changed_files: List[str]) -> List[CheckResult]:
    """Fail if tracked ops/signals files contain Windows absolute path patterns."""
    results: List[CheckResult] = []
    targets = [p for p in changed_files if p.startswith(SIGNALS_PREFIX)]
    if not targets:
        results.append(CheckResult(PASS, "signals_abs_path", "No ops/signals changes"))
        return results

    violations: List[Tuple[str, str]] = []
    for rel in targets:
        path = repo_root / rel
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            results.append(CheckResult(WARN, f"signals_abs_path:{rel}", f"read failed: {exc}"))
            continue
        if ABS_WIN_RE.search(content) or ABS_USERS_RE.search(content):
            violations.append((rel, "windows absolute path pattern detected"))
            continue

        # If this is JSON and has run_dir_rel, enforce relative path safety.
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, dict):
            run_dir_rel = payload.get("run_dir_rel")
            if isinstance(run_dir_rel, str):
                if ":" in run_dir_rel:
                    violations.append((rel, "run_dir_rel must not contain ':'"))
                    continue
                if run_dir_rel.startswith("\\"):
                    violations.append((rel, "run_dir_rel must not start with '\\\\'"))
                    continue
                if "\\" in run_dir_rel:
                    violations.append((rel, "run_dir_rel must not contain '\\\\'"))
                    continue

    if violations:
        for rel, msg in violations:
            results.append(CheckResult(FAIL, f"signals_abs_path:{rel}", msg))
    else:
        results.append(CheckResult(PASS, "signals_abs_path", f"Checked {len(targets)} file(s)"))
    return results


def print_results(all_results: List[CheckResult], base_ref: str, head_ref: str) -> int:
    worst = PASS
    counts = {PASS: 0, WARN: 0, FAIL: 0}
    for r in all_results:
        counts[r.severity] = counts.get(r.severity, 0) + 1
        rank = {PASS: 0, WARN: 1, FAIL: 2}[r.severity]
        worst_rank = {PASS: 0, WARN: 1, FAIL: 2}[worst]
        if rank > worst_rank:
            worst = r.severity

    if worst == PASS:
        _safe_print("CI_GUARD SUMMARY: PASS")
    else:
        _safe_print(f"CI_GUARD SUMMARY: {worst} ({counts[worst]})")
    _safe_print()

    _safe_print(f"-- Base: {base_ref}, Head: {head_ref} --")
    _safe_print()

    fails = [r for r in all_results if r.severity == FAIL]
    warns = [r for r in all_results if r.severity == WARN]
    passes = [r for r in all_results if r.severity == PASS]

    if fails:
        _safe_print("-- FAIL --")
        for r in fails:
            _safe_print(f"  [FAIL] {r.label}: {r.message}")
        _safe_print()

    if warns:
        _safe_print("-- WARN --")
        for r in warns:
            _safe_print(f"  [WARN] {r.label}: {r.message}")
        _safe_print()

    if passes:
        _safe_print("-- PASS --")
        for r in passes:
            _safe_print(f"  [PASS] {r.label}: {r.message}")
        _safe_print()

    _safe_print("-- Checks Performed --")
    _safe_print("  A) exports/**, data/** commit prevention")
    _safe_print("  B) PROGRESS_LOG append-only enforcement")
    _safe_print("  C) Root loose copies modification prevention")
    _safe_print("  D) STATUS.md generated-only warning")
    _safe_print("  E) ops/signals/** absolute Windows path guardrail")
    _safe_print("  F) In-repo garment/fitting legacy mirror edit prevention")
    _safe_print()

    if worst == FAIL:
        _safe_print("-- Next Actions --")
        _safe_print("  Fix FAIL items above before merging PR.")

    return 1 if worst == FAIL else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CI guard for boundary enforcement (Round 05)")
    parser.add_argument("--base", type=str, default="origin/main", help="Base ref for diff (default: origin/main)")
    parser.add_argument("--head", type=str, default="HEAD", help="Head ref for diff (default: HEAD)")
    parser.add_argument("--repo-root", type=str, default=None, help="Repo root (default: auto-detect)")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root) if args.repo_root else find_repo_root()
    if not repo_root:
        _safe_print("ERROR: Could not find repo root. Use --repo-root or run from repo.")
        return 1

    changed_files, err = get_changed_files(repo_root, args.base, args.head)
    if err:
        _safe_print(f"ERROR: {err}")
        _safe_print("Trying fallback: HEAD~1...HEAD")
        changed_files, err2 = get_changed_files(repo_root, "HEAD~1", "HEAD")
        if err2:
            _safe_print(f"ERROR: Fallback also failed: {err2}")
            return 1
        args.base = "HEAD~1"

    loose_copies = parse_loose_copies(repo_root)
    canonical_changed = set(f for f in changed_files if f in loose_copies.values())

    all_results: List[CheckResult] = []
    all_results.extend(check_forbidden_paths(changed_files))
    all_results.extend(check_progress_log_append_only(repo_root, changed_files, args.base, args.head))
    all_results.extend(check_loose_copies(changed_files, loose_copies, canonical_changed))
    all_results.extend(check_status_generated(changed_files))
    all_results.extend(check_legacy_mirror_changes(repo_root, changed_files))
    all_results.extend(check_signals_no_abs_windows_paths(repo_root, changed_files))

    return print_results(all_results, args.base, args.head)


if __name__ == "__main__":
    sys.exit(main())
