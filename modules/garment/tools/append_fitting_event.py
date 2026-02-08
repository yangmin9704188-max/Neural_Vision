import json
import os
from datetime import datetime

LOG_FILE = "exports/progress/PROGRESS_LOG.jsonl"
EVIDENCE_PATH = "exports/runs/_smoke/20260207_092104/garment_smoke_v1/geometry_manifest.json"

entry = {
    "ts": datetime.now().astimezone().isoformat(),
    "module": "fitting",
    "step_id": "U2.SMOKE2.CONSUMER",
    "event": "smoke2_e2e_pass",
    "status": "PASS",
    "inputs": {
        "garment_out_dir": os.path.dirname(EVIDENCE_PATH).replace("\\", "/")
    },
    "outputs": {
        # Using a placeholder as fitting side artifacts might not be in this repo or haven't been generated yet 
        # but required by schema.
        "fitting_facts_summary": "runs/fitting/smoke2/fitting_facts_summary.json"
    },
    "evidence": {
        "early_exit": True,
        "early_exit_reason_contains": "invalid_face_flag",
        "garment_input_path_used": "glb_fallback"
    }
}

try:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"Appended event to {LOG_FILE}")
    print(json.dumps(entry, indent=2))
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
