#!/usr/bin/env python3
"""
Smoke-1/2/3 E2E runner. Generates fitting_facts_summary at run time per smoke type.
- Smoke1: normal completion (early_exit=false)
- Smoke2: hard gate (early_exit=true, early_exit_reason)
- Smoke3: degraded (degraded_state, warnings_summary)
Facts-only. No quality thresholds.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Seoul")
except ImportError:
    TZ = None


def _ts_now() -> str:
    if TZ:
        return datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")


SMOKE_CONFIGS = [
    {
        "run_id": "fitting_smoke1_ok",
        "early_exit": False,
        "early_exit_reason": None,
        "degraded_state": {},
        "warnings_summary": {},
    },
    {
        "run_id": "fitting_smoke2_hard_gate",
        "early_exit": True,
        "early_exit_reason": "garment_hard_gate_violation: invalid_face_flag",
        "degraded_state": {"reason": "hard_gate"},
        "warnings_summary": {},
    },
    {
        "run_id": "fitting_smoke3_degraded",
        "early_exit": False,
        "early_exit_reason": None,
        "degraded_state": {"partial_convergence": True},
        "warnings_summary": {
            "PARTIAL_CONVERGENCE": {
                "count": 1,
                "sample_messages": ["iter_max reached; residual above nominal"],
                "truncated": False,
            },
        },
    },
]


def _write_facts_summary(run_dir: Path, cfg: dict) -> None:
    """Write fitting_facts_summary.v1 to run_dir root and output/ if needed."""
    payload = {
        "schema_version": "fitting_facts_summary.v1",
        "garment_input_path_used": "npz",
        "early_exit": cfg["early_exit"],
        "early_exit_reason": cfg["early_exit_reason"],
        "degraded_state": cfg["degraded_state"],
        "warnings_summary": cfg["warnings_summary"],
    }
    # Run root (minset)
    root_path = run_dir / "facts_summary.json"
    root_path.parent.mkdir(parents=True, exist_ok=True)
    root_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # output/ if exists (fitting_manifest output path)
    out_path = run_dir / "output" / "facts_summary.json"
    if out_path.parent.exists():
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_solver_and_validate(repo: Path, run_dir: Path, run_id: str) -> tuple[bool, str]:
    """Run tier1 solver then validate fit_signal. Returns (ok, note)."""
    solver = repo / "tools" / "run_tier1_constraint_solver.py"
    validator = repo / "tools" / "validate_fit_signal.py"
    if not solver.exists():
        return False, "solver not found"
    r = subprocess.run(
        [sys.executable, str(solver), "--run-dir", str(run_dir)],
        capture_output=True, text=True, cwd=str(repo), timeout=30,
    )
    if r.returncode != 0:
        return False, f"solver exit={r.returncode}"
    fit_path = run_dir / "fit_signal.json"
    if not fit_path.exists():
        return False, "fit_signal.json not created"
    if not validator.exists():
        return True, "validator not found (skipped)"
    rv = subprocess.run(
        [sys.executable, str(validator), "--fit-signal", str(fit_path)],
        capture_output=True, text=True, cwd=str(repo), timeout=10,
    )
    return rv.returncode == 0, "OK" if rv.returncode == 0 else "VALIDATION FAILED"


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    runs = repo / "runs"
    fit_notes: list[str] = []

    for cfg in SMOKE_CONFIGS:
        run_dir = runs / cfg["run_id"]
        if run_dir.exists():
            _write_facts_summary(run_dir, cfg)
            ok, note = _run_solver_and_validate(repo, run_dir, cfg["run_id"])
            fit_notes.append(f"{cfg['run_id']}: fit_signal {note}")

    if fit_notes:
        for n in fit_notes:
            print(n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
