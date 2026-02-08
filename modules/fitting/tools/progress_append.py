#!/usr/bin/env python3
"""
Append one JSON line to exports/progress/PROGRESS_LOG.jsonl.
Self-contained (no main repo). Used by run_end_hook and runners.
Schema: ts, module, step_id, event, dod_done_delta, dod_total(opt), note, status, ...
"""
import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime


def _ts_now() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    except ImportError:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _is_valid_step_id(s: str) -> bool:
    """Reject UNSPECIFIED, empty, or invalid format. Allow Fxx, Gxx, F_BACKFILL."""
    if not s or not isinstance(s, str) or not s.strip():
        return False
    s = s.strip()
    if s.upper() == "UNSPECIFIED":
        return False
    if s == "F_BACKFILL":
        return True
    return bool(re.match(r"^[FG]\d{2}$", s, re.IGNORECASE))


def main() -> int:
    parser = argparse.ArgumentParser(description="Append progress event to PROGRESS_LOG.jsonl")
    parser.add_argument("--step", required=True, dest="step_id", help="e.g. F01, F02 (UNSPECIFIED rejected)")
    parser.add_argument("--done", type=int, default=0, dest="dod_done_delta", help="dod_done_delta")
    parser.add_argument("--total", type=int, default=None, dest="dod_total", help="dod_total (optional)")
    parser.add_argument("--note", default="", help="note")
    parser.add_argument("--event", default="note", help="event type")
    parser.add_argument("--status", default="OK", choices=("OK", "WARN", "FAIL"))
    parser.add_argument("--module", default="fitting")
    parser.add_argument("--evidence", action="append", default=[], help="evidence path(s)")
    parser.add_argument("--gate-code", action="append", default=[], help="e.g. EVIDENCE_ONLY_SAMPLES")
    args = parser.parse_args()

    if not _is_valid_step_id(args.step_id):
        print("progress_append: step_id required and must be Fxx/Gxx (UNSPECIFIED rejected). Exit 1.", file=sys.stderr)
        return 1

    repo = Path(__file__).resolve().parents[1]
    log_dir = repo / "exports" / "progress"
    log_path = log_dir / "PROGRESS_LOG.jsonl"

    ev = {
        "ts": _ts_now(),
        "module": args.module,
        "step_id": args.step_id,
        "event": args.event,
        "run_id": "N/A",
        "status": args.status,
        "dod_done_delta": args.dod_done_delta,
        "note": args.note,
        "evidence": args.evidence or [],
        "warnings": [f"[{g}]" for g in args.gate_code],
    }
    if args.dod_total is not None:
        ev["dod_total"] = args.dod_total

    line = json.dumps(ev, ensure_ascii=False) + "\n"

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        print(f"progress_append: FAIL {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
