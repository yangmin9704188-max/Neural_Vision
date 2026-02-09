#!/usr/bin/env python3
"""
Generate minimal U1-valid fitting outputs from M0-only fixtures.

Outputs in one run directory:
- geometry_manifest.json
- fitting_facts_summary.json

This harness is intentionally input-light and can run without Body/Garment artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("fitting_m0_%Y%m%d_%H%M%S")


def _build_facts(mode: str, garment_input_used: str) -> dict:
    early_exit = mode == "hard_gate"
    degraded = mode == "degraded"
    return {
        "schema_version": "fitting_facts_summary.v1",
        "garment_input_path_used": garment_input_used,
        "early_exit": early_exit,
        "early_exit_reason": "garment_hard_gate_violation: m0_simulated" if early_exit else None,
        "warnings_summary": (
            ["M0_ONLY_FIXTURE_NO_UPSTREAM_INPUTS", "DEGRADED_MODE_ACTIVE"] if degraded else []
        ),
        "degraded_state": "high_warning_degraded" if degraded else "none",
    }


def _build_manifest(run_id: str) -> dict:
    fp = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    return {
        "schema_version": "geometry_manifest.v1",
        "module_name": "fitting",
        "contract_version": "contract.v1",
        "created_at": _utc_now_z(),
        "inputs_fingerprint": fp,
        "version_keys": {
            "snapshot_version": "m0",
            "semantic_version": "0.1.0",
            "geometry_impl_version": "m0_harness.v1",
            "dataset_version": "none",
        },
        "artifacts": ["fitting_facts_summary.json"],
        "warnings": ["M0_FIXTURE_ONLY"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate minimal fitting U1 artifacts from M0 fixtures.")
    ap.add_argument("--run-id", default=None, help="Run ID (default: timestamp-based)")
    ap.add_argument(
        "--mode",
        choices=("ok", "degraded", "hard_gate"),
        default="ok",
        help="ok: normal, degraded: degraded_state high, hard_gate: early_exit true",
    )
    ap.add_argument(
        "--garment-input-used",
        choices=("npz", "glb_fallback"),
        default="glb_fallback",
        help="Field value for fitting_facts_summary.garment_input_path_used",
    )
    ap.add_argument(
        "--out-root",
        default=None,
        help="Output root directory (default: modules/fitting/runs/m0)",
    )
    args = ap.parse_args()

    repo = _repo_root()
    run_id = args.run_id or _default_run_id()
    out_root = Path(args.out_root).resolve() if args.out_root else (repo / "modules" / "fitting" / "runs" / "m0")
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    facts = _build_facts(mode=args.mode, garment_input_used=args.garment_input_used)
    manifest = _build_manifest(run_id=run_id)

    facts_path = run_dir / "fitting_facts_summary.json"
    manifest_path = run_dir / "geometry_manifest.json"

    facts_path.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[M0_RUN_DIR] {run_dir}")
    print(f"[GEOMETRY_MANIFEST] {manifest_path}")
    print(f"[FITTING_FACTS_SUMMARY] {facts_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
