#!/usr/bin/env python3
"""
Append ROUND_END events for Smoke-1/2/3 E2E to PROGRESS_LOG.jsonl.
Step-id: F12 (smoke1), F13 (smoke2), F14 (smoke3). Evidence includes minset paths.
"""
import argparse
import json
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Append Smoke-1/2/3 ROUND_END events.")
    parser.add_argument("--strict-result", default="", help="strict-run result e.g. OK or SKIPPED")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    log_path = repo / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    strict_suffix = f"; strict-run={args.strict_result}" if args.strict_result else ""

    # Idempotent: skip if already appended
    existing_rounds = set()
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
                if ev.get("event") == "round_end" and ev.get("round_id", "").startswith("fitting_smoke_e2e_"):
                    existing_rounds.add(ev["round_id"])
            except json.JSONDecodeError:
                pass

    rounds = [
        ("F12", "fitting_smoke1_ok", f"Smoke-1 E2E: full minset{strict_suffix}"),
        ("F13", "fitting_smoke2_hard_gate", "Smoke-2 E2E: early_exit=true, hard gate"),
        ("F14", "fitting_smoke3_degraded", "Smoke-3 E2E: degraded_state, warnings_summary"),
    ]

    ts = _ts_now()
    appended = 0
    for step_id, run_id, note in rounds:
        round_id = f"fitting_smoke_e2e_{run_id}"
        if round_id in existing_rounds:
            continue
        evidence = [
            f"runs/{run_id}/geometry_manifest.json",
            f"runs/{run_id}/facts_summary.json",
            f"runs/{run_id}/RUN_README.md",
        ]
        ev = {
            "ts": ts,
            "module": "fitting",
            "step_id": step_id,
            "event": "round_end",
            "round_id": round_id,
            "run_id": run_id,
            "status": "OK",
            "dod_done_delta": 0,
            "note": note,
            "evidence": evidence,
            "evidence_paths": evidence,
            "warnings": [],
            "lane": "smoke",
            "minset_created": evidence,
        }
        line = json.dumps(ev, ensure_ascii=False) + "\n"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
        appended += 1
        existing_rounds.add(round_id)

    print(f"append_smoke_e2e_rounds: appended {appended} ROUND_END event(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
