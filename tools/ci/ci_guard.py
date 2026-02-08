#!/usr/bin/env python3
"""ci_guard.py — CI guard for boundary enforcement (Round 05).

Enforces:
  - exports/**, data/** commit prevention
  - PROGRESS_LOG append-only (no deletions)
  - Root loose copies modification prevention
  - STATUS.md generated-only warning

Exit codes: 0 = PASS/WARN, 1 = FAIL
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ── Constants ────────────────────────────────────────────────────────

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

FORBIDDEN_PATHS = ["data/", "exports/"]
PROGRESS_LOG_PATHS = [
    "exports/progress/PROGRESS_LOG.jsonl",
    "modules/body/exports/progress/PROGRESS_LOG.jsonl",
    "modules/garment/exports/progress/PROGRESS_LOG.jsonl",
    "modules/fitting/exports/progress/PROGRESS_LOG.jsonl",
]
STATUS_PATHS = ["ops/STATUS.md", "STATUS.md"]


class CheckResult:
    """Single check result."""
    __slots__ = ("severity", "label", "message")

    def __init__(self, severity: str, label: str, message: str):
        self.severity = severity
        self.label = label
        self.message = message


# ── Repo root detection ──────────────────────────────────────────────

def find_repo_root(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find repository root by walking up until .git/ or project_map.md."""
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


# ── Git diff operations ──────────────────────────────────────────────

def get_changed_files(repo_root: Path, base_ref: str, head_ref: str) -> Tuple[List[str], Optional[str]]:
    """Get list of changed files between base and head."""
    cmd = ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if result.returncode != 0:
            return [], f"git diff failed: {result.stderr[:200]}"
        files = [line.strip() for line in result.stdout.split("\n") if line.strip()]
        return files, None
    except Exception as exc:
        return [], f"git diff error: {exc}"


def get_file_diff(repo_root: Path, file_path: str, base_ref: str, head_ref: str) -> Tuple[str, Optional[str]]:
    """Get unified diff for a specific file."""
    cmd = ["git", "diff", "--unified=0", f"{base_ref}...{head_ref}", "--", file_path]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return result.stdout, None
    except Exception as exc:
        return "", f"git diff error: {exc}"


# ── Root loose copies parser ─────────────────────────────────────────

def parse_loose_copies(repo_root: Path) -> Dict[str, str]:
    """Parse project_map.md for root loose copies mapping."""
    project_map = repo_root / "project_map.md"
    if not project_map.is_file():
        return {}

    loose_copies: Dict[str, str] = {}
    try:
        with open(project_map, encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Find "Root 루즈 파일 (정리 대상)" section
        match = re.search(r"##\s*Root 루즈 파일.*?\n```(.*?)```", content, re.DOTALL)
        if not match:
            return {}

        section = match.group(1)
        # Parse lines like: ├── dependency_ledger_v1.json # → contracts/dependency_ledger_v1.json 의 사본
        for line in section.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Extract filename and canonical path
            parts = re.split(r"[├└│]", line)
            if len(parts) < 2:
                continue
            file_part = parts[1].strip()
            if "→" in file_part:
                file_name = file_part.split("#")[0].strip()
                canonical_match = re.search(r"→\s*([^\s]+)", file_part)
                if canonical_match:
                    canonical = canonical_match.group(1).strip()
                    loose_copies[file_name] = canonical

        return loose_copies
    except Exception:
        return {}


# ── Check implementations ────────────────────────────────────────────

def check_forbidden_paths(changed_files: List[str]) -> List[CheckResult]:
    """Check A: exports/**, data/** commit detection."""
    results: List[CheckResult] = []
    violations = []

    for file_path in changed_files:
        for forbidden in FORBIDDEN_PATHS:
            if file_path.startswith(forbidden):
                violations.append(file_path)
                break

    if violations:
        for v in violations:
            results.append(CheckResult(FAIL, "forbidden_path", f"{v} (local-only, no commit)"))
    else:
        results.append(CheckResult(PASS, "forbidden_paths", "No exports/data commits"))

    return results


def check_progress_log_append_only(repo_root: Path, changed_files: List[str],
                                     base_ref: str, head_ref: str) -> List[CheckResult]:
    """Check B: PROGRESS_LOG append-only (no deletions)."""
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

        # Check for deletions (lines starting with -)
        deletions = [line for line in diff.split("\n") if line.startswith("-") and not line.startswith("---")]
        if deletions:
            results.append(CheckResult(FAIL, f"progress_log:{log_file}",
                                      f"Append-only violation: {len(deletions)} deletion(s) detected"))
        else:
            results.append(CheckResult(PASS, f"progress_log:{log_file}", "Append-only OK (additions only)"))

    return results


def check_loose_copies(changed_files: List[str], loose_copies: Dict[str, str],
                        canonical_also_changed: Set[str]) -> List[CheckResult]:
    """Check C: Root loose copies modification."""
    results: List[CheckResult] = []
    violations = []

    for file_path in changed_files:
        if file_path in loose_copies:
            canonical = loose_copies[file_path]
            if canonical in canonical_also_changed:
                # Both copy and canonical modified → downgrade to WARN
                results.append(CheckResult(WARN, f"loose_copy:{file_path}",
                                          f"Modified with canonical → {canonical} (sync OK)"))
            else:
                violations.append((file_path, canonical))

    if violations:
        for copy, canonical in violations:
            results.append(CheckResult(FAIL, f"loose_copy:{copy}",
                                      f"Root copy modified → use canonical: {canonical}"))
    else:
        if not any(f in loose_copies for f in changed_files):
            results.append(CheckResult(PASS, "loose_copies", "No root copies modified"))

    return results


def check_status_generated(changed_files: List[str]) -> List[CheckResult]:
    """Check D: STATUS.md generated-only warning."""
    results: List[CheckResult] = []
    status_files = [f for f in changed_files if f in STATUS_PATHS]

    if status_files:
        for sf in status_files:
            results.append(CheckResult(WARN, f"status:{sf}",
                                      "Modified: ensure generated-only block not manually edited"))
    else:
        results.append(CheckResult(PASS, "status", "No STATUS.md changes"))

    return results


# ── Output formatting ────────────────────────────────────────────────

def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def print_results(all_results: List[CheckResult], base_ref: str, head_ref: str) -> int:
    """Print summary and return exit code."""
    worst = PASS
    counts = {PASS: 0, WARN: 0, FAIL: 0}
    for r in all_results:
        counts[r.severity] = counts.get(r.severity, 0) + 1
        rank = {PASS: 0, WARN: 1, FAIL: 2}.get(r.severity, 0)
        worst_rank = {PASS: 0, WARN: 1, FAIL: 2}.get(worst, 0)
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
    if fails:
        _safe_print("-- FAIL --")
        for r in fails:
            _safe_print(f"  [FAIL] {r.label}: {r.message}")
        _safe_print()

    warns = [r for r in all_results if r.severity == WARN]
    if warns:
        _safe_print("-- WARN --")
        for r in warns:
            _safe_print(f"  [WARN] {r.label}: {r.message}")
        _safe_print()

    passes = [r for r in all_results if r.severity == PASS]
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
    _safe_print()

    if worst == FAIL:
        _safe_print("-- Next Actions --")
        _safe_print("  Fix FAIL items above before merging PR.")

    return 1 if worst == FAIL else 0


# ── Main ─────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="CI guard for boundary enforcement (Round 05)")
    parser.add_argument("--base", type=str, default="origin/main",
                        help="Base ref for diff (default: origin/main)")
    parser.add_argument("--head", type=str, default="HEAD",
                        help="Head ref for diff (default: HEAD)")
    parser.add_argument("--repo-root", type=str, default=None,
                        help="Repo root (default: auto-detect)")
    args = parser.parse_args(argv)

    # Repo root
    if args.repo_root:
        repo_root = Path(args.repo_root)
    else:
        repo_root = find_repo_root()
    if not repo_root:
        _safe_print("ERROR: Could not find repo root. Use --repo-root or run from repo.")
        return 1

    # Get changed files
    changed_files, err = get_changed_files(repo_root, args.base, args.head)
    if err:
        _safe_print(f"ERROR: {err}")
        _safe_print("Trying fallback: HEAD~1...HEAD")
        changed_files, err2 = get_changed_files(repo_root, "HEAD~1", "HEAD")
        if err2:
            _safe_print(f"ERROR: Fallback also failed: {err2}")
            return 1
        args.base = "HEAD~1"

    # Parse loose copies
    loose_copies = parse_loose_copies(repo_root)
    canonical_changed = set(f for f in changed_files if f in loose_copies.values())

    # Run checks
    all_results: List[CheckResult] = []
    all_results.extend(check_forbidden_paths(changed_files))
    all_results.extend(check_progress_log_append_only(repo_root, changed_files, args.base, args.head))
    all_results.extend(check_loose_copies(changed_files, loose_copies, canonical_changed))
    all_results.extend(check_status_generated(changed_files))

    return print_results(all_results, args.base, args.head)


if __name__ == "__main__":
    sys.exit(main())
