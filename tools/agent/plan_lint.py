#!/usr/bin/env python3
"""plan_lint.py — Validate master_plan_v1.json structure (Round 03).

Checks:
  - plan_version exists and valid
  - steps array exists
  - step_id unique across all steps
  - module enum valid (body|garment|fitting|common)
  - depends_on references existing step_ids only
  - phase enum valid (P0|P1|P2|P3)
  - commands is array (empty OK)
  - dod/evidence optional but type-checked if present

Exit codes: 0 = PASS/WARN, 1 = FAIL
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Constants ────────────────────────────────────────────────────────

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

VALID_MODULES = {"body", "garment", "fitting", "common"}
VALID_PHASES = {"P0", "P1", "P2", "P3"}


class CheckResult:
    """Single check result."""
    __slots__ = ("severity", "label", "message")

    def __init__(self, severity: str, label: str, message: str):
        self.severity = severity
        self.label = label
        self.message = message

    def to_dict(self) -> Dict[str, str]:
        return {"severity": self.severity, "label": self.label, "message": self.message}


# ── Lint logic ───────────────────────────────────────────────────────

def lint_plan(plan_path: Path) -> List[CheckResult]:
    results: List[CheckResult] = []

    # Load JSON
    if not plan_path.is_file():
        results.append(CheckResult(FAIL, "plan_file", f"Not found: {plan_path}"))
        return results

    try:
        with open(plan_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        results.append(CheckResult(FAIL, "json_parse", f"Parse error: {exc}"))
        return results

    results.append(CheckResult(PASS, "json_parse", "OK"))

    # plan_version
    pv = data.get("plan_version")
    if not isinstance(pv, str) or not pv:
        results.append(CheckResult(FAIL, "plan_version", "Missing or invalid"))
    else:
        results.append(CheckResult(PASS, "plan_version", pv))

    # steps array
    steps = data.get("steps")
    if not isinstance(steps, list):
        results.append(CheckResult(FAIL, "steps", "Missing or not an array"))
        return results

    results.append(CheckResult(PASS, "steps", f"Array with {len(steps)} items"))

    # Check each step
    step_ids_seen: Set[str] = set()
    all_step_ids: Set[str] = {s.get("step_id") for s in steps if isinstance(s.get("step_id"), str)}

    for i, step in enumerate(steps):
        _lint_step(step, i, step_ids_seen, all_step_ids, results)
        sid = step.get("step_id")
        if isinstance(sid, str):
            step_ids_seen.add(sid)

    return results


def _lint_step(step: Any, idx: int, seen: Set[str], all_ids: Set[str],
               results: List[CheckResult]) -> None:
    """Lint a single step."""
    if not isinstance(step, dict):
        results.append(CheckResult(FAIL, f"step[{idx}]", "Not an object"))
        return

    sid = step.get("step_id")
    if not isinstance(sid, str) or not sid:
        results.append(CheckResult(FAIL, f"step[{idx}]:step_id", "Missing or invalid"))
        return

    label = f"step:{sid}"

    # Uniqueness
    if sid in seen:
        results.append(CheckResult(FAIL, f"{label}:unique", "Duplicate step_id"))
    else:
        results.append(CheckResult(PASS, f"{label}:unique", "OK"))

    # module
    mod = step.get("module")
    if mod in VALID_MODULES:
        results.append(CheckResult(PASS, f"{label}:module", mod))
    else:
        results.append(CheckResult(FAIL, f"{label}:module",
                                   f"Invalid: {mod!r} (expected body|garment|fitting|common)"))

    # phase
    phase = step.get("phase")
    if phase in VALID_PHASES:
        results.append(CheckResult(PASS, f"{label}:phase", phase))
    else:
        results.append(CheckResult(FAIL, f"{label}:phase",
                                   f"Invalid: {phase!r} (expected P0|P1|P2|P3)"))

    # depends_on
    deps = step.get("depends_on")
    if not isinstance(deps, list):
        results.append(CheckResult(FAIL, f"{label}:depends_on", "Missing or not an array"))
    else:
        for dep in deps:
            if not isinstance(dep, str):
                results.append(CheckResult(FAIL, f"{label}:depends_on",
                                           f"Non-string dependency: {dep!r}"))
            elif dep not in all_ids:
                results.append(CheckResult(FAIL, f"{label}:depends_on",
                                           f"References non-existent step: {dep!r}"))
        if all(isinstance(d, str) and d in all_ids for d in deps):
            results.append(CheckResult(PASS, f"{label}:depends_on",
                                       f"{len(deps)} deps, all valid"))

    # unlock (optional but if present, check structure)
    unlock = step.get("unlock")
    if unlock is not None:
        if isinstance(unlock, dict):
            req_u1 = unlock.get("requires_u1")
            req_u2 = unlock.get("requires_u2")
            if isinstance(req_u1, bool) and isinstance(req_u2, bool):
                results.append(CheckResult(PASS, f"{label}:unlock", "u1/u2 flags OK"))
            else:
                results.append(CheckResult(WARN, f"{label}:unlock",
                                           "requires_u1/u2 not both boolean"))

    # commands (array expected)
    cmds = step.get("commands")
    if isinstance(cmds, list):
        results.append(CheckResult(PASS, f"{label}:commands", f"{len(cmds)} commands"))
    elif cmds is None:
        results.append(CheckResult(WARN, f"{label}:commands", "Missing (optional but recommended)"))
    else:
        results.append(CheckResult(FAIL, f"{label}:commands", "Not an array"))

    # dod (optional, array expected)
    dod = step.get("dod")
    if isinstance(dod, list):
        results.append(CheckResult(PASS, f"{label}:dod", f"{len(dod)} items"))
    elif dod is None:
        pass  # OK, optional
    else:
        results.append(CheckResult(WARN, f"{label}:dod", "Present but not an array"))

    # evidence (optional, object expected)
    ev = step.get("evidence")
    if isinstance(ev, dict):
        results.append(CheckResult(PASS, f"{label}:evidence", "Object present"))
    elif ev is None:
        pass  # OK, optional
    else:
        results.append(CheckResult(WARN, f"{label}:evidence", "Present but not an object"))


# ── Output ───────────────────────────────────────────────────────────

def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _summary_line(results: List[CheckResult]) -> Tuple[str, int]:
    worst = PASS
    counts = {PASS: 0, WARN: 0, FAIL: 0}
    for r in results:
        counts[r.severity] = counts.get(r.severity, 0) + 1
        rank = {PASS: 0, WARN: 1, FAIL: 2}.get(r.severity, 0)
        worst_rank = {PASS: 0, WARN: 1, FAIL: 2}.get(worst, 0)
        if rank > worst_rank:
            worst = r.severity
    return worst, counts[worst]


def print_results(results: List[CheckResult], plan_path: Path, *,
                  json_output: bool = False) -> int:
    worst, count = _summary_line(results)

    if json_output:
        out = {
            "summary": worst,
            "summary_count": count,
            "plan_path": str(plan_path),
            "checks": [r.to_dict() for r in results],
        }
        _safe_print(json.dumps(out, indent=2, ensure_ascii=False))
        return 1 if worst == FAIL else 0

    # Human
    if worst == PASS:
        _safe_print("PLAN_LINT SUMMARY: PASS")
    else:
        _safe_print(f"PLAN_LINT SUMMARY: {worst} ({count})")
    _safe_print()

    _safe_print(f"-- Plan: {plan_path.name} --")
    _safe_print()

    fails = [r for r in results if r.severity == FAIL]
    if fails:
        _safe_print("-- FAIL --")
        for r in fails:
            _safe_print(f"  [FAIL] {r.label}: {r.message}")
        _safe_print()

    warns = [r for r in results if r.severity == WARN]
    if warns:
        _safe_print("-- WARN --")
        for r in warns:
            _safe_print(f"  [WARN] {r.label}: {r.message}")
        _safe_print()

    _safe_print("-- Suggested Next --")
    if worst == FAIL:
        _safe_print("  Fix the FAIL items above, then re-run plan_lint.")
    else:
        _safe_print("  py tools/agent/next_step.py --module all --top 5")

    return 1 if worst == FAIL else 0


# ── Main ─────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate master_plan_v1.json structure (Round 03)")
    parser.add_argument("--plan", type=str, default="contracts/master_plan_v1.json",
                        help="Path to plan JSON (default: contracts/master_plan_v1.json)")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Output structured JSON")
    args = parser.parse_args(argv)

    plan_path = Path(args.plan)
    results = lint_plan(plan_path)
    return print_results(results, plan_path, json_output=args.json_output)


if __name__ == "__main__":
    sys.exit(main())
