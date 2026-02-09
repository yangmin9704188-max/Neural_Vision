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
MAX_RETRY = 2
ITER_MAX_PER_ATTEMPT = 100
CAMERA_PRESET_ID = "fixed_camera_preset_v1"
CAMERA_PARAMS = {
    "fov_deg": 45.0,
    "camera_distance_m": 2.0,
    "yaw_deg": 0.0,
    "pitch_deg": -10.0,
    "roll_deg": 0.0,
    "near_m": 0.1,
    "far_m": 10.0,
    "image_resolution_w": 1920,
    "image_resolution_h": 1080,
}
FIT_SIGNAL_WEIGHTS = {
    "score_clipping": 0.6,
    "score_fit_signal": 0.25,
    "score_smoothness": 0.15,
}


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


def _build_retry_regen_telemetry(early_exit: bool, early_exit_reason: str | None) -> dict:
    if early_exit:
        return {
            "policy_version": "regen_loop.v1",
            "max_retry": MAX_RETRY,
            "iter_max_per_attempt": ITER_MAX_PER_ATTEMPT,
            "attempt_count": 0,
            "retries_used": 0,
            "retry_budget_remaining": MAX_RETRY,
            "regen_triggered": False,
            "termination_reason": "early_exit_no_retry",
            "early_exit_reason": early_exit_reason,
            "attempts": [],
        }
    return {
        "policy_version": "regen_loop.v1",
        "max_retry": MAX_RETRY,
        "iter_max_per_attempt": ITER_MAX_PER_ATTEMPT,
        "attempt_count": 1,
        "retries_used": 0,
        "retry_budget_remaining": MAX_RETRY,
        "regen_triggered": False,
        "termination_reason": "completed",
        "early_exit_reason": None,
        "attempts": [
            {
                "attempt_index": 1,
                "trigger": "initial_run",
                "constraint_strength_scale": 1.0,
                "memory_cleared": True,
                "iter_limit": ITER_MAX_PER_ATTEMPT,
                "iter_used": 0,
                "wall_ms": 1,
                "outcome": "completed",
            }
        ],
    }


def _build_fit_signal(
    *,
    body_rel: str,
    garment_rel: str,
    garment_used: str,
    early_exit: bool,
    early_exit_reason: str | None,
    degraded_state: str,
    warnings_summary: list[str],
    retry_regen_telemetry: dict,
    created_at: str,
    version_keys: dict,
) -> dict:
    score = 0.25 if early_exit else 1.0
    score_total = (
        FIT_SIGNAL_WEIGHTS["score_clipping"] * score
        + FIT_SIGNAL_WEIGHTS["score_fit_signal"] * score
        + FIT_SIGNAL_WEIGHTS["score_smoothness"] * score
    )
    warnings = []
    for code in warnings_summary:
        warnings.append(
            {
                "code": code,
                "severity": "warning",
                "message": f"{code} observed while consuming M1 inputs",
            }
        )
    return {
        "schema_version": "fit_signal.v0",
        "created_at": created_at,
        "input_refs": {
            "body_subset_path": f"{body_rel}/body_measurements_subset.json",
            "garment_ref": f"{garment_rel}/geometry_manifest.json",
            "resolved_paths": {
                "body_subset_path_resolved": f"{body_rel}/body_measurements_subset.json",
                "garment_ref_resolved": f"{garment_rel}/geometry_manifest.json",
            },
        },
        "solver": {
            "solver_id": "fitting_m1_signal_consumer",
            "solver_version": "1.1",
            "notes": "metadata_only_solver_stub",
        },
        "timing": {"wall_ms": 1, "notes": "m1_e2e_signal_consumer"},
        "quality_scores": {
            "clipping_score": score,
            "penetration_score": score,
            "constraint_violation_score": score,
        },
        "flags": {"early_exit": early_exit, "degraded": degraded_state != "none"},
        "camera": {
            "camera_preset_id": CAMERA_PRESET_ID,
            "params": CAMERA_PARAMS,
        },
        "regen_telemetry": retry_regen_telemetry,
        "version_keys": version_keys,
        "explainability": {
            "weights": FIT_SIGNAL_WEIGHTS,
            "score_components": {
                "score_clipping": score,
                "score_fit_signal": score,
                "score_smoothness": score,
            },
            "score_total": round(score_total, 6),
            "decision_trace": {
                "garment_input_path_used": garment_used,
                "degraded_state": degraded_state,
                "early_exit_reason": early_exit_reason,
                "warning_codes": warnings_summary,
            },
        },
        "warnings": warnings,
    }


def _build_provenance(
    *,
    body_signal: dict,
    garment_signal: dict,
    body_rel: str,
    garment_rel: str,
    run_id: str,
    run_dir_rel: str,
    version_keys: dict,
    retry_regen_telemetry: dict,
    created_at: str,
) -> dict:
    cache_key_src = f"{body_rel}|{garment_rel}|{run_id}".encode("utf-8")
    return {
        "schema_version": "fitting_provenance.v1",
        "created_at": created_at,
        "solver": {
            "solver_id": "fitting_m1_signal_consumer",
            "solver_version": "1.1",
            "max_retry": MAX_RETRY,
            "iter_max_per_attempt": ITER_MAX_PER_ATTEMPT,
        },
        "camera": {
            "camera_preset_id": CAMERA_PRESET_ID,
            "params": CAMERA_PARAMS,
        },
        "cache": {
            "cache_policy_version": "cache_policy.v1",
            "cache_namespace": "fitting_m1",
            "cache_key": hashlib.sha256(cache_key_src).hexdigest(),
            "cache_hit": False,
        },
        "version_keys": version_keys,
        "inputs": {
            "body_run_id": body_signal.get("run_id"),
            "garment_run_id": garment_signal.get("run_id"),
            "body_run_dir_rel": body_rel,
            "garment_run_dir_rel": garment_rel,
        },
        "outputs": {
            "run_id": run_id,
            "run_dir_rel": run_dir_rel,
            "fit_signal_path": "fit_signal.json",
            "provenance_path": "provenance.json",
        },
        "retry_regen_telemetry": retry_regen_telemetry,
    }


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
    retry_regen_telemetry = _build_retry_regen_telemetry(early_exit, early_exit_reason)

    fingerprint_src = f"{body_rel}|{garment_rel}|{run_id}".encode("utf-8")
    version_keys = {
        "snapshot_version": "m1",
        "semantic_version": "0.1.0",
        "geometry_impl_version": "run_m1_e2e.v2",
        "dataset_version": "none",
    }
    created_at = _utc_now_z()
    geometry_manifest = {
        "schema_version": "geometry_manifest.v1",
        "module_name": "fitting",
        "contract_version": "contract.v1",
        "created_at": created_at,
        "inputs_fingerprint": hashlib.sha256(fingerprint_src).hexdigest(),
        "version_keys": version_keys,
        "artifacts": artifacts,
        "warnings": warnings,
    }
    fit_signal = _build_fit_signal(
        body_rel=body_rel,
        garment_rel=garment_rel,
        garment_used=garment_used,
        early_exit=early_exit,
        early_exit_reason=early_exit_reason,
        degraded_state=degraded_state,
        warnings_summary=warnings_summary,
        retry_regen_telemetry=retry_regen_telemetry,
        created_at=created_at,
        version_keys=version_keys,
    )
    provenance = _build_provenance(
        body_signal=body_signal,
        garment_signal=garment_signal,
        body_rel=body_rel,
        garment_rel=garment_rel,
        run_id=run_id,
        run_dir_rel=run_dir_rel,
        version_keys=version_keys,
        retry_regen_telemetry=retry_regen_telemetry,
        created_at=created_at,
    )
    artifacts.extend(["fit_signal.json", "provenance.json"])
    fitting_facts_summary = {
        "schema_version": "fitting_facts_summary.v1",
        "garment_input_path_used": garment_used,
        "early_exit": early_exit,
        "early_exit_reason": early_exit_reason,
        "warnings_summary": warnings_summary,
        "degraded_state": degraded_state,
        "camera_preset_id": CAMERA_PRESET_ID,
        "fit_signal_path": "fit_signal.json",
        "provenance_path": "provenance.json",
        "retry_regen_telemetry": retry_regen_telemetry,
    }

    _write_json(run_dir_abs / "geometry_manifest.json", geometry_manifest)
    _write_json(run_dir_abs / "fitting_facts_summary.json", fitting_facts_summary)
    _write_json(run_dir_abs / "fit_signal.json", fit_signal)
    _write_json(run_dir_abs / "provenance.json", provenance)

    fitting_signal = {
        "schema_version": "m1_signal.v1",
        "module": "fitting",
        "m_level": "M1",
        "run_id": run_id,
        "run_dir_rel": run_dir_rel,
        "created_at_utc": created_at,
        "inputs": {
            "body_run_id": body_signal.get("run_id"),
            "garment_run_id": garment_signal.get("run_id"),
            "body_run_dir_rel": body_rel,
            "garment_run_dir_rel": garment_rel,
        },
        "camera_preset_id": CAMERA_PRESET_ID,
        "outputs": {
            "fit_signal_path": "fit_signal.json",
            "provenance_path": "provenance.json",
        },
        "retry_regen_telemetry": {
            "max_retry": retry_regen_telemetry.get("max_retry"),
            "iter_max_per_attempt": retry_regen_telemetry.get("iter_max_per_attempt"),
            "attempt_count": retry_regen_telemetry.get("attempt_count"),
            "retries_used": retry_regen_telemetry.get("retries_used"),
            "regen_triggered": retry_regen_telemetry.get("regen_triggered"),
            "termination_reason": retry_regen_telemetry.get("termination_reason"),
        },
    }
    _write_json(args.fitting_signal, fitting_signal)

    print(f"RUN_DIR_REL={run_dir_rel}")
    print(f"BODY_RUN_ID={body_signal.get('run_id')}")
    print(f"GARMENT_RUN_ID={garment_signal.get('run_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
