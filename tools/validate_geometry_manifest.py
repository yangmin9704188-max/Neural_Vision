#!/usr/bin/env python3
"""Validate geometry_manifest.json against contracts/geometry_manifest_v1.schema.json."""
import json
import sys
from argparse import ArgumentParser
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema required. Install with: pip install jsonschema", file=sys.stderr)
    sys.exit(2)


def _repo_root() -> Path:
    """Project root (parent of tools/)."""
    return Path(__file__).resolve().parent.parent


def validate_manifest(run_dir: Path, strict_artifacts: bool = False) -> bool:
    """
    Load geometry_manifest.json from run_dir and validate against v1 schema.
    Optionally warn if artifact paths don't exist under run_dir (no hard-fail unless strict_artifacts).
    Returns True if valid, False otherwise.
    """
    manifest_path = run_dir / "geometry_manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found.", file=sys.stderr)
        return False

    schema_path = _repo_root() / "contracts" / "geometry_manifest_v1.schema.json"
    if not schema_path.exists():
        print(f"ERROR: Schema not found: {schema_path}", file=sys.stderr)
        return False

    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        print(f"ERROR: Schema validation failed: {e}", file=sys.stderr)
        return False

    # Additional checks: artifact paths exist (warn only unless strict)
    artifacts = data.get("artifacts", [])
    for rel in artifacts:
        full = (run_dir / rel).resolve()
        run_resolved = run_dir.resolve()
        if not full.exists():
            msg = f"WARN: Artifact path does not exist: {rel}"
            if strict_artifacts:
                print(f"ERROR: {msg}", file=sys.stderr)
                return False
            print(msg, file=sys.stderr)
        elif not str(full).startswith(str(run_resolved)):
            print(f"WARN: Artifact path escapes run_dir: {rel}", file=sys.stderr)

    return True


def main() -> int:
    parser = ArgumentParser(description="Validate geometry_manifest.json against v1 schema")
    parser.add_argument("--run_dir", type=Path, required=True, help="Run directory containing geometry_manifest.json")
    parser.add_argument("--strict_artifacts", action="store_true", help="Fail if artifact paths don't exist")
    args = parser.parse_args()

    ok = validate_manifest(args.run_dir, strict_artifacts=args.strict_artifacts)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
