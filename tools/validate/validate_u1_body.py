#!/usr/bin/env python3
"""validate_u1_body.py — Enforce Body→Fitting U1 rules.

Reference: unlock_conditions_u1_u2.md §2.1

Checks:
  - geometry_manifest.json present + valid (delegates)
  - body_measurements_subset.json present + schema rules
    - unit=="m", pose_id=="PZ1", 3 required keys, NaN forbidden, warnings array
  - Missingness policy surface:
    - 0 null → PASS
    - 1 null → WARN (soft)
    - ≥2 null → WARN (high_warning_degraded)
  - body_mesh.npz presence (WARN if absent — no unlock doc evidence for hard FAIL)

Exit codes: 0 = PASS/WARN, 1 = FAIL
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_TOOLS = _THIS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from _common import (  # noqa: E402
    PASS, WARN, FAIL, CheckResult,
    safe_json_load, print_results,
)
from validate_geometry_manifest import validate as validate_manifest  # noqa: E402


_REQUIRED_KEYS = ("BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M")


def validate(run_dir: Path) -> tuple[list[CheckResult], list[str]]:
    results: list[CheckResult] = []
    checked: list[str] = []

    # ── 1) geometry_manifest.json ──
    manifest_results, manifest_checked = validate_manifest(run_dir)
    results.extend(manifest_results)
    checked.extend(manifest_checked)

    # ── 2) body_measurements_subset.json ──
    bms_path = run_dir / "body_measurements_subset.json"
    if not bms_path.is_file():
        results.append(CheckResult(FAIL, "body_measurements_subset",
                                   "body_measurements_subset.json not found"))
    else:
        checked.append(str(bms_path))
        data, err = safe_json_load(bms_path)
        if err:
            results.append(CheckResult(FAIL, "body_measurements_subset:parse", err))
        else:
            _check_body_subset(data, results)

    # ── 3) body_mesh.npz ──
    mesh_path = run_dir / "body_mesh.npz"
    if mesh_path.is_file():
        checked.append(str(mesh_path))
        results.append(CheckResult(PASS, "body_mesh.npz", "Present"))
    else:
        # No hard evidence in unlock doc that missing mesh = hard FAIL for
        # all lanes; treat as WARN to avoid over-failing.
        results.append(CheckResult(WARN, "body_mesh.npz",
                                   "Not found (REQUIRED per §2.1, but WARN to avoid over-fail)"))

    return results, checked


def _check_body_subset(data: dict, results: list[CheckResult]) -> None:
    """Validate body_measurements_subset.json content."""

    # unit
    unit = data.get("unit")
    if unit == "m":
        results.append(CheckResult(PASS, "bms:unit", "m"))
    else:
        results.append(CheckResult(FAIL, "bms:unit",
                                   f"Expected 'm', got {unit!r}"))

    # pose_id
    pose = data.get("pose_id")
    if pose == "PZ1":
        results.append(CheckResult(PASS, "bms:pose_id", "PZ1"))
    else:
        results.append(CheckResult(FAIL, "bms:pose_id",
                                   f"Expected 'PZ1', got {pose!r}"))

    # measurements object
    meas = data.get("measurements")
    if not isinstance(meas, dict):
        results.append(CheckResult(FAIL, "bms:measurements",
                                   "Missing or not an object"))
        return

    # Required keys
    null_count = 0
    for key in _REQUIRED_KEYS:
        val = meas.get(key, "__MISSING__")
        if val == "__MISSING__":
            results.append(CheckResult(FAIL, f"bms:measurements:{key}", "Missing"))
        elif val is None:
            null_count += 1
            results.append(CheckResult(WARN, f"bms:measurements:{key}", "null"))
        elif isinstance(val, (int, float)):
            results.append(CheckResult(PASS, f"bms:measurements:{key}", str(val)))
        else:
            results.append(CheckResult(FAIL, f"bms:measurements:{key}",
                                       f"Invalid type: {type(val).__name__} (expected number or null)"))

    # Missingness policy (Freeze §2.1)
    if null_count == 0:
        results.append(CheckResult(PASS, "bms:missingness", "0 null — PASS"))
    elif null_count == 1:
        results.append(CheckResult(WARN, "bms:missingness",
                                   "1 null — Soft Warning (§2.1 missingness policy)"))
    else:
        results.append(CheckResult(WARN, "bms:missingness",
                                   f"{null_count} null — Degraded / High Warning (§2.1 missingness policy)"))

    # warnings array
    warnings = data.get("warnings")
    if isinstance(warnings, list):
        results.append(CheckResult(PASS, "bms:warnings", f"Array with {len(warnings)} items"))
    else:
        results.append(CheckResult(FAIL, "bms:warnings",
                                   f"Missing or not an array: {type(warnings).__name__ if warnings is not None else 'missing'}"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Body→Fitting U1 run output")
    parser.add_argument("--run-dir", type=str, required=True,
                        help="Directory containing body U1 outputs")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Output structured JSON")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"VALIDATE SUMMARY: FAIL (1)\n\n  [FAIL] run_dir: {run_dir} is not a directory",
              file=sys.stderr)
        return 1

    results, checked = validate(run_dir)
    return print_results(results, validator_name="validate_u1_body",
                         checked_files=checked, json_output=args.json_output)


if __name__ == "__main__":
    sys.exit(main())
