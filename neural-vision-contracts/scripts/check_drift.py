#!/usr/bin/env python3
"""
Contract drift checker.

Compares local schema files against a pinned contracts tag.
Place contracts_pin.json in the consumer repo root.

Usage (from consumer repo):
    python scripts/check_drift.py --pin contracts_pin.json --schemas-dir contracts/schemas

contracts_pin.json format:
{
  "contracts_repo": "neural-vision-contracts",
  "pinned_tag": "v0.1.0",
  "pinned_sha": "<commit-sha>",
  "schemas_used": [
    "schemas/geometry_manifest.v1.schema.json",
    ...
  ]
}
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Check contract schema drift")
    parser.add_argument("--pin", required=True, help="Path to contracts_pin.json")
    parser.add_argument("--schemas-dir", required=True,
                        help="Path to local schemas directory (contracts package root)")
    args = parser.parse_args()

    pin_path = Path(args.pin)
    schemas_root = Path(args.schemas_dir)

    if not pin_path.exists():
        print(f"ERROR: pin file not found: {pin_path}")
        sys.exit(1)

    with open(pin_path, "r", encoding="utf-8") as f:
        pin = json.load(f)

    print(f"Pinned tag: {pin.get('pinned_tag', 'UNKNOWN')}")
    print(f"Pinned SHA: {pin.get('pinned_sha', 'UNKNOWN')}")
    print()

    schemas_used = pin.get("schemas_used", [])
    if not schemas_used:
        print("WARNING: no schemas_used listed in pin file")
        sys.exit(0)

    drift_found = False
    for schema_rel in schemas_used:
        local_path = schemas_root / schema_rel
        if not local_path.exists():
            print(f"  MISSING: {schema_rel}")
            drift_found = True
            continue

        local_sha = sha256_file(local_path)
        print(f"  OK: {schema_rel} (sha256: {local_sha[:16]}...)")

    if drift_found:
        print()
        print("DRIFT DETECTED: one or more schemas are missing locally.")
        print("Run sync to update local copies from the pinned tag.")
        sys.exit(1)
    else:
        print()
        print("No drift detected. All pinned schemas present locally.")


if __name__ == "__main__":
    main()
