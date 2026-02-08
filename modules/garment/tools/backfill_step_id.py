#!/usr/bin/env python3
"""Append STEP_ID_BACKFILLED events for UNSPECIFIED events. Idempotent."""
import json
import sys
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Seoul")
except ImportError:
    TZ = None


def _ts_now():
    from datetime import datetime
    if TZ:
        return datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    return __import__("datetime").datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")


def main():
    repo = Path(__file__).resolve().parents[1]
    log_path = repo / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    if not log_path.exists():
        return 0

    unspecified = 0
    backfilled = 0
    for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
            sid = ev.get("step_id", "")
            w = ev.get("warnings") or []
            gc = ev.get("gate_codes") or []
            if sid == "UNSPECIFIED" or any("[STEP_ID_MISSING]" in str(x) for x in w):
                unspecified += 1
            if any("STEP_ID_BACKFILLED" in str(x) for x in (gc + w)):
                backfilled += 1
        except json.JSONDecodeError:
            pass

    to_add = max(0, unspecified - backfilled)
    if to_add == 0:
        return 0

    evidence = ["exports/runs/_smoke/20260206_171420/geometry_manifest.json"]
    for _ in range(to_add):
        ev = {
            "ts": _ts_now(),
            "module": "garment",
            "step_id": "G_BACKFILL",
            "event": "backfill",
            "run_id": "N/A",
            "status": "OK",
            "dod_done_delta": 0,
            "note": "Backfill: previous step-id missing event corrected; original run_end_ops_hook UNSPECIFIED",
            "evidence": evidence,
            "warnings": ["[STEP_ID_BACKFILLED]"],
            "gate_codes": ["STEP_ID_BACKFILLED"],
        }
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    print(f"backfill_step_id: appended {to_add} backfill event(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
