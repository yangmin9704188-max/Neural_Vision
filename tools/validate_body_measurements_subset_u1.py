#!/usr/bin/env python3
"""Validate body_measurements_subset.json U1 schema (Body→Fitting interface)."""
from __future__ import annotations

import json
import math
import sys
from argparse import ArgumentParser
from pathlib import Path

U1_KEYS = ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    """Load JSON; return (data, error). Checks for NaN/Infinity in raw text before parse."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        return None, f"Failed to read file: {e}"

    # Reject NaN/Infinity tokens (JSON spec disallows them)
    for bad in ("NaN", "Infinity", "-Infinity"):
        if bad in raw:
            return None, f"JSON must not contain {bad}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"

    return data, None


def _check_finite(obj: object, path: str) -> list[str]:
    """Recursively check floats are finite. Returns list of error strings."""
    errs: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            errs.extend(_check_finite(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            errs.extend(_check_finite(v, f"{path}[{i}]"))
    elif isinstance(obj, float):
        if not math.isfinite(obj):
            errs.append(f"Non-finite value at {path}: {obj}")
    return errs


def validate(data: dict) -> tuple[bool, list[str], dict]:
    """
    Validate U1 schema. Returns (ok, errors, report_dict).
    report_dict: null_counts, cases_1_null, cases_2plus_null, warnings_added
    """
    errors: list[str] = []
    report: dict = {
        "null_counts": {k: 0 for k in U1_KEYS},
        "cases_1_null": 0,
        "cases_2plus_null": 0,
        "warnings_added": [],
    }

    # unit == "m"
    if data.get("unit") != "m":
        errors.append(f"unit must be 'm', got {data.get('unit')!r}")

    # pose_id == "PZ1"
    if data.get("pose_id") != "PZ1":
        errors.append(f"pose_id must be 'PZ1', got {data.get('pose_id')!r}")

    # keys includes BUST_CIRC_M, WAIST_CIRC_M, HIP_CIRC_M
    keys = data.get("keys")
    if not isinstance(keys, list):
        errors.append("keys must be an array")
    else:
        for k in U1_KEYS:
            if k not in keys:
                errors.append(f"keys must include {k}")

    # warnings field exists and is array
    warnings = data.get("warnings")
    if warnings is None:
        errors.append("warnings field is required")
    elif not isinstance(warnings, list):
        errors.append("warnings must be an array")

    # NaN/Inf check on parsed floats
    finite_errs = _check_finite(data, "root")
    errors.extend(finite_errs)

    # Count nulls per key and per-case degradation
    cases = data.get("cases", [])
    if not isinstance(cases, list):
        errors.append("cases must be an array")
    else:
        for case in cases:
            if not isinstance(case, dict):
                continue
            null_count = 0
            for k in U1_KEYS:
                v = case.get(k)
                if v is None:
                    report["null_counts"][k] += 1
                    null_count += 1
            if null_count == 1:
                report["cases_1_null"] += 1
            elif null_count >= 2:
                report["cases_2plus_null"] += 1

        # Mutually exclusive: 2+ nulls => DEGRADED_HIGH only; 1 null => SOFT only
        if report["cases_2plus_null"] > 0:
            report["warnings_added"].append("U1_SUBSET_NULL_DEGRADED_HIGH")
        elif report["cases_1_null"] > 0:
            report["warnings_added"].append("U1_SUBSET_NULL_SOFT")

    ok = len(errors) == 0
    return ok, errors, report


def main() -> int:
    parser = ArgumentParser(description="Validate body_measurements_subset.json U1 schema")
    parser.add_argument("--run_dir", type=Path, required=True, help="Leaf run dir containing body_measurements_subset.json")
    args = parser.parse_args()

    path = args.run_dir / "body_measurements_subset.json"
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1

    data, load_err = _load_json(path)
    if load_err:
        print(f"ERROR: {load_err}", file=sys.stderr)
        return 1

    ok, errors, report = validate(data)

    # Report
    print("=== body_measurements_subset U1 validation ===")
    print(f"run_dir: {args.run_dir}")
    print()
    print("Null counts per key:")
    for k in U1_KEYS:
        print(f"  {k}: {report['null_counts'][k]}")
    print(f"Cases with 1 null (of 3 keys): {report['cases_1_null']}")
    print(f"Cases with 2+ nulls (of 3 keys): {report['cases_2plus_null']}")
    if report["warnings_added"]:
        print(f"Warnings: {report['warnings_added']}")
    print()

    if errors:
        print("Schema violations:")
        for e in errors:
            print(f"  ERROR: {e}")
        print()
        return 1

    print("VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
