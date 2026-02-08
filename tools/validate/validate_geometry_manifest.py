#!/usr/bin/env python3
"""validate_geometry_manifest.py — Enforce geometry_manifest.json rules (U1 Freeze).

Reference: unlock_conditions_u1_u2.md §1.1

Checks:
  - schema_version == "geometry_manifest.v1"
  - module_name, contract_version present and valid
  - created_at: YYYY-MM-DDTHH:MM:SSZ (no milliseconds)
  - inputs_fingerprint: plausible SHA-256 hex
  - version_keys: 4 keys present, non-null, non-empty; UNSPECIFIED → WARN
  - artifacts: all relative paths (no absolute)

Exit codes: 0 = PASS/WARN, 1 = FAIL
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root or tools/validate/
_THIS = Path(__file__).resolve()
_TOOLS = _THIS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from _common import (  # noqa: E402
    PASS, WARN, FAIL, CheckResult,
    safe_json_load, is_absolute_path, is_plausible_fingerprint,
    check_created_at, print_results,
)


def validate(run_dir: Path) -> tuple[list[CheckResult], list[str]]:
    results: list[CheckResult] = []
    checked: list[str] = []

    manifest_path = run_dir / "geometry_manifest.json"
    if not manifest_path.is_file():
        results.append(CheckResult(FAIL, "manifest_exists",
                                   "geometry_manifest.json not found in run-dir"))
        return results, checked

    checked.append(str(manifest_path))
    data, err = safe_json_load(manifest_path)
    if err:
        results.append(CheckResult(FAIL, "json_parse", err))
        return results, checked

    # ── schema_version ──
    sv = data.get("schema_version")
    if sv == "geometry_manifest.v1":
        results.append(CheckResult(PASS, "schema_version", "OK"))
    else:
        results.append(CheckResult(FAIL, "schema_version",
                                   f"Expected 'geometry_manifest.v1', got {sv!r}"))

    # ── module_name ──
    mn = data.get("module_name")
    if mn in ("body", "fitting", "garment"):
        results.append(CheckResult(PASS, "module_name", f"{mn}"))
    elif mn is None:
        results.append(CheckResult(FAIL, "module_name", "Missing"))
    else:
        results.append(CheckResult(FAIL, "module_name",
                                   f"Invalid: {mn!r} (expected body|fitting|garment)"))

    # ── contract_version ──
    cv = data.get("contract_version")
    if isinstance(cv, str) and cv:
        results.append(CheckResult(PASS, "contract_version", cv))
    else:
        results.append(CheckResult(FAIL, "contract_version",
                                   f"Missing or empty: {cv!r}"))

    # ── created_at ──
    ca = data.get("created_at")
    if not isinstance(ca, str):
        results.append(CheckResult(FAIL, "created_at", f"Missing or non-string: {ca!r}"))
    else:
        sev, msg = check_created_at(ca)
        results.append(CheckResult(sev, "created_at", msg))

    # ── inputs_fingerprint ──
    fp = data.get("inputs_fingerprint")
    if not isinstance(fp, str) or not fp:
        results.append(CheckResult(FAIL, "inputs_fingerprint",
                                   f"Missing or empty: {fp!r}"))
    elif is_plausible_fingerprint(fp):
        results.append(CheckResult(PASS, "inputs_fingerprint", "Plausible SHA-256 format"))
    else:
        results.append(CheckResult(WARN, "inputs_fingerprint",
                                   f"Not a recognised SHA-256 hex pattern: {fp[:40]}..."))

    # ── version_keys ──
    vk = data.get("version_keys")
    if not isinstance(vk, dict):
        results.append(CheckResult(FAIL, "version_keys", "Missing or not an object"))
    else:
        for key in ("snapshot_version", "semantic_version",
                    "geometry_impl_version", "dataset_version"):
            val = vk.get(key)
            if val is None or val == "":
                results.append(CheckResult(FAIL, f"version_keys:{key}",
                                           "null or empty (Freeze §1.1.4)"))
            elif val == "UNSPECIFIED":
                results.append(CheckResult(WARN, f"version_keys:{key}",
                                           f"VERSION_KEY_UNSPECIFIED:{key}"))
            else:
                results.append(CheckResult(PASS, f"version_keys:{key}", val))

    # ── artifacts ──
    arts = data.get("artifacts")
    if not isinstance(arts, list):
        results.append(CheckResult(FAIL, "artifacts", "Missing or not an array"))
    else:
        abs_found = []
        for i, p in enumerate(arts):
            if isinstance(p, str) and is_absolute_path(p):
                abs_found.append(p)
        if abs_found:
            results.append(CheckResult(FAIL, "artifacts:absolute_path",
                                       f"Absolute path(s) found (Freeze §1.1.5): {abs_found}"))
        else:
            results.append(CheckResult(PASS, "artifacts",
                                       f"{len(arts)} path(s), all relative"))

    return results, checked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate geometry_manifest.json (U1 Freeze rules)")
    parser.add_argument("--run-dir", type=str, required=True,
                        help="Directory containing geometry_manifest.json")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Output structured JSON")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"VALIDATE SUMMARY: FAIL (1)\n\n  [FAIL] run_dir: {run_dir} is not a directory",
              file=sys.stderr)
        return 1

    results, checked = validate(run_dir)
    return print_results(results, validator_name="validate_geometry_manifest",
                         checked_files=checked, json_output=args.json_output)


if __name__ == "__main__":
    sys.exit(main())
