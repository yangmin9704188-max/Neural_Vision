#!/usr/bin/env python3
"""Generate deterministic M0 garment outputs for U1 validation.

This tool creates a minimal run directory that is independent from Body/Fitting
outputs. Default mode is hard-gate, so missing mesh is allowed by
validate_u1_garment.py (WARN only).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CREATED_AT_UTC = "2026-01-01T00:00:00Z"


def _sha256_hex(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_manifest(mode: str, with_mesh: bool) -> dict:
    fingerprint_seed = {
        "fixture": "garment_m0",
        "mode": mode,
        "with_mesh": with_mesh,
        "schema_version": "geometry_manifest.v1",
    }
    artifacts = [
        "geometry_manifest.json",
        "garment_proxy_meta.json",
    ]
    if with_mesh:
        artifacts.append("garment_proxy_mesh.glb")

    return {
        "schema_version": "geometry_manifest.v1",
        "module_name": "garment",
        "contract_version": "garment.contract.m0.v1",
        "created_at": CREATED_AT_UTC,
        "inputs_fingerprint": _sha256_hex(fingerprint_seed),
        "version_keys": {
            "snapshot_version": "m0-snapshot-v1",
            "semantic_version": "m0-semantic-v1",
            "geometry_impl_version": "m0-fixture-gen-v1",
            "dataset_version": "m0-dataset-v1",
        },
        "artifacts": artifacts,
    }


def _build_meta(mode: str) -> dict:
    hard_gate = mode == "hard-gate"
    return {
        "schema_version": "garment_proxy_meta.v1",
        "invalid_face_flag": hard_gate,
        "negative_face_area_flag": False,
        "self_intersection_flag": False,
        "source": "m0_fixture_generator",
        "warnings": (
            ["HARD_GATE_SIMULATED_INVALID_FACE"] if hard_gate else []
        ),
    }


def _write_placeholder_glb(path: Path) -> None:
    # Minimal deterministic placeholder bytes. Validation only checks existence.
    data = b"glTF\x02\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00"
    path.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic M0 garment fixture output"
    )
    parser.add_argument("--run-dir", required=True, help="Output run directory")
    parser.add_argument(
        "--mode",
        choices=("hard-gate", "normal"),
        default="hard-gate",
        help="hard-gate: mesh optional, normal: write mesh by default",
    )
    parser.add_argument(
        "--with-mesh",
        action="store_true",
        help="Also write garment_proxy_mesh.glb",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    write_mesh = args.with_mesh or args.mode == "normal"

    manifest = _build_manifest(args.mode, write_mesh)
    meta = _build_meta(args.mode)

    _write_json(run_dir / "geometry_manifest.json", manifest)
    _write_json(run_dir / "garment_proxy_meta.json", meta)

    if write_mesh:
        _write_placeholder_glb(run_dir / "garment_proxy_mesh.glb")

    print(f"m0_fixture_ready: {run_dir.as_posix()}")
    print(f"mode={args.mode} with_mesh={str(write_mesh).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
