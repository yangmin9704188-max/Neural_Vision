#!/usr/bin/env python3
"""
Run fitting_facts_summary validator on labs/samples/fitting_facts_summary_v1_*.json.
Reports PASS/FAIL per file. Usage (from repo root):
  py -3 tools/run_facts_summary_validation_suite.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.validate_fitting_facts_summary import validate_facts


def main() -> int:
    samples = [
        REPO_ROOT / "labs" / "samples" / "fitting_facts_summary_v1_pass.json",
        REPO_ROOT / "labs" / "samples" / "fitting_facts_summary_v1_fail.json",
    ]
    results: list[tuple[Path, bool, list[str]]] = []
    for path in samples:
        if path.is_file():
            ok, errors = validate_facts(path, REPO_ROOT)
            results.append((path, ok, errors))
        else:
            results.append((path, False, [f"file not found: {path}"]))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    for path, ok, errors in results:
        rel = path.relative_to(REPO_ROOT) if REPO_ROOT in path.parents else path
        status = "PASS" if ok else "FAIL"
        print(f"{status}\t{rel}")
        if not ok and errors:
            for e in errors[:5]:
                print(f"   - {e}")
            if len(errors) > 5:
                print(f"   ... and {len(errors) - 5} more")
    print("---")
    print(f"Total: {len(results)}, PASS: {passed}, FAIL: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
