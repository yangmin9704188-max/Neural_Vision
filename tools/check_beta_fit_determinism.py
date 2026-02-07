#!/usr/bin/env python3
"""
Step4: Determinism subset check for beta_fit_v0.
Compare fit_result.json hashes for a deterministic subset (e.g. first 10 ids) between two run dirs.
Writes determinism_check.json to run_dir_1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare beta_fit subset hashes for determinism")
    parser.add_argument("--run_dir_1", type=Path, required=True, help="First run dir (e.g. full batch)")
    parser.add_argument("--run_dir_2", type=Path, required=True, help="Second run dir (subset re-run)")
    parser.add_argument("--subset_size", type=int, default=10, help="Number of prototype ids to compare (default 10)")
    args = parser.parse_args()

    run1 = args.run_dir_1.resolve()
    run2 = args.run_dir_2.resolve()
    subset_ids = [f"p{i:04d}" for i in range(args.subset_size)]
    mismatches = []
    hash_matches = True
    for p_id in subset_ids:
        f1 = run1 / "prototypes" / p_id / "fit_result.json"
        f2 = run2 / "prototypes" / p_id / "fit_result.json"
        if not f1.exists():
            mismatches.append({"prototype_id": p_id, "reason": "missing_in_run_1"})
            hash_matches = False
            continue
        if not f2.exists():
            mismatches.append({"prototype_id": p_id, "reason": "missing_in_run_2"})
            hash_matches = False
            continue
        h1 = hashlib.sha256(f1.read_bytes()).hexdigest()
        h2 = hashlib.sha256(f2.read_bytes()).hexdigest()
        if h1 != h2:
            mismatches.append({"prototype_id": p_id, "hash_1": h1[:16], "hash_2": h2[:16]})
            hash_matches = False

    out = {
        "schema_version": "determinism_check_v0",
        "run_dir_1": str(run1),
        "run_dir_2": str(run2),
        "subset_ids": subset_ids,
        "hash_matches": hash_matches,
        "mismatches": mismatches,
    }
    out_path = run1 / "determinism_check.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    from tools.utils.atomic_io import atomic_save_json
    atomic_save_json(out_path, out)
    print(f"[DONE] determinism_check.json -> {out_path}")
    print(f"  hash_matches={hash_matches} mismatches={len(mismatches)}")
    return 0 if hash_matches else 1


if __name__ == "__main__":
    sys.exit(main())
