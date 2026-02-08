#!/usr/bin/env python3
"""
Run gen_fitting_facts_summary_stub on body_subset_ok and body_subset_missing_key samples.
Outputs to runs/smoke_test/facts_summary_stub/ and validates with tools/validate_fitting_facts_summary.py.
Usage (from repo root):
  py -3 tools/run_facts_summary_stub_suite.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "runs" / "smoke_test" / "facts_summary_stub"
STUB_SCRIPT = REPO_ROOT / "tools" / "gen_fitting_facts_summary_stub.py"
VALIDATOR = REPO_ROOT / "tools" / "validate_fitting_facts_summary.py"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    samples = [
        ("labs/samples/body_subset_ok.json", "fitting_facts_summary_ok.json"),
        ("labs/samples/body_subset_missing_key.json", "fitting_facts_summary_missing_key.json"),
    ]

    for body_subset_rel, out_name in samples:
        body_path = REPO_ROOT / body_subset_rel
        out_path = OUT_DIR / out_name
        if not body_path.is_file():
            print(f"SKIP {body_subset_rel} (not found)", file=sys.stderr)
            continue
        subprocess.run(
            [
                sys.executable,
                str(STUB_SCRIPT),
                "--body-subset",
                str(body_path),
                "--out",
                str(out_path),
            ],
            check=True,
            cwd=str(REPO_ROOT),
        )
        print(f"Generated: {out_path.relative_to(REPO_ROOT)}")

    # Validate both outputs
    results: list[tuple[Path, bool, list[str]]] = []
    for _, out_name in samples:
        out_path = OUT_DIR / out_name
        if out_path.is_file():
            if str(REPO_ROOT) not in sys.path:
                sys.path.insert(0, str(REPO_ROOT))
            from tools.validate_fitting_facts_summary import validate_facts
            ok, errors = validate_facts(out_path, REPO_ROOT)
            results.append((out_path, ok, errors))
        else:
            results.append((out_path, False, ["file not produced"]))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    for path, ok, errors in results:
        rel = path.relative_to(REPO_ROOT)
        status = "PASS" if ok else "FAIL"
        print(f"{status}\t{rel}")
        if not ok and errors:
            for e in errors[:5]:
                print(f"   - {e}")
    print("---")
    print(f"Validator: {passed}/{len(results)} PASS")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
