#!/usr/bin/env python3
"""Backfill existing body_measurements_subset.json to M0 format (schema v1, measurements with BUST/WAIST/HIP)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
M0_KEYS = ["BUST", "WAIST", "HIP"]
U1_TO_M0 = {"BUST_CIRC_M": "BUST", "WAIST_CIRC_M": "WAIST", "HIP_CIRC_M": "HIP"}


def ensure_m0(path: Path) -> bool:
    """Ensure file has M0 fields. Returns True if updated."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False

    measurements = {}
    missing_keys = []
    cases = data.get("cases") or []
    for m0_k in M0_KEYS:
        u1_k = next((u for u, m in U1_TO_M0.items() if m == m0_k), None)
        val = None
        if cases and u1_k:
            first = cases[0] if isinstance(cases[0], dict) else {}
            v = first.get(u1_k)
            if v is not None and isinstance(v, (int, float)):
                try:
                    fv = float(v)
                    if fv == fv:  # not NaN
                        val = fv
                except (TypeError, ValueError):
                    pass
        measurements[m0_k] = val
        if val is None:
            missing_keys.append(m0_k)

    if data.get("schema_version") == "body_measurements_subset.v1" and "measurements" in data:
        existing_m = data.get("measurements") or {}
        if all(k in existing_m for k in M0_KEYS):
            return False

    data["schema_version"] = "body_measurements_subset.v1"
    data["unit"] = "m"
    data["measurements"] = measurements
    data["missing_keys"] = missing_keys
    for k, v in measurements.items():
        data[k] = v

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def main() -> int:
    runs = REPO_ROOT / "exports" / "runs"
    if not runs.exists():
        print("exports/runs not found")
        return 0
    updated = 0
    for p in runs.rglob("body_measurements_subset.json"):
        if ensure_m0(p):
            print(f"Updated: {p.relative_to(REPO_ROOT)}")
            updated += 1
    print(f"Backfill done: {updated} files updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
