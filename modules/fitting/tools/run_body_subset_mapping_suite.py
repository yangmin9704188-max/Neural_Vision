#!/usr/bin/env python3
"""
Run body subset normalization + stub suite.
- normalize_body_subset on alias_ok, unmapped, bad_unit
- bad_unit: expect exit 1
- alias_ok, unmapped: expect exit 0
- stub generation + fitting_facts_summary validator on alias_ok and unmapped
Usage (from repo root):
  py -3 tools/run_body_subset_mapping_suite.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "runs" / "smoke_test" / "body_subset_mapping"
NORMALIZE = REPO_ROOT / "tools" / "normalize_body_subset.py"
STUB = REPO_ROOT / "tools" / "gen_fitting_facts_summary_stub.py"
VALIDATOR = REPO_ROOT / "tools" / "validate_fitting_facts_summary.py"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0

    # Normalize: alias_ok (exit 0), unmapped (exit 0), bad_unit (exit 1)
    cases = [
        ("labs/samples/body_subset_alias_ok.json", "alias_ok.json", 0),
        ("labs/samples/body_subset_unmapped_key.json", "unmapped.json", 0),
        ("labs/samples/body_subset_bad_unit.json", "bad_unit.json", 1),
    ]
    for in_rel, out_name, expect_exit in cases:
        in_path = REPO_ROOT / in_rel
        out_path = OUT_DIR / out_name
        if not in_path.is_file():
            print(f"SKIP {in_rel} (not found)")
            continue
        r = subprocess.run(
            [sys.executable, str(NORMALIZE), "--in", str(in_path), "--out", str(out_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if r.returncode != expect_exit:
            print(f"FAIL normalize {in_rel}: expected exit {expect_exit}, got {r.returncode}")
            if r.stderr:
                print(" ", r.stderr.strip()[:200])
            failed += 1
        else:
            print(f"OK   normalize {in_rel} (exit {r.returncode})")

    # Stub: alias_ok, unmapped (both exit 0)
    stub_cases = [
        ("labs/samples/body_subset_alias_ok.json", "facts_alias_ok.json"),
        ("labs/samples/body_subset_unmapped_key.json", "facts_unmapped.json"),
    ]
    for in_rel, out_name in stub_cases:
        in_path = REPO_ROOT / in_rel
        out_path = OUT_DIR / out_name
        r = subprocess.run(
            [sys.executable, str(STUB), "--body-subset", str(in_path), "--out", str(out_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(f"FAIL stub {in_rel}: exit {r.returncode}")
            failed += 1
        else:
            print(f"OK   stub {in_rel}")

    # Validate facts outputs
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tools.validate_fitting_facts_summary import validate_facts

    for in_rel, out_name in stub_cases:
        out_path = OUT_DIR / out_name
        if out_path.is_file():
            ok, errors = validate_facts(out_path, REPO_ROOT)
            if ok:
                print(f"OK   validator {out_name}")
            else:
                print(f"FAIL validator {out_name}:", errors[:2])
                failed += 1

    print("---")
    print(f"Suite: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
