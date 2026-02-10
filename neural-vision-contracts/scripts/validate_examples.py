#!/usr/bin/env python3
"""
Validate example JSON files against their corresponding schemas.

Usage:
    python scripts/validate_examples.py [--schema-dir schemas] [--examples-dir examples]

Exit codes:
    0 = all examples valid
    1 = one or more validation failures
"""
import argparse
import json
import os
import sys
from pathlib import Path

try:
    from jsonschema import validate, ValidationError, Draft202012Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# Mapping: example filename pattern -> schema filename
SCHEMA_MAP = {
    "body_infer_request": "body_infer_request.v1.schema.json",
    "seller_intake_request": "seller_intake_request.v1.schema.json",
    "fitting_run_request": "fitting_run_request.v1.schema.json",
    # Response files validate embedded domain objects
}

# For response files, validate nested objects against domain schemas
RESPONSE_NESTED_SCHEMAS = {
    "body_infer_response": [
        ("$.data.measurements", "body_measurements_subset.v1.schema.json"),
        ("$.manifest", "geometry_manifest.v1.schema.json"),
    ],
    "seller_intake_response": [
        ("$.data.proxy_meta", "garment_proxy_meta.v1.schema.json"),
        ("$.manifest", "geometry_manifest.v1.schema.json"),
    ],
    "fitting_run_response": [
        ("$.data.facts", "fitting_facts_summary.v1.schema.json"),
        ("$.manifest", "geometry_manifest.v1.schema.json"),
    ],
    "generation_run_response": [
        ("$.data.delivery", "generation_delivery.v1.schema.json"),
        ("$.data.provenance", "gen_provenance.v1.schema.json"),
        ("$.manifest", "geometry_manifest.v1.schema.json"),
    ],
}


def resolve_jsonpath(data: dict, path: str):
    """Simple JSONPath resolver for dotted paths starting with $."""
    parts = path.lstrip("$").lstrip(".").split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def load_schema(schema_dir: Path, schema_file: str) -> dict:
    """Load and return a JSON schema."""
    schema_path = schema_dir / schema_file
    if not schema_path.exists():
        print(f"  SKIP: schema not found: {schema_path}")
        return None
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_file(json_path: Path, schema: dict) -> list[str]:
    """Validate a JSON file against a schema. Returns list of error messages."""
    errors = []
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if HAS_JSONSCHEMA:
        try:
            Draft202012Validator(schema).validate(data)
        except ValidationError as e:
            errors.append(f"{e.json_path}: {e.message}")
    else:
        # Fallback: basic required-field check
        if "required" in schema:
            for key in schema["required"]:
                if key not in data:
                    errors.append(f"Missing required field: {key}")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate examples against schemas")
    # Resolve paths relative to this script's parent's parent (repo root)
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--schema-dir", default=str(repo_root / "schemas"),
                        help="Path to schemas directory")
    parser.add_argument("--examples-dir", default=str(repo_root / "examples"),
                        help="Path to examples directory")
    args = parser.parse_args()

    schema_dir = Path(args.schema_dir)
    examples_dir = Path(args.examples_dir)

    if not schema_dir.exists():
        print(f"ERROR: schema directory not found: {schema_dir}")
        sys.exit(1)
    if not examples_dir.exists():
        print(f"ERROR: examples directory not found: {examples_dir}")
        sys.exit(1)

    total = 0
    passed = 0
    failed = 0
    skipped = 0

    print(f"Schema dir:   {schema_dir}")
    print(f"Examples dir: {examples_dir}")
    print()

    for scenario_dir in sorted(examples_dir.iterdir()):
        if not scenario_dir.is_dir():
            continue
        print(f"=== {scenario_dir.name} ===")

        for json_file in sorted(scenario_dir.glob("*.json")):
            stem = json_file.stem  # e.g., "body_infer_request"
            total += 1

            # 1) Direct schema validation (request files)
            if stem in SCHEMA_MAP:
                schema = load_schema(schema_dir, SCHEMA_MAP[stem])
                if schema is None:
                    skipped += 1
                    continue
                errors = validate_file(json_file, schema)
                if errors:
                    print(f"  FAIL: {json_file.name}")
                    for e in errors:
                        print(f"        {e}")
                    failed += 1
                else:
                    print(f"  PASS: {json_file.name} (vs {SCHEMA_MAP[stem]})")
                    passed += 1

            # 2) Nested schema validation (response files)
            elif stem in RESPONSE_NESTED_SCHEMAS:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                all_ok = True
                for jsonpath, schema_file in RESPONSE_NESTED_SCHEMAS[stem]:
                    nested = resolve_jsonpath(data, jsonpath)
                    if nested is None:
                        print(f"  SKIP: {json_file.name} -> {jsonpath} not found")
                        continue
                    schema = load_schema(schema_dir, schema_file)
                    if schema is None:
                        continue

                    if HAS_JSONSCHEMA:
                        try:
                            Draft202012Validator(schema).validate(nested)
                        except ValidationError as e:
                            print(f"  FAIL: {json_file.name} -> {jsonpath} vs {schema_file}")
                            print(f"        {e.json_path}: {e.message}")
                            all_ok = False
                    else:
                        if "required" in schema:
                            for key in schema["required"]:
                                if key not in nested:
                                    print(f"  FAIL: {json_file.name} -> {jsonpath} missing {key}")
                                    all_ok = False

                if all_ok:
                    print(f"  PASS: {json_file.name} (nested schema checks)")
                    passed += 1
                else:
                    failed += 1
            else:
                print(f"  SKIP: {json_file.name} (no schema mapping)")
                skipped += 1

        print()

    print("=" * 40)
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}  Skipped: {skipped}")

    if not HAS_JSONSCHEMA:
        print()
        print("WARNING: jsonschema package not installed. Only basic checks performed.")
        print("Install with: pip install jsonschema")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
