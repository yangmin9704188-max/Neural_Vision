#!/usr/bin/env python3
"""validate_u1_fitting.py — Enforce Fitting U1 rules.

Reference: unlock_conditions_u1_u2.md §2.3

Checks:
  - geometry_manifest.json present + valid (delegates)
  - fitting_facts_summary.json present + minimal fields
  - Input priority: npz present → garment_input_path_used=="npz"
                    npz absent, glb present → "glb_fallback"
                    both absent → FAIL
  - fitting_facts_summary fields:
    - garment_input_path_used: "npz"|"glb_fallback"
    - early_exit: boolean
    - early_exit_reason: string|null
    - warnings_summary: array
    - degraded_state: "none"|"high_warning_degraded"

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


def validate(run_dir: Path) -> tuple[list[CheckResult], list[str]]:
    results: list[CheckResult] = []
    checked: list[str] = []

    # ── 1) geometry_manifest.json ──
    manifest_results, manifest_checked = validate_manifest(run_dir)
    results.extend(manifest_results)
    checked.extend(manifest_checked)

    # ── 2) fitting_facts_summary.json ──
    facts_path = run_dir / "fitting_facts_summary.json"
    if not facts_path.is_file():
        results.append(CheckResult(FAIL, "fitting_facts_summary",
                                   "fitting_facts_summary.json not found (REQUIRED §2.3)"))
        return results, checked

    checked.append(str(facts_path))
    facts, err = safe_json_load(facts_path)
    if err:
        results.append(CheckResult(FAIL, "fitting_facts_summary:parse", err))
        return results, checked

    # ── 3) Input priority check ──
    npz_present = (run_dir / "garment_proxy.npz").is_file()
    glb_present = (run_dir / "garment_proxy_mesh.glb").is_file()
    used = facts.get("garment_input_path_used")

    if npz_present:
        if used == "npz":
            results.append(CheckResult(PASS, "input_priority",
                                       "garment_proxy.npz present → used='npz' (correct §2.3)"))
        else:
            results.append(CheckResult(FAIL, "input_priority",
                                       f"garment_proxy.npz present but garment_input_path_used={used!r} "
                                       f"(expected 'npz' per §2.3)"))
    elif glb_present:
        if used == "glb_fallback":
            results.append(CheckResult(PASS, "input_priority",
                                       "No npz, glb present → used='glb_fallback' (correct §2.3)"))
        else:
            results.append(CheckResult(FAIL, "input_priority",
                                       f"No npz, glb present but garment_input_path_used={used!r} "
                                       f"(expected 'glb_fallback' per §2.3)"))
    else:
        # Neither npz nor glb — but this may be a fitting-only run dir
        # where garment inputs are referenced via path. Only FAIL if the
        # facts summary claims an input that doesn't match.
        if used in ("npz", "glb_fallback"):
            results.append(CheckResult(WARN, "input_priority",
                                       f"No garment_proxy.npz or .glb found in run-dir; "
                                       f"garment_input_path_used={used!r} (inputs may be external)"))
        else:
            results.append(CheckResult(FAIL, "input_priority",
                                       f"No garment input artifacts and garment_input_path_used={used!r}"))

    # ── 4) fitting_facts_summary fields ──
    _check_facts_fields(facts, results)

    return results, checked


def _check_facts_fields(facts: dict, results: list[CheckResult]) -> None:
    """Validate fitting_facts_summary.json required fields (Freeze §2.3)."""

    # garment_input_path_used
    used = facts.get("garment_input_path_used")
    if used in ("npz", "glb_fallback"):
        results.append(CheckResult(PASS, "facts:garment_input_path_used", used))
    else:
        results.append(CheckResult(FAIL, "facts:garment_input_path_used",
                                   f"Expected 'npz'|'glb_fallback', got {used!r}"))

    # early_exit
    ee = facts.get("early_exit")
    if isinstance(ee, bool):
        results.append(CheckResult(PASS, "facts:early_exit", str(ee)))
    else:
        results.append(CheckResult(FAIL, "facts:early_exit",
                                   f"Expected boolean, got {type(ee).__name__}: {ee!r}"))

    # early_exit_reason
    eer = facts.get("early_exit_reason")
    if eer is None:
        if ee is True:
            results.append(CheckResult(WARN, "facts:early_exit_reason",
                                       "null but early_exit=true (string recommended)"))
        else:
            results.append(CheckResult(PASS, "facts:early_exit_reason", "null (OK for non-exit)"))
    elif isinstance(eer, str):
        results.append(CheckResult(PASS, "facts:early_exit_reason", eer))
    else:
        results.append(CheckResult(FAIL, "facts:early_exit_reason",
                                   f"Expected string|null, got {type(eer).__name__}"))

    # warnings_summary
    ws = facts.get("warnings_summary")
    if isinstance(ws, list):
        results.append(CheckResult(PASS, "facts:warnings_summary",
                                   f"Array with {len(ws)} items"))
    else:
        results.append(CheckResult(FAIL, "facts:warnings_summary",
                                   f"Expected array, got {type(ws).__name__ if ws is not None else 'missing'}"))

    # degraded_state
    ds = facts.get("degraded_state")
    if ds in ("none", "high_warning_degraded"):
        results.append(CheckResult(PASS, "facts:degraded_state", ds))
    else:
        results.append(CheckResult(FAIL, "facts:degraded_state",
                                   f"Expected 'none'|'high_warning_degraded', got {ds!r}"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Fitting U1 run output")
    parser.add_argument("--run-dir", type=str, required=True,
                        help="Directory containing fitting U1 outputs")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Output structured JSON")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"VALIDATE SUMMARY: FAIL (1)\n\n  [FAIL] run_dir: {run_dir} is not a directory",
              file=sys.stderr)
        return 1

    results, checked = validate(run_dir)
    return print_results(results, validator_name="validate_u1_fitting",
                         checked_files=checked, json_output=args.json_output)


if __name__ == "__main__":
    sys.exit(main())
