#!/usr/bin/env python3
"""Backfill geometry_manifest.json into existing body run dirs (where facts_summary.json exists)."""
from __future__ import annotations

import json
import sys
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path


def backfill_body_run_dir(run_dir: Path) -> bool:
    """Write geometry_manifest.json to run_dir if facts_summary.json exists. Return True on success."""
    run_dir = Path(run_dir).resolve()
    facts = run_dir / "facts_summary.json"
    if not facts.exists():
        print(f"[backfill] SKIP {run_dir}: facts_summary.json not found", file=sys.stderr)
        return False

    # Infer artifacts from run_dir contents
    artifacts_list = ["facts_summary.json"]
    if (run_dir / "body_measurements_subset.json").exists():
        artifacts_list.append("body_measurements_subset.json")
    npz_path = run_dir / "artifacts" / "visual" / "verts_proxy.npz"
    if npz_path.exists():
        artifacts_list.append(npz_path.relative_to(run_dir).as_posix())

    stub_geom = {
        "schema_version": "geometry_manifest.v1",
        "module_name": "body",
        "contract_version": "v0",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs_fingerprint": "sha256:stub",
        "version_keys": {
            "snapshot_version": "unknown",
            "semantic_version": "unknown",
            "geometry_impl_version": "unknown",
            "dataset_version": "unknown",
        },
        "artifacts": artifacts_list,
        "warnings": ["GEOMETRY_MANIFEST_STUB"],
    }
    geom_path = run_dir / "geometry_manifest.json"
    with open(geom_path, "w", encoding="utf-8") as f:
        json.dump(stub_geom, f, indent=2)
    print(f"[manifest] wrote {geom_path} schema_version={stub_geom['schema_version']}")
    return True


def main() -> int:
    parser = ArgumentParser(description="Backfill geometry_manifest.json into body run dirs")
    parser.add_argument("--run_dir", type=Path, required=True, help="Body run directory (e.g. geo_v0_s1)")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Find all run dirs under path with facts_summary.json and backfill each",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        print(f"ERROR: {run_dir} does not exist", file=sys.stderr)
        return 1

    count = 0
    if args.recursive:
        for facts in run_dir.rglob("facts_summary.json"):
            parent = facts.parent
            if backfill_body_run_dir(parent):
                count += 1
    else:
        if backfill_body_run_dir(run_dir):
            count = 1

    return 0 if count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
