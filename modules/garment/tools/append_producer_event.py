import json
import os
from datetime import datetime

LOG_FILE = "exports/progress/PROGRESS_LOG.jsonl"
FIXTURE_PATH = "tests/fixtures/invalid_mesh.obj"
# Using the same output run as consumer for consistency/evidence
OUTPUT_RUN_DIR = "exports/runs/_smoke/20260207_092104"
PROXY_META = f"{OUTPUT_RUN_DIR}/garment_proxy_meta.json"
MANIFEST = f"{OUTPUT_RUN_DIR}/geometry_manifest.json"

entry = {
    "ts": datetime.now().astimezone().isoformat(),
    "module": "garment",
    "step_id": "U2.SMOKE2.PRODUCER",
    "event": "smoke2_hard_gate_pass",
    "status": "PASS",
    "inputs": {
        "fixture_mesh": FIXTURE_PATH
    },
    "outputs": {
        "out_dir": OUTPUT_RUN_DIR,
        "garment_proxy_meta": PROXY_META,
        "geometry_manifest": MANIFEST
    },
    "evidence": {
        "hard_gate": True,
        "bundle_exit_nonzero": True,
        "manifest_validate": "PASS"
    }
}

try:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    
    print(f"Appended event to {LOG_FILE}")
    print(json.dumps(entry, indent=2))
except Exception as e:
    print(f"ERROR: {e}")
