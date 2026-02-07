#!/usr/bin/env python3
"""
Find latest beta_fit_v0 run_dir under exports/runs.
Search: exports/runs/** for summary.json where path contains "beta_fit_v0".
Exclude: paths containing "verification" (do not traverse verification/**).
Latest by: 1) run_id timestamp parsed from parent dir name (run_YYYYMMDD_HHMMSS), else 2) summary.json mtime.
Returns single run_dir path (directory containing summary.json) or None.
Exit 0 always; prints run_dir (one line) or empty line when not found.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORTS_RUNS = REPO_ROOT / "exports" / "runs"

# Parent dir name pattern: run_YYYYMMDD_HHMMSS
RUN_ID_PATTERN = re.compile(r"^run_(\d{8})_(\d{6})$")


def _parse_run_id_ts(parent_name: str) -> datetime | None:
    """Parse run_YYYYMMDD_HHMMSS to datetime (UTC placeholder; no TZ). Returns None if no match."""
    m = RUN_ID_PATTERN.match(parent_name.strip())
    if not m:
        return None
    try:
        ymd, hms = m.group(1), m.group(2)
        return datetime(
            int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]),
            int(hms[:2]), int(hms[2:4]), int(hms[4:6]),
        )
    except (ValueError, IndexError):
        return None


def find_latest_beta_fit_run(repo_root: Path | None = None) -> Path | None:
    """
    Discover latest beta_fit_v0 run_dir under exports/runs.
    - Search for summary.json under repo_root/exports/runs, where path contains "beta_fit_v0".
    - Exclude paths containing "verification".
    - Latest: by run_id timestamp (run_YYYYMMDD_HHMMSS) if parseable, else by summary.json mtime.
    - Returns run_dir (directory containing summary.json) or None.
    """
    base = (repo_root or REPO_ROOT).resolve()
    runs_base = base / "exports" / "runs"
    if not runs_base.exists():
        return None

    candidates: list[tuple[Path, datetime | None, float]] = []  # (run_dir, parsed_ts, mtime)
    for summary_path in runs_base.rglob("summary.json"):
        try:
            rel = summary_path.relative_to(base)
            if "verification" in rel.parts:
                continue
            path_str = str(rel).replace("\\", "/")
            if "beta_fit_v0" not in path_str:
                continue
        except ValueError:
            continue
        run_dir = summary_path.parent
        parsed = _parse_run_id_ts(run_dir.name)
        mtime = summary_path.stat().st_mtime
        # Use parsed timestamp for sorting if available; else we sort by mtime (store None for parsed)
        candidates.append((run_dir, parsed, mtime))

    if not candidates:
        return None

    # Sort by latest: use parsed run_id timestamp if available, else mtime. Newer first.
    def sort_key(item: tuple[Path, datetime | None, float]) -> float:
        _run_dir, parsed, mtime = item
        if parsed is not None:
            return -parsed.timestamp()
        return -mtime

    candidates.sort(key=sort_key)
    return candidates[0][0]


def main() -> int:
    run_dir = find_latest_beta_fit_run()
    if run_dir is not None:
        print(run_dir)
    else:
        print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
