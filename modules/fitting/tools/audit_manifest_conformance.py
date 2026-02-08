#!/usr/bin/env python3
"""
Audit geometry_manifest.json in run dirs against contracts/geometry_manifest.schema.json.
With --check_files, verify artifact paths (artifacts.mesh_path etc.) exist under each run_dir.
Usage:
  python tools/audit_manifest_conformance.py --schema contracts/geometry_manifest.schema.json \
    --run_dir_body <dir> --run_dir_fitting <dir> --run_dir_garment <dir> --check_files
  (If only one runner exists, point all three to the same run_dir.)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("error: jsonschema required. pip install jsonschema", file=sys.stderr)
    sys.exit(1)


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text), None
    except FileNotFoundError:
        return None, f"file not found: {path}"
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def _collect_artifact_paths(manifest: dict, schema: dict) -> list[str]:
    """Collect artifact paths for --check_files. Supports v1 (artifacts array) and legacy (artifacts object)."""
    paths: list[str] = []
    art = manifest.get("artifacts")
    # v1: artifacts is array of strings
    if isinstance(art, list):
        for p in art:
            if isinstance(p, str) and p:
                paths.append(p)
        return paths
    # legacy: artifacts is object with mesh_path etc.
    if not isinstance(art, dict):
        return paths
    for key in ("mesh_path", "measurements_path", "npz_path"):
        if key in art and art[key]:
            p = art[key]
            if isinstance(p, str):
                paths.append(p)
    aux = art.get("aux_paths")
    if isinstance(aux, list):
        for p in aux:
            if isinstance(p, str) and p:
                paths.append(p)
    return paths


def audit_run_dir(run_dir: Path, schema: dict, check_files: bool) -> list[str]:
    errs: list[str] = []
    manifest_path = run_dir / "geometry_manifest.json"
    data, load_err = _load_json(manifest_path)
    if load_err:
        errs.append(f"{run_dir}: {load_err}")
        return errs
    assert data is not None
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        errs.append(f"{run_dir}: schema violation: {e.message}")
    if check_files:
        for rel in _collect_artifact_paths(data, schema):
            full = (run_dir / rel).resolve()
            if not full.is_file():
                errs.append(f"{run_dir}: artifact missing: {rel}")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit geometry_manifest.json in run dirs.")
    ap.add_argument("--schema", type=Path, required=True, help="Path to geometry_manifest schema JSON")
    ap.add_argument("--run_dir_body", type=Path, required=True, help="Body leaf run dir")
    ap.add_argument("--run_dir_fitting", type=Path, required=True, help="Fitting leaf run dir")
    ap.add_argument("--run_dir_garment", type=Path, required=True, help="Garment leaf run dir")
    ap.add_argument("--check_files", action="store_true", help="Verify artifact files exist")
    args = ap.parse_args()

    schema_path = args.schema.resolve()
    if not schema_path.is_file():
        print(f"error: schema not found: {schema_path}", file=sys.stderr)
        return 1
    schema_data, sch_err = _load_json(schema_path)
    if sch_err or schema_data is None:
        print(f"error: schema load failed: {sch_err}", file=sys.stderr)
        return 1

    run_dirs = [
        ("body", args.run_dir_body),
        ("fitting", args.run_dir_fitting),
        ("garment", args.run_dir_garment),
    ]
    all_errs: list[str] = []
    for name, run_dir in run_dirs:
        r = run_dir.resolve()
        if not r.is_dir():
            all_errs.append(f"{name} run_dir not found or not dir: {r}")
            continue
        all_errs.extend(audit_run_dir(r, schema_data, args.check_files))

    if not all_errs:
        print("AUDIT OK")
        return 0
    print("AUDIT FAILED", file=sys.stderr)
    for e in all_errs:
        print(" -", e, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
