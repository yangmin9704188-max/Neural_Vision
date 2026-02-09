#!/usr/bin/env python3
"""Publish Garment M1 run and apply G40/G41 contract tracking.

G40_M1_INTAKE_GATE_TRACK
- records intake/gatekeeper metrics
- reflects foreign_object_result into garment_proxy_meta.json

G41_M1_PROXY_LATENT_TRACK
- aligns proxy/meta + fit_hint + latent/meta contracts
- applies thickness default policy with warning/provenance
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


REQUIRED_FILES = ("geometry_manifest.json", "garment_proxy_meta.json")
OPTIONAL_FILES = ("garment_proxy_mesh.glb", "garment_proxy.npz")
TRACKING_FILES = ("intake_gatekeeper_metrics.json", "fit_hint.json", "latent_meta.json")
DEFAULT_SHARED_M1_ROOT = Path(r"C:/Users/caino/Desktop/NV_shared_data/shared_m1")
SIGNAL_REL_PATH = Path("ops") / "signals" / "m1" / "garment" / "LATEST.json"
M1_CONTRACT_VERSION = "garment.contract.m1.v1"
THICKNESS_DEFAULT_M = 0.002
STRETCH_DEFAULT = "balanced"

MATERIAL_POLICY = {
    "cotton": {"stretch_class": "low", "thickness_garment_m": 0.0012},
    "denim": {"stretch_class": "low", "thickness_garment_m": 0.0028},
    "wool": {"stretch_class": "medium", "thickness_garment_m": 0.0024},
    "polyester": {"stretch_class": "medium", "thickness_garment_m": 0.0016},
    "spandex": {"stretch_class": "high", "thickness_garment_m": 0.0010},
}


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        has_git = (candidate / ".git").exists()
        has_layout = (candidate / "modules").exists() and (candidate / "ops").exists()
        if has_git or has_layout:
            return candidate
    raise RuntimeError("Unable to locate repo root from current path")


def _to_repo_rel_or_abs(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return str(path.resolve())


def _resolve_shared_m1_root(repo_root: Path) -> Path:
    env = os.getenv("NV_SHARED_M1_ROOT", "").strip()
    if not env:
        return DEFAULT_SHARED_M1_ROOT
    env_path = Path(env)
    if env_path.is_absolute():
        return env_path
    return (repo_root / env_path).resolve()


def _now_iso_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _append_warning_once(meta: dict, code: str) -> None:
    warnings = meta.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
    if code not in warnings:
        warnings.append(code)
    meta["warnings"] = warnings


def _extract_hard_gate_flags(meta: dict) -> dict[str, bool]:
    flags_obj = meta.get("flags", {})
    if not isinstance(flags_obj, dict):
        flags_obj = {}
    out = {}
    for key in ("negative_face_area_flag", "self_intersection_flag", "invalid_face_flag"):
        top = meta.get(key)
        nested = flags_obj.get(key)
        value = top if isinstance(top, bool) else nested if isinstance(nested, bool) else False
        out[key] = bool(value)
    meta.update(out)
    meta["flags"] = dict(out)
    return out


def _normalize_foreign_object_result(meta: dict) -> dict:
    existing = meta.get("foreign_object_result")
    if not isinstance(existing, dict):
        existing = {}
    detected = bool(existing.get("detected", False))
    try:
        score = float(existing.get("score", 0.0))
    except Exception:
        score = 0.0
    score = max(0.0, min(1.0, score))
    label = str(existing.get("label", "none")) if existing.get("label") is not None else "none"
    return {
        "detected": detected,
        "score": score,
        "label": label,
        "status": "blocked" if detected else "clear",
        "source": "intake_gatekeeper.v1",
    }


def _derive_material_profile(meta: dict) -> dict:
    token = meta.get("material_token")
    if not isinstance(token, str) or not token.strip():
        material = meta.get("material")
        if isinstance(material, dict) and isinstance(material.get("material_token"), str):
            token = material.get("material_token")

    token_norm = token.strip().lower() if isinstance(token, str) and token.strip() else ""
    existing_thickness = meta.get("thickness_garment_m")
    existing_stretch = meta.get("stretch_class")
    if isinstance(existing_thickness, (int, float)) and float(existing_thickness) > 0 and isinstance(existing_stretch, str):
        return {
            "material_token": token_norm or "UNSPECIFIED",
            "stretch_class": existing_stretch.strip() or STRETCH_DEFAULT,
            "thickness_garment_m": float(existing_thickness),
            "default_applied": False,
            "default_reason": "",
            "source": "proxy_meta_existing",
        }

    policy = MATERIAL_POLICY.get(token_norm)
    if policy:
        return {
            "material_token": token_norm,
            "stretch_class": policy["stretch_class"],
            "thickness_garment_m": float(policy["thickness_garment_m"]),
            "default_applied": False,
            "default_reason": "",
            "source": "material_token_policy",
        }

    reason = "material_token_missing" if not token_norm else f"material_token_unknown:{token_norm}"
    return {
        "material_token": token_norm or "UNSPECIFIED",
        "stretch_class": STRETCH_DEFAULT,
        "thickness_garment_m": THICKNESS_DEFAULT_M,
        "default_applied": True,
        "default_reason": reason,
        "source": "default_policy",
    }


def _apply_g40_intake_gate_track(
    repo_root: Path,
    run_dir: Path,
    run_id: str,
    source_dir: Path,
) -> dict:
    meta_path = run_dir / "garment_proxy_meta.json"
    meta = _read_json(meta_path)
    flags = _extract_hard_gate_flags(meta)
    foreign_object_result = _normalize_foreign_object_result(meta)

    required_presence = {name: (run_dir / name).is_file() for name in REQUIRED_FILES}
    optional_presence = {name: (run_dir / name).is_file() for name in OPTIONAL_FILES}
    metrics = {
        "schema_version": "garment_intake_gatekeeper.v1",
        "module": "garment",
        "step_id": "G40_M1_INTAKE_GATE_TRACK",
        "m_level": "M1",
        "status": "OK",
        "contract_version": M1_CONTRACT_VERSION,
        "tracked_at": _now_iso_local(),
        "run_id": run_id,
        "run_dir_rel": _to_repo_rel_or_abs(run_dir, repo_root),
        "source_run_dir_rel": _to_repo_rel_or_abs(source_dir, repo_root),
        "required_presence": required_presence,
        "optional_presence": optional_presence,
        "hard_gate_flags": flags,
        "hard_gate_triggered": any(flags.values()),
        "foreign_object_result": foreign_object_result,
        "metrics": {
            "required_ok_count": sum(1 for v in required_presence.values() if v),
            "required_total": len(REQUIRED_FILES),
            "optional_present_count": sum(1 for v in optional_presence.values() if v),
            "missing_required_count": sum(1 for v in required_presence.values() if not v),
        },
    }

    if foreign_object_result["detected"]:
        _append_warning_once(meta, "FOREIGN_OBJECT_DETECTED")
        metrics["status"] = "WARN"

    meta["foreign_object_result"] = foreign_object_result
    meta["intake_gatekeeper_metrics_path"] = "intake_gatekeeper_metrics.json"
    meta["m_level"] = "M1"
    meta["contract_version"] = M1_CONTRACT_VERSION
    _write_json(meta_path, meta)
    _write_json(run_dir / "intake_gatekeeper_metrics.json", metrics)
    return metrics


def _apply_g41_proxy_latent_track(
    repo_root: Path,
    run_dir: Path,
    run_id: str,
) -> dict:
    meta_path = run_dir / "garment_proxy_meta.json"
    meta = _read_json(meta_path)
    profile = _derive_material_profile(meta)

    fit_hint_warnings = []
    if profile["default_applied"]:
        fit_hint_warnings.append("THICKNESS_DEFAULTED")
        _append_warning_once(meta, "THICKNESS_DEFAULTED")
        if profile["default_reason"]:
            _append_warning_once(meta, f"THICKNESS_DEFAULTED_REASON:{profile['default_reason']}")

    fit_hint = {
        "schema_version": "garment_fit_hint.v1",
        "module": "garment",
        "m_level": "M1",
        "contract_version": M1_CONTRACT_VERSION,
        "run_id": run_id,
        "run_dir_rel": _to_repo_rel_or_abs(run_dir, repo_root),
        "stretch_class": profile["stretch_class"],
        "thickness_garment_m": float(profile["thickness_garment_m"]),
        "thickness_policy": {
            "policy_id": "material_token_map_v1",
            "source": profile["source"],
            "default_applied": profile["default_applied"],
            "default_reason": profile["default_reason"],
            "material_token": profile["material_token"],
        },
        "provenance": {
            "generated_by": "modules/garment/tools/publish_m1.py",
            "generated_at": _now_iso_local(),
            "proxy_meta_path": "garment_proxy_meta.json",
        },
        "warnings": fit_hint_warnings,
    }

    latent_dir = run_dir / "garment_latent_asset"
    latent_dir.mkdir(parents=True, exist_ok=True)
    latent_meta = {
        "schema_version": "garment_latent_meta.v1",
        "module": "garment",
        "m_level": "M1",
        "contract_version": M1_CONTRACT_VERSION,
        "run_id": run_id,
        "fit_hint_path": "fit_hint.json",
        "proxy_meta_path": "garment_proxy_meta.json",
        "latent_asset_dir": "garment_latent_asset",
        "needs_reprocessing": False,
        "provenance": {
            "generated_by": "modules/garment/tools/publish_m1.py",
            "generated_at": _now_iso_local(),
        },
        "warnings": [],
    }

    meta["fit_hint_path"] = "fit_hint.json"
    meta["latent_meta_path"] = "latent_meta.json"
    meta["stretch_class"] = fit_hint["stretch_class"]
    meta["thickness_garment_m"] = fit_hint["thickness_garment_m"]
    meta["thickness_policy"] = fit_hint["thickness_policy"]
    provenance = meta.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    provenance["thickness_policy"] = {
        "default_applied": profile["default_applied"],
        "default_reason": profile["default_reason"],
        "material_token": profile["material_token"],
    }
    meta["provenance"] = provenance
    meta["proxy_fit_latent_alignment"] = {
        "schema_version": "garment_proxy_fit_latent_alignment.v1",
        "contract_version": M1_CONTRACT_VERSION,
        "fit_hint_path": "fit_hint.json",
        "latent_meta_path": "latent_meta.json",
    }

    _write_json(meta_path, meta)
    _write_json(run_dir / "fit_hint.json", fit_hint)
    _write_json(run_dir / "latent_meta.json", latent_meta)
    return {
        "default_applied": profile["default_applied"],
        "default_reason": profile["default_reason"],
        "fit_hint_path": "fit_hint.json",
        "latent_meta_path": "latent_meta.json",
    }


def _update_geometry_manifest(run_dir: Path, extra_artifacts: list[str]) -> None:
    manifest_path = run_dir / "geometry_manifest.json"
    manifest = _read_json(manifest_path)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = []
    merged = []
    for item in artifacts + extra_artifacts:
        if isinstance(item, str) and item and item not in merged:
            merged.append(item)
    manifest["artifacts"] = merged
    manifest["contract_version"] = M1_CONTRACT_VERSION
    manifest["m_level"] = "M1"
    manifest["fit_hint_path"] = "fit_hint.json"
    manifest["latent_meta_path"] = "latent_meta.json"
    manifest["intake_gatekeeper_metrics_path"] = "intake_gatekeeper_metrics.json"
    _write_json(manifest_path, manifest)


def _write_latest_signal(
    repo_root: Path,
    run_id: str,
    source_dir: Path,
    run_dir: Path,
) -> None:
    run_dir_rel = os.path.relpath(str(run_dir.resolve()), str(repo_root.resolve()))
    source_dir_rel = os.path.relpath(str(source_dir.resolve()), str(repo_root.resolve()))
    optional_present = []
    for name in OPTIONAL_FILES + TRACKING_FILES:
        if (run_dir / name).exists():
            optional_present.append(name)

    signal = {
        "schema_version": "m1_latest_signal.v1",
        "module": "garment",
        "m_level": "M1",
        "status": "OK",
        "updated_at": _now_iso_local(),
        "run_id": run_id,
        "run_dir_rel": run_dir_rel,
        "source_run_dir_rel": source_dir_rel,
        "required_files": list(REQUIRED_FILES),
        "optional_files_present": optional_present,
    }
    _write_json(repo_root / SIGNAL_REL_PATH, signal)


def _candidate_run_dirs(repo_root: Path, shared_m1_root: Path) -> Iterable[Path]:
    roots = (
        repo_root / "runs",
        repo_root / "exports" / "runs",
        shared_m1_root / "garment",
    )
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        for manifest in root.rglob("geometry_manifest.json"):
            run_dir = manifest.parent
            key = str(run_dir.resolve())
            if key in seen:
                continue
            seen.add(key)
            if (run_dir / "garment_proxy_meta.json").exists():
                yield run_dir


def _pick_latest_run_dir(repo_root: Path, shared_m1_root: Path) -> Optional[Path]:
    candidates = list(_candidate_run_dirs(repo_root, shared_m1_root))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _read_hard_gate_flag(meta_path: Path) -> bool:
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        flags = payload.get("flags", {})
        if isinstance(flags, dict):
            return bool(flags.get("invalid_face_flag", False))
        return bool(payload.get("invalid_face_flag", False))
    except Exception:
        return False


def _copy(src_dir: Path, dst_dir: Path, filenames: Iterable[str]) -> list[str]:
    copied = []
    for name in filenames:
        src = src_dir / name
        if not src.exists():
            continue
        dst = dst_dir / name
        shutil.copy2(src, dst)
        copied.append(name)
    return copied


def _append_m1_progress_event(
    repo_root: Path,
    run_id: str,
    source_dir: Path,
    run_dir: Path,
) -> None:
    """Best-effort append for Garment M1 publish. Never raises."""
    appender = repo_root / "tools" / "ops" / "append_progress_event.py"
    if not appender.exists():
        print("WARN: append_progress_event.py not found; skipping progress append", file=sys.stderr)
        return

    garment_lab_root = repo_root / "modules" / "garment"
    if not garment_lab_root.exists():
        garment_lab_root = repo_root

    source_manifest = _to_repo_rel_or_abs(source_dir / "geometry_manifest.json", repo_root)
    published_manifest = _to_repo_rel_or_abs(run_dir / "geometry_manifest.json", repo_root)
    run_dir_rel = _to_repo_rel_or_abs(run_dir, repo_root)

    cmd = [
        sys.executable,
        str(appender),
        "--lab-root", str(garment_lab_root),
        "--module", "garment",
        "--step-id", "G10_M1_PUBLISH",
        "--event", "note",
        "--run-id", run_id,
        "--status", "OK",
        "--m-level", "M1",
        "--note", f"Garment M1 published: {run_dir_rel}",
        "--evidence", source_manifest,
        "--evidence", published_manifest,
    ]
    try:
        subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=False)
    except Exception as exc:
        print(f"WARN: failed to append M1 progress event: {exc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Garment M1 shared artifacts")
    parser.add_argument(
        "--source-run-dir",
        default=None,
        help="Source run directory containing manifest/meta. Defaults to latest detected run.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Publish run id. Defaults to current UTC timestamp (YYYYmmdd_HHMMSS).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite destination run directory if it already exists.",
    )
    parser.add_argument(
        "--no-signal-update",
        action="store_true",
        help="Do not update ops/signals/m1/garment/LATEST.json.",
    )
    parser.add_argument(
        "--no-progress-event",
        action="store_true",
        help="Do not append G10_M1_PUBLISH event to PROGRESS_LOG.",
    )
    args = parser.parse_args()

    repo_root = _find_repo_root(Path(__file__).resolve())
    shared_m1_root = _resolve_shared_m1_root(repo_root)

    if args.source_run_dir:
        source_path = Path(args.source_run_dir)
        if source_path.is_absolute():
            source_dir = source_path.resolve()
        else:
            source_dir = (repo_root / source_path).resolve()
    else:
        source_dir = _pick_latest_run_dir(repo_root, shared_m1_root)
        if source_dir is None:
            print("ERROR: no run directory with required files found", file=sys.stderr)
            return 1

    if not source_dir.exists() or not source_dir.is_dir():
        print(f"ERROR: source run dir not found: {source_dir}", file=sys.stderr)
        return 1

    missing = [name for name in REQUIRED_FILES if not (source_dir / name).exists()]
    if missing:
        print(f"ERROR: missing required files in source run dir: {', '.join(missing)}", file=sys.stderr)
        return 1

    run_id = args.run_id or _utc_run_id()
    run_dir = shared_m1_root / "garment" / run_id
    if run_dir.exists():
        if not args.overwrite:
            print(f"ERROR: destination already exists: {run_dir}", file=sys.stderr)
            return 1
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    copied_required = _copy(source_dir, run_dir, REQUIRED_FILES)
    copied_optional = _copy(source_dir, run_dir, OPTIONAL_FILES)

    g40_metrics = _apply_g40_intake_gate_track(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id=run_id,
        source_dir=source_dir,
    )
    g41_result = _apply_g41_proxy_latent_track(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id=run_id,
    )
    _update_geometry_manifest(run_dir, list(TRACKING_FILES))

    if not args.no_signal_update:
        _write_latest_signal(
            repo_root=repo_root,
            run_id=run_id,
            source_dir=source_dir,
            run_dir=run_dir,
        )

    hard_gate = _read_hard_gate_flag(source_dir / "garment_proxy_meta.json")
    run_dir_rel = os.path.relpath(str(run_dir.resolve()), str(repo_root.resolve()))

    print(f"SHARED_M1_ROOT={shared_m1_root.resolve()}")
    print(f"SOURCE_RUN_DIR_REL={_to_repo_rel_or_abs(source_dir, repo_root)}")
    print(f"HARD_GATE={'1' if hard_gate else '0'}")
    print(f"COPIED_REQUIRED={','.join(copied_required)}")
    print(f"COPIED_OPTIONAL={','.join(copied_optional)}")
    print(f"RUN_DIR_ABS={run_dir.resolve()}")
    print(f"RUN_DIR_REL={run_dir_rel}")
    print(f"G40_STATUS={g40_metrics.get('status', 'OK')}")
    print(f"G41_THICKNESS_DEFAULTED={'1' if g41_result.get('default_applied') else '0'}")

    if not args.no_progress_event:
        _append_m1_progress_event(
            repo_root=repo_root,
            run_id=run_id,
            source_dir=source_dir,
            run_dir=run_dir,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
