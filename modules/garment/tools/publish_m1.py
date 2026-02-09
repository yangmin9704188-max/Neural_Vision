#!/usr/bin/env python3
"""Publish Garment M1 output to local shared storage (repo-relative).

Writes run outputs under:
  data/shared_m1/garment/<run_id>/

Required files:
  - geometry_manifest.json
  - garment_proxy_meta.json
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
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


def _default_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"g11_m1_{ts}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish Garment M1 output under data/shared_m1/garment/<run_id>"
    )
    parser.add_argument("--run-id", default=None, help="Run id segment for shared folder")
    parser.add_argument(
        "--mode",
        choices=("hard-gate", "normal"),
        default="hard-gate",
        help="Fixture generation mode",
    )
    parser.add_argument("--with-mesh", action="store_true", help="Generate mesh artifact too")
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    repo_root = _find_repo_root(script_path.parent)
    if repo_root is None:
        print("ERROR: could not find repo root", file=sys.stderr)
        return 1

    run_id = args.run_id or _default_run_id()
    run_dir_rel = Path("data") / "shared_m1" / "garment" / run_id
    run_dir_abs = repo_root / run_dir_rel

    generator = script_path.with_name("generate_m0_fixture.py")
    cmd = [
        sys.executable,
        str(generator),
        "--run-dir",
        str(run_dir_abs),
        "--mode",
        args.mode,
    ]
    if args.with_mesh:
        cmd.append("--with-mesh")

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: fixture generation failed: {exc}", file=sys.stderr)
        return 1

    required = [
        run_dir_abs / "geometry_manifest.json",
        run_dir_abs / "garment_proxy_meta.json",
    ]
    missing = [p for p in required if not p.is_file()]
    if missing:
        print("ERROR: missing required files:", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 1

    print(run_dir_rel.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
