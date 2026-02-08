#!/usr/bin/env python3
"""validate_u1_garment.py — Enforce Garment→Fitting U1 rules.

Reference: unlock_conditions_u1_u2.md §2.2

Checks:
  - geometry_manifest.json present + valid (delegates)
  - garment_proxy_meta.json present + hard gate flag logic
  - Hard Gate: if any flag true → meta+manifest required, glb/npz optional
  - Non-hard-gate: garment_proxy_mesh.glb required
  - garment_proxy.npz presence → INFO

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


_HARD_GATE_FLAGS = (
    "negative_face_area_flag",
    "self_intersection_flag",
    "invalid_face_flag",
)


def validate(run_dir: Path) -> tuple[list[CheckResult], list[str]]:
    results: list[CheckResult] = []
    checked: list[str] = []

    # ── 1) geometry_manifest.json ──
    manifest_results, manifest_checked = validate_manifest(run_dir)
    results.extend(manifest_results)
    checked.extend(manifest_checked)

    # ── 2) garment_proxy_meta.json ──
    meta_path = run_dir / "garment_proxy_meta.json"
    hard_gate = False

    if not meta_path.is_file():
        results.append(CheckResult(FAIL, "garment_proxy_meta",
                                   "garment_proxy_meta.json not found (REQUIRED §2.2)"))
    else:
        checked.append(str(meta_path))
        meta_data, err = safe_json_load(meta_path)
        if err:
            results.append(CheckResult(FAIL, "garment_proxy_meta:parse", err))
        else:
            hard_gate = _check_hard_gate(meta_data, results)

    # ── 3) Mesh / NPZ files ──
    glb_path = run_dir / "garment_proxy_mesh.glb"
    npz_path = run_dir / "garment_proxy.npz"

    if hard_gate:
        # Hard gate: glb/npz are optional (§2.2)
        if glb_path.is_file():
            checked.append(str(glb_path))
            results.append(CheckResult(PASS, "garment_proxy_mesh.glb",
                                       "Present (hard gate — optional)"))
        else:
            results.append(CheckResult(WARN, "garment_proxy_mesh.glb",
                                       "Not found (OK — hard gate, mesh optional §2.2)"))

        if npz_path.is_file():
            checked.append(str(npz_path))
            results.append(CheckResult(PASS, "garment_proxy.npz",
                                       "Present (hard gate — optional)"))
    else:
        # Non-hard-gate: glb required
        if glb_path.is_file():
            checked.append(str(glb_path))
            results.append(CheckResult(PASS, "garment_proxy_mesh.glb", "Present"))
        else:
            results.append(CheckResult(FAIL, "garment_proxy_mesh.glb",
                                       "Not found (REQUIRED when no hard gate §2.2)"))

        if npz_path.is_file():
            checked.append(str(npz_path))
            results.append(CheckResult(PASS, "garment_proxy.npz",
                                       "Present (RECOMMENDED — Fitting will prefer npz)"))

    return results, checked


def _check_hard_gate(meta: dict, results: list[CheckResult]) -> bool:
    """Check hard gate flags. Returns True if hard gate triggered."""
    triggered: list[str] = []

    for flag_name in _HARD_GATE_FLAGS:
        val = meta.get(flag_name)
        if not isinstance(val, bool):
            results.append(CheckResult(FAIL, f"meta:{flag_name}",
                                       f"Missing or not boolean: {val!r}"))
        elif val:
            triggered.append(flag_name)
            results.append(CheckResult(WARN, f"meta:{flag_name}",
                                       f"true — Hard Gate triggered"))
        else:
            results.append(CheckResult(PASS, f"meta:{flag_name}", "false"))

    if triggered:
        results.append(CheckResult(WARN, "hard_gate",
                                   f"Early Exit: {', '.join(triggered)} (§2.2)"))
        return True
    else:
        results.append(CheckResult(PASS, "hard_gate", "No hard gate flags"))
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Garment→Fitting U1 run output")
    parser.add_argument("--run-dir", type=str, required=True,
                        help="Directory containing garment U1 outputs")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Output structured JSON")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"VALIDATE SUMMARY: FAIL (1)\n\n  [FAIL] run_dir: {run_dir} is not a directory",
              file=sys.stderr)
        return 1

    results, checked = validate(run_dir)
    return print_results(results, validator_name="validate_u1_garment",
                         checked_files=checked, json_output=args.json_output)


if __name__ == "__main__":
    sys.exit(main())
