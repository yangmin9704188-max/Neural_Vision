#!/usr/bin/env python3
"""Publish Garment M1 output into shared non-git storage and update signal."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SIGNAL_PATH = REPO_ROOT / "ops" / "signals" / "m1" / "garment" / "LATEST.json"


def _default_shared_root() -> Path:
    return REPO_ROOT.parent / "NV_shared_data" / "shared_m1"


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_garment_m1")


def _to_repo_rel(path: Path) -> str:
    return os.path.relpath(path, REPO_ROOT).replace("\\", "/")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish Garment M1 output under ../NV_shared_data/shared_m1/garment/<run_id>"
    )
    parser.add_argument("--run-id", default=None, help="Run id segment for shared folder")
    parser.add_argument("--shared-root", default=str(_default_shared_root()), help="Shared root path")
    parser.add_argument(
        "--mode",
        choices=("hard-gate", "normal"),
        default="normal",
        help="Fixture generation mode (default: normal)",
    )
    parser.add_argument("--with-mesh", action="store_true", help="Generate mesh artifact too")
    parser.add_argument("--no-signal-update", action="store_true", help="Do not write ops/signals/m1/garment/LATEST.json")
    args = parser.parse_args()

    run_id = args.run_id or _default_run_id()
    shared_root = Path(args.shared_root).resolve()
    run_dir_abs = shared_root / "garment" / run_id
    run_dir_abs.mkdir(parents=True, exist_ok=True)

    generator = Path(__file__).resolve().with_name("generate_m0_fixture.py")
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

    run_dir_rel = _to_repo_rel(run_dir_abs)

    if not args.no_signal_update:
        signal_payload = {
            "schema_version": "m1_signal.v1",
            "module": "garment",
            "m_level": "M1",
            "run_id": run_id,
            "run_dir_rel": run_dir_rel,
            "created_at_utc": _utc_now_z(),
        }
        _write_json(SIGNAL_PATH, signal_payload)

    print(f"RUN_DIR_REL={run_dir_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
