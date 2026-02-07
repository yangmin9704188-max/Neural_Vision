#!/usr/bin/env python3
"""
Run-end ops hook: B2 unlock readiness (if beta_fit run found) → append progress → render_work_briefs → render_status.
Called from postprocess_round or run completion. Exit 0 always. Facts-only; never gate.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# B2 unlock: default thresholds (must match generate_unlock_signal_b2_v0.py defaults when used)
B2_THRESHOLD_SCORE = 70.0
B2_THRESHOLD_RESIDUAL_P90_CM = 1.0
B2_MAX_FAILURES = 0


def _get_lab_roots() -> dict[str, Path | None]:
    """ENV > lab_roots.local.json. Returns fitting, garment roots or None."""
    roots = {"fitting": None, "garment": None}
    for k, env_key in (("fitting", "FITTING_LAB_ROOT"), ("garment", "GARMENT_LAB_ROOT")):
        v = os.environ.get(env_key, "").strip()
        if v:
            roots[k] = Path(v).resolve()
        else:
            roots[k] = None

    if roots["fitting"] is None or roots["garment"] is None:
        cfg_path = REPO_ROOT / "ops" / "lab_roots.local.json"
        if cfg_path.exists():
            try:
                with open(cfg_path, encoding="utf-8") as f:
                    cfg = json.load(f)
                for k, key in (("fitting", "FITTING_LAB_ROOT"), ("garment", "GARMENT_LAB_ROOT")):
                    if roots[k] is None and cfg.get(key):
                        roots[k] = (REPO_ROOT / cfg[key]).resolve()
            except Exception:
                pass
    return roots


def _b2_unlock_rules_match(unlock_path: Path) -> bool:
    """True if unlock_signal.json exists and rules match current CLI thresholds."""
    if not unlock_path.exists():
        return False
    try:
        with open(unlock_path, encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("rules") or {}
        return (
            rules.get("threshold_score") == B2_THRESHOLD_SCORE
            and rules.get("threshold_residual_p90_cm") == B2_THRESHOLD_RESIDUAL_P90_CM
            and rules.get("max_failures") == B2_MAX_FAILURES
        )
    except Exception:
        return False


def _run_b2_unlock_readiness() -> None:
    """Discover latest beta_fit_v0 run; generate unlock_signal + optionally append progress. Never raises."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        from tools.ops.find_latest_beta_fit_run import find_latest_beta_fit_run
    except ImportError:
        print("[B2 unlock] skip: find_latest_beta_fit_run not importable")
        return

    run_dir = find_latest_beta_fit_run(REPO_ROOT)
    if run_dir is None:
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "ops" / "append_progress_event.py"),
                    "--lab-root", str(REPO_ROOT),
                    "--module", "body",
                    "--step-id", "B04",
                    "--event", "note",
                    "--note", "B2 unlock signal skipped: no beta_fit_v0 summary.json found",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                check=False,
            )
        except Exception:
            pass
        print("[B2 unlock] skip: no beta_fit_v0 run_dir found")
        return

    unlock_path = run_dir / "unlock_signal.json"
    rules_match = _b2_unlock_rules_match(unlock_path)
    log_progress = not rules_match

    cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "generate_unlock_signal_b2_v0.py"),
        "--run_dir", str(run_dir),
        "--out_dir", str(run_dir),
        "--threshold_score", "70",
        "--threshold_residual_p90_cm", "1.0",
        "--max_failures", "0",
    ]
    if log_progress:
        cmd.append("--log-progress")

    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if r.returncode != 0:
        print(f"[B2 unlock] generator exit {r.returncode}: {run_dir}")
        return
    print(f"[B2 unlock] run_dir={run_dir} log_progress={log_progress} rules_match={rules_match}")


def main() -> int:
    warnings = 0
    roots = _get_lab_roots()
    fitting_step = os.environ.get("FITTING_STEP_ID", "F01")
    garment_step = os.environ.get("GARMENT_STEP_ID", "G01")

    for module, lab_root, step_id in (
        ("fitting", roots["fitting"], fitting_step),
        ("garment", roots["garment"], garment_step),
    ):
        if lab_root is None or not lab_root.exists():
            continue
        cmd = [
            sys.executable,
            str(REPO_ROOT / "tools" / "ops" / "append_progress_event.py"),
            "--lab-root", str(lab_root),
            "--module", module,
            "--step-id", step_id,
            "--event", "run_finished",
            "--status", "OK",
            "--note", "run end hook",
            "--dod-done-delta", "0",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
        if r.returncode != 0:
            warnings += 1

    try:
        _run_b2_unlock_readiness()
    except Exception as e:
        print(f"[B2 unlock] warning: {e}")
        warnings += 1

    for script in ("render_work_briefs.py", "render_status.py"):
        cmd = [sys.executable, str(REPO_ROOT / "tools" / script)]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
        if r.returncode != 0:
            warnings += 1

    print(f"ops hook done, warnings={warnings}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
