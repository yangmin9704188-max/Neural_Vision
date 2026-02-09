#!/usr/bin/env python3
"""Resolve Body M1 input path from signal if available.

Reads:
  ops/signals/m1/body/LATEST.json

Prints:
  - resolved absolute local path when available
  - "not available" when signal is missing or invalid

Always exits 0.
"""
from __future__ import annotations

import json
from pathlib import Path


def _find_repo_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / ".git").exists() or (current / "project_map.md").is_file():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def main() -> int:
    here = Path(__file__).resolve()
    repo_root = _find_repo_root(here.parent)
    if repo_root is None:
        print("not available")
        return 0

    signal_path = repo_root / "ops" / "signals" / "m1" / "body" / "LATEST.json"
    if not signal_path.is_file():
        print("not available")
        return 0

    try:
        data = json.loads(signal_path.read_text(encoding="utf-8"))
    except Exception:
        print("not available")
        return 0

    run_dir_rel = data.get("run_dir_rel")
    if not isinstance(run_dir_rel, str) or not run_dir_rel.strip():
        print("not available")
        return 0

    rel_path = Path(run_dir_rel)
    if rel_path.is_absolute():
        print("not available")
        return 0

    resolved = (repo_root / rel_path).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        print("not available")
        return 0

    print(resolved.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
