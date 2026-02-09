#!/usr/bin/env python3
"""Consume Body/Garment M1 signals, run fitting M1 E2E, and publish fitting signal."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BODY_SIGNAL = REPO_ROOT / "ops" / "signals" / "m1" / "body" / "LATEST.json"
GARMENT_SIGNAL = REPO_ROOT / "ops" / "signals" / "m1" / "garment" / "LATEST.json"
FITTING_SIGNAL = REPO_ROOT / "ops" / "signals" / "m1" / "fitting" / "LATEST.json"


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_fitting_m1")


def _sanitize_run_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return cleaned or _default_run_id()


def _is_safe_rel_path(value: str) -> bool:
    if not value or not isinstance(value, str):
        return False
    norm = value.strip().replace("\\", "/")
    if not norm:
        return False
    if norm.startswith("/") or norm.startswith("file://"):
        return False
    if re.match(r"^[A-Za-z]:", norm):
        return False
    return True


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_signal_run_dir(signal_payload: dict, label: str) -> tuple[str, Path]:
    run_dir_rel = signal_payload.get("run_dir_rel")
    if not isinstance(run_dir_rel, str) or not _is_safe_rel_path(run_dir_rel):
        raise ValueError(f"{label} signal has invalid run_dir_rel")
    run_dir_abs = (REPO_ROOT / run_dir_rel).resolve()
    if not run_dir_abs.is_dir():
        raise FileNotFoundError(f"{label} run_dir does not exist: {run_dir_rel}")
    return run_dir_rel.replace("\\", "/"), run_dir_abs


def _pick_garment_input(garment_run_dir: Path) -> tuple[str, Path | None]:
    npz = garment_run_dir / "garment_proxy.npz"
    glb = garment_run_dir / "garment_proxy_mesh.glb"
    if npz.is_file():
        return "npz", npz
    if glb.is_file():
        return "glb_fallback", glb
    return "glb_fallback", None


def _derive_early_exit(garment_signal: dict) -> tuple[bool, str | None]:
    if garment_signal.get("hard_gate") is True:
        return True, str(garment_signal.get("hard_gate_reason") or "garment_hard_gate_violation: signal")
    if garment_signal.get("early_exit") is True:
        return True, str(garment_signal.get("early_exit_reason") or "garment_hard_gate_violation: early_exit")
    if str(garment_signal.get("status", "")).upper() == "HARD_GATE":
        return True, str(garment_signal.get("reason") or "garment_hard_gate_violation: status=HARD_GATE")
    return False, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fitting M1 E2E from Body/Garment M1 signals.")
    parser.add_argument("--body-signal", type=Path, default=BODY_SIGNAL)
    parser.add_argument("--garment-signal", type=Path, default=GARMENT_SIGNAL)
    parser.add_argument("--fitting-signal", type=Path, default=FITTING_SIGNAL)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    body_signal = _load_json(args.body_signal)
    garment_signal = _load_json(args.garment_signal)

    body_rel, _body_abs = _resolve_signal_run_dir(body_signal, "body")
    garment_rel, garment_abs = _resolve_signal_run_dir(garment_signal, "garment")

    run_id = _sanitize_run_id(args.run_id or _default_run_id())
    run_dir_rel = f"data/shared_m1/fitting/{run_id}"
    run_dir_abs = (REPO_ROOT / run_dir_rel).resolve()
    run_dir_abs.mkdir(parents=True, exist_ok=True)

    garment_used, garment_src = _pick_garment_input(garment_abs)
    artifacts = ["fitting_facts_summary.json"]
    warnings: list[str] = []

    if garment_src is not None:
        artifact_name = "garment_proxy.npz" if garment_used == "npz" else "garment_proxy_mesh.glb"
        shutil.copy2(garment_src, run_dir_abs / artifact_name)
        artifacts.append(artifact_name)
    else:
        warnings.append("GARMENT_INPUT_ARTIFACT_MISSING")

    early_exit, early_exit_reason = _derive_early_exit(garment_signal)
    degraded_state = "high_warning_degraded" if early_exit else "none"
    warnings_summary = ["M1_GARMENT_HARD_GATE"] if early_exit else []

    fingerprint_src = f"{body_rel}|{garment_rel}|{run_id}".encode("utf-8")
    geometry_manifest = {
        "schema_version": "geometry_manifest.v1",
        "module_name": "fitting",
        "contract_version": "contract.v1",
        "created_at": _utc_now_z(),
        "inputs_fingerprint": hashlib.sha256(fingerprint_src).hexdigest(),
        "version_keys": {
            "snapshot_version": "m1",
            "semantic_version": "0.1.0",
            "geometry_impl_version": "run_m1_e2e.v1",
            "dataset_version": "none",
        },
        "artifacts": artifacts,
        "warnings": warnings,
    }
    fitting_facts_summary = {
        "schema_version": "fitting_facts_summary.v1",
        "garment_input_path_used": garment_used,
        "early_exit": early_exit,
        "early_exit_reason": early_exit_reason,
        "warnings_summary": warnings_summary,
        "degraded_state": degraded_state,
    }

    _write_json(run_dir_abs / "geometry_manifest.json", geometry_manifest)
    _write_json(run_dir_abs / "fitting_facts_summary.json", fitting_facts_summary)

    fitting_signal = {
        "schema_version": "m1_signal.v1",
        "module": "fitting",
        "m_level": "M1",
        "run_id": run_id,
        "run_dir_rel": run_dir_rel,
        "created_at_utc": _utc_now_z(),
        "inputs": {
            "body_run_id": body_signal.get("run_id"),
            "garment_run_id": garment_signal.get("run_id"),
            "body_run_dir_rel": body_rel,
            "garment_run_dir_rel": garment_rel,
        },
    }
    _write_json(args.fitting_signal, fitting_signal)

    print(f"RUN_DIR_REL={run_dir_rel}")
    print(f"BODY_RUN_ID={body_signal.get('run_id')}")
    print(f"GARMENT_RUN_ID={garment_signal.get('run_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
