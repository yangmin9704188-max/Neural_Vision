#!/usr/bin/env python3
"""
Run Fitting Manifest Validator on labs/samples/*.json and runs/smoke_test/manifest*.json.
Reports PASS/FAIL per file. Optionally appends one event to exports/progress/PROGRESS_LOG.jsonl.
Usage (from repo root):
  py -3 tools/run_manifest_validation_suite.py
  py -3 tools/run_manifest_validation_suite.py --progress
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import validator (same repo)
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.validate_fitting_manifest import (
    _geometry_schema_path,
    _find_manifest_in_dir,
    _load_json,
    validate_manifest,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run manifest validation suite (labs/samples + runs/smoke_test).")
    ap.add_argument("--progress", action="store_true", help="Append one event to exports/progress/PROGRESS_LOG.jsonl")
    ap.add_argument("--strict-run", action="store_true", help="Also run strict-run validation on runs/smoke_test_strict_pass and runs/smoke_test_missing_facts_summary")
    ap.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repo root (default: script parent parent)")
    args = ap.parse_args()
    repo_root = args.repo_root.resolve()

    samples_dir = repo_root / "labs" / "samples"
    smoke_dir = repo_root / "runs" / "smoke_test"
    geometry_schema = None
    gs_path = _geometry_schema_path(repo_root)
    if gs_path.is_file():
        gs, _ = _load_json(gs_path)
        if gs is not None:
            geometry_schema = gs

    candidates: list[Path] = []
    if samples_dir.is_dir():
        for f in sorted(samples_dir.glob("manifest*.json")):
            candidates.append(f)
    if smoke_dir.is_dir():
        for f in sorted(smoke_dir.glob("manifest*.json")):
            if f not in candidates:
                candidates.append(f)

    results: list[tuple[Path, bool, list[str]]] = []
    for manifest_path in candidates:
        ok, errors = validate_manifest(manifest_path, repo_root, geometry_schema, strict_run=False)
        results.append((manifest_path, ok, errors))

    # Optional strict-run tests on run-dirs
    if args.strict_run:
        strict_dirs = [
            REPO_ROOT / "runs" / "smoke_test_strict_pass",
            REPO_ROOT / "runs" / "smoke_test_missing_facts_summary",
            REPO_ROOT / "runs" / "smoke_test_missing_body_subset",
            REPO_ROOT / "runs" / "smoke_test_garment_artifacts_binding_pass",
            REPO_ROOT / "runs" / "smoke_test_garment_artifacts_binding_fail",
        ]
        for run_dir in strict_dirs:
            if not run_dir.is_dir():
                results.append((run_dir, False, [f"run-dir not found: {run_dir}"]))
                continue
            path, err = _find_manifest_in_dir(run_dir, repo_root)
            if err:
                results.append((run_dir, False, [err]))
            elif path is None:
                results.append((run_dir, False, ["no fitting manifest found in run-dir"]))
            else:
                ok, errors = validate_manifest(path, repo_root, geometry_schema, strict_run=True)
                results.append((path, ok, errors))

    # Report
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    for path, ok, errors in results:
        rel = path.relative_to(repo_root) if repo_root in path.parents else path
        status = "PASS" if ok else "FAIL"
        print(f"{status}\t{rel}")
        if not ok and errors:
            for e in errors[:5]:
                print(f"   - {e}")
            if len(errors) > 5:
                print(f"   ... and {len(errors) - 5} more")
    print("---")
    print(f"Total: {len(results)}, PASS: {passed}, FAIL: {failed}")

    if args.progress:
        progress_file = repo_root / "exports" / "progress" / "PROGRESS_LOG.jsonl"
        progress_file.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "module": "fitting",
            "step_id": "F01",
            "event": "manifest_validation_suite",
            "run_id": "N/A",
            "status": "OK" if failed == 0 else "WARN",
            "dod_done_delta": 0,
            "note": f"manifest validation suite: {passed} PASS, {failed} FAIL",
            "evidence": [f"{p.relative_to(repo_root)}: {'PASS' if ok else 'FAIL'}" for p, ok, _ in results],
            "warnings": [] if failed == 0 else [f"{p.relative_to(repo_root)}: {errs}" for p, ok, errs in results if not ok and errs],
        }
        with open(progress_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        print(f"Appended to {progress_file.relative_to(repo_root)}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
