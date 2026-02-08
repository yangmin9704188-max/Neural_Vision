#!/usr/bin/env python3
"""
Minimal smoke manifest runner for MODULE=fitting.
Creates exports/runs/_smoke/<RUN_ID>/fitting_smoke_v1/ with README.txt and geometry_manifest.json.
Wiring-only: no real fitting computation. Conforms to contracts/geometry_manifest_v1.schema.json.

Run:
  python -m modules.fitting.src.runners.run_fitting_smoke_manifest
  python modules/fitting/src/runners/run_fitting_smoke_manifest.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MODULE = "fitting"
FILE_BASENAME = "run_fitting_smoke_manifest.py"


def _repo_root() -> Path:
    """Assume runner is invoked from repo root or path contains repo root."""
    cwd = Path.cwd()
    for p in [cwd, cwd.parent]:
        if (p / "contracts" / "geometry_manifest_v1.schema.json").is_file():
            return p
        if (p / "contracts" / "geometry_manifest.schema.json").is_file():
            return p
    return cwd


def main() -> int:
    repo = _repo_root()
    run_id = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    leaf_name = f"{MODULE}_smoke_v1"
    leaf_run_dir = repo / "exports" / "runs" / "_smoke" / run_id / leaf_name
    leaf_run_dir.mkdir(parents=True, exist_ok=True)

    readme = leaf_run_dir / "README.txt"
    readme.write_text("fitting smoke artifact\n", encoding="utf-8")

    # Conform to MAIN repo canonical geometry_manifest_v1.schema.json
    now_utc = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "schema_version": "geometry_manifest.v1",
        "module_name": MODULE,
        "contract_version": "v0",
        "created_at": now_utc,
        "fingerprint": "sha256:stub",
        "inputs_fingerprint": "sha256:stub",
        "version_keys": {
            "snapshot_version": "smoke",
            "semantic_version": "0.0.0",
            "geometry_impl_version": "smoke_v1",
            "dataset_version": "none",
        },
        "artifacts": ["README.txt"],
        "warnings": ["SMOKE_ONLY"],
    }
    manifest_path = leaf_run_dir / "geometry_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    abs_run_dir = leaf_run_dir.resolve()
    abs_manifest = manifest_path.resolve()
    print(f"[run_dir] {abs_run_dir}")
    print(f"[manifest] {abs_manifest}")

    # Progress append (F01: smoke run)
    _append_progress(step_id="F01", dod_done_delta=0, note="smoke manifest run")
    return 0


def _append_progress(step_id: str, dod_done_delta: int = 0, note: str = "") -> None:
    """Append progress event via tools/progress_append.py (best-effort)."""
    try:
        # modules/fitting/src/runners -> fitting_lab
        repo = Path(__file__).resolve().parents[4]
        script = repo / "tools" / "progress_append.py"
        if not script.exists():
            return
        subprocess.run(
            [sys.executable, str(script), "--step", step_id, "--done", str(dod_done_delta), "--note", note, "--event", "run_finished"],
            cwd=str(repo), capture_output=True, timeout=5
        )
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
