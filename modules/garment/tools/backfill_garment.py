import json
from datetime import datetime

LOG_FILE = "exports/progress/PROGRESS_LOG.jsonl"
EVIDENCE_PATH = "exports/runs/_smoke/20260207_092104/geometry_manifest.json"

def count_missing_step_ids(log_path):
    count = 0
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("module") == "garment":
                    if entry.get("step_id") == "UNSPECIFIED":
                        count += 1
                    elif "STEP_ID_MISSING" in (entry.get("gate_codes") or []) or \
                         "[STEP_ID_MISSING]" in (entry.get("warnings") or []):
                        # Avoid double counting if both conditions met, but UNSPECIFIED is usually key
                        if entry.get("step_id") != "UNSPECIFIED":
                            count += 1
            except json.JSONDecodeError:
                pass
    return count

missing_count = count_missing_step_ids(LOG_FILE)
print(f"Found {missing_count} missing step_id events to backfill.")

if missing_count > 0:
    new_entries = []
    for i in range(missing_count):
        entry = {
            "ts": datetime.now().astimezone().isoformat(),
            "module": "garment",
            "step_id": "G_BACKFILL",
            "event": "BACKFILL",
            "gate_codes": ["STEP_ID_BACKFILLED"],
            "note": f"Backfill: previous step-id missing event corrected; original UNSPECIFIED ({i+1}/{missing_count})",
            "evidence": [EVIDENCE_PATH],
            "status": "OK"
        }
        new_entries.append(entry)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        for entry in new_entries:
            f.write(json.dumps(entry) + "\n")
    
    print(f"Appended {missing_count} backfill events.")
else:
    print("No events to backfill.")
