#!/usr/bin/env python3
"""doctor.py — Neural Vision repo bootstrap / health checker.

Read-only by default.  With --fix, creates missing (empty) directories
and placeholder PROGRESS_LOG.jsonl files so that the ops pipeline can run.

Exit codes:
    0  PASS or WARN-only
    1  at least one FAIL
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

REQUIRED_BOOT_FILES: List[Tuple[str, List[str]]] = [
    # (label, candidate_paths — first existing wins)
    ("HUB", ["HUB.md", "ops/HUB.md"]),
    ("STATUS", ["STATUS.md", "ops/STATUS.md"]),
    ("project_map", ["project_map.md"]),
    ("unlock_conditions", ["unlock_conditions_u1_u2.md"]),
    ("phase_plan", ["phase_plan_unlock_driven.md"]),
]

REQUIRED_SCRIPTS: List[str] = [
    "tools/render_work_briefs.py",
    "tools/render_status.py",
    "tools/ops/append_progress_event.py",
    "tools/ops/run_end_ops_hook.py",
]

PROGRESS_LOG_LOCATIONS: List[str] = [
    "exports/progress/PROGRESS_LOG.jsonl",
    "modules/fitting/exports/progress/PROGRESS_LOG.jsonl",
    "modules/garment/exports/progress/PROGRESS_LOG.jsonl",
]

GITIGNORE_EXPECTED_PATTERNS: List[str] = [
    "data/",
    "exports/",
]

# ──────────────────────────────────────────────────────────────────────
# Severity helpers
# ──────────────────────────────────────────────────────────────────────

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


class CheckResult:
    """Single check outcome."""

    def __init__(self, severity: str, label: str, message: str,
                 detail: Optional[str] = None):
        self.severity = severity
        self.label = label
        self.message = message
        self.detail = detail

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "severity": self.severity,
            "label": self.label,
            "message": self.message,
        }
        if self.detail:
            d["detail"] = self.detail
        return d


# ──────────────────────────────────────────────────────────────────────
# 1) Repo root detection
# ──────────────────────────────────────────────────────────────────────

def find_repo_root(start: Optional[Path] = None) -> Tuple[Optional[Path], CheckResult]:
    """Walk upward from *start* (default cwd) looking for .git/ or project_map.md."""
    cur = (start or Path.cwd()).resolve()
    for _ in range(20):  # safety cap
        if (cur / ".git").is_dir():
            return cur, CheckResult(PASS, "repo_root", f"Found .git at {cur}")
        if (cur / "project_map.md").is_file():
            return cur, CheckResult(PASS, "repo_root",
                                    f"Fallback: project_map.md at {cur}")
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return None, CheckResult(FAIL, "repo_root",
                             "Could not locate repo root (.git/ or project_map.md)")


# ──────────────────────────────────────────────────────────────────────
# 2) Required boot files
# ──────────────────────────────────────────────────────────────────────

def check_required_files(root: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    for label, candidates in REQUIRED_BOOT_FILES:
        found = None
        for c in candidates:
            if (root / c).is_file():
                found = c
                break
        if found:
            results.append(CheckResult(PASS, f"file:{label}", f"Found {found}"))
        else:
            tried = ", ".join(candidates)
            results.append(CheckResult(FAIL, f"file:{label}",
                                       f"Missing (tried: {tried})"))
    return results


# ──────────────────────────────────────────────────────────────────────
# 3) Required ops scripts
# ──────────────────────────────────────────────────────────────────────

def check_required_scripts(root: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    for script in REQUIRED_SCRIPTS:
        if (root / script).is_file():
            results.append(CheckResult(PASS, f"script:{script}", "OK"))
        else:
            results.append(CheckResult(FAIL, f"script:{script}", "Missing"))
    return results


# ──────────────────────────────────────────────────────────────────────
# 4) Write-boundary / gitignore warnings
# ──────────────────────────────────────────────────────────────────────

def check_gitignore_patterns(root: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    gi_path = root / ".gitignore"
    if not gi_path.is_file():
        results.append(CheckResult(WARN, "gitignore", ".gitignore not found"))
        return results

    try:
        gi_text = gi_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        results.append(CheckResult(WARN, "gitignore", "Could not read .gitignore"))
        return results

    for pat in GITIGNORE_EXPECTED_PATTERNS:
        # Accept any line containing the pattern (e.g. "data/**", "exports/runs/")
        if any(pat in line for line in gi_text.splitlines()):
            results.append(CheckResult(PASS, f"gitignore:{pat}",
                                       f"Pattern containing '{pat}' found"))
        else:
            results.append(CheckResult(WARN, f"gitignore:{pat}",
                                       f"No gitignore pattern containing '{pat}'"))
    return results


def check_progress_logs(root: Path, *, fix: bool = False) -> List[CheckResult]:
    results: List[CheckResult] = []
    for loc in PROGRESS_LOG_LOCATIONS:
        full = root / loc
        if full.is_file():
            results.append(CheckResult(PASS, f"progress_log:{loc}", "Exists"))
        else:
            msg = f"Missing: {loc}"
            if fix:
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text("", encoding="utf-8")
                msg += " → created (empty)"
            results.append(CheckResult(WARN, f"progress_log:{loc}", msg))
    return results


# ──────────────────────────────────────────────────────────────────────
# 5) Root loose files (copies)
# ──────────────────────────────────────────────────────────────────────

_LOOSE_BLOCK_RE = re.compile(
    r"##\s*Root\s+루즈\s+파일\s*\(정리\s*대상\).*?```(.*?)```",
    re.DOTALL,
)
_LOOSE_LINE_RE = re.compile(
    r"[├└]──\s+(\S+)\s+#\s*→\s*(.+?)(?:\s+의\s+사본)?$",
)


def _parse_loose_map(root: Path) -> Optional[List[Tuple[str, str]]]:
    """Return [(root_file, canonical_path), ...] or None on parse failure.
    
    Returns empty list [] if section indicates "NONE" or "cleaned" status.
    """
    pm = root / "project_map.md"
    if not pm.is_file():
        return None
    try:
        text = pm.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    
    # Find the section header
    section_match = re.search(
        r"##\s*Root\s+루즈\s+파일\s*\(정리\s*대상\)(.*?)(?=^##|\Z)",
        text, re.MULTILINE | re.DOTALL
    )
    if not section_match:
        return None
    
    section_content = section_match.group(1)
    
    # Check for "Status: NONE" or "Round 06 cleaned" indicating no active loose files
    if re.search(r"Status.*?NONE|cleaned|Round\s*0?6", section_content, re.IGNORECASE):
        return []  # Empty list = no loose files (success state)
    
    # Try old format (code block with tree structure)
    m = _LOOSE_BLOCK_RE.search(text)
    if m:
        block = m.group(1)
        pairs: List[Tuple[str, str]] = []
        for line in block.splitlines():
            lm = _LOOSE_LINE_RE.search(line)
            if lm:
                pairs.append((lm.group(1).strip(), lm.group(2).strip()))
        return pairs if pairs else None
    
    return None


def check_loose_files(root: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    mapping = _parse_loose_map(root)
    if mapping is None:
        results.append(CheckResult(
            WARN, "loose_files",
            "project_map.md에 'Root 루즈 파일 (정리 대상)' 섹션을 찾지 못함"))
        return results

    found_any = False
    for filename, canonical in mapping:
        if (root / filename).is_file():
            found_any = True
            results.append(CheckResult(
                WARN, f"loose:{filename}",
                f"Root copy exists -> canonical: {canonical}"))
    if not found_any:
        results.append(CheckResult(PASS, "loose_files",
                                   "No root loose copies detected"))
    return results


# ──────────────────────────────────────────────────────────────────────
# 6) Lab roots config
# ──────────────────────────────────────────────────────────────────────

def check_lab_roots(root: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    lr_path = root / "ops" / "lab_roots.local.json"

    # Track which keys are configured via local config
    local_config_valid = {"FITTING_LAB_ROOT": False, "GARMENT_LAB_ROOT": False}

    if not lr_path.is_file():
        results.append(CheckResult(
            WARN, "lab_roots:file",
            "ops/lab_roots.local.json not found (optional - use .example to create)"))
    else:
        try:
            data = json.loads(lr_path.read_text(encoding="utf-8", errors="ignore"))
            results.append(CheckResult(PASS, "lab_roots:file",
                                       "ops/lab_roots.local.json parsed OK"))
            for key in ("FITTING_LAB_ROOT", "GARMENT_LAB_ROOT"):
                val = data.get(key)
                if val:
                    resolved = (root / val).resolve()
                    if resolved.is_dir():
                        results.append(CheckResult(
                            PASS, f"lab_roots:{key}",
                            f"{key}={val} → exists"))
                        local_config_valid[key] = True
                    else:
                        results.append(CheckResult(
                            WARN, f"lab_roots:{key}",
                            f"{key}={val} → directory not found"))
                else:
                    results.append(CheckResult(
                        WARN, f"lab_roots:{key}",
                        f"{key} not set in lab_roots.local.json"))
        except (json.JSONDecodeError, OSError) as exc:
            results.append(CheckResult(
                WARN, "lab_roots:file",
                f"ops/lab_roots.local.json parse error: {exc}"))

    # Environment variable info
    for env_key in ("FITTING_LAB_ROOT", "GARMENT_LAB_ROOT"):
        val = os.environ.get(env_key)
        if val:
            results.append(CheckResult(
                PASS, f"env:{env_key}", f"Set → {val}"))
        else:
            # If local config is valid, downgrade to PASS with info message
            if local_config_valid[env_key]:
                results.append(CheckResult(
                    PASS, f"env:{env_key}",
                    f"Not set (OK: ops/lab_roots.local.json provides {env_key})"))
            else:
                results.append(CheckResult(
                    WARN, f"env:{env_key}", "Not set"))

    return results


# ──────────────────────────────────────────────────────────────────────
# Aggregation & output
# ──────────────────────────────────────────────────────────────────────

def _severity_rank(s: str) -> int:
    return {PASS: 0, WARN: 1, FAIL: 2}.get(s, 0)


def _summary_line(results: List[CheckResult]) -> Tuple[str, int]:
    """Return (overall_severity, count_of_that_severity)."""
    worst = PASS
    counts = {PASS: 0, WARN: 0, FAIL: 0}
    for r in results:
        counts[r.severity] = counts.get(r.severity, 0) + 1
        if _severity_rank(r.severity) > _severity_rank(worst):
            worst = r.severity
    return worst, counts[worst]


def _safe_print(text: str = "") -> None:
    """Print with fallback for consoles that cannot encode all Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def print_human(results: List[CheckResult], repo_root: Optional[Path]) -> None:
    worst, count = _summary_line(results)
    if worst == PASS:
        _safe_print("DOCTOR SUMMARY: PASS")
    else:
        _safe_print(f"DOCTOR SUMMARY: {worst} ({count})")
    _safe_print()

    # --- Repo Root ---
    _safe_print("-- Repo Root --")
    for r in results:
        if r.label == "repo_root":
            _safe_print(f"  [{r.severity}] {r.message}")
    _safe_print()

    # --- Required Files ---
    _safe_print("-- Required Files --")
    for r in results:
        if r.label.startswith("file:"):
            tag = r.label.split(":", 1)[1]
            _safe_print(f"  [{r.severity}] {tag}: {r.message}")
    _safe_print()

    # --- Required Scripts ---
    _safe_print("-- Required Scripts --")
    for r in results:
        if r.label.startswith("script:"):
            script = r.label.split(":", 1)[1]
            _safe_print(f"  [{r.severity}] {script}")
    _safe_print()

    # --- Warnings ---
    warnings = [r for r in results
                if r.severity == WARN and not r.label.startswith(("file:", "script:"))]
    if warnings:
        _safe_print("-- Warnings --")
        for r in warnings:
            _safe_print(f"  [{WARN}] {r.label}: {r.message}")
        _safe_print()

    # --- Suggested next command ---
    _safe_print("-- Suggested Next Command --")
    if worst == FAIL:
        fails = [r for r in results if r.severity == FAIL]
        missing_files = [r for r in fails if r.label.startswith("file:")]
        if missing_files:
            names = ", ".join(r.label.split(":", 1)[1] for r in missing_files)
            _safe_print(f"  Fix missing required files first: {names}")
        missing_scripts = [r for r in fails if r.label.startswith("script:")]
        if missing_scripts:
            names = ", ".join(r.label.split(":", 1)[1] for r in missing_scripts)
            _safe_print(f"  Fix missing scripts: {names}")
    else:
        _safe_print("  py tools/render_status.py   # refresh STATUS.md")
        _safe_print("  py tools/ops/run_end_ops_hook.py   # full ops cycle")


def print_json(results: List[CheckResult], repo_root: Optional[Path]) -> None:
    worst, count = _summary_line(results)
    out: Dict[str, Any] = {
        "summary": worst,
        "summary_count": count,
        "repo_root": str(repo_root) if repo_root else None,
        "checks": [r.to_dict() for r in results],
    }
    _safe_print(json.dumps(out, indent=2, ensure_ascii=False))


# ──────────────────────────────────────────────────────────────────────
# CLI entry
# ──────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Neural Vision repo bootstrap / health checker")
    parser.add_argument("--repo-root", type=str, default=None,
                        help="Repo root path (default: auto-detect upward from cwd)")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Output structured JSON")
    parser.add_argument("--fix", action="store_true",
                        help="Create missing dirs / empty PROGRESS_LOG.jsonl (safe)")
    args = parser.parse_args(argv)

    # ── 1) Repo root ──
    start = Path(args.repo_root) if args.repo_root else None
    repo_root, root_result = find_repo_root(start)
    results: List[CheckResult] = [root_result]

    if repo_root is None:
        # Cannot proceed without a root
        if args.json_output:
            print_json(results, repo_root)
        else:
            print_human(results, repo_root)
        return 1

    # ── 2) Required boot files ──
    results.extend(check_required_files(repo_root))

    # ── 3) Required scripts ──
    results.extend(check_required_scripts(repo_root))

    # ── 4) Gitignore patterns + PROGRESS_LOG ──
    results.extend(check_gitignore_patterns(repo_root))
    results.extend(check_progress_logs(repo_root, fix=args.fix))

    # ── 5) Loose files ──
    results.extend(check_loose_files(repo_root))

    # ── 6) Lab roots ──
    results.extend(check_lab_roots(repo_root))

    # ── Output ──
    if args.json_output:
        print_json(results, repo_root)
    else:
        print_human(results, repo_root)

    worst, _ = _summary_line(results)
    return 1 if worst == FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
