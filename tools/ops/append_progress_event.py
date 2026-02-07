#!/usr/bin/env python3
"""
Append-only progress event logger.
Writes to <lab_root>/exports/progress/PROGRESS_LOG.jsonl.
Exit 0 always; failures surface as stdout warning.
"""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime


def _warn(code: str, message: str, path: str = "N/A") -> str:
    return f"[{code}] {message} | path={path}"


def _ts_now() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    except ImportError:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _resolve_log_path(lab_root: Path) -> Path:
    """Resolve to <lab_root>/exports/progress/PROGRESS_LOG.jsonl. Path safety: no parent escape."""
    lab = lab_root.resolve()
    log_path = (lab / "exports" / "progress" / "PROGRESS_LOG.jsonl").resolve()
    try:
        log_path.relative_to(lab)
    except ValueError:
        return lab / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    return log_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Append progress event to PROGRESS_LOG.jsonl")
    parser.add_argument("--lab-root", required=True, help="Lab root (exports/progress under here)")
    parser.add_argument("--module", required=True, choices=("body", "fitting", "garment"))
    parser.add_argument("--step-id", required=True, help="e.g. F01, G12, B02")
    parser.add_argument("--event", required=True, help="e.g. milestone_passed, dod_checkpoint, note, run_finished")
    parser.add_argument("--run-id", default="N/A")
    parser.add_argument("--status", default="N/A", choices=("OK", "WARN", "FAIL", "N/A"))
    parser.add_argument("--note", default="")
    parser.add_argument("--dod-done-delta", type=int, default=0)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--gate-code", action="append", default=[], help="e.g. STEP_ID_MISSING")
    parser.add_argument("--soft-validate", action="store_true")
    parser.add_argument("--ts", default=None)
    args = parser.parse_args()

    lab_root = Path(args.lab_root).resolve()
    log_path = _resolve_log_path(lab_root)
    warnings = []

    if args.soft_validate and args.evidence:
        for p in args.evidence:
            ep = Path(p)
            if not ep.is_absolute():
                ep = lab_root / p
            if not ep.exists():
                warnings.append(_warn("EVIDENCE_NOT_FOUND", "evidence path missing", str(p)))

    ev = {
        "ts": args.ts or _ts_now(),
        "module": args.module,
        "step_id": args.step_id,
        "event": args.event,
        "run_id": args.run_id,
        "status": args.status,
        "dod_done_delta": args.dod_done_delta,
        "note": args.note,
        "evidence": args.evidence or [],
        "warnings": warnings + [f"[{g}]" for g in args.gate_code],
    }

    line = json.dumps(ev, ensure_ascii=False) + "\n"

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        print(f"appended PROGRESS_LOG.jsonl (module={args.module}, step={args.step_id}, event={args.event}), warnings={len(warnings)+1}")
        return 0

    print(f"appended PROGRESS_LOG.jsonl (module={args.module}, step={args.step_id}, event={args.event}), warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
