#!/usr/bin/env python3
"""
Run-end ops hook: append progress → render_work_briefs → render_status.
Called from postprocess_round or run completion. Exit 0 always.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


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

    for script in ("render_work_briefs.py", "render_status.py"):
        cmd = [sys.executable, str(REPO_ROOT / "tools" / script)]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
        if r.returncode != 0:
            warnings += 1

    print(f"ops hook done, warnings={warnings}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
