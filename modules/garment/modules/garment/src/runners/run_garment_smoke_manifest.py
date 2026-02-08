import datetime
import json
import subprocess
import sys
from pathlib import Path

# MODULE CONSTANTS
MODULE = "garment"
SCHEMA_VERSION = "geometry_manifest.v1"
CONTRACT_VERSION = "v0"

def get_run_id():
    # Timestamp based RUN_ID
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")

def main():
    # 1. Setup paths
    # Robust root finding: look for 'exports' or 'modules'
    script_path = Path(__file__).resolve()
    current = script_path.parent
    root = None
    for _ in range(6):
        if (current / "exports").exists() and (current / "modules").exists():
            root = current
            break
        current = current.parent
    
    if root is None:
        root = Path.cwd()

    run_id = get_run_id()
    leaf_run_dir = root / "exports" / "runs" / "_smoke" / run_id / f"{MODULE}_smoke_v1"
    leaf_run_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Create artifact
    readme_path = leaf_run_dir / "README.txt"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"{MODULE} smoke artifact\nRun ID: {run_id}\nTimestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")

    # 3. Create Manifest (Conforming to geometry_manifest_v1.schema.json)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "module_name": MODULE,
        "contract_version": CONTRACT_VERSION,
        "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs_fingerprint": "sha256:stub",
        "version_keys": {
            "snapshot_version": "unknown",
            "semantic_version": "unknown",
            "geometry_impl_version": "smoke_v1",
            "dataset_version": "unknown"
        },
        "artifacts": ["README.txt"],
        "warnings": ["SMOKE_ONLY"]
    }

    # WRITE IT
    manifest_path = leaf_run_dir / "geometry_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # 4. Log
    print(f"[manifest] wrote {manifest_path} schema_version={SCHEMA_VERSION} module={MODULE}")
    print(f"[run_dir] {leaf_run_dir}")

    # 5. Progress append (G01: smoke run)
    _append_progress(step_id="G01", dod_done_delta=0, note="smoke manifest run")

    return 0


def _append_progress(step_id: str, dod_done_delta: int = 0, note: str = "", status: str = "OK") -> None:
    """Append progress event via tools/progress_append.py (best-effort)."""
    try:
        # modules/garment/src/runners -> garment_lab
        repo = Path(__file__).resolve().parents[4]
        script = repo / "tools" / "progress_append.py"
        if not script.exists():
            return
        subprocess.run(
            [sys.executable, str(script), "--step", step_id, "--done", str(dod_done_delta), "--note", note, "--event", "run_finished", "--status", status],
            cwd=str(repo), capture_output=True, timeout=5
        )
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main() or 0)
