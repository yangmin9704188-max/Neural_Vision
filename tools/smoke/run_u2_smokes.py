#!/usr/bin/env python3
"""run_u2_smokes.py — U2 Runnable Unlock: run 3 smoke scenarios.

Reference: unlock_conditions_u1_u2.md §3 (Freeze: Smoke 3종)

Smoke-1 (OK E2E):     Normal flow, all validators FAIL=0, early_exit=false, degraded_state="none"
Smoke-2 (Hard Gate):  Garment hard gate flag → early_exit=true, reason populated
Smoke-3 (Degraded):   Body 2+ null keys → degraded/high_warning_degraded surfaced

Exit codes: 0 = all smokes PASS/WARN, 1 = any smoke FAIL
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Repo root detection (same approach as doctor.py) ─────────────────

def _find_repo_root() -> Path:
    cur = Path(__file__).resolve()
    for _ in range(20):
        if (cur / ".git").is_dir():
            return cur
        if (cur / "project_map.md").is_file():
            return cur
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return Path.cwd()


REPO_ROOT = _find_repo_root()

# ── Import validators ────────────────────────────────────────────────
# Add tools/validate to path so we can import the validate() functions.

_VALIDATE_DIR = REPO_ROOT / "tools" / "validate"
if str(_VALIDATE_DIR) not in sys.path:
    sys.path.insert(0, str(_VALIDATE_DIR))

from _common import PASS, WARN, FAIL, CheckResult, safe_json_load, severity_rank, summary_line  # noqa: E402
from validate_u1_body import validate as validate_body       # noqa: E402
from validate_u1_garment import validate as validate_garment # noqa: E402
from validate_u1_fitting import validate as validate_fitting # noqa: E402

# ── Fixture paths ────────────────────────────────────────────────────

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "u2_smokes"

SMOKE_IDS = ("smoke1_ok", "smoke2_hardgate", "smoke3_degraded")

# ── Safe print ───────────────────────────────────────────────────────

def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


# ── Copy fixture to workdir ──────────────────────────────────────────

def _copy_fixture(fixture_dir: Path, workdir: Path) -> None:
    """Recursively copy fixture to workdir (create if needed)."""
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(fixture_dir, workdir)


# ── Smoke result container ───────────────────────────────────────────

class SmokeResult:
    def __init__(self, smoke_id: str, workdir: Path):
        self.smoke_id = smoke_id
        self.workdir = workdir
        self.validator_results: Dict[str, Tuple[str, int, List[Dict]]] = {}
        # key = validator_name, value = (worst_severity, fail_count, checks_list)
        self.smoke_checks: List[CheckResult] = []
        self.overall: str = PASS

    def add_validator(self, name: str, results: List[CheckResult]) -> None:
        worst, _ = summary_line(results)
        fail_count = sum(1 for r in results if r.severity == FAIL)
        self.validator_results[name] = (worst, fail_count, [r.to_dict() for r in results])

    def add_check(self, result: CheckResult) -> None:
        self.smoke_checks.append(result)

    def compute_overall(self) -> None:
        """Overall = worst across all validators (FAIL 0 required) + smoke checks."""
        worst = PASS
        # Any validator with FAIL → smoke FAIL
        for name, (vsev, vfail, _) in self.validator_results.items():
            if vfail > 0:
                worst = FAIL
                break
            if severity_rank(vsev) > severity_rank(worst):
                worst = vsev
        # Smoke-specific checks
        for c in self.smoke_checks:
            if c.severity == FAIL:
                worst = FAIL
                break
            if severity_rank(c.severity) > severity_rank(worst):
                worst = c.severity
        self.overall = worst

    def to_dict(self) -> Dict[str, Any]:
        return {
            "smoke_id": self.smoke_id,
            "workdir": str(self.workdir),
            "overall": self.overall,
            "validators": {
                name: {"worst": w, "fail_count": fc, "checks": ch}
                for name, (w, fc, ch) in self.validator_results.items()
            },
            "smoke_checks": [c.to_dict() for c in self.smoke_checks],
        }


# ── Run individual smoke ─────────────────────────────────────────────

def _run_smoke1_ok(workdir: Path) -> SmokeResult:
    """Smoke-1: Normal E2E — all validators FAIL=0, early_exit=false, degraded_state='none'."""
    sr = SmokeResult("smoke1_ok", workdir)

    body_dir = workdir / "body_run"
    garment_dir = workdir / "garment_run"
    fitting_dir = workdir / "fitting_run"

    # Run validators
    if body_dir.is_dir():
        br, _ = validate_body(body_dir)
        sr.add_validator("validate_u1_body", br)

    if garment_dir.is_dir():
        gr, _ = validate_garment(garment_dir)
        sr.add_validator("validate_u1_garment", gr)

    if fitting_dir.is_dir():
        fr, _ = validate_fitting(fitting_dir)
        sr.add_validator("validate_u1_fitting", fr)

    # Smoke-specific: fitting_facts_summary checks
    facts_path = fitting_dir / "fitting_facts_summary.json"
    facts, err = safe_json_load(facts_path)
    if err:
        sr.add_check(CheckResult(FAIL, "smoke1:facts_load", err))
    else:
        # early_exit must be false
        if facts.get("early_exit") is False:
            sr.add_check(CheckResult(PASS, "smoke1:early_exit", "false (expected)"))
        else:
            sr.add_check(CheckResult(FAIL, "smoke1:early_exit",
                                     f"Expected false, got {facts.get('early_exit')!r}"))
        # degraded_state must be "none"
        ds = facts.get("degraded_state")
        if ds == "none":
            sr.add_check(CheckResult(PASS, "smoke1:degraded_state", "none (expected)"))
        else:
            sr.add_check(CheckResult(FAIL, "smoke1:degraded_state",
                                     f"Expected 'none', got {ds!r}"))

    sr.compute_overall()
    return sr


def _run_smoke2_hardgate(workdir: Path) -> SmokeResult:
    """Smoke-2: Garment Hard Gate — early_exit=true, reason populated."""
    sr = SmokeResult("smoke2_hardgate", workdir)

    body_dir = workdir / "body_run"
    garment_dir = workdir / "garment_run"
    fitting_dir = workdir / "fitting_run"

    # Run validators
    if body_dir.is_dir():
        br, _ = validate_body(body_dir)
        sr.add_validator("validate_u1_body", br)

    if garment_dir.is_dir():
        gr, _ = validate_garment(garment_dir)
        sr.add_validator("validate_u1_garment", gr)

    if fitting_dir.is_dir():
        fr, _ = validate_fitting(fitting_dir)
        sr.add_validator("validate_u1_fitting", fr)

    # Smoke-specific: garment hard gate must be detected
    meta_path = garment_dir / "garment_proxy_meta.json"
    meta, err = safe_json_load(meta_path)
    if err:
        sr.add_check(CheckResult(FAIL, "smoke2:meta_load", err))
    else:
        gate_flags = ["negative_face_area_flag", "self_intersection_flag", "invalid_face_flag"]
        any_true = any(meta.get(f) is True for f in gate_flags)
        if any_true:
            sr.add_check(CheckResult(PASS, "smoke2:hard_gate_detected",
                                     "At least one hard gate flag is true (intended path)"))
        else:
            sr.add_check(CheckResult(FAIL, "smoke2:hard_gate_detected",
                                     "No hard gate flags are true (smoke2 requires at least one)"))

    # Smoke-specific: fitting_facts_summary checks
    facts_path = fitting_dir / "fitting_facts_summary.json"
    facts, err = safe_json_load(facts_path)
    if err:
        sr.add_check(CheckResult(FAIL, "smoke2:facts_load", err))
    else:
        # early_exit must be true
        if facts.get("early_exit") is True:
            sr.add_check(CheckResult(PASS, "smoke2:early_exit", "true (expected for hard gate)"))
        else:
            sr.add_check(CheckResult(FAIL, "smoke2:early_exit",
                                     f"Expected true, got {facts.get('early_exit')!r}"))
        # early_exit_reason should be populated (WARN if null per U2 spec §3)
        eer = facts.get("early_exit_reason")
        if isinstance(eer, str) and eer:
            sr.add_check(CheckResult(PASS, "smoke2:early_exit_reason", eer))
        elif eer is None:
            sr.add_check(CheckResult(WARN, "smoke2:early_exit_reason",
                                     "null (string recommended when early_exit=true)"))
        else:
            sr.add_check(CheckResult(WARN, "smoke2:early_exit_reason",
                                     f"Unexpected value: {eer!r}"))

    sr.compute_overall()
    return sr


def _run_smoke3_degraded(workdir: Path) -> SmokeResult:
    """Smoke-3: Body null missingness → degraded/high warning surfaced."""
    sr = SmokeResult("smoke3_degraded", workdir)

    body_dir = workdir / "body_run"
    garment_dir = workdir / "garment_run"
    fitting_dir = workdir / "fitting_run"

    # Run validators
    if body_dir.is_dir():
        br, _ = validate_body(body_dir)
        sr.add_validator("validate_u1_body", br)

    if garment_dir.is_dir():
        gr, _ = validate_garment(garment_dir)
        sr.add_validator("validate_u1_garment", gr)

    if fitting_dir.is_dir():
        fr, _ = validate_fitting(fitting_dir)
        sr.add_validator("validate_u1_fitting", fr)

    # Smoke-specific: body_measurements_subset must have ≥2 nulls → degraded
    bms_path = body_dir / "body_measurements_subset.json"
    bms, err = safe_json_load(bms_path)
    if err:
        sr.add_check(CheckResult(FAIL, "smoke3:bms_load", err))
    else:
        meas = bms.get("measurements", {})
        null_count = sum(1 for k in ("BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M")
                         if meas.get(k) is None)
        if null_count >= 2:
            sr.add_check(CheckResult(PASS, "smoke3:null_count",
                                     f"{null_count} null keys (>=2: degraded path intended)"))
        else:
            sr.add_check(CheckResult(FAIL, "smoke3:null_count",
                                     f"{null_count} null keys (expected >=2 for degraded scenario)"))

    # Smoke-specific: fitting_facts_summary.degraded_state must be "high_warning_degraded"
    facts_path = fitting_dir / "fitting_facts_summary.json"
    facts, err = safe_json_load(facts_path)
    if err:
        sr.add_check(CheckResult(FAIL, "smoke3:facts_load", err))
    else:
        ds = facts.get("degraded_state")
        if ds == "high_warning_degraded":
            sr.add_check(CheckResult(PASS, "smoke3:degraded_state",
                                     "high_warning_degraded (expected)"))
        else:
            sr.add_check(CheckResult(FAIL, "smoke3:degraded_state",
                                     f"Expected 'high_warning_degraded', got {ds!r}"))

    # Check that the body validator detected the degraded/high warning
    if body_dir.is_dir():
        body_checks = sr.validator_results.get("validate_u1_body", (PASS, 0, []))
        checks_list = body_checks[2]
        found_degraded = any("Degraded" in c.get("message", "") or "High Warning" in c.get("message", "")
                             for c in checks_list)
        if found_degraded:
            sr.add_check(CheckResult(PASS, "smoke3:body_degraded_surfaced",
                                     "Degraded/High Warning detected by body validator"))
        else:
            sr.add_check(CheckResult(WARN, "smoke3:body_degraded_surfaced",
                                     "Body validator did not explicitly surface 'Degraded/High Warning'"))

    sr.compute_overall()
    return sr


_SMOKE_RUNNERS = {
    "smoke1_ok": _run_smoke1_ok,
    "smoke2_hardgate": _run_smoke2_hardgate,
    "smoke3_degraded": _run_smoke3_degraded,
}

# ── Output ───────────────────────────────────────────────────────────

def _print_human(results: List[SmokeResult]) -> None:
    # Overall summary
    worst = PASS
    fail_count = 0
    warn_count = 0
    for sr in results:
        if sr.overall == FAIL:
            fail_count += 1
        elif sr.overall == WARN:
            warn_count += 1
        if severity_rank(sr.overall) > severity_rank(worst):
            worst = sr.overall

    if worst == PASS:
        _safe_print("U2 SMOKE SUMMARY: PASS")
    elif worst == FAIL:
        _safe_print(f"U2 SMOKE SUMMARY: FAIL ({fail_count})")
    else:
        _safe_print(f"U2 SMOKE SUMMARY: WARN ({warn_count})")
    _safe_print()

    for sr in results:
        _safe_print(f"== {sr.smoke_id} [{sr.overall}] ==")
        _safe_print(f"   workdir: {sr.workdir}")

        # Validators
        _safe_print("   validators:")
        for vname, (vsev, vfail, _) in sr.validator_results.items():
            _safe_print(f"     {vname}: {vsev} (FAIL={vfail})")

        # Smoke-specific checks
        fails = [c for c in sr.smoke_checks if c.severity == FAIL]
        warns = [c for c in sr.smoke_checks if c.severity == WARN]
        passes = [c for c in sr.smoke_checks if c.severity == PASS]

        if fails:
            _safe_print("   FAIL:")
            for c in fails:
                _safe_print(f"     [{c.severity}] {c.label}: {c.message}")
        if warns:
            _safe_print("   WARN:")
            for c in warns:
                _safe_print(f"     [{c.severity}] {c.label}: {c.message}")
        if passes and not fails:
            _safe_print("   smoke checks: all PASS")

        _safe_print()

    # Suggested next
    _safe_print("-- Suggested Next --")
    if worst == FAIL:
        _safe_print("  Fix the FAIL items above, then re-run: py tools/smoke/run_u2_smokes.py")
    else:
        _safe_print("  U2 Runnable Unlock criteria met. Proceed to ops cycle:")
        _safe_print("  py tools/ops/run_end_ops_hook.py")


def _print_json(results: List[SmokeResult]) -> None:
    worst = PASS
    for sr in results:
        if severity_rank(sr.overall) > severity_rank(worst):
            worst = sr.overall

    out = {
        "summary": worst,
        "smokes": [sr.to_dict() for sr in results],
    }
    _safe_print(json.dumps(out, indent=2, ensure_ascii=False))


# ── Main ─────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="U2 Runnable Unlock: run smoke 3 scenarios (Freeze §3)")
    parser.add_argument("--only", choices=list(_SMOKE_RUNNERS.keys()),
                        help="Run a single smoke only")
    parser.add_argument("--workdir", type=str, default=None,
                        help="Base workdir (default: .tmp/u2_smokes/<timestamp>)")
    parser.add_argument("--keep-workdir", action="store_true",
                        help="Keep workdir after run (default: keep)")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Output structured JSON")
    args = parser.parse_args(argv)

    # Determine smokes to run
    if args.only:
        smoke_ids = [args.only]
    else:
        smoke_ids = list(SMOKE_IDS)

    # Workdir
    if args.workdir:
        base_workdir = Path(args.workdir)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base_workdir = REPO_ROOT / ".tmp" / "u2_smokes" / ts

    # Run smokes
    all_results: List[SmokeResult] = []
    for sid in smoke_ids:
        fixture_dir = FIXTURES_DIR / sid
        if not fixture_dir.is_dir():
            sr = SmokeResult(sid, base_workdir / sid)
            sr.add_check(CheckResult(FAIL, f"{sid}:fixture_missing",
                                     f"Fixture dir not found: {fixture_dir}"))
            sr.compute_overall()
            all_results.append(sr)
            continue

        workdir = base_workdir / sid
        _copy_fixture(fixture_dir, workdir)

        runner = _SMOKE_RUNNERS[sid]
        sr = runner(workdir)
        all_results.append(sr)

    # Output
    if args.json_output:
        _print_json(all_results)
    else:
        _print_human(all_results)

    # Exit code
    worst = PASS
    for sr in all_results:
        if severity_rank(sr.overall) > severity_rank(worst):
            worst = sr.overall

    return 1 if worst == FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
