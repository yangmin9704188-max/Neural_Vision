#!/usr/bin/env python3
"""Publish Body M1 artifacts into data/shared_m1/body/<run_id>."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE_REL = Path("tests/fixtures/u2_smokes/smoke1_ok/body_run")
MANIFEST_NAME = "geometry_manifest.json"
REQUIRED_FILES = ("body_measurements_subset.json",)
OPTIONAL_FILES = ("body_mesh.npz",)


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_body_m1")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _coerce_non_empty(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return default


def _compute_inputs_fingerprint(run_dir: Path, copied_files: list[str]) -> str:
    hasher = hashlib.sha256()
    for name in sorted(copied_files):
        p = run_dir / name
        hasher.update(name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(p.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _resolve_source_dir(args: argparse.Namespace) -> Path:
    if args.source_run_dir:
        return Path(args.source_run_dir).resolve()
    if args.from_fixture or not args.source_run_dir:
        return (REPO_ROOT / DEFAULT_FIXTURE_REL).resolve()
    raise ValueError("unable to resolve source run directory")


def _copy_minset(source_dir: Path, out_dir: Path) -> list[str]:
    copied: list[str] = []
    for name in REQUIRED_FILES:
        src = source_dir / name
        if not src.is_file():
            raise FileNotFoundError(f"required file missing in source: {src}")
        shutil.copy2(src, out_dir / name)
        copied.append(name)

    for name in OPTIONAL_FILES:
        src = source_dir / name
        if src.is_file():
            shutil.copy2(src, out_dir / name)
            copied.append(name)
    return copied


def _write_manifest(
    source_dir: Path,
    out_dir: Path,
    run_dir_rel: str,
    copied_files: list[str],
) -> None:
    source_manifest_path = source_dir / MANIFEST_NAME
    source_manifest: dict[str, Any] = {}
    if source_manifest_path.is_file():
        source_manifest = _load_json(source_manifest_path)

    source_version_keys = source_manifest.get("version_keys")
    if not isinstance(source_version_keys, dict):
        source_version_keys = {}

    artifacts = [f"{run_dir_rel}/body_measurements_subset.json"]
    if "body_mesh.npz" in copied_files:
        artifacts.insert(0, f"{run_dir_rel}/body_mesh.npz")

    manifest = {
        "schema_version": "geometry_manifest.v1",
        "module_name": "body",
        "contract_version": _coerce_non_empty(source_manifest.get("contract_version"), "v1.1"),
        "created_at": _utc_now_z(),
        "inputs_fingerprint": _compute_inputs_fingerprint(out_dir, copied_files),
        "version_keys": {
            "snapshot_version": _coerce_non_empty(source_version_keys.get("snapshot_version"), "UNSPECIFIED"),
            "semantic_version": _coerce_non_empty(source_version_keys.get("semantic_version"), "UNSPECIFIED"),
            "geometry_impl_version": _coerce_non_empty(source_version_keys.get("geometry_impl_version"), "UNSPECIFIED"),
            "dataset_version": _coerce_non_empty(source_version_keys.get("dataset_version"), "UNSPECIFIED"),
        },
        "artifacts": artifacts,
        "warnings": source_manifest.get("warnings") if isinstance(source_manifest.get("warnings"), list) else [],
    }
    _write_json(out_dir / MANIFEST_NAME, manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish Body M1 artifacts")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--source-run-dir", type=str, help="Source run directory containing Body U1 outputs")
    group.add_argument("--from-fixture", action="store_true", help="Use tests fixture as source run directory")
    parser.add_argument("--run-id", type=str, help="Run ID for data/shared_m1/body/<run_id>")
    args = parser.parse_args(argv)

    source_dir = _resolve_source_dir(args)
    if not source_dir.is_dir():
        print(f"source run dir not found: {source_dir}", file=sys.stderr)
        return 2

    run_id = args.run_id or _default_run_id()
    run_dir_rel = f"data/shared_m1/body/{run_id}"
    out_dir = (REPO_ROOT / run_dir_rel).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        copied = _copy_minset(source_dir, out_dir)
        _write_manifest(source_dir, out_dir, run_dir_rel, copied)
    except Exception as exc:
        print(f"publish failed: {exc}", file=sys.stderr)
        return 1

    required_out = (MANIFEST_NAME, "body_measurements_subset.json")
    for name in required_out:
        if not (out_dir / name).is_file():
            print(f"publish failed: required output missing: {name}", file=sys.stderr)
            return 1

    print(f"RUN_DIR_REL={run_dir_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

