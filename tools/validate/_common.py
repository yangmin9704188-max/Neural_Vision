"""Shared helpers for U1 validators.

Standard-library only. Windows-safe (pathlib, utf-8).
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Severity constants ──────────────────────────────────────────────
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


class CheckResult:
    """Single check outcome."""

    __slots__ = ("severity", "label", "message")

    def __init__(self, severity: str, label: str, message: str):
        self.severity = severity
        self.label = label
        self.message = message

    def to_dict(self) -> Dict[str, str]:
        return {"severity": self.severity, "label": self.label, "message": self.message}


# ── Safe JSON loader (NaN/Infinity → FAIL) ──────────────────────────

def _reject_nan_inf(val: str) -> None:  # pragma: no cover
    """parse_constant callback — raise on NaN / Infinity / -Infinity."""
    raise ValueError(f"JSON contains forbidden literal: {val!r}")


def safe_json_load(path: Path) -> Tuple[Optional[Any], Optional[str]]:
    """Load JSON file, rejecting NaN/Infinity.

    Returns (data, None) on success or (None, error_message) on failure.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return None, f"Cannot read {path}: {exc}"
    try:
        data = json.loads(text, parse_constant=_reject_nan_inf)
    except (json.JSONDecodeError, ValueError) as exc:
        return None, f"JSON parse error in {path.name}: {exc}"
    return data, None


# ── Absolute-path detector ──────────────────────────────────────────

_ABS_PATH_RE = re.compile(r"^(/|\\\\|[A-Za-z]:)")


def is_absolute_path(p: str) -> bool:
    """Return True if *p* looks like an absolute path."""
    return bool(_ABS_PATH_RE.match(p))


# ── Fingerprint format check ────────────────────────────────────────

_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_SHA256_PREFIX_RE = re.compile(r"^sha256:[0-9a-fA-F]+")


def is_plausible_fingerprint(fp: str) -> bool:
    """Accept bare 64-hex or sha256:<hex> prefixed format."""
    return bool(_HEX64_RE.match(fp) or _SHA256_PREFIX_RE.match(fp))


# ── created_at format check ─────────────────────────────────────────

_CREATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_MILLIS_RE = re.compile(r"\.\d+Z$")


def check_created_at(val: str) -> Tuple[str, str]:
    """Return (severity, message) for created_at value."""
    if _MILLIS_RE.search(val):
        return FAIL, f"created_at contains milliseconds (Freeze §1.1.2): {val}"
    if not _CREATED_AT_RE.match(val):
        return FAIL, f"created_at format invalid (expected YYYY-MM-DDTHH:MM:SSZ): {val}"
    return PASS, "created_at format OK"


# ── Output helpers ──────────────────────────────────────────────────

def severity_rank(s: str) -> int:
    return {PASS: 0, WARN: 1, FAIL: 2}.get(s, 0)


def summary_line(results: List[CheckResult]) -> Tuple[str, int]:
    """Return (worst_severity, count_of_worst)."""
    worst = PASS
    counts: Dict[str, int] = {PASS: 0, WARN: 0, FAIL: 0}
    for r in results:
        counts[r.severity] = counts.get(r.severity, 0) + 1
        if severity_rank(r.severity) > severity_rank(worst):
            worst = r.severity
    return worst, counts[worst]


def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def print_results(results: List[CheckResult], *, validator_name: str,
                  checked_files: Optional[List[str]] = None,
                  json_output: bool = False) -> int:
    """Print results and return exit code (0=PASS/WARN, 1=FAIL)."""

    worst, count = summary_line(results)

    if json_output:
        import json as _json
        out = {
            "summary": worst,
            "summary_count": count,
            "validator": validator_name,
            "checks": [r.to_dict() for r in results],
        }
        if checked_files:
            out["checked_files"] = checked_files
        _safe_print(_json.dumps(out, indent=2, ensure_ascii=False))
        return 1 if worst == FAIL else 0

    # Human-readable
    if worst == PASS:
        _safe_print(f"VALIDATE SUMMARY: PASS")
    else:
        _safe_print(f"VALIDATE SUMMARY: {worst} ({count})")
    _safe_print()

    # FAIL list
    fails = [r for r in results if r.severity == FAIL]
    if fails:
        _safe_print("-- FAIL --")
        for r in fails:
            _safe_print(f"  [FAIL] {r.label}: {r.message}")
        _safe_print()

    # WARN list
    warns = [r for r in results if r.severity == WARN]
    if warns:
        _safe_print("-- WARN --")
        for r in warns:
            _safe_print(f"  [WARN] {r.label}: {r.message}")
        _safe_print()

    # Checked files
    if checked_files:
        _safe_print("-- Checked Files --")
        for f in checked_files:
            _safe_print(f"  {f}")
        _safe_print()

    # Suggested next command
    _safe_print("-- Suggested Next Command --")
    if worst == FAIL:
        _safe_print("  Fix the FAIL items above, then re-run this validator.")
    else:
        _safe_print("  py tools/ops/run_end_ops_hook.py   # full ops cycle")

    return 1 if worst == FAIL else 0
