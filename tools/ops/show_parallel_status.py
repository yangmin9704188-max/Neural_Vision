#!/usr/bin/env python3
"""show_parallel_status.py

Cross-module snapshot for parallel execution.
- Reads latest progress events (body/garment/fitting)
- Reads m1 signal readiness from ops/signals/m1/*/LATEST.json
- Prints a compact human table or JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def find_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    if start is None:
        start = Path.cwd()
    cur = start.resolve()
    while True:
        if (cur / ".git").is_dir():
            return cur
        if (cur / "project_map.md").is_file():
            return cur
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent


def parse_iso(ts: Any) -> Optional[datetime]:
    if not isinstance(ts, str) or not ts.strip():
        return None
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def to_epoch(dt: Optional[datetime]) -> float:
    if dt is None:
        return float("-inf")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.is_file():
        return
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                if isinstance(data, dict):
                    yield data
    except Exception:
        return


def latest_event_for_module(repo_root: Path, module: str) -> Optional[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    module_log = repo_root / "modules" / module / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    logs = [
        (module_log, 0),  # Prefer module-owned progress log on timestamp ties.
        (repo_root / "exports" / "progress" / "PROGRESS_LOG.jsonl", 1),
    ]
    for p, source_rank in logs:
        seq = 0
        for rec in iter_jsonl(p):
            if str(rec.get("module", "")).lower() == module:
                rec = dict(rec)
                rec["_source_log"] = str(p.relative_to(repo_root))
                rec["_source_rank"] = source_rank
                rec["_seq"] = seq
                candidates.append(rec)
            seq += 1
    if not candidates:
        return None
    candidates.sort(
        key=lambda r: (
            to_epoch(parse_iso(r.get("ts"))),
            -int(r.get("_source_rank", 1)),
            int(r.get("_seq", 0)),
        )
    )
    return candidates[-1]


def read_signal(repo_root: Path, module: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    sig = repo_root / "ops" / "signals" / "m1" / module / "LATEST.json"
    if not sig.is_file():
        return False, None
    try:
        data = json.loads(sig.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False, None
        run_dir_rel = data.get("run_dir_rel")
        if isinstance(run_dir_rel, str) and run_dir_rel.strip():
            run_dir = (repo_root / run_dir_rel).resolve()
            return run_dir.exists(), data
        return False, data
    except Exception:
        return False, None


def short_note(text: Any, limit: int = 80) -> str:
    if not isinstance(text, str):
        return ""
    one = " ".join(text.split())
    if len(one) <= limit:
        return one
    return one[: limit - 3] + "..."


def render_human(rows: List[Dict[str, Any]], repo_root: Path) -> None:
    print("PARALLEL STATUS SNAPSHOT")
    print(f"repo_root: {repo_root}")
    print()
    header = (
        f"{'module':<8} {'signal':<7} {'step_id':<32} "
        f"{'status':<8} {'ts':<25} note"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['module']:<8} {r['signal_ready']:<7} {r['step_id']:<32} "
            f"{r['status']:<8} {r['ts']:<25} {r['note']}"
        )
    print()
    print("tip:")
    print("  py tools/agent/next_step.py --module all --top 10")
    print("  py tools/ops/show_parallel_status.py --json")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Show cross-module status snapshot for parallel execution"
    )
    ap.add_argument("--json", action="store_true", help="Output JSON")
    args = ap.parse_args()

    repo_root = find_repo_root()
    if repo_root is None:
        print("ERROR: repository root not found", file=sys.stderr)
        return 1

    rows: List[Dict[str, Any]] = []
    for module in ("body", "garment", "fitting"):
        evt = latest_event_for_module(repo_root, module)
        sig_ready, sig_data = read_signal(repo_root, module)
        row = {
            "module": module,
            "signal_ready": "yes" if sig_ready else "no",
            "signal_run_dir_rel": (
                sig_data.get("run_dir_rel")
                if isinstance(sig_data, dict)
                else None
            ),
            "step_id": (evt or {}).get("step_id") or "N/A",
            "status": (evt or {}).get("status") or "N/A",
            "ts": (evt or {}).get("ts") or "N/A",
            "note": short_note((evt or {}).get("note", ""), 90),
            "progress_log": (evt or {}).get("_source_log"),
        }
        rows.append(row)

    if args.json:
        out = {
            "schema_version": "parallel_status.v1",
            "repo_root": str(repo_root),
            "rows": rows,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        render_human(rows, repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
