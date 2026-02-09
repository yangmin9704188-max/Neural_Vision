#!/usr/bin/env python3
"""Publish Body M1 artifacts into data/shared_m1/body/<run_id>."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE_REL = Path("tests/fixtures/u2_smokes/smoke1_ok/body_run")
MANIFEST_NAME = "geometry_manifest.json"
REQUIRED_FILES = ("body_measurements_subset.json",)
OPTIONAL_FILES = ("body_mesh.npz",)
RUNTIME_TELEMETRY_NAME = "body_runtime_telemetry.json"
CACHE_POLICY_NAME = "body_cache_policy.json"
QUALITY_GATE_NAME = "body_quality_gate.json"


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_body_m1")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _coerce_non_empty(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        fval = float(value)
    except (TypeError, ValueError):
        return default
    if fval < 0:
        return default
    return fval


def _compute_inputs_fingerprint(run_dir: Path, copied_files: list[str]) -> str:
    hasher = hashlib.sha256()
    for name in sorted(copied_files):
        p = run_dir / name
        hasher.update(name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(p.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _resolve_source_dir(args: argparse.Namespace) -> Path:
    if args.source_run_dir:
        return Path(args.source_run_dir).resolve()
    if args.from_fixture or not args.source_run_dir:
        return (REPO_ROOT / DEFAULT_FIXTURE_REL).resolve()
    raise ValueError("unable to resolve source run directory")


def _copy_minset(source_dir: Path, out_dir: Path) -> list[str]:
    copied: list[str] = []
    for name in REQUIRED_FILES:
        src = source_dir / name
        if not src.is_file():
            raise FileNotFoundError(f"required file missing in source: {src}")
        shutil.copy2(src, out_dir / name)
        copied.append(name)

    for name in OPTIONAL_FILES:
        src = source_dir / name
        if src.is_file():
            shutil.copy2(src, out_dir / name)
            copied.append(name)
    return copied


def _build_manifest(
    source_dir: Path,
    out_dir: Path,
    run_dir_rel: str,
    copied_files: list[str],
) -> dict[str, Any]:
    source_manifest_path = source_dir / MANIFEST_NAME
    source_manifest: dict[str, Any] = {}
    if source_manifest_path.is_file():
        source_manifest = _load_json(source_manifest_path)

    source_version_keys = source_manifest.get("version_keys")
    if not isinstance(source_version_keys, dict):
        source_version_keys = {}

    artifacts = [f"{run_dir_rel}/body_measurements_subset.json"]
    if "body_mesh.npz" in copied_files:
        artifacts.insert(0, f"{run_dir_rel}/body_mesh.npz")

    manifest = {
        "schema_version": "geometry_manifest.v1",
        "module_name": "body",
        "contract_version": _coerce_non_empty(source_manifest.get("contract_version"), "v1.1"),
        "created_at": _utc_now_z(),
        "inputs_fingerprint": _compute_inputs_fingerprint(out_dir, copied_files),
        "version_keys": {
            "snapshot_version": _coerce_non_empty(source_version_keys.get("snapshot_version"), "UNSPECIFIED"),
            "semantic_version": _coerce_non_empty(source_version_keys.get("semantic_version"), "UNSPECIFIED"),
            "geometry_impl_version": _coerce_non_empty(source_version_keys.get("geometry_impl_version"), "UNSPECIFIED"),
            "dataset_version": _coerce_non_empty(source_version_keys.get("dataset_version"), "UNSPECIFIED"),
        },
        "artifacts": artifacts,
        "warnings": source_manifest.get("warnings") if isinstance(source_manifest.get("warnings"), list) else [],
    }
    return manifest


def _load_prev_version_keys() -> tuple[dict[str, str] | None, str | None]:
    signal_path = REPO_ROOT / "ops" / "signals" / "m1" / "body" / "LATEST.json"
    if not signal_path.is_file():
        return None, "previous signal not found"

    try:
        signal = _load_json(signal_path)
    except Exception as exc:
        return None, f"failed to read previous signal: {exc}"

    run_dir_rel = signal.get("run_dir_rel")
    if not isinstance(run_dir_rel, str) or not run_dir_rel.strip():
        return None, "previous signal has no run_dir_rel"

    prev_manifest_path = (REPO_ROOT / run_dir_rel).resolve() / MANIFEST_NAME
    if not prev_manifest_path.is_file():
        return None, f"previous manifest not found: {prev_manifest_path}"

    try:
        prev_manifest = _load_json(prev_manifest_path)
    except Exception as exc:
        return None, f"failed to read previous manifest: {exc}"

    prev_keys = prev_manifest.get("version_keys")
    if not isinstance(prev_keys, dict):
        return None, "previous manifest has no version_keys object"

    normalized: dict[str, str] = {}
    for key in ("snapshot_version", "semantic_version", "geometry_impl_version", "dataset_version"):
        normalized[key] = _coerce_non_empty(prev_keys.get(key), "UNSPECIFIED")
    return normalized, None


def _write_runtime_telemetry(
    out_dir: Path,
    run_id: str,
    run_dir_rel: str,
    args: argparse.Namespace,
    elapsed_s: float,
) -> tuple[str, list[str]]:
    latency_s = _coerce_float(args.latency_s, elapsed_s)
    gpu_time_s = _coerce_float(args.gpu_time_s, 0.0)
    vram_peak_gb = _coerce_float(args.vram_peak_gb, 0.0)

    latency_budget = _coerce_float(args.latency_budget_s, 2.0)
    gpu_budget = _coerce_float(args.gpu_budget_s, 0.5)
    vram_budget = _coerce_float(args.vram_budget_gb, 6.0)

    violations: list[str] = []
    if latency_s > latency_budget:
        violations.append("LATENCY_BUDGET_EXCEEDED")
    if gpu_time_s > gpu_budget:
        violations.append("GPU_TIME_BUDGET_EXCEEDED")
    if vram_peak_gb > vram_budget:
        violations.append("VRAM_BUDGET_EXCEEDED")

    warnings: list[str] = []
    if args.gpu_time_s is None:
        warnings.append("GPU_TIME_NOT_OBSERVED_DEFAULTED")
    if args.vram_peak_gb is None:
        warnings.append("VRAM_PEAK_NOT_OBSERVED_DEFAULTED")
    if args.prototype_id == "UNSPECIFIED":
        warnings.append("PROTOTYPE_ID_UNSPECIFIED")
    if args.height_quant_2cm == "UNSPECIFIED":
        warnings.append("HEIGHT_QUANT_2CM_UNSPECIFIED")

    payload = {
        "schema_version": "body_runtime_telemetry.v1",
        "module_name": "body",
        "run_id": run_id,
        "run_dir_rel": run_dir_rel,
        "cache_key_fields": {
            "prototype_id": args.prototype_id,
            "height_quant_2cm": args.height_quant_2cm,
            "pose_id": args.pose_id,
            "cache_hit": bool(args.cache_hit),
        },
        "telemetry": {
            "latency_s": round(latency_s, 6),
            "gpu_time_s": round(gpu_time_s, 6),
            "vram_peak_gb": round(vram_peak_gb, 6),
        },
        "budgets": {
            "latency_s_p95_max": latency_budget,
            "gpu_time_s_max": gpu_budget,
            "vram_peak_gb_max": vram_budget,
        },
        "budget_status": {
            "within_budget": len(violations) == 0,
            "violations": violations,
            "violation_policy": {
                "on_violation": [
                    "record warning code BODY_BUDGET_EXCEEDED",
                    "set exposure_state=degraded",
                    "require review before promotion",
                ],
                "reference": "ssot/Body_Module_Plan_v1.md",
            },
        },
        "warnings": warnings,
    }
    _write_json(out_dir / RUNTIME_TELEMETRY_NAME, payload)
    return RUNTIME_TELEMETRY_NAME, violations


def _write_cache_policy(
    out_dir: Path,
    run_id: str,
    run_dir_rel: str,
    args: argparse.Namespace,
    manifest: dict[str, Any],
) -> str:
    current_keys = manifest.get("version_keys")
    if not isinstance(current_keys, dict):
        current_keys = {}
    normalized_current = {
        "snapshot_version": _coerce_non_empty(current_keys.get("snapshot_version"), "UNSPECIFIED"),
        "semantic_version": _coerce_non_empty(current_keys.get("semantic_version"), "UNSPECIFIED"),
        "geometry_impl_version": _coerce_non_empty(current_keys.get("geometry_impl_version"), "UNSPECIFIED"),
        "dataset_version": _coerce_non_empty(current_keys.get("dataset_version"), "UNSPECIFIED"),
    }
    version_keys_null_free = all(v is not None and str(v).strip() != "" for v in normalized_current.values())

    prev_keys, prev_warning = _load_prev_version_keys()
    changed: list[str] = []
    if isinstance(prev_keys, dict):
        for key in normalized_current:
            if normalized_current[key] != _coerce_non_empty(prev_keys.get(key), "UNSPECIFIED"):
                changed.append(key)
    expected_invalidate = len(changed) > 0

    warnings: list[str] = []
    if prev_warning:
        warnings.append(prev_warning)
    if not version_keys_null_free:
        warnings.append("VERSION_KEYS_NULL_OR_EMPTY")

    payload = {
        "schema_version": "body_cache_policy.v1",
        "module_name": "body",
        "run_id": run_id,
        "run_dir_rel": run_dir_rel,
        "cache_key_schema": ["prototype_id", "height_quant_2cm", "pose_id"],
        "cache_key_example": f"prototype_id={args.prototype_id}|height_quant_2cm={args.height_quant_2cm}|pose_id={args.pose_id}",
        "version_key_invalidation": {
            "trigger_keys": ["snapshot_version", "semantic_version", "geometry_impl_version", "dataset_version"],
            "previous_version_keys": prev_keys,
            "current_version_keys": normalized_current,
            "changed_keys": changed,
            "invalidate_cache": expected_invalidate,
        },
        "validation": {
            "version_keys_null_free": version_keys_null_free,
            "version_keys_traceability": "geometry_manifest.version_keys",
            "cache_invalidation_semantics_validated": expected_invalidate == (len(changed) > 0),
        },
        "warnings": warnings,
    }
    _write_json(out_dir / CACHE_POLICY_NAME, payload)
    return CACHE_POLICY_NAME


def _write_quality_gate(
    out_dir: Path,
    run_id: str,
    run_dir_rel: str,
    args: argparse.Namespace,
    violations: list[str],
) -> tuple[str, str, list[str]]:
    score = _coerce_float(args.calibration_quality_score, 0.0)
    threshold = _coerce_float(args.quality_gate_threshold, 70.0)

    if score < threshold:
        exposure_state = "blocked"
        decision_code = "CALIBRATION_SCORE_BELOW_THRESHOLD"
    elif violations:
        exposure_state = "degraded"
        decision_code = "BUDGET_VIOLATION_DEGRADED"
    else:
        exposure_state = "promotable"
        decision_code = "QUALITY_GATE_PASSED"

    warnings: list[str] = []
    if exposure_state == "blocked":
        warnings.append("BODY_QUALITY_GATE_BLOCKED")
    if exposure_state == "degraded":
        warnings.append("BODY_QUALITY_GATE_DEGRADED")

    payload = {
        "schema_version": "body_quality_gate.v1",
        "module_name": "body",
        "run_id": run_id,
        "run_dir_rel": run_dir_rel,
        "calibration_quality_score": score,
        "quality_gate_threshold": threshold,
        "budget_violations": list(violations),
        "exposure_state": exposure_state,
        "decision_code": decision_code,
        "deterministic_policy": {
            "if_score_lt_threshold": "blocked",
            "if_score_ge_threshold_and_budget_violation": "degraded",
            "if_score_ge_threshold_and_no_budget_violation": "promotable",
        },
        "warnings": warnings,
    }
    _write_json(out_dir / QUALITY_GATE_NAME, payload)
    return QUALITY_GATE_NAME, exposure_state, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish Body M1 artifacts")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--source-run-dir", type=str, help="Source run directory containing Body U1 outputs")
    group.add_argument("--from-fixture", action="store_true", help="Use tests fixture as source run directory")
    parser.add_argument("--run-id", type=str, help="Run ID for data/shared_m1/body/<run_id>")
    parser.add_argument("--prototype-id", type=str, default="UNSPECIFIED", help="Body prototype id for cache key")
    parser.add_argument("--height-quant-2cm", type=str, default="UNSPECIFIED", help="Height quantized to 2cm bucket")
    parser.add_argument("--pose-id", type=str, default="PZ1", help="Pose id for cache key (default: PZ1)")
    parser.add_argument("--cache-hit", action="store_true", help="Mark cache hit for telemetry")
    parser.add_argument("--latency-s", type=float, default=None, help="Override measured latency seconds")
    parser.add_argument("--gpu-time-s", type=float, default=None, help="GPU compute seconds (optional)")
    parser.add_argument("--vram-peak-gb", type=float, default=None, help="VRAM peak GB (optional)")
    parser.add_argument("--latency-budget-s", type=float, default=2.0, help="Latency budget (seconds)")
    parser.add_argument("--gpu-budget-s", type=float, default=0.5, help="GPU time budget (seconds)")
    parser.add_argument("--vram-budget-gb", type=float, default=6.0, help="VRAM peak budget (GB)")
    parser.add_argument("--calibration-quality-score", type=float, default=85.0, help="Body calibration quality score [0,100]")
    parser.add_argument("--quality-gate-threshold", type=float, default=70.0, help="Quality gate threshold (default: 70)")
    args = parser.parse_args(argv)

    source_dir = _resolve_source_dir(args)
    if not source_dir.is_dir():
        print(f"source run dir not found: {source_dir}", file=sys.stderr)
        return 2

    run_id = args.run_id or _default_run_id()
    run_dir_rel = f"data/shared_m1/body/{run_id}"
    out_dir = (REPO_ROOT / run_dir_rel).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        started = time.perf_counter()
        copied = _copy_minset(source_dir, out_dir)
        manifest = _build_manifest(source_dir, out_dir, run_dir_rel, copied)
        telemetry_name, violations = _write_runtime_telemetry(
            out_dir=out_dir,
            run_id=run_id,
            run_dir_rel=run_dir_rel,
            args=args,
            elapsed_s=time.perf_counter() - started,
        )
        cache_name = _write_cache_policy(
            out_dir=out_dir,
            run_id=run_id,
            run_dir_rel=run_dir_rel,
            args=args,
            manifest=manifest,
        )
        gate_name, exposure_state, gate_warnings = _write_quality_gate(
            out_dir=out_dir,
            run_id=run_id,
            run_dir_rel=run_dir_rel,
            args=args,
            violations=violations,
        )
        artifacts = list(manifest.get("artifacts", []))
        artifacts.extend(
            [
                f"{run_dir_rel}/{telemetry_name}",
                f"{run_dir_rel}/{cache_name}",
                f"{run_dir_rel}/{gate_name}",
            ]
        )
        manifest["artifacts"] = artifacts
        manifest["quality_gate"] = {
            "calibration_quality_score": _coerce_float(args.calibration_quality_score, 0.0),
            "threshold": _coerce_float(args.quality_gate_threshold, 70.0),
            "exposure_state": exposure_state,
        }
        if violations:
            warnings = manifest.get("warnings")
            if not isinstance(warnings, list):
                warnings = []
            warnings = list(warnings)
            if "BODY_BUDGET_EXCEEDED" not in warnings:
                warnings.append("BODY_BUDGET_EXCEEDED")
            manifest["warnings"] = warnings
        if gate_warnings:
            warnings = manifest.get("warnings")
            if not isinstance(warnings, list):
                warnings = []
            warnings = list(warnings)
            for code in gate_warnings:
                if code not in warnings:
                    warnings.append(code)
            manifest["warnings"] = warnings
        _write_json(out_dir / MANIFEST_NAME, manifest)
    except Exception as exc:
        print(f"publish failed: {exc}", file=sys.stderr)
        return 1

    required_out = (MANIFEST_NAME, "body_measurements_subset.json")
    for name in required_out:
        if not (out_dir / name).is_file():
            print(f"publish failed: required output missing: {name}", file=sys.stderr)
            return 1

    print(f"RUN_DIR_REL={run_dir_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

