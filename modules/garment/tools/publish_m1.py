#!/usr/bin/env python3
"""
Publish Garment M1 artifacts to shared path:
  <SHARED_M1_ROOT>/garment/<run_id>

Default SHARED_M1_ROOT:
  C:/Users/caino/Desktop/NV_shared_data/shared_m1

Override:
  NV_SHARED_M1_ROOT=<absolute_or_relative_path>

Required input files in source run dir:
- geometry_manifest.json
- garment_proxy_meta.json

Optional input files:
- garment_proxy_mesh.glb
- garment_proxy.npz

Hard-gate runs are still publishable as long as required files exist.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


REQUIRED_FILES = ("geometry_manifest.json", "garment_proxy_meta.json")
OPTIONAL_FILES = ("garment_proxy_mesh.glb", "garment_proxy.npz")
DEFAULT_SHARED_M1_ROOT = Path(r"C:/Users/caino/Desktop/NV_shared_data/shared_m1")


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        has_git = (candidate / ".git").exists()
        has_layout = (candidate / "modules").exists() and (candidate / "ops").exists()
        if has_git or has_layout:
            return candidate
    raise RuntimeError("Unable to locate repo root from current path")


def _to_repo_rel_or_abs(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return str(path.resolve())


def _resolve_shared_m1_root(repo_root: Path) -> Path:
    env = os.getenv("NV_SHARED_M1_ROOT", "").strip()
    if not env:
        return DEFAULT_SHARED_M1_ROOT
    env_path = Path(env)
    if env_path.is_absolute():
        return env_path
    return (repo_root / env_path).resolve()


def _candidate_run_dirs(repo_root: Path, shared_m1_root: Path) -> Iterable[Path]:
    roots = (
        repo_root / "runs",
        repo_root / "exports" / "runs",
        shared_m1_root / "garment",
    )
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        for manifest in root.rglob("geometry_manifest.json"):
            run_dir = manifest.parent
            key = str(run_dir.resolve())
            if key in seen:
                continue
            seen.add(key)
            if (run_dir / "garment_proxy_meta.json").exists():
                yield run_dir


def _pick_latest_run_dir(repo_root: Path, shared_m1_root: Path) -> Optional[Path]:
    candidates = list(_candidate_run_dirs(repo_root, shared_m1_root))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _read_hard_gate_flag(meta_path: Path) -> bool:
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        flags = payload.get("flags", {})
        if isinstance(flags, dict):
            return bool(flags.get("invalid_face_flag", False))
        return bool(payload.get("invalid_face_flag", False))
    except Exception:
        return False


def _copy(src_dir: Path, dst_dir: Path, filenames: Iterable[str]) -> list[str]:
    copied = []
    for name in filenames:
        src = src_dir / name
        if not src.exists():
            continue
        dst = dst_dir / name
        shutil.copy2(src, dst)
        copied.append(name)
    return copied


def _append_m1_progress_event(
    repo_root: Path,
    run_id: str,
    source_dir: Path,
    run_dir: Path,
) -> None:
    """Best-effort append for Garment M1 publish. Never raises."""
    appender = repo_root / "tools" / "ops" / "append_progress_event.py"
    if not appender.exists():
        print("WARN: append_progress_event.py not found; skipping progress append", file=sys.stderr)
        return

    garment_lab_root = repo_root / "modules" / "garment"
    if not garment_lab_root.exists():
        garment_lab_root = repo_root

    source_manifest = _to_repo_rel_or_abs(source_dir / "geometry_manifest.json", repo_root)
    published_manifest = _to_repo_rel_or_abs(run_dir / "geometry_manifest.json", repo_root)
    run_dir_rel = _to_repo_rel_or_abs(run_dir, repo_root)

    cmd = [
        sys.executable,
        str(appender),
        "--lab-root", str(garment_lab_root),
        "--module", "garment",
        "--step-id", "G10_M1_PUBLISH",
        "--event", "note",
        "--run-id", run_id,
        "--status", "OK",
        "--m-level", "M1",
        "--note", f"Garment M1 published: {run_dir_rel}",
        "--evidence", source_manifest,
        "--evidence", published_manifest,
    ]
    try:
        subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=False)
    except Exception as exc:
        print(f"WARN: failed to append M1 progress event: {exc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Garment M1 shared artifacts")
    parser.add_argument(
        "--source-run-dir",
        default=None,
        help="Source run directory containing manifest/meta. Defaults to latest detected run.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Publish run id. Defaults to current UTC timestamp (YYYYmmdd_HHMMSS).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite destination run directory if it already exists.",
    )
    parser.add_argument(
        "--no-progress-event",
        action="store_true",
        help="Do not append G10_M1_PUBLISH event to PROGRESS_LOG.",
    )
    args = parser.parse_args()

    repo_root = _find_repo_root(Path(__file__).resolve())
    shared_m1_root = _resolve_shared_m1_root(repo_root)

    if args.source_run_dir:
        source_path = Path(args.source_run_dir)
        if source_path.is_absolute():
            source_dir = source_path.resolve()
        else:
            source_dir = (repo_root / source_path).resolve()
    else:
        source_dir = _pick_latest_run_dir(repo_root, shared_m1_root)
        if source_dir is None:
            print("ERROR: no run directory with required files found", file=sys.stderr)
            return 1

    if not source_dir.exists() or not source_dir.is_dir():
        print(f"ERROR: source run dir not found: {source_dir}", file=sys.stderr)
        return 1

    missing = [name for name in REQUIRED_FILES if not (source_dir / name).exists()]
    if missing:
        print(f"ERROR: missing required files in source run dir: {', '.join(missing)}", file=sys.stderr)
        return 1

    run_id = args.run_id or _utc_run_id()
    run_dir = shared_m1_root / "garment" / run_id
    if run_dir.exists():
        if not args.overwrite:
            print(f"ERROR: destination already exists: {run_dir}", file=sys.stderr)
            return 1
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    copied_required = _copy(source_dir, run_dir, REQUIRED_FILES)
    copied_optional = _copy(source_dir, run_dir, OPTIONAL_FILES)

    hard_gate = _read_hard_gate_flag(source_dir / "garment_proxy_meta.json")
    run_dir_rel = os.path.relpath(str(run_dir.resolve()), str(repo_root.resolve()))

    print(f"SHARED_M1_ROOT={shared_m1_root.resolve()}")
    print(f"SOURCE_RUN_DIR_REL={_to_repo_rel_or_abs(source_dir, repo_root)}")
    print(f"HARD_GATE={'1' if hard_gate else '0'}")
    print(f"COPIED_REQUIRED={','.join(copied_required)}")
    print(f"COPIED_OPTIONAL={','.join(copied_optional)}")
    print(f"RUN_DIR_ABS={run_dir.resolve()}")
    print(f"RUN_DIR_REL={run_dir_rel}")
    if not args.no_progress_event:
        _append_m1_progress_event(
            repo_root=repo_root,
            run_id=run_id,
            source_dir=source_dir,
            run_dir=run_dir,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())


