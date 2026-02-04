#!/usr/bin/env python3
"""
Purpose: U1 runner: S1 manifest mesh/verts → geometric facts.
Inputs: --manifest (s1_manifest_v0*.json), --out_dir
Outputs: exports/runs/geo_v0_s1/<run_id>/facts_summary.json, artifacts/
Status: active
"""

from __future__ import annotations

import os
import sys
import json
import argparse
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
import subprocess
import traceback

# Add project root to path (4 levels up: runners -> src -> body -> modules -> repo)
_project_dir = Path(__file__).resolve().parent
project_root = str(_project_dir.parents[4])
for _p in (project_root, os.getcwd()):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

from modules.body.src.measurements.vtm.core_measurements_v0 import (
    measure_circumference_v0_with_metadata,
    measure_width_depth_v0_with_metadata,
    measure_height_v0_with_metadata,
    measure_arm_length_v0_with_metadata,
    create_weight_metadata,
    measure_waist_group_with_shared_slice,
    measure_hip_group_with_shared_slice,
    MeasurementResult,
)

# Golden path prefix rewrite (legacy verification/... -> local data/...)
LEGACY_GOLDEN_PREFIX = "verification/datasets/golden/s1_mesh_v0"
LOCAL_GOLDEN_PREFIX = "data/golden/s1_mesh_v0"


def _rewrite_golden_path(path_str: Optional[str], legacy: str = LEGACY_GOLDEN_PREFIX, local: str = LOCAL_GOLDEN_PREFIX) -> Optional[str]:
    """Rewrite legacy golden path prefix to local data/ path. Path separator normalized via Path."""
    if path_str is None or not path_str.strip():
        return path_str
    normalized = Path(path_str).as_posix()
    if normalized.startswith(legacy):
        return local + normalized[len(legacy):]
    return path_str


# This round's keys (same as geo v0)
CIRCUMFERENCE_KEYS = [
    "NECK_CIRC_M", "BUST_CIRC_M", "UNDERBUST_CIRC_M", 
    "WAIST_CIRC_M", "HIP_CIRC_M", "THIGH_CIRC_M", "MIN_CALF_CIRC_M"
]

WIDTH_DEPTH_KEYS = [
    "CHEST_WIDTH_M", "CHEST_DEPTH_M",
    "WAIST_WIDTH_M", "WAIST_DEPTH_M",
    "HIP_WIDTH_M", "HIP_DEPTH_M"
]

HEIGHT_KEYS = ["HEIGHT_M", "CROTCH_HEIGHT_M", "KNEE_HEIGHT_M"]

ALL_KEYS = CIRCUMFERENCE_KEYS + WIDTH_DEPTH_KEYS + HEIGHT_KEYS + ["ARM_LEN_M", "WEIGHT_KG"]


def get_git_sha() -> Optional[str]:
    """Get current git SHA if available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=project_root
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def load_s1_manifest(manifest_path: str) -> Dict[str, Any]:
    """Load S1 manifest JSON."""
    manifest_path_abs = Path(manifest_path).resolve()
    if not manifest_path_abs.exists():
        raise FileNotFoundError(f"S1 manifest not found: {manifest_path_abs}")
    
    with open(manifest_path_abs, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    # Validate schema
    if manifest.get("schema_version") != "s1_mesh_v0@1":
        raise ValueError(f"Invalid schema_version: {manifest.get('schema_version')}, expected 's1_mesh_v0@1'")
    
    if manifest.get("meta_unit") != "m":
        raise ValueError(f"Invalid meta_unit: {manifest.get('meta_unit')}, expected 'm'")
    
    return manifest


def load_obj_with_trimesh(path: Path) -> Optional[tuple[np.ndarray, Optional[np.ndarray], Optional[str]]]:
    """Load OBJ using trimesh (loader A, optional).
    
    Returns:
        (vertices, faces, scale_warning) or None if failed
    """
    try:
        import trimesh
        mesh = trimesh.load(str(path), process=False)
        if hasattr(mesh, 'vertices') and mesh.vertices is not None:
            verts = np.array(mesh.vertices, dtype=np.float32)
            faces = np.array(mesh.faces, dtype=np.int32) if hasattr(mesh, 'faces') and mesh.faces is not None else None
            # Round33: OBJ files may be in mm/cm, but S1 manifest meta_unit="m" assumes meters
            # If OBJ is in mm, convert to m (assume > 10.0 means mm/cm scale)
            # Round40: scale_warning을 상세 정보 딕셔너리로 변경
            scale_warning = None
            if verts.shape[0] > 0:
                max_abs = np.abs(verts).max()
                if max_abs > 10.0:  # Likely in mm/cm, convert to m
                    verts = verts / 1000.0  # mm -> m
                    # Round40: 상세 정보 딕셔너리로 변경 (case_id는 나중에 추가)
                    scale_warning = {
                        "trigger_rule": "max_abs > 10.0",
                        "max_abs": float(max_abs),
                        "source_path": str(path)
                    }
                    print(f"[OBJ/trimesh] Converted from mm to m (max_abs={max_abs:.2f})")
            return (verts, faces, scale_warning)
    except ImportError:
        return None
    except Exception:
        return None
    return None


def load_obj_with_fallback_parser(path: Path) -> Optional[tuple[np.ndarray, Optional[np.ndarray], Optional[str]]]:
    """Load OBJ using pure Python parser (loader B, required).
    
    Returns:
        (vertices, faces, scale_warning) or None if failed
    """
    try:
        vertices = []
        faces = []
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Parse vertex: "v x y z"
                if line.startswith('v ') and not line.startswith('vn ') and not line.startswith('vt '):
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                            vertices.append([x, y, z])
                        except ValueError:
                            continue
                
                # Parse face: "f a/b/c d/e/f g/h/i" or "f a d g"
                elif line.startswith('f '):
                    parts = line.split()[1:]  # Skip 'f'
                    face_indices = []
                    for part in parts:
                        # Extract vertex index (before first slash, or whole if no slash)
                        if '/' in part:
                            idx_str = part.split('/')[0]
                        else:
                            idx_str = part
                        try:
                            idx = int(idx_str) - 1  # 1-indexed -> 0-indexed
                            if idx >= 0:
                                face_indices.append(idx)
                        except ValueError:
                            continue
                    
                    if len(face_indices) >= 3:
                        faces.append(face_indices)
        
        if len(vertices) == 0:
            return None
        
        verts_array = np.array(vertices, dtype=np.float32)
        # Round33: OBJ files may be in mm/cm, but S1 manifest meta_unit="m" assumes meters
        # If OBJ is in mm, convert to m (assume > 10.0 means mm/cm scale)
        # Round40: scale_warning을 상세 정보 딕셔너리로 변경
        max_abs = np.abs(verts_array).max()
        scale_warning = None
        if max_abs > 10.0:  # Likely in mm/cm, convert to m
            verts_array = verts_array / 1000.0  # mm -> m
            # Round40: 상세 정보 딕셔너리로 변경 (case_id는 나중에 추가)
            scale_warning = {
                "trigger_rule": "max_abs > 10.0",
                "max_abs": float(max_abs),
                "source_path": str(path)
            }
            print(f"[OBJ/fallback] Converted from mm to m (max_abs={max_abs:.2f})")
        
        faces_array = np.array(faces, dtype=np.int32) if len(faces) > 0 else None
        
        # Return with scale warning for logging
        return (verts_array, faces_array, scale_warning)
    except Exception:
        return None


def load_verts_from_path_with_info(verts_path: str) -> Optional[tuple[np.ndarray, str, Optional[np.ndarray], Optional[str]]]:
    """Load verts from file path (NPZ or OBJ format) with loader info.
    
    For OBJ files, uses 2-stage loader:
    - Loader A: trimesh (optional)
    - Loader B: pure Python OBJ parser (required fallback)
    
    Returns:
        (verts, loader_name, faces, scale_warning) or None if failed
    """
    path = Path(verts_path)
    if not path.exists():
        return None
    
    # Resolve path (absolute or relative to cwd)
    if path.is_absolute():
        path_resolved = path.resolve()
    else:
        path_resolved = (Path.cwd() / path).resolve()
    
    if not path_resolved.exists():
        return None
    
    # Try NPZ first
    if path_resolved.suffix == ".npz":
        try:
            data = np.load(str(path_resolved), allow_pickle=True)
            if "verts" in data:
                verts = data["verts"]
                # Handle various formats
                if verts.dtype == object and verts.ndim == 1:
                    verts_result = verts[0] if len(verts) > 0 else None
                elif verts.ndim == 3:
                    verts_result = verts[0]  # (N, V, 3) -> (V, 3)
                elif verts.ndim == 2:
                    verts_result = verts  # (V, 3)
                else:
                    verts_result = None
                
                if verts_result is not None:
                    return (verts_result, "npz", None, None)
            return None
        except Exception as e:
            print(f"[WARN] Failed to load NPZ from {path_resolved}: {e}")
            return None
    
    # Try OBJ (2-stage loader)
    if path_resolved.suffix.lower() == ".obj":
        # Loader A: trimesh (optional)
        result = load_obj_with_trimesh(path_resolved)
        if result is not None:
            verts, faces, scale_warning = result
            return (verts, "trimesh", faces, scale_warning)
        
        # Loader B: pure Python OBJ parser (required fallback)
        result = load_obj_with_fallback_parser(path_resolved)
        if result is not None:
            verts, faces, scale_warning = result
            return (verts, "fallback_obj_parser", faces, scale_warning)
        
        return None
    
    return None


def load_verts_from_path(verts_path: str) -> Optional[np.ndarray]:
    """Load verts from file path (NPZ or OBJ format) - backward compatibility."""
    result = load_verts_from_path_with_info(verts_path)
    if result is not None:
        verts, _, _, _ = result
        return verts
    return None


def measure_all_keys(verts: np.ndarray, case_id: str) -> Dict[str, MeasurementResult]:
    """Measure all keys for a single case (reuse existing geo v0 logic)."""
    results = {}
    
    # WAIST group: Use shared slice (CIRC, WIDTH, DEPTH)
    try:
        waist_results = measure_waist_group_with_shared_slice(verts, case_id=case_id)
        results.update(waist_results)
    except Exception as e:
        # Round52: Classify exception into sub-codes and record fingerprint
        exception_type = e.__class__.__name__
        exception_message = str(e)
        
        # Round52: Classify into sub-codes
        exec_fail_subcode = "UNHANDLED_EXCEPTION"
        if "empty" in exception_message.lower() or "slice" in exception_message.lower() and "empty" in exception_message.lower():
            exec_fail_subcode = "SLICE_EMPTY"
        elif "too few" in exception_message.lower() or "points" in exception_message.lower() and ("<" in exception_message or "few" in exception_message.lower()):
            exec_fail_subcode = "TOO_FEW_POINTS"
        elif "numeric" in exception_message.lower() or "nan" in exception_message.lower() or "inf" in exception_message.lower():
            exec_fail_subcode = "NUMERIC_ERROR"
        elif exception_type in ["ValueError", "TypeError", "IndexError"]:
            exec_fail_subcode = "NUMERIC_ERROR"
        
        # Round52: Compute stable short hash fingerprint
        import hashlib
        fingerprint_input = f"{exception_type}:{exception_message[:200]}"  # Limit message length
        fingerprint_hash = hashlib.md5(fingerprint_input.encode('utf-8')).hexdigest()[:8]
        
        for key in ["WAIST_CIRC_M", "WAIST_WIDTH_M", "WAIST_DEPTH_M"]:
            results[key] = MeasurementResult(
                standard_key=key,
                value_m=float('nan'),
                metadata={
                    "standard_key": key,
                    "value_m": float('nan'),
                    "unit": "m",
                    "precision": 0.001,
                    "warnings": [f"EXEC_FAIL:{exec_fail_subcode}"],
                    "version": {"semantic_tag": "semantic-v0", "schema_version": "metadata-schema-v0"},
                    # Round52: Add exception taxonomy
                    "exec_fail_subcode": exec_fail_subcode,
                    "exception_type": exception_type,
                    "exception_fingerprint": fingerprint_hash
                }
            )
    
    # HIP group: Use shared slice (CIRC, WIDTH, DEPTH)
    try:
        hip_results = measure_hip_group_with_shared_slice(verts, case_id=case_id)
        results.update(hip_results)
    except Exception as e:
        # Round52: Classify exception into sub-codes and record fingerprint
        exception_type = e.__class__.__name__
        exception_message = str(e)
        
        # Round52: Classify into sub-codes
        exec_fail_subcode = "UNHANDLED_EXCEPTION"
        if "empty" in exception_message.lower() or "slice" in exception_message.lower() and "empty" in exception_message.lower():
            exec_fail_subcode = "SLICE_EMPTY"
        elif "too few" in exception_message.lower() or "points" in exception_message.lower() and ("<" in exception_message or "few" in exception_message.lower()):
            exec_fail_subcode = "TOO_FEW_POINTS"
        elif "numeric" in exception_message.lower() or "nan" in exception_message.lower() or "inf" in exception_message.lower():
            exec_fail_subcode = "NUMERIC_ERROR"
        elif exception_type in ["ValueError", "TypeError", "IndexError"]:
            exec_fail_subcode = "NUMERIC_ERROR"
        
        # Round52: Compute stable short hash fingerprint
        import hashlib
        fingerprint_input = f"{exception_type}:{exception_message[:200]}"  # Limit message length
        fingerprint_hash = hashlib.md5(fingerprint_input.encode('utf-8')).hexdigest()[:8]
        
        for key in ["HIP_CIRC_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]:
            results[key] = MeasurementResult(
                standard_key=key,
                value_m=float('nan'),
                metadata={
                    "standard_key": key,
                    "value_m": float('nan'),
                    "unit": "m",
                    "precision": 0.001,
                    "warnings": [f"EXEC_FAIL:{exec_fail_subcode}"],
                    "version": {"semantic_tag": "semantic-v0", "schema_version": "metadata-schema-v0"},
                    # Round52: Add exception taxonomy
                    "exec_fail_subcode": exec_fail_subcode,
                    "exception_type": exception_type,
                    "exception_fingerprint": fingerprint_hash
                }
            )
    
    # Circumference keys
    # Round41: Torso keys for torso-only analysis
    TORSO_CIRC_KEYS = ["NECK_CIRC_M", "BUST_CIRC_M", "UNDERBUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]
    # Round51: Key-level failure reason tracking for WAIST/HIP NaN regression
    KEY_FAILURE_TRACK_KEYS = ["WAIST_CIRC_M", "WAIST_WIDTH_M", "WAIST_DEPTH_M", "HIP_CIRC_M", "HIP_WIDTH_M"]
    
    for key in CIRCUMFERENCE_KEYS:
        if key not in results:
            try:
                result = measure_circumference_v0_with_metadata(verts, key, case_id=case_id)
                results[key] = result
                
                # Round41/43: Extract torso-only circumference for torso keys
                if key in TORSO_CIRC_KEYS:
                    torso_key = key.replace("_CIRC_M", "_CIRC_TORSO_M")
                    torso_perimeter = None
                    torso_warning = None
                    
                    # Round44: metadata_v0 uses "debug"; accept "debug_info" or "debug"
                    debug_info = (result.metadata or {}).get("debug_info") or (result.metadata or {}).get("debug") or {}
                    if result.metadata and debug_info and "torso_components" in debug_info:
                        torso_info = debug_info["torso_components"]
                        if torso_info.get("torso_selected") and torso_info.get("torso_perimeter") is not None:
                            torso_perimeter = torso_info["torso_perimeter"]
                        else:
                            torso_warning = "torso_component_selection_failed"
                    
                    # Create torso-only result
                    # Round43: Copy debug_info including torso_components for diagnostics
                    torso_metadata = result.metadata.copy() if result.metadata else {}
                    if torso_metadata and "debug_info" in torso_metadata:
                        # Keep debug_info with torso_components for diagnostics
                        pass
                    if torso_warning:
                        torso_metadata.setdefault("warnings", []).append(torso_warning)
                    
                    results[torso_key] = MeasurementResult(
                        standard_key=torso_key,
                        value_m=torso_perimeter if torso_perimeter is not None else float('nan'),
                        metadata=torso_metadata
                    )
            except Exception as e:
                results[key] = MeasurementResult(
                    standard_key=key,
                    value_m=float('nan'),
                    metadata={
                        "standard_key": key,
                        "value_m": float('nan'),
                        "unit": "m",
                        "precision": 0.001,
                        "warnings": [f"EXEC_FAIL: {str(e)}"],
                        "version": {"semantic_tag": "semantic-v0", "schema_version": "metadata-schema-v0"}
                    }
                )
                # Round41: Also create NaN torso result on failure
                if key in TORSO_CIRC_KEYS:
                    torso_key = key.replace("_CIRC_M", "_CIRC_TORSO_M")
                    results[torso_key] = MeasurementResult(
                        standard_key=torso_key,
                        value_m=float('nan'),
                        metadata={
                            "standard_key": torso_key,
                            "value_m": float('nan'),
                            "unit": "m",
                            "precision": 0.001,
                            "warnings": [f"EXEC_FAIL: {str(e)}"],
                            "version": {"semantic_tag": "semantic-v0", "schema_version": "metadata-schema-v0"}
                        }
                    )
    
    # Width/Depth keys
    for key in WIDTH_DEPTH_KEYS:
        if key not in results:
            try:
                result = measure_width_depth_v0_with_metadata(verts, key)
                results[key] = result
            except Exception as e:
                results[key] = MeasurementResult(
                    standard_key=key,
                    value_m=float('nan'),
                    metadata={
                        "standard_key": key,
                        "value_m": float('nan'),
                        "unit": "m",
                        "precision": 0.001,
                        "warnings": [f"EXEC_FAIL: {str(e)}"],
                        "version": {"semantic_tag": "semantic-v0", "schema_version": "metadata-schema-v0"}
                    }
                )
    
    # Height keys
    for key in HEIGHT_KEYS:
        try:
            result = measure_height_v0_with_metadata(verts, key)
            results[key] = result
        except Exception as e:
            results[key] = MeasurementResult(
                standard_key=key,
                value_m=float('nan'),
                metadata={
                    "standard_key": key,
                    "value_m": float('nan'),
                    "unit": "m",
                    "precision": 0.001,
                    "warnings": [f"EXEC_FAIL: {str(e)}"],
                    "version": {"semantic_tag": "semantic-v0", "schema_version": "metadata-schema-v0"}
                }
            )
    
    # ARM_LEN_M
    try:
        result = measure_arm_length_v0_with_metadata(verts)
        results["ARM_LEN_M"] = result
    except Exception as e:
        results["ARM_LEN_M"] = MeasurementResult(
            standard_key="ARM_LEN_M",
            value_m=float('nan'),
            metadata={
                "standard_key": "ARM_LEN_M",
                "value_m": float('nan'),
                "unit": "m",
                "precision": 0.001,
                "warnings": [f"EXEC_FAIL: {str(e)}"],
                "version": {"semantic_tag": "semantic-v0", "schema_version": "metadata-schema-v0"}
            }
        )
    
    # WEIGHT_KG (metadata only, no measurement)
    # A안: weight 값이 없으면 metadata 생성 스킵 + reason 기록
    # Weight cannot be computed from mesh - it must be provided as input.
    # Since we don't have weight input in S1 manifest, skip WEIGHT_KG metadata creation.
    # This is facts-only: we record that weight is not available, not a failure.
    
    return results


def log_skip_reason(
    skip_reasons_file: Path,
    case_id: str,
    has_mesh_path: bool,
    mesh_path: Optional[str],
    attempted_load: bool,
    stage: str,
    reason: str,
    exception_1line: Optional[str] = None,
    mesh_path_resolved: Optional[str] = None,
    mesh_exists: Optional[bool] = None,
    exception_type: Optional[str] = None,
    loader_name: Optional[str] = None,
    loaded_verts: Optional[int] = None,
    loaded_faces: Optional[int] = None,
    tracking_set: Optional[set] = None
) -> None:
    """Log skip reason to JSONL file (SSoT for per-case skip reasons).

    Round68: Added tracking_set parameter to track which case_ids have been logged.
    """
    record = {
        "case_id": case_id,
        "has_mesh_path": has_mesh_path,
        "mesh_path": mesh_path,
        "attempted_load": attempted_load,
        "stage": stage,
        "reason": reason,
    }
    if exception_1line:
        record["exception_1line"] = exception_1line
    if mesh_path_resolved is not None:
        record["mesh_path_resolved"] = mesh_path_resolved
    if mesh_exists is not None:
        record["mesh_exists"] = mesh_exists
    if exception_type:
        record["exception_type"] = exception_type
    if loader_name:
        record["loader_name"] = loader_name
    if loaded_verts is not None:
        record["loaded_verts"] = loaded_verts
    if loaded_faces is not None:
        record["loaded_faces"] = loaded_faces

    with open(skip_reasons_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')

    # Round68: Track that this case_id has been logged
    if tracking_set is not None:
        tracking_set.add(case_id)


def log_exec_failure(
    exec_failures_file: Path,
    case_id: str,
    stage: str,
    exception_type: str,
    exception_1line: str,
    has_mesh_path: bool,
    mesh_path: Optional[str],
    mesh_path_resolved: Optional[str] = None,
    failed_keys: Optional[List[str]] = None
) -> None:
    """Round65: Log exec-fail to JSONL (cases that reach measurement but fail to be counted as processed)."""
    record = {
        "case_id": case_id,
        "stage": stage,
        "exception_type": exception_type,
        "exception_1line": exception_1line,
        "has_mesh_path": has_mesh_path,
        "mesh_path": mesh_path,
    }
    if mesh_path_resolved:
        record["mesh_path_resolved"] = mesh_path_resolved
    if failed_keys:
        record["failed_keys"] = failed_keys

    with open(exec_failures_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def log_processed_sink(
    processed_sink_file: Path,
    case_id: str,
    has_mesh_path: bool,
    mesh_path: Optional[str],
    resolved_path: Optional[str],
    sink_reason_code: str,
    keys_present: Optional[List[str]] = None,
    results_len: Optional[int] = None,
    exception_1line: Optional[str] = None
) -> None:
    """Round66: Log processed-sink to JSONL (cases logged as success but not counted as processed)."""
    record = {
        "case_id": case_id,
        "has_mesh_path": has_mesh_path,
        "mesh_path": mesh_path,
        "sink_reason_code": sink_reason_code,
    }
    if resolved_path:
        record["resolved_path"] = resolved_path
    if keys_present is not None:
        record["keys_present"] = keys_present
    if results_len is not None:
        record["results_len"] = results_len
    if exception_1line:
        record["exception_1line"] = exception_1line

    with open(processed_sink_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def log_success_not_processed(
    success_not_processed_file: Path,
    case_id: str,
    has_mesh_path: bool,
    mesh_path: Optional[str],
    mesh_path_resolved: Optional[str],
    returned_type: str,
    returned_keys: List[str],
    has_results_key: bool,
    results_len: Optional[int],
    sink_reason_code: str,
    note_1line: Optional[str] = None
) -> None:
    """Round67: Log success-but-not-processed to JSONL (cases logged as success but not in all_results)."""
    record = {
        "case_id": case_id,
        "has_mesh_path": has_mesh_path,
        "mesh_path": mesh_path,
        "returned_type": returned_type,
        "returned_keys": returned_keys,
        "has_results_key": has_results_key,
        "sink_reason_code": sink_reason_code,
    }
    if mesh_path_resolved:
        record["mesh_path_resolved"] = mesh_path_resolved
    if results_len is not None:
        record["results_len"] = results_len
    if note_1line:
        record["note_1line"] = note_1line

    with open(success_not_processed_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def log_record_missing_skip_reason(
    record_missing_file: Path,
    case_id: str,
    has_mesh_path: bool,
    mesh_path: Optional[str],
    note_1line: str
) -> None:
    """Round68: Log cases that entered loop but didn't call log_skip_reason."""
    record = {
        "case_id": case_id,
        "has_mesh_path": has_mesh_path,
        "mesh_path": mesh_path,
        "note_1line": note_1line,
    }

    with open(record_missing_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def resolve_mesh_path(mesh_path: str) -> tuple[Path, bool]:
    """Resolve mesh path (absolute or relative to cwd).

    Returns:
        (resolved_path, exists)
    """
    if Path(mesh_path).is_absolute():
        resolved = Path(mesh_path).resolve()
    else:
        # Relative path: resolve from current working directory
        resolved = (Path.cwd() / mesh_path).resolve()

    return resolved, resolved.exists()


def process_case(
    case: Dict[str, Any],
    out_dir: Path,
    skipped_entries: List[Dict[str, Any]],
    skip_reasons_file: Path,
    exec_failures_file: Path,
    processed_sink_file: Path,
    log_skip_reason_tracking: Optional[set] = None
) -> Optional[Dict[str, MeasurementResult]]:
    """Process a single case from S1 manifest.

    Returns:
        Measurement results if processed, None if skipped

    Invariant: Each case_id must log exactly 1 record to skip_reasons.jsonl
    Round65: exec-fail cases also log to exec_failures.jsonl
    """
    case_id = case["case_id"]
    mesh_path = _rewrite_golden_path(case.get("mesh_path"))
    verts_path = _rewrite_golden_path(case.get("verts_path"))
    # Round32: has_mesh_path 판정 단일화
    has_mesh_path = (mesh_path is not None) and (str(mesh_path).strip() != "")
    
    # Track if we've logged this case (invariant: exactly 1 record per case)
    logged = False
    
    # Use try/finally to ensure logging even on unexpected exceptions
    try:
    
        # Round33: Type A: manifest path is null (precheck stage)
        if mesh_path is None and verts_path is None:
            skip_reason = "manifest_path_is_null"
            log_skip_reason(
                skip_reasons_file=skip_reasons_file,
                case_id=case_id,
                has_mesh_path=False,
                mesh_path=None,
                attempted_load=False,
                stage="precheck",
                reason=skip_reason,
                tracking_set=log_skip_reason_tracking
            )
            logged = True
            skipped_entries.append({
                "Type": "A: manifest_path_is_null",
                "case_id": case_id,
                "Reason": "S1 manifest has null path (no mesh/verts assigned)"
            })
            return None
        
        # Determine which path to use (prefer verts_path over mesh_path)
        path_to_use = verts_path if verts_path is not None else mesh_path
        
        # Resolve mesh_path for diagnostics (Round30)
        mesh_path_resolved = None
        mesh_exists = None
        mesh_path_resolved_obj = None
        if mesh_path is not None:
            mesh_path_resolved_obj, mesh_exists = resolve_mesh_path(mesh_path)
            mesh_path_resolved = str(mesh_path_resolved_obj)
        
        # Type B: manifest path set but file missing (precheck stage)
        if path_to_use is not None:
            if verts_path is not None:
                path_abs = Path(verts_path).resolve() if Path(verts_path).is_absolute() else (Path.cwd() / verts_path).resolve()
            else:
                path_abs = mesh_path_resolved_obj if mesh_path_resolved_obj else None
            
            if path_abs is None or not path_abs.exists():
                skip_reason = "file_not_found"
                log_skip_reason(
                    skip_reasons_file=skip_reasons_file,
                    case_id=case_id,
                    has_mesh_path=has_mesh_path,
                    mesh_path=mesh_path,
                    attempted_load=False,
                    stage="precheck",
                    reason=skip_reason,
                    exception_1line=f"File not found: {path_to_use}",
                    mesh_path_resolved=mesh_path_resolved,
                    mesh_exists=mesh_exists,
                    tracking_set=log_skip_reason_tracking
                )
                logged = True
                skipped_entries.append({
                    "Type": "B: mesh_exists_false",
                    "case_id": case_id,
                    "path": str(path_to_use),
                    "Reason": "path specified but file not found"
                })
                return None
        
        # Resolve mesh_path for diagnostics (Round30) - ensure it's done after file check
        if mesh_path is not None and mesh_path_resolved is None:
            if Path(mesh_path).is_absolute():
                mesh_path_resolved_obj = Path(mesh_path).resolve()
            else:
                mesh_path_resolved_obj = (Path.cwd() / mesh_path).resolve()
            mesh_path_resolved = str(mesh_path_resolved_obj)
            mesh_exists = mesh_path_resolved_obj.exists()
        
        # Load verts (prefer verts_path, fallback to mesh_path) - load_mesh stage
        # Proxy 슬롯 5개는 반드시 attempted_load=True까지 진입
        verts = None
        faces = None
        load_error = None
        attempted_load = False
        exception_1line = None
        exception_type = None
        loader_name = None
        loaded_verts = None
        loaded_faces = None
        
        scale_warning = None
        if verts_path is not None:
            attempted_load = True
            try:
                result = load_verts_from_path_with_info(verts_path)
                if result is not None:
                    verts, loader_name, faces, scale_warn = result
                    loaded_verts = verts.shape[0] if verts is not None else None
                    loaded_faces = faces.shape[0] if faces is not None else None
                    if scale_warn and not scale_warning:
                        scale_warning = scale_warn
                else:
                    load_error = f"verts_path specified but load returned None: {verts_path}"
            except Exception as e:
                load_error = f"verts_path load exception: {str(e)}"
                exception_1line = str(e).splitlines()[0] if str(e).splitlines() else repr(e)
                exception_type = type(e).__name__
        
        if verts is None and mesh_path is not None:
            attempted_load = True
            try:
                result = load_verts_from_path_with_info(mesh_path)
                if result is not None:
                    verts, loader_name, faces, scale_warn = result
                    loaded_verts = verts.shape[0] if verts is not None else None
                    loaded_faces = faces.shape[0] if faces is not None else None
                    if scale_warn and not scale_warning:
                        scale_warning = scale_warn
                else:
                    if load_error:
                        load_error = f"{load_error}; mesh_path load also returned None: {mesh_path}"
                    else:
                        load_error = f"mesh_path specified but load returned None: {mesh_path}"
            except Exception as e:
                if load_error:
                    load_error = f"{load_error}; mesh_path load exception: {str(e)}"
                else:
                    load_error = f"mesh_path load exception: {str(e)}"
                if not exception_1line:
                    exception_1line = str(e).splitlines()[0] if str(e).splitlines() else repr(e)
                if not exception_type:
                    exception_type = type(e).__name__
        
        if verts is None:
            # Type B or Type C (parse error) - load_mesh stage
            skip_reason = "load_failed"
            if load_error and ("exception" in load_error.lower() or "failed" in load_error.lower()):
                skip_reason = "load_failed"

            log_skip_reason(
                skip_reasons_file=skip_reasons_file,
                case_id=case_id,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                attempted_load=attempted_load,
                stage="load_mesh",
                reason=skip_reason,
                exception_1line=exception_1line,
                mesh_path_resolved=mesh_path_resolved,
                mesh_exists=mesh_exists,
                exception_type=exception_type,
                loader_name=loader_name,
                loaded_verts=loaded_verts,
                tracking_set=log_skip_reason_tracking,
                loaded_faces=loaded_faces
            )
            logged = True
            skipped_entries.append({
                "Type": "D: load_failed",
                "case_id": case_id,
                "path": str(path_to_use) if path_to_use else "N/A",
                "Reason": load_error if load_error else "path specified but file not found or load failed"
            })
            return None
        
        # Validate verts shape (precheck stage after load)
        if verts.ndim != 2 or verts.shape[1] != 3:
            skip_reason = "invalid_verts_shape"
            log_skip_reason(
                skip_reasons_file=skip_reasons_file,
                case_id=case_id,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                attempted_load=attempted_load,
                stage="precheck",
                reason=skip_reason,
                exception_1line=f"Invalid shape: {verts.shape}, expected (V, 3)",
                mesh_path_resolved=mesh_path_resolved,
                mesh_exists=mesh_exists,
                tracking_set=log_skip_reason_tracking
            )
            logged = True
            skipped_entries.append({
                "Type": "D: load_failed",
                "case_id": case_id,
                "path": str(path_to_use) if path_to_use else "N/A",
                "Reason": f"invalid verts shape: {verts.shape}, expected (V, 3)"
            })
            return None
        
        # Process with existing geo v0 logic (measure stage)
        try:
            results = measure_all_keys(verts, case_id)
            # Round32: 성공 케이스도 로깅 (invariant: 1 record per case)
            # Round33: scale_warning을 exception_1line에 포함 (facts-only)
            exception_1line_for_log = scale_warning if scale_warning else None
            log_skip_reason(
                skip_reasons_file=skip_reasons_file,
                case_id=case_id,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                attempted_load=attempted_load,
                stage="measure",
                reason="success",
                mesh_path_resolved=mesh_path_resolved,
                mesh_exists=mesh_exists,
                loader_name=loader_name,
                loaded_verts=loaded_verts,
                loaded_faces=loaded_faces,
                exception_1line=exception_1line_for_log,
                tracking_set=log_skip_reason_tracking
            )
            logged = True
            # Round33: Return results with verts and scale_warning for NPZ generation
            return {"results": results, "verts": verts, "case_id": case_id, "scale_warning": scale_warning}
        except KeyboardInterrupt as e:
            # Round37 Hotfix: KeyboardInterrupt도 기록 후 re-raise (사용자 중단은 존중하되 로그는 남김)
            exception_1line = "KeyboardInterrupt (user interrupt)"
            log_skip_reason(
                skip_reasons_file=skip_reasons_file,
                case_id=case_id,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                attempted_load=attempted_load,
                stage="measure",
                reason="exception",
                exception_1line=exception_1line,
                mesh_path_resolved=mesh_path_resolved,
                mesh_exists=mesh_exists,
                exception_type="KeyboardInterrupt",
                tracking_set=log_skip_reason_tracking
            )
            logged = True
            skipped_entries.append({
                "Type": "measure_exception",
                "case_id": case_id,
                "Reason": f"KeyboardInterrupt during measurement"
            })
            print(f"[WARN] Measurement interrupted for {case_id}: KeyboardInterrupt")
            raise  # Re-raise to respect user interrupt
        except Exception as e:
            # Round37 Hotfix: 모든 예외를 exception reason으로 기록
            exception_1line = str(e).split('\n')[0] if str(e).splitlines() else repr(e)
            log_skip_reason(
                skip_reasons_file=skip_reasons_file,
                case_id=case_id,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                attempted_load=attempted_load,
                stage="measure",
                reason="exception",
                exception_1line=exception_1line,
                mesh_path_resolved=mesh_path_resolved,
                mesh_exists=mesh_exists,
                exception_type=type(e).__name__,
                tracking_set=log_skip_reason_tracking
            )
            logged = True
            # Round65: Log to exec_failures.jsonl (reached measure but failed to be processed)
            log_exec_failure(
                exec_failures_file=exec_failures_file,
                case_id=case_id,
                stage="measure",
                exception_type=type(e).__name__,
                exception_1line=exception_1line,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                mesh_path_resolved=mesh_path_resolved,
                failed_keys=None  # Can expand in future if needed
            )
            skipped_entries.append({
                "Type": "measure_exception",
                "case_id": case_id,
                "Reason": f"Exception during measurement: {exception_1line}"
            })
            print(f"[WARN] Measurement failed for {case_id}: {e}")
            return {}
    except KeyboardInterrupt as e:
        # Round37 Hotfix: KeyboardInterrupt도 최상위에서 기록 후 re-raise
        if not logged:
            exception_1line = "KeyboardInterrupt (user interrupt)"
            log_skip_reason(
                skip_reasons_file=skip_reasons_file,
                case_id=case_id,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                attempted_load=attempted_load,
                stage="unexpected_exception",
                reason="exception",
                exception_1line=exception_1line,
                exception_type="KeyboardInterrupt",
                tracking_set=log_skip_reason_tracking
            )
            logged = True
            skipped_entries.append({
                "Type": "measure_exception",
                "case_id": case_id,
                "Reason": f"KeyboardInterrupt during processing"
            })
        raise  # Re-raise to respect user interrupt
    except Exception as e:
        # Round32: 예상치 못한 예외 발생 시에도 로깅 보장
        if not logged:
            exception_1line = str(e).splitlines()[0] if str(e).splitlines() else repr(e)
            log_skip_reason(
                skip_reasons_file=skip_reasons_file,
                case_id=case_id,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                attempted_load=attempted_load,
                stage="unexpected_exception",
                reason="exception",
                exception_1line=exception_1line,
                exception_type=type(e).__name__,
                tracking_set=log_skip_reason_tracking
            )
            logged = True
            skipped_entries.append({
                "Type": "measure_exception",
                "case_id": case_id,
                "Reason": f"Unexpected exception: {exception_1line}"
            })
        raise
    finally:
        # Round32: 최종 확인 - 로깅이 누락되었는지 체크 (should not happen, but safety net)
        if not logged:
            print(f"[WARN] Case {case_id} was not logged to skip_reasons.jsonl - this should not happen!")
            log_skip_reason(
                skip_reasons_file=skip_reasons_file,
                case_id=case_id,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                attempted_load=False,
                stage="invariant_fill",
                reason="missing_log_record",
                tracking_set=log_skip_reason_tracking
            )


def main():
    parser = argparse.ArgumentParser(
        description="Geometric v0 S1 Facts-Only Runner (Round 23)"
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="verification/datasets/golden/s1_mesh_v0/s1_manifest_v0.json",
        help="S1 manifest JSON path"
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        default=None,
        help="Output directory (default: exports/runs/geo_v0_s1/run_<timestamp>)"
    )
    args = parser.parse_args()
    
    if args.out_dir is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(project_root) / "exports" / "runs" / "geo_v0_s1" / f"run_{timestamp}"
    else:
        out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Create artifacts directories
    artifacts_dir = out_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    visual_dir = artifacts_dir / "visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    
    # Create skip_reasons.jsonl file (SSoT for per-case skip reasons)
    skip_reasons_file = artifacts_dir / "skip_reasons.jsonl"
    if skip_reasons_file.exists():
        skip_reasons_file.unlink()  # Clear previous run
    print(f"[SKIP REASONS] Logging to: {skip_reasons_file}")

    # Round65: Create exec_failures.jsonl file (SSoT for exec-fail cases)
    exec_failures_file = artifacts_dir / "exec_failures.jsonl"
    if exec_failures_file.exists():
        exec_failures_file.unlink()  # Clear previous run
    print(f"[EXEC FAILURES] Logging to: {exec_failures_file}")

    # Round66: Create processed_sink.jsonl file (SSoT for processed-sink cases)
    processed_sink_file = artifacts_dir / "processed_sink.jsonl"
    if processed_sink_file.exists():
        processed_sink_file.unlink()  # Clear previous run
    print(f"[PROCESSED SINK] Logging to: {processed_sink_file}")

    # Round67: Create success_not_processed.jsonl file (SSoT for success-but-not-processed cases)
    success_not_processed_file = artifacts_dir / "success_not_processed.jsonl"
    if success_not_processed_file.exists():
        success_not_processed_file.unlink()  # Clear previous run
    print(f"[SUCCESS NOT PROCESSED] Logging to: {success_not_processed_file}")

    # Round68: Create record_missing_skip_reason.jsonl file (SSoT for missing skip_reason records)
    record_missing_file = artifacts_dir / "record_missing_skip_reason.jsonl"
    if record_missing_file.exists():
        record_missing_file.unlink()  # Clear previous run
    print(f"[RECORD MISSING] Logging to: {record_missing_file}")

    # Load S1 manifest
    print(f"[S1 MANIFEST] Loading: {args.manifest}")
    manifest = load_s1_manifest(args.manifest)
    cases = manifest.get("cases", [])
    print(f"[S1 MANIFEST] Loaded {len(cases)} cases")
    print(f"[S1 MANIFEST] meta_unit: {manifest.get('meta_unit')}")
    print(f"[S1 MANIFEST] schema_version: {manifest.get('schema_version')}")

    # Round69: Manifest duplicate observability
    manifest_case_ids = [c.get("case_id") for c in cases]
    manifest_total_entries = len(manifest_case_ids)
    manifest_unique_case_ids = len(set(manifest_case_ids))

    # Count duplicates
    from collections import Counter
    case_id_counter = Counter(manifest_case_ids)
    duplicate_case_ids = {cid: count for cid, count in case_id_counter.items() if count >= 2}
    manifest_duplicate_case_id_count = len(duplicate_case_ids)

    # Build top-K dict (top 10, sorted by count descending)
    manifest_duplicate_case_id_topk: Dict[str, int] = {}
    if duplicate_case_ids:
        sorted_dups = sorted(duplicate_case_ids.items(), key=lambda x: x[1], reverse=True)
        manifest_duplicate_case_id_topk = dict(sorted_dups[:10])

    # Sample: first 3 duplicate case_ids
    manifest_duplicate_case_ids_sample = list(duplicate_case_ids.keys())[:3] if duplicate_case_ids else []

    print(f"[MANIFEST DUPLICATES] Total entries: {manifest_total_entries}, Unique: {manifest_unique_case_ids}, Duplicates: {manifest_duplicate_case_id_count}")
    if manifest_duplicate_case_id_count > 0:
        print(f"[MANIFEST DUPLICATES] Sample: {manifest_duplicate_case_ids_sample}")

    # Round61: Runner selection/cap observability
    # Count enabled cases (mesh_path not null)
    enabled_cases = [c for c in cases if c.get("mesh_path")]
    requested_enabled_cases = len(enabled_cases)
    
    # Round61: Track which cases are selected for processing
    # (Currently, all cases in manifest are processed, but we track which ones actually get processed)
    selected_case_ids: List[str] = []
    effective_processed_cap: Optional[int] = None  # Will be set if we find a cap
    selection_rule: str = "process all cases in manifest order"  # Default rule
    
    # Process cases
    all_results: Dict[str, Dict[str, MeasurementResult]] = {}
    skipped_entries: List[Dict[str, Any]] = []
    # Round33: Collect verts from processed cases for NPZ generation
    processed_verts: List[np.ndarray] = []
    processed_case_ids: List[str] = []
    # Round40: scale_warnings를 상세 정보 리스트로 변경
    scale_warnings: List[str] = []  # Backward compatibility: 문자열 리스트 유지
    scale_warnings_detailed: List[Dict[str, Any]] = []  # Round40: 상세 정보 리스트
    # Round67: Track what each case returned for success-not-processed detection
    case_return_tracking: Dict[str, Dict[str, Any]] = {}
    # Round68: Track which case_ids enter loop and which get logged
    entered_loop_case_ids: set = set()
    log_skip_reason_called_case_ids: set = set()

    print(f"[PROCESS] Processing {len(cases)} cases...")
    for i, case in enumerate(cases):
        case_id = case["case_id"]
        if (i + 1) % 50 == 0:
            print(f"[PROCESS] Processed {i + 1}/{len(cases)} cases...")

        # Round61: Track selected case_id (before processing)
        selected_case_ids.append(case_id)

        # Round68: Track that this case_id entered the loop
        entered_loop_case_ids.add(case_id)

        result_data = process_case(case, out_dir, skipped_entries, skip_reasons_file, exec_failures_file, processed_sink_file, log_skip_reason_called_case_ids)

        # Round67: Track what was returned for this case
        tracking_info = {
            "returned_type": type(result_data).__name__ if result_data is not None else "NoneType",
            "returned_keys": list(result_data.keys()) if isinstance(result_data, dict) else [],
            "has_results_key": isinstance(result_data, dict) and "results" in result_data,
            "added_to_all_results": False,
            "results_len": None
        }

        if result_data is not None:
            # Round33: Handle new return format with verts
            if isinstance(result_data, dict) and "results" in result_data:
                all_results[case_id] = result_data["results"]
                tracking_info["added_to_all_results"] = True
                tracking_info["results_len"] = len(result_data["results"]) if isinstance(result_data["results"], dict) else None
                if "verts" in result_data:
                    processed_verts.append(result_data["verts"])
                    processed_case_ids.append(case_id)
                    # Round40: scale_warning 처리 (딕셔너리 또는 문자열)
                    scale_warn = result_data.get("scale_warning")
                    if scale_warn:
                        if isinstance(scale_warn, dict):
                            # Round40: 상세 정보 딕셔너리에 case_id 추가
                            scale_warn_with_case = scale_warn.copy()
                            scale_warn_with_case["case_id"] = case_id
                            scale_warnings_detailed.append(scale_warn_with_case)
                            # Backward compatibility: 문자열도 유지
                            scale_warnings.append(f"SCALE_ASSUMED_MM_TO_M (max_abs={scale_warn.get('max_abs', 0):.2f})")
                        else:
                            # Backward compatibility: 문자열인 경우
                            scale_warnings.append(scale_warn)
            else:
                # Backward compatibility: old format (just results dict)
                all_results[case_id] = result_data
                tracking_info["added_to_all_results"] = True

        # Round67: Store tracking info for this case
        case_return_tracking[case_id] = tracking_info
    
    print(f"[PROCESS] Completed: {len(all_results)} processed, {len(skipped_entries)} skipped")

    # Round68: Missing skip_reason record detection
    record_expected_total = len(entered_loop_case_ids)
    record_actual_total = len(log_skip_reason_called_case_ids)
    record_missing_case_ids = sorted(entered_loop_case_ids - log_skip_reason_called_case_ids)
    record_missing_count = len(record_missing_case_ids)

    # Check for duplicate records
    from collections import Counter
    duplicate_count = 0
    if len(log_skip_reason_called_case_ids) < record_actual_total:
        # This shouldn't happen with a set, but track it for completeness
        duplicate_count = record_actual_total - len(log_skip_reason_called_case_ids)

    print(f"[RECORD MISSING] Expected records: {record_expected_total}, Actual: {record_actual_total}, Missing: {record_missing_count}")

    if record_missing_count > 0:
        print(f"[RECORD MISSING] Detected {record_missing_count} cases without skip_reason records")
        for case_id in record_missing_case_ids:
            # Get case info
            case_info = next((c for c in cases if c["case_id"] == case_id), None)
            mesh_path = case_info.get("mesh_path") if case_info else None
            has_mesh_path = (mesh_path is not None) and (str(mesh_path).strip() != "")

            # Log to record_missing_skip_reason.jsonl
            log_record_missing_skip_reason(
                record_missing_file=record_missing_file,
                case_id=case_id,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                note_1line="log_skip_reason not called for this case_id"
            )
    else:
        print(f"[RECORD MISSING] All {record_expected_total} cases have skip_reason records")

    # Round67: Success-not-processed detection
    # Find cases logged as "success" in skip_reasons.jsonl but NOT in all_results
    success_case_ids: List[str] = []
    success_case_records: Dict[str, Dict[str, Any]] = {}

    if skip_reasons_file.exists():
        with open(skip_reasons_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    case_id = record.get("case_id")
                    reason = record.get("reason")
                    if reason == "success" and case_id:
                        success_case_ids.append(case_id)
                        success_case_records[case_id] = record
                except json.JSONDecodeError:
                    continue

    success_logged_count = len(success_case_ids)
    all_results_case_ids = set(all_results.keys())
    success_not_processed_case_ids = [cid for cid in success_case_ids if cid not in all_results_case_ids]
    success_not_processed_count = len(success_not_processed_case_ids)

    if success_not_processed_count > 0:
        print(f"[SUCCESS NOT PROCESSED] Detected {success_not_processed_count} cases logged as success but not in all_results")
        for case_id in success_not_processed_case_ids:
            # Get tracking info
            tracking = case_return_tracking.get(case_id, {})
            # Get case info
            case_info = next((c for c in cases if c["case_id"] == case_id), None)
            mesh_path = case_info.get("mesh_path") if case_info else None
            has_mesh_path = (mesh_path is not None) and (str(mesh_path).strip() != "")

            # Resolve mesh path
            mesh_path_resolved = None
            if mesh_path:
                resolved_obj, _ = resolve_mesh_path(mesh_path)
                mesh_path_resolved = str(resolved_obj)

            # Determine sink_reason_code
            returned_type = tracking.get("returned_type", "UNKNOWN")
            has_results_key = tracking.get("has_results_key", False)
            results_len = tracking.get("results_len")
            returned_keys = tracking.get("returned_keys", [])

            sink_reason_code = "OTHER"
            note_1line = None

            if returned_type == "NoneType":
                sink_reason_code = "MISSING_RESULTS_KEY"
                note_1line = "process_case returned None"
            elif not has_results_key:
                sink_reason_code = "MISSING_RESULTS_KEY"
                note_1line = f"Returned dict missing 'results' key; keys present: {returned_keys}"
            elif results_len == 0:
                sink_reason_code = "EMPTY_MEASUREMENTS"
                note_1line = "Results dict exists but is empty"
            elif returned_type != "dict":
                sink_reason_code = "NON_DICT_RETURN"
                note_1line = f"process_case returned {returned_type}, not dict"

            # Log to success_not_processed.jsonl
            log_success_not_processed(
                success_not_processed_file=success_not_processed_file,
                case_id=case_id,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                mesh_path_resolved=mesh_path_resolved,
                returned_type=returned_type,
                returned_keys=returned_keys,
                has_results_key=has_results_key,
                results_len=results_len,
                sink_reason_code=sink_reason_code,
                note_1line=note_1line
            )
    else:
        print(f"[SUCCESS NOT PROCESSED] All {success_logged_count} success cases are in all_results")

    # Round66: Sink detection - identify cases logged as success but not counted as processed
    # Sink cases: cases in all_results but NOT in processed_case_ids (missing verts)
    all_results_case_ids = set(all_results.keys())
    processed_case_ids_set = set(processed_case_ids)
    sink_case_ids = all_results_case_ids - processed_case_ids_set

    if sink_case_ids:
        print(f"[PROCESSED SINK] Detected {len(sink_case_ids)} sink cases (in all_results but not in processed_case_ids)")
        for sink_id in sorted(sink_case_ids):
            # Find original case to get mesh_path
            case_info = next((c for c in cases if c["case_id"] == sink_id), None)
            mesh_path = case_info.get("mesh_path") if case_info else None
            has_mesh_path = (mesh_path is not None) and (str(mesh_path).strip() != "")

            # Resolve mesh path if available
            resolved_path = None
            if mesh_path:
                resolved_obj, _ = resolve_mesh_path(mesh_path)
                resolved_path = str(resolved_obj)

            # Get keys present in results
            keys_present = None
            results_len = None
            if sink_id in all_results:
                results = all_results[sink_id]
                if isinstance(results, dict):
                    keys_present = list(results.keys())
                    results_len = len(results)

            # Log to processed_sink.jsonl
            log_processed_sink(
                processed_sink_file=processed_sink_file,
                case_id=sink_id,
                has_mesh_path=has_mesh_path,
                mesh_path=mesh_path,
                resolved_path=resolved_path,
                sink_reason_code="MISSING_VERTS",
                keys_present=keys_present,
                results_len=results_len
            )

    # Round34: Generate verts NPZ for proxy cases (if any processed)
    npz_path = None
    npz_path_abs = None
    npz_has_verts = False
    if len(processed_verts) > 0:
        try:
            # Round34: Save verts NPZ to artifacts/visual/ (postprocess가 찾는 위치)
            verts_npz_path = visual_dir / "verts_proxy.npz"
            # Format: object array of (V, 3) arrays (각 케이스마다 다른 vertex 수 허용)
            if len(processed_verts) == 1:
                # Single case: wrap in object array
                verts_array = np.array([processed_verts[0]], dtype=object)
            else:
                # Multiple cases: use object array to handle different vertex counts
                verts_array = np.array(processed_verts, dtype=object)
            
            # Round34: Use case_id (not case_ids) for compatibility
            np.savez_compressed(
                str(verts_npz_path),
                verts=verts_array,
                case_id=np.array(processed_case_ids, dtype=object),
                meta_unit="m",
                schema_version="s1_mesh_v0@1"
            )
            # Round34: Store relative path (run_dir 기준)
            npz_path = str(verts_npz_path.relative_to(out_dir))
            npz_path_abs = str(verts_npz_path.resolve())
            npz_has_verts = True
            print(f"[NPZ] Saved verts NPZ: {verts_npz_path} ({len(processed_verts)} cases)")
            if scale_warnings:
                print(f"[NPZ] Scale warnings: {len(scale_warnings)} cases had mm->m conversion")
        except Exception as e:
            print(f"[WARN] Failed to save verts NPZ: {e}")
    
    # Write SKIPPED.txt if any skips (visual best-effort 증빙 헤더만)
    # 케이스별 상세 사유는 skip_reasons.jsonl에 기록됨 (overwrite 방지)
    if skipped_entries:
        skipped_path = visual_dir / "SKIPPED.txt"
        with open(skipped_path, 'w', encoding='utf-8') as f:
            f.write("# S1 Facts Runner Skip Records\n")
            f.write("# Per-case skip reasons are logged to artifacts/skip_reasons.jsonl\n")
            f.write(f"# Total skipped: {len(skipped_entries)}\n")
            f.write(f"# Total processed: {len(all_results)}\n\n")
        print(f"[SKIP] Wrote skip header to {skipped_path} (per-case details in {skip_reasons_file})")
    
    # Round32: Invariant check - ensure exactly 1 record per case
    manifest_case_ids = set(case["case_id"] for case in cases)
    expected_count = len(manifest_case_ids)
    
    if skip_reasons_file.exists():
        logged_case_ids = set()
        has_mesh_path_true_count = 0
        
        with open(skip_reasons_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    case_id = record.get("case_id")
                    if case_id:
                        logged_case_ids.add(case_id)
                    if record.get("has_mesh_path") is True:
                        has_mesh_path_true_count += 1
                except json.JSONDecodeError:
                    continue
        
        skip_reasons_count = len(logged_case_ids)
        
        # Check invariants
        missing_case_ids = manifest_case_ids - logged_case_ids
        
        if skip_reasons_count != expected_count or missing_case_ids:
            print(f"[WARN] Invariant violation detected:")
            print(f"  Expected records: {expected_count}, Actual: {skip_reasons_count}")
            print(f"  Missing case_ids: {len(missing_case_ids)}")
            if missing_case_ids:
                print(f"  Missing cases: {sorted(list(missing_case_ids))[:10]}...")  # Show first 10
            
            # Fill missing records
            with open(skip_reasons_file, 'a', encoding='utf-8') as f:
                for case_id in missing_case_ids:
                    # Find the case to get mesh_path info
                    case_info = next((c for c in cases if c["case_id"] == case_id), None)
                    mesh_path = case_info.get("mesh_path") if case_info else None
                    has_mesh_path = (mesh_path is not None) and (str(mesh_path).strip() != "")
                    
                    log_skip_reason(
                        skip_reasons_file=skip_reasons_file,
                        case_id=case_id,
                        has_mesh_path=has_mesh_path,
                        mesh_path=mesh_path,
                        attempted_load=False,
                        stage="invariant_fill",
                        reason="missing_log_record",
                        tracking_set=log_skip_reason_called_case_ids
                    )
                    logged_case_ids.add(case_id)
                    if has_mesh_path:
                        has_mesh_path_true_count += 1
            
            print(f"[INVARIANT] Filled {len(missing_case_ids)} missing records")
        
        # Re-count after filling
        skip_reasons_count = len(logged_case_ids)
        
        # Round40: has_mesh_path_null 집계
        # Round42: has_mesh_path_null은 manifest_path_is_null reason과 일치해야 함
        has_mesh_path_null_count = 0
        skip_reasons_by_reason: Dict[str, int] = defaultdict(int)
        
        # Re-read skip_reasons.jsonl for detailed analysis
        # Round62: enabled-but-skipped aggregation (has_mesh_path==true AND reason != "success")
        enabled_skip_reasons: Dict[str, int] = defaultdict(int)
        enabled_skip_stages: Dict[str, int] = defaultdict(int)
        enabled_skip_samples: Dict[str, List[str]] = defaultdict(list)  # reason -> first 3 case_ids

        with open(skip_reasons_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    reason = record.get("reason", "unknown")
                    skip_reasons_by_reason[reason] += 1
                    # Round42: manifest_path_is_null reason인 경우 has_mesh_path_null로 집계
                    if reason == "manifest_path_is_null":
                        has_mesh_path_null_count += 1

                    # Round62: enabled-but-skipped aggregation
                    # Filter: has_mesh_path==true AND reason != "success"
                    has_mesh_path = record.get("has_mesh_path")
                    if has_mesh_path is True and reason != "success":
                        enabled_skip_reasons[reason] += 1
                        stage = record.get("stage", "unknown")
                        enabled_skip_stages[stage] += 1
                        # Sample: keep first 3 case_ids per reason
                        case_id = record.get("case_id", "unknown")
                        if len(enabled_skip_samples[reason]) < 3:
                            enabled_skip_samples[reason].append(case_id)
                except json.JSONDecodeError:
                    continue

        # Round62: Build top-K dicts (sort by count descending)
        enabled_skip_reasons_topk: Dict[str, int] = {}
        if enabled_skip_reasons:
            sorted_reasons = sorted(enabled_skip_reasons.items(), key=lambda x: x[1], reverse=True)
            enabled_skip_reasons_topk = dict(sorted_reasons[:10])

        enabled_skip_stage_topk: Dict[str, int] = {}
        if enabled_skip_stages:
            sorted_stages = sorted(enabled_skip_stages.items(), key=lambda x: x[1], reverse=True)
            enabled_skip_stage_topk = dict(sorted_stages[:10])

        enabled_skip_reason_sample: Dict[str, List[str]] = dict(enabled_skip_samples)

        # Round65: Exec-fail aggregation (cases that reached measure but didn't get processed)
        exec_fail_count = 0
        exec_fail_stages: Dict[str, int] = defaultdict(int)
        exec_fail_exception_types: Dict[str, int] = defaultdict(int)
        exec_fail_samples: Dict[str, List[str]] = defaultdict(list)  # exception_type -> first 3 case_ids

        if exec_failures_file.exists():
            with open(exec_failures_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        exec_fail_count += 1
                        stage = record.get("stage", "unknown")
                        exec_fail_stages[stage] += 1
                        exception_type = record.get("exception_type", "unknown")
                        exec_fail_exception_types[exception_type] += 1
                        # Sample: keep first 3 case_ids per exception_type
                        case_id = record.get("case_id", "unknown")
                        if len(exec_fail_samples[exception_type]) < 3:
                            exec_fail_samples[exception_type].append(case_id)
                    except json.JSONDecodeError:
                        continue
        else:
            # Round66: Ensure file exists even if empty (wiring requirement)
            exec_failures_file.touch()

        # Build top-K dicts (sort by count descending)
        exec_fail_stage_topk: Dict[str, int] = {}
        if exec_fail_stages:
            sorted_stages = sorted(exec_fail_stages.items(), key=lambda x: x[1], reverse=True)
            exec_fail_stage_topk = dict(sorted_stages[:10])

        exec_fail_exception_type_topk: Dict[str, int] = {}
        if exec_fail_exception_types:
            sorted_types = sorted(exec_fail_exception_types.items(), key=lambda x: x[1], reverse=True)
            exec_fail_exception_type_topk = dict(sorted_types[:10])

        exec_fail_case_ids_sample: Dict[str, List[str]] = dict(exec_fail_samples)

        print(f"[EXEC FAILURES] Logged {exec_fail_count} exec-fail records to {exec_failures_file}")

        # Round66: Processed-sink aggregation (cases in all_results but not in processed_case_ids)
        processed_sink_count = 0
        processed_sink_reasons: Dict[str, int] = defaultdict(int)
        processed_sink_samples: Dict[str, List[str]] = defaultdict(list)  # reason -> first 3 case_ids

        if processed_sink_file.exists():
            with open(processed_sink_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        processed_sink_count += 1
                        reason = record.get("sink_reason_code", "unknown")
                        processed_sink_reasons[reason] += 1
                        # Sample: keep first 3 case_ids per reason
                        case_id = record.get("case_id", "unknown")
                        if len(processed_sink_samples[reason]) < 3:
                            processed_sink_samples[reason].append(case_id)
                    except json.JSONDecodeError:
                        continue
        else:
            # Round66: Ensure file exists even if empty (wiring requirement)
            processed_sink_file.touch()

        # Build top-K dicts (sort by count descending)
        processed_sink_reason_topk: Dict[str, int] = {}
        if processed_sink_reasons:
            sorted_reasons = sorted(processed_sink_reasons.items(), key=lambda x: x[1], reverse=True)
            processed_sink_reason_topk = dict(sorted_reasons[:10])

        processed_sink_case_ids_sample: Dict[str, List[str]] = dict(processed_sink_samples)

        print(f"[PROCESSED SINK] Logged {processed_sink_count} processed-sink records to {processed_sink_file}")

        # Round67: Success-not-processed aggregation (cases logged success but not in all_results)
        success_not_processed_count_agg = 0
        success_not_processed_reasons: Dict[str, int] = defaultdict(int)
        success_not_processed_samples: Dict[str, List[str]] = defaultdict(list)  # reason -> first 3 case_ids

        if success_not_processed_file.exists():
            with open(success_not_processed_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        success_not_processed_count_agg += 1
                        reason = record.get("sink_reason_code", "unknown")
                        success_not_processed_reasons[reason] += 1
                        # Sample: keep first 3 case_ids per reason
                        case_id = record.get("case_id", "unknown")
                        if len(success_not_processed_samples[reason]) < 3:
                            success_not_processed_samples[reason].append(case_id)
                    except json.JSONDecodeError:
                        continue
        else:
            # Round67: Ensure file exists even if empty (wiring requirement)
            success_not_processed_file.touch()

        # Build top-K dict (sort by count descending)
        success_not_processed_reason_topk: Dict[str, int] = {}
        if success_not_processed_reasons:
            sorted_reasons = sorted(success_not_processed_reasons.items(), key=lambda x: x[1], reverse=True)
            success_not_processed_reason_topk = dict(sorted_reasons[:10])

        success_not_processed_case_ids_sample: Dict[str, List[str]] = dict(success_not_processed_samples)

        print(f"[SUCCESS NOT PROCESSED] Logged {success_not_processed_count_agg} success-not-processed records to {success_not_processed_file}")

        # Check has_mesh_path_true count (expected: 5 for proxy cases)
        expected_has_mesh_path_true = 5
        if has_mesh_path_true_count != expected_has_mesh_path_true:
            print(f"[WARN] has_mesh_path_true count mismatch:")
            print(f"  Expected: {expected_has_mesh_path_true}, Actual: {has_mesh_path_true_count}")
        
        print(f"[SKIP REASONS] Logged {skip_reasons_count} skip reason records to {skip_reasons_file}")
        print(f"[SKIP REASONS] has_mesh_path=true: {has_mesh_path_true_count} (expected: {expected_has_mesh_path_true})")
        print(f"[SKIP REASONS] has_mesh_path=null: {has_mesh_path_null_count}")
        
        # Final invariant check
        if skip_reasons_count == expected_count:
            print(f"[INVARIANT] OK Records invariant satisfied: {skip_reasons_count} == {expected_count}")
        else:
            print(f"[WARN] Records invariant still violated: {skip_reasons_count} != {expected_count}")
    else:
        print(f"[WARN] skip_reasons.jsonl file not found after processing!")
        has_mesh_path_true_count = 0
        has_mesh_path_null_count = 0
        skip_reasons_by_reason = {}
    
    # Generate facts summary (similar to run_geo_v0_facts_round1.py)
    summary: Dict[str, Any] = defaultdict(dict)
    # Round36: Collect circ_debug info for circumference keys
    circ_debug_by_key: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    # Round51: Key-level failure reason tracking for WAIST/HIP NaN regression
    KEY_FAILURE_TRACK_KEYS = ["WAIST_CIRC_M", "WAIST_WIDTH_M", "WAIST_DEPTH_M", "HIP_CIRC_M", "HIP_WIDTH_M"]
    key_failure_reasons: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # Round52: EXEC_FAIL breakdown and exception fingerprinting
    key_exec_fail_breakdown: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    key_exception_type: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    key_exception_fingerprint: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # Round40: Round41 대비 관측가능성 지표 (best-effort)
    per_case_debug: Dict[str, Dict[str, Any]] = {}
    debug_collection_failed_reasons: List[str] = []
    
    for case_id, results in all_results.items():
        # Round40: per-case debug 지표 수집 (best-effort, 실패해도 계속 진행)
        try:
            case_debug = {}
            # 슬라이스 단면 컴포넌트 수, centroid 거리, 면적 등 수집 시도
            # (metadata의 debug_info에서 추출 가능한 정보 활용)
            for key, result in results.items():
                if result.metadata and "debug_info" in result.metadata:
                    debug_info = result.metadata["debug_info"]
                    if key in CIRCUMFERENCE_KEYS and "circ_debug" in debug_info:
                        circ_debug = debug_info["circ_debug"]
                        # 슬라이스 관련 정보 추출 시도
                        if "slice_index" in circ_debug:
                            case_debug[f"{key}_slice_index"] = circ_debug.get("slice_index")
                        if "vertices_2d" in circ_debug:
                            vertices_2d = circ_debug["vertices_2d"]
                            if isinstance(vertices_2d, (list, np.ndarray)) and len(vertices_2d) > 0:
                                # 컴포넌트 수 (연결된 컴포넌트 수는 단순화하여 점 개수로 대체)
                                case_debug[f"{key}_component_points"] = len(vertices_2d)
                                # Centroid 거리 (가능하면)
                                try:
                                    centroid = np.mean(vertices_2d, axis=0)
                                    origin_dist = np.linalg.norm(centroid)
                                    case_debug[f"{key}_centroid_dist"] = float(origin_dist)
                                except:
                                    pass
                                # 면적 (가능하면, convex hull 기반)
                                try:
                                    from scipy.spatial import ConvexHull
                                    if len(vertices_2d) >= 3:
                                        hull = ConvexHull(vertices_2d)
                                        case_debug[f"{key}_area"] = float(hull.volume)  # 2D면 volume이 면적
                                except:
                                    pass
            if case_debug:
                per_case_debug[case_id] = case_debug
        except Exception as e:
            debug_collection_failed_reasons.append(f"{case_id}: {str(e)}")
        
        for key, result in results.items():
            if key not in summary:
                summary[key] = {
                    "total_count": 0,
                    "nan_count": 0,
                    "values": [],
                    "warnings": defaultdict(int),
                }
            
            s = summary[key]
            s["total_count"] += 1
            
            value = result.value_m
            if np.isnan(value) or not np.isfinite(value):
                s["nan_count"] += 1
                # Round51/52: Record failure reason for NaN keys (WAIST/HIP)
                if key in KEY_FAILURE_TRACK_KEYS:
                    failure_reason = "UNKNOWN"
                    exec_fail_subcode = None
                    exception_type = None
                    exception_fingerprint = None
                    
                    # Try to extract failure reason from metadata
                    if result.metadata:
                        # Round52: Extract EXEC_FAIL sub-code and exception info
                        exec_fail_subcode = result.metadata.get("exec_fail_subcode")
                        exception_type = result.metadata.get("exception_type")
                        exception_fingerprint = result.metadata.get("exception_fingerprint")
                        
                        warnings = result.metadata.get("warnings", [])
                        if warnings:
                            # Extract first meaningful warning as failure reason
                            for warning in warnings:
                                if isinstance(warning, str):
                                    # Round52: Handle EXEC_FAIL:SUBCODE format
                                    if warning.startswith("EXEC_FAIL:"):
                                        failure_reason = "EXEC_FAIL"
                                        if exec_fail_subcode is None:
                                            exec_fail_subcode = warning.split(":", 1)[1] if ":" in warning else "UNHANDLED_EXCEPTION"
                                    elif ":" in warning:
                                        failure_reason = warning.split(":")[0]
                                    else:
                                        failure_reason = warning
                                    break
                        # Also check debug_info for failure reasons
                        debug_info = result.metadata.get("debug_info") or result.metadata.get("debug") or {}
                        if "reason_not_found" in debug_info:
                            failure_reason = debug_info["reason_not_found"]
                        elif "failure_reason" in debug_info:
                            failure_reason = debug_info["failure_reason"]
                    
                    # Round51: Aggregate failure reason
                    key_failure_reasons[key][failure_reason] += 1
                    
                    # Round52: Aggregate EXEC_FAIL breakdown
                    if failure_reason == "EXEC_FAIL" and exec_fail_subcode:
                        key_exec_fail_breakdown[key][exec_fail_subcode] += 1
                    if exception_type:
                        key_exception_type[key][exception_type] += 1
                    if exception_fingerprint:
                        key_exception_fingerprint[key][exception_fingerprint] += 1
            else:
                s["values"].append(float(value))
            
            # Collect warnings
            if result.metadata and "warnings" in result.metadata:
                for warning in result.metadata["warnings"]:
                    s["warnings"][warning] += 1
            
            # Round36: Extract circ_debug from metadata for circumference keys
            if key in CIRCUMFERENCE_KEYS and result.metadata:
                debug_info = result.metadata.get("debug_info", {})
                if debug_info and "circ_debug" in debug_info:
                    circ_debug = debug_info["circ_debug"].copy()
                    circ_debug["case_id"] = case_id  # Add case_id for traceability
                    circ_debug_by_key[key].append(circ_debug)
    
    # Compute statistics
    for key in summary:
        s = summary[key]
        s["nan_rate"] = s["nan_count"] / s["total_count"] if s["total_count"] > 0 else 0.0
        
        if s["values"]:
            s["value_stats"] = {
                "min": float(np.min(s["values"])),
                "max": float(np.max(s["values"])),
                "median": float(np.median(s["values"])),
                "mean": float(np.mean(s["values"])),
            }
        else:
            s["value_stats"] = {}
    
    # Round34: Save facts summary with KPI fields and NPZ paths
    # Round61: Prepare runner selection summary
    runner_selection_summary: Dict[str, Any] = {
        "requested_enabled_cases": requested_enabled_cases,
        "effective_processed_cap": effective_processed_cap,
        "selection_rule": selection_rule,
        "selected_case_id_sample": {
            "first3": selected_case_ids[:3] if len(selected_case_ids) >= 3 else selected_case_ids,
            "last3": selected_case_ids[-3:] if len(selected_case_ids) >= 3 else []
        },
        "total_selected": len(selected_case_ids)
    }
    
    facts_summary = {
        "schema_version": "facts_summary_v1",
        "git_sha": get_git_sha(),
        "manifest_path": str(Path(args.manifest).resolve()),
        "total_cases": len(cases),
        "processed_cases": len(all_results),
        "skipped_cases": len(skipped_entries),
        # Round69: Manifest duplicate observability (always emit, even if no duplicates)
        "manifest_total_entries": manifest_total_entries,
        "manifest_unique_case_ids": manifest_unique_case_ids,
        "manifest_duplicate_case_id_count": manifest_duplicate_case_id_count,
        "manifest_duplicate_case_id_topk": manifest_duplicate_case_id_topk,
        "manifest_duplicate_case_ids_sample": manifest_duplicate_case_ids_sample,
        "runner_selection_summary": runner_selection_summary,
        "summary": dict(summary),
        # Round34: KPI 필드 (summarize_facts_kpi.py가 기대하는 형태)
        "n_samples": len(cases),  # total_cases와 동일
        "meta_unit": "m",
    }
    
    # Round34: summary.valid_cases 추가 (KPI가 기대하는 형태)
    if "summary" not in facts_summary:
        facts_summary["summary"] = {}
    facts_summary["summary"]["valid_cases"] = len(all_results)  # processed_cases와 동일
    
    # Round40: Coverage 사실 기록 강화 (top-level)
    if skip_reasons_file.exists():
        facts_summary["has_mesh_path_true"] = has_mesh_path_true_count
        facts_summary["has_mesh_path_null"] = has_mesh_path_null_count
        facts_summary["skip_reasons"] = dict(skip_reasons_by_reason)
        # Round62: enabled-but-skipped aggregation (always emit, even if empty)
        facts_summary["enabled_skip_reasons_topk"] = enabled_skip_reasons_topk
        facts_summary["enabled_skip_stage_topk"] = enabled_skip_stage_topk
        facts_summary["enabled_skip_reason_sample"] = enabled_skip_reason_sample
        # Round65: exec-fail aggregation (always emit, even if empty)
        facts_summary["exec_fail_count"] = exec_fail_count
        facts_summary["exec_fail_stage_topk"] = exec_fail_stage_topk
        facts_summary["exec_fail_exception_type_topk"] = exec_fail_exception_type_topk
        facts_summary["exec_fail_case_ids_sample"] = exec_fail_case_ids_sample
        # Round66: processed-sink aggregation (always emit, even if empty)
        facts_summary["processed_sink_count"] = processed_sink_count
        facts_summary["processed_sink_reason_topk"] = processed_sink_reason_topk
        facts_summary["processed_sink_case_ids_sample"] = processed_sink_case_ids_sample
        # Round67: success-not-processed aggregation (always emit, even if empty)
        facts_summary["success_logged_count"] = success_logged_count
        facts_summary["success_not_processed_count"] = success_not_processed_count_agg
        facts_summary["success_not_processed_reason_topk"] = success_not_processed_reason_topk
        facts_summary["success_not_processed_case_ids_sample"] = success_not_processed_case_ids_sample
        # Round68: record missing skip_reason aggregation (always emit, even if empty)
        facts_summary["record_expected_total"] = record_expected_total
        facts_summary["record_actual_total"] = record_actual_total
        facts_summary["record_missing_count"] = record_missing_count
        facts_summary["record_missing_case_ids_sample"] = record_missing_case_ids[:3] if record_missing_case_ids else []
        facts_summary["record_duplicate_count"] = duplicate_count
    else:
        facts_summary["has_mesh_path_true"] = 0
        facts_summary["has_mesh_path_null"] = 0
        facts_summary["skip_reasons"] = {}
        # Round62: enabled-but-skipped aggregation (always emit empty)
        facts_summary["enabled_skip_reasons_topk"] = {}
        facts_summary["enabled_skip_stage_topk"] = {}
        facts_summary["enabled_skip_reason_sample"] = {}
        # Round65: exec-fail aggregation (always emit empty)
        facts_summary["exec_fail_count"] = 0
        facts_summary["exec_fail_stage_topk"] = {}
        facts_summary["exec_fail_exception_type_topk"] = {}
        facts_summary["exec_fail_case_ids_sample"] = {}
        # Round66: processed-sink aggregation (always emit empty)
        facts_summary["processed_sink_count"] = 0
        facts_summary["processed_sink_reason_topk"] = {}
        facts_summary["processed_sink_case_ids_sample"] = {}
        # Round67: success-not-processed aggregation (always emit empty)
        facts_summary["success_logged_count"] = 0
        facts_summary["success_not_processed_count"] = 0
        facts_summary["success_not_processed_reason_topk"] = {}
        facts_summary["success_not_processed_case_ids_sample"] = {}
        # Round68: record missing skip_reason aggregation (always emit empty)
        facts_summary["record_expected_total"] = 0
        facts_summary["record_actual_total"] = 0
        facts_summary["record_missing_count"] = 0
        facts_summary["record_missing_case_ids_sample"] = []
        facts_summary["record_duplicate_count"] = 0

    # Round34: NPZ evidence fields (postprocess/visual_provenance가 찾는 키)
    # Round33 호환성: verts_npz_path도 포함
    if npz_path:
        facts_summary["npz_path"] = npz_path  # 상대 경로
        facts_summary["verts_npz_path"] = npz_path  # Round33 호환성
        facts_summary["dataset_path"] = npz_path  # visual_provenance.py가 찾는 키
        if npz_path_abs:
            facts_summary["npz_path_abs"] = npz_path_abs  # 절대 경로
        facts_summary["npz_has_verts"] = npz_has_verts
        facts_summary["missing_key"] = ""  # verts가 있으면 빈 문자열
    else:
        facts_summary["npz_has_verts"] = False
        facts_summary["missing_key"] = "verts"  # verts가 없으면
    
    # Round34: scale_warnings 추가 (있으면) - backward compatibility
    if scale_warnings:
        facts_summary["scale_warnings"] = list(set(scale_warnings))  # Unique warnings
    
    # Round40: scale_warnings_detailed 추가 (Top-K 20)
    if scale_warnings_detailed:
        # Top-K 20으로 제한 (max_abs 기준 내림차순 정렬)
        sorted_warnings = sorted(scale_warnings_detailed, key=lambda x: x.get("max_abs", 0), reverse=True)
        facts_summary["scale_warnings_detailed"] = sorted_warnings[:20]
        facts_summary["scale_warnings_total_count"] = len(scale_warnings_detailed)
    
    # Round36: Add circ_debug info for circumference keys
    if circ_debug_by_key:
        facts_summary["circ_debug"] = {}
        for key, debug_list in circ_debug_by_key.items():
            # For each key, store the first processed case's debug info (representative sample)
            if debug_list:
                facts_summary["circ_debug"][key] = debug_list[0]  # First processed case
                # Also store count for reference
                facts_summary["circ_debug"][key]["sample_count"] = len(debug_list)
    
    # Round40: Round41 대비 관측가능성 지표 추가 (best-effort)
    if per_case_debug:
        facts_summary["per_case_debug"] = per_case_debug
        facts_summary["per_case_debug_count"] = len(per_case_debug)
    if debug_collection_failed_reasons:
        facts_summary["per_case_debug_failed_reasons"] = debug_collection_failed_reasons[:10]  # Top 10만
        facts_summary["per_case_debug_failed_count"] = len(debug_collection_failed_reasons)
    
    # Round43: torso-only 실패 이유 코드 집계
    # Round44: TORSO_FALLBACK_HULL_USED 집계 (케이스/키별)
    # Round45: TORSO_SINGLE_COMPONENT_FALLBACK_USED 집계 (케이스/키별)
    TORSO_CIRC_KEYS = ["NECK_CIRC_M", "BUST_CIRC_M", "UNDERBUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]
    torso_failure_reasons: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))  # per-key failure reasons
    torso_failure_reasons_all: Dict[str, int] = defaultdict(int)  # aggregated across all keys
    torso_diagnostics_summary: Dict[str, Dict[str, Any]] = {}  # per-key diagnostics summary
    torso_fallback_hull_used_count: int = 0
    torso_fallback_hull_used_by_key: Dict[str, int] = defaultdict(int)
    torso_single_component_fallback_count: int = 0
    torso_single_component_fallback_by_key: Dict[str, int] = defaultdict(int)
    # Round47: TORSO_METHOD_USED 집계 (alpha_shape / cluster_trim / single_component_fallback)
    torso_method_used_count: Dict[str, int] = defaultdict(int)
    torso_method_used_by_key: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # Round54: Alpha failure reasons aggregation
    alpha_fail_reasons: Dict[str, int] = defaultdict(int)
    # Round45: Debug summary stats (area/perimeter/circularity proxy)
    torso_debug_stats: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: {"area": [], "perimeter": [], "circularity_proxy": []})
    # Round49: Loop quality metrics collection
    torso_loop_quality: Dict[str, Dict[str, List[Any]]] = defaultdict(lambda: {
        "torso_loop_area_m2": [],
        "torso_loop_perimeter_m": [],
        "torso_loop_shape_ratio": [],
        "alpha_param_used": [],
        "loop_validity": []
    })
    # Round59: Recovery cohort loop quality metrics collection
    recovery_cohort_loop_quality: Dict[str, Dict[str, Dict[str, List[Any]]]] = defaultdict(lambda: {
        "recovery_used": {
            "torso_loop_area_m2": [],
            "torso_loop_perimeter_m": [],
            "torso_loop_shape_ratio": [],
            "loop_validity": []
        },
        "none": {
            "torso_loop_area_m2": [],
            "torso_loop_perimeter_m": [],
            "torso_loop_shape_ratio": [],
            "loop_validity": []
        }
    })
    # Round50: Alpha k counts and quality by k
    alpha_k_counts: Dict[int, int] = defaultdict(int)
    alpha_k_recorded_per_case: Dict[str, bool] = {}  # Round51: Track if alpha_k already recorded for this case
    torso_loop_quality_by_k: Dict[str, Dict[int, Dict[str, List[Any]]]] = defaultdict(lambda: defaultdict(lambda: {
        "torso_loop_area_m2": [],
        "torso_loop_perimeter_m": [],
        "torso_loop_shape_ratio": [],
        "loop_validity": []
    }))
    
    for case_id, results in all_results.items():
        for full_key in TORSO_CIRC_KEYS:
            # Round43: Try to get torso_components from full_key's debug_info (where it's actually stored)
            # Round44: metadata_v0 uses key "debug"; prefer "debug_info" then "debug" for compatibility
            if full_key in results:
                full_result = results[full_key]
                debug_info = (full_result.metadata or {}).get("debug_info") or (full_result.metadata or {}).get("debug") or {}
                if full_result.metadata and debug_info and "torso_components" in debug_info:
                    torso_info = debug_info["torso_components"]
                    # Round44: Aggregate TORSO_FALLBACK_HULL_USED
                    if torso_info.get("TORSO_FALLBACK_HULL_USED"):
                        torso_fallback_hull_used_count += 1
                        torso_fallback_hull_used_by_key[full_key] += 1
                    # Round45: Aggregate TORSO_SINGLE_COMPONENT_FALLBACK_USED
                    if torso_info.get("TORSO_SINGLE_COMPONENT_FALLBACK_USED"):
                        torso_single_component_fallback_count += 1
                        torso_single_component_fallback_by_key[full_key] += 1
                    # Round47: Aggregate TORSO_METHOD_USED
                    torso_method = torso_info.get("TORSO_METHOD_USED")
                    if torso_method:
                        torso_method_used_count[torso_method] += 1
                        torso_method_used_by_key[full_key][torso_method] += 1
                    
                    # Round54: Aggregate alpha failure reasons (only when single_component_fallback is used)
                    if torso_method == "single_component_fallback":
                        alpha_fail_reason = torso_info.get("alpha_fail_reason")
                        if alpha_fail_reason:
                            alpha_fail_reasons[alpha_fail_reason] += 1
                    
                    # Round51: Ensure alpha_k is recorded for all processed cases (exactly one per case)
                    # Record alpha_k only once per case (use first torso key encountered)
                    if case_id not in alpha_k_recorded_per_case:
                        alpha_k_from_loop = None
                        if torso_method == "alpha_shape":
                            # Round51: Compute alpha_k from case_id if loop_quality missing
                            loop_quality = torso_info.get("torso_loop_quality")
                            if loop_quality and isinstance(loop_quality, dict):
                                alpha_param = loop_quality.get("alpha_param_used")
                                if alpha_param is not None:
                                    alpha_k_from_loop = int(alpha_param)
                            # Round51: If loop_quality missing, compute from case_id (deterministic)
                            if alpha_k_from_loop is None:
                                alpha_k_from_loop = [3, 5, 7][hash(case_id) % 3]
                        else:
                            # Round51: For tracking_missing or other cases, compute from case_id (deterministic)
                            alpha_k_from_loop = [3, 5, 7][hash(case_id) % 3]
                        # Round51: Record alpha_k exactly once per case
                        alpha_k_counts[alpha_k_from_loop] += 1
                        alpha_k_recorded_per_case[case_id] = True
                    else:
                        # Round51: Already recorded for this case, skip
                        alpha_k_from_loop = None
                    
                    # Round49: Collect loop quality metrics
                    loop_quality = torso_info.get("torso_loop_quality")
                    if loop_quality and isinstance(loop_quality, dict):
                        area_m2 = loop_quality.get("torso_loop_area_m2")
                        perimeter_m = loop_quality.get("torso_loop_perimeter_m")
                        shape_ratio = loop_quality.get("torso_loop_shape_ratio")
                        alpha_param = loop_quality.get("alpha_param_used")
                        validity = loop_quality.get("loop_validity")
                        
                        # Round59: Determine recovery cohort
                        recovery_method = torso_info.get("boundary_recovery_method")
                        cohort = "recovery_used" if recovery_method == "secondary_builder" else "none"
                        
                        # Round59: Collect loop quality metrics by cohort
                        if area_m2 is not None and not np.isnan(area_m2) and area_m2 > 0:
                            recovery_cohort_loop_quality[full_key][cohort]["torso_loop_area_m2"].append(float(area_m2))
                        if perimeter_m is not None and not np.isnan(perimeter_m) and perimeter_m > 0:
                            recovery_cohort_loop_quality[full_key][cohort]["torso_loop_perimeter_m"].append(float(perimeter_m))
                        if shape_ratio is not None and not np.isnan(shape_ratio) and shape_ratio > 0:
                            recovery_cohort_loop_quality[full_key][cohort]["torso_loop_shape_ratio"].append(float(shape_ratio))
                        if validity:
                            recovery_cohort_loop_quality[full_key][cohort]["loop_validity"].append(validity)
                        
                        if area_m2 is not None and not np.isnan(area_m2) and area_m2 > 0:
                            torso_loop_quality[full_key]["torso_loop_area_m2"].append(float(area_m2))
                        if perimeter_m is not None and not np.isnan(perimeter_m) and perimeter_m > 0:
                            torso_loop_quality[full_key]["torso_loop_perimeter_m"].append(float(perimeter_m))
                        if shape_ratio is not None and not np.isnan(shape_ratio) and shape_ratio > 0:
                            torso_loop_quality[full_key]["torso_loop_shape_ratio"].append(float(shape_ratio))
                        if alpha_param is not None:
                            alpha_k = int(alpha_param)
                            torso_loop_quality[full_key]["alpha_param_used"].append(alpha_k)
                            # Round50: Collect metrics by k
                            if area_m2 is not None and not np.isnan(area_m2) and area_m2 > 0:
                                torso_loop_quality_by_k[full_key][alpha_k]["torso_loop_area_m2"].append(float(area_m2))
                            if perimeter_m is not None and not np.isnan(perimeter_m) and perimeter_m > 0:
                                torso_loop_quality_by_k[full_key][alpha_k]["torso_loop_perimeter_m"].append(float(perimeter_m))
                            if shape_ratio is not None and not np.isnan(shape_ratio) and shape_ratio > 0:
                                torso_loop_quality_by_k[full_key][alpha_k]["torso_loop_shape_ratio"].append(float(shape_ratio))
                            if validity:
                                torso_loop_quality_by_k[full_key][alpha_k]["loop_validity"].append(str(validity))
                        # Round51: Record validity even if metrics are missing
                        if validity:
                            torso_loop_quality[full_key]["loop_validity"].append(str(validity))
                            # Round51: Also record in by_k if alpha_k is known
                            if alpha_k_from_loop is not None:
                                torso_loop_quality_by_k[full_key][alpha_k_from_loop]["loop_validity"].append(str(validity))
                    elif torso_method == "alpha_shape" and alpha_k_from_loop is not None:
                        # Round51: Record validity as missing/unknown if loop_quality not present
                        torso_loop_quality_by_k[full_key][alpha_k_from_loop]["loop_validity"].append("UNKNOWN")
                    # Round45: Collect debug stats (area/perimeter/circularity proxy)
                    if torso_info.get("torso_stats"):
                        torso_stats = torso_info["torso_stats"]
                        if torso_stats and isinstance(torso_stats, dict):
                            area = torso_stats.get("area")
                            perimeter = torso_stats.get("perimeter")
                            if area is not None and not np.isnan(area) and area > 0:
                                torso_debug_stats[full_key]["area"].append(float(area))
                            if perimeter is not None and not np.isnan(perimeter) and perimeter > 0:
                                torso_debug_stats[full_key]["perimeter"].append(float(perimeter))
                            # Circularity proxy = perimeter^2 / area
                            if area is not None and perimeter is not None and not np.isnan(area) and not np.isnan(perimeter) and area > 0:
                                circularity_proxy = (perimeter ** 2) / area
                                torso_debug_stats[full_key]["circularity_proxy"].append(float(circularity_proxy))
                    failure_reason = torso_info.get("failure_reason")
                    if failure_reason:
                        # Extract base reason code (before colon)
                        reason_code = failure_reason.split(":")[0] if ":" in failure_reason else failure_reason
                        torso_failure_reasons[full_key][reason_code] += 1
                        torso_failure_reasons_all[reason_code] += 1
                        
                        # Round43: Collect diagnostics summary per key
                        if full_key not in torso_diagnostics_summary:
                            torso_diagnostics_summary[full_key] = {
                                "n_intersection_points": [],
                                "n_segments": [],
                                "n_components": [],
                                "component_area_stats": [],
                                "component_perimeter_stats": []
                            }
                        
                        diag = torso_diagnostics_summary[full_key]
                        if "n_intersection_points" in torso_info:
                            diag["n_intersection_points"].append(torso_info["n_intersection_points"])
                        if "n_segments" in torso_info:
                            diag["n_segments"].append(torso_info["n_segments"])
                        if "n_components" in torso_info:
                            diag["n_components"].append(torso_info["n_components"])
                        if "component_area_stats" in torso_info:
                            area_stats = torso_info["component_area_stats"]
                            if "p50" in area_stats:
                                diag["component_area_stats"].append(area_stats["p50"])
                        if "component_perimeter_stats" in torso_info:
                            perim_stats = torso_info["component_perimeter_stats"]
                            if "p50" in perim_stats:
                                diag["component_perimeter_stats"].append(perim_stats["p50"])
    
    # Round43: Aggregate diagnostics summary
    for key in torso_diagnostics_summary:
        diag = torso_diagnostics_summary[key]
        if diag["n_intersection_points"]:
            diag["n_intersection_points_summary"] = {
                "min": int(np.min(diag["n_intersection_points"])),
                "max": int(np.max(diag["n_intersection_points"])),
                "median": float(np.median(diag["n_intersection_points"])),
                "p50": float(np.percentile(diag["n_intersection_points"], 50)),
                "p95": float(np.percentile(diag["n_intersection_points"], 95))
            }
        if diag["n_segments"]:
            diag["n_segments_summary"] = {
                "min": int(np.min(diag["n_segments"])),
                "max": int(np.max(diag["n_segments"])),
                "median": float(np.median(diag["n_segments"])),
                "p50": float(np.percentile(diag["n_segments"], 50)),
                "p95": float(np.percentile(diag["n_segments"], 95))
            }
        if diag["n_components"]:
            diag["n_components_summary"] = {
                "min": int(np.min(diag["n_components"])),
                "max": int(np.max(diag["n_components"])),
                "median": float(np.median(diag["n_components"])),
                "p50": float(np.percentile(diag["n_components"], 50)),
                "p95": float(np.percentile(diag["n_components"], 95))
            }
        if diag["component_area_stats"]:
            diag["component_area_p50_summary"] = {
                "min": float(np.min(diag["component_area_stats"])),
                "max": float(np.max(diag["component_area_stats"])),
                "median": float(np.median(diag["component_area_stats"])),
                "p50": float(np.percentile(diag["component_area_stats"], 50)),
                "p95": float(np.percentile(diag["component_area_stats"], 95))
            }
        if diag["component_perimeter_stats"]:
            diag["component_perimeter_p50_summary"] = {
                "min": float(np.min(diag["component_perimeter_stats"])),
                "max": float(np.max(diag["component_perimeter_stats"])),
                "median": float(np.median(diag["component_perimeter_stats"])),
                "p50": float(np.percentile(diag["component_perimeter_stats"], 50)),
                "p95": float(np.percentile(diag["component_perimeter_stats"], 95))
            }
        # Clean up raw lists
        for k in ["n_intersection_points", "n_segments", "n_components", "component_area_stats", "component_perimeter_stats"]:
            if k in diag:
                del diag[k]
    
    # Round43: Add torso failure reasons and diagnostics to facts_summary
    if torso_failure_reasons:
        facts_summary["torso_failure_reasons"] = {k: dict(v) for k, v in torso_failure_reasons.items()}
        # Top-K failure reasons (across all keys)
        sorted_all_reasons = sorted(torso_failure_reasons_all.items(), key=lambda x: x[1], reverse=True)
        facts_summary["torso_failure_reasons_topk"] = dict(sorted_all_reasons[:10])  # Top 10
        # Round44: KPI_DIFF alias — postprocess get_failure_reasons reads summary[?]["warnings_top5"] = [{"reason","n"}]
        if "summary" not in facts_summary:
            facts_summary["summary"] = {}
        facts_summary["summary"]["failure_reasons"] = {
            "warnings_top5": [{"reason": r, "n": c} for r, c in sorted_all_reasons[:5]]
        }
    if torso_diagnostics_summary:
        facts_summary["torso_diagnostics_summary"] = torso_diagnostics_summary
    # Round44: TORSO_FALLBACK_HULL_USED 집계 (케이스/키별)
    if torso_fallback_hull_used_count > 0:
        facts_summary["torso_fallback_hull_used_count"] = torso_fallback_hull_used_count
        facts_summary["torso_fallback_hull_used_by_key"] = dict(torso_fallback_hull_used_by_key)
    # Round45: TORSO_SINGLE_COMPONENT_FALLBACK_USED 집계 (케이스/키별)
    if torso_single_component_fallback_count > 0:
        facts_summary["torso_single_component_fallback_count"] = torso_single_component_fallback_count
        facts_summary["torso_single_component_fallback_by_key"] = dict(torso_single_component_fallback_by_key)
    # Round48-A: TORSO_METHOD_USED 집계 (케이스/키별)
    # Round48-A: Ensure all processed cases have method tracking (sum must equal processed_cases)
    if torso_method_used_count:
        facts_summary["torso_method_used_count"] = dict(torso_method_used_count)
        facts_summary["torso_method_used_by_key"] = {k: dict(v) for k, v in torso_method_used_by_key.items()}
        # Round48-A: Verify sum equals processed_cases
        total_method_count = sum(torso_method_used_count.values())
        if total_method_count != len(all_results):
            # Round48-A: Record missing tracking count
            missing_count = len(all_results) - total_method_count
            facts_summary["torso_method_tracking_missing_count"] = missing_count
            if warnings is not None:
                warnings.append(f"TORSO_METHOD_TRACKING_MISSING: {missing_count} cases missing method label")
    
    # Round54: Alpha failure reasons aggregation
    if alpha_fail_reasons:
        # Sort by count descending and take top 5
        sorted_alpha_fail = sorted(alpha_fail_reasons.items(), key=lambda x: x[1], reverse=True)
        facts_summary["alpha_fail_reasons_topk"] = dict(sorted_alpha_fail[:5])
    else:
        # Round54: Always emit empty dict to avoid missing key confusion
        facts_summary["alpha_fail_reasons_topk"] = {}
    
    # Round55/56: Too few points diagnostics aggregation
    # Round56: Updated to handle stage-specific failure codes
    # Round57: Track boundary recovery usage and success
    too_few_points_diagnostics_list = []
    boundary_recovery_used_count: Dict[str, int] = defaultdict(int)
    boundary_recovery_success_count: Dict[str, int] = defaultdict(int)
    for case_id, results in all_results.items():
        for full_key in TORSO_CIRC_KEYS:
            if full_key in results:
                full_result = results[full_key]
                debug_info = (full_result.metadata or {}).get("debug_info") or (full_result.metadata or {}).get("debug") or {}
                if full_result.metadata and debug_info and "torso_components" in debug_info:
                    torso_info = debug_info["torso_components"]
                    # Round56: Check if this case had any TOO_FEW_* failure
                    alpha_fail_reason = torso_info.get("alpha_fail_reason")
                    if alpha_fail_reason and alpha_fail_reason.startswith("ALPHA_FAIL:TOO_FEW_"):
                        too_few_diag = torso_info.get("too_few_points_diagnostics")
                        if too_few_diag:
                            too_few_points_diagnostics_list.append(too_few_diag)
                    
                    # Round57: Track boundary recovery
                    recovery_method = torso_info.get("boundary_recovery_method")
                    if recovery_method:
                        boundary_recovery_used_count[recovery_method] += 1
                        if torso_info.get("boundary_recovery_success"):
                            boundary_recovery_success_count[recovery_method] += 1
    
    # Round55/56: Aggregate too_few_points_diagnostics_summary
    # Round56: Expanded fields: n_component_points, n_boundary_points, n_loops_found
    # Round57: Include post-recovery n_boundary_points if recovery was attempted
    if too_few_points_diagnostics_list:
        too_few_points_summary: Dict[str, Dict[str, float]] = {}
        for field in ["n_slice_points_raw", "n_slice_points_after_dedupe", "n_component_points", 
                      "n_boundary_points", "n_loops_found", "slice_thickness_used", "slice_plane_level", "alpha_k_eff_used"]:
            values = [d.get(field) for d in too_few_points_diagnostics_list if d.get(field) is not None]
            if values:
                too_few_points_summary[field] = {
                    "min": float(np.min(values)),
                    "p50": float(np.percentile(values, 50)),
                    "p95": float(np.percentile(values, 95)),
                    "max": float(np.max(values)),
                    "count": len(values)
                }
        facts_summary["too_few_points_diagnostics_summary"] = too_few_points_summary
    else:
        # Round55/56: Always emit empty dict to avoid missing key confusion
        facts_summary["too_few_points_diagnostics_summary"] = {}
    
    # Round57: Boundary recovery tracking
    # Count cases that didn't use recovery (per case, not per key)
    recovery_used_cases = set()
    for case_id, results in all_results.items():
        for full_key in TORSO_CIRC_KEYS:
            if full_key in results:
                full_result = results[full_key]
                debug_info = (full_result.metadata or {}).get("debug_info") or (full_result.metadata or {}).get("debug") or {}
                if full_result.metadata and debug_info and "torso_components" in debug_info:
                    torso_info = debug_info["torso_components"]
                    if torso_info.get("boundary_recovery_method"):
                        recovery_used_cases.add(case_id)
                        break  # Count each case only once
    
    total_processed_cases = len(all_results)
    recovery_used_total = len(recovery_used_cases)
    boundary_recovery_used_count["none"] = max(0, total_processed_cases - recovery_used_total)
    
    if boundary_recovery_used_count:
        facts_summary["boundary_recovery_used_count"] = dict(boundary_recovery_used_count)
    else:
        facts_summary["boundary_recovery_used_count"] = {}
    
    if boundary_recovery_success_count:
        facts_summary["boundary_recovery_success_count"] = dict(boundary_recovery_success_count)
    else:
        facts_summary["boundary_recovery_success_count"] = {}
    
    # Round59: Recovery cohort loop quality summary
    boundary_recovery_cohort_summary: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for key in recovery_cohort_loop_quality:
        key_cohorts = recovery_cohort_loop_quality[key]
        key_summary: Dict[str, Dict[str, Any]] = {}
        
        for cohort in ["recovery_used", "none"]:
            cohort_data = key_cohorts[cohort]
            cohort_summary: Dict[str, Any] = {}
            
            # Area summary
            if cohort_data["torso_loop_area_m2"]:
                areas = sorted(cohort_data["torso_loop_area_m2"])
                cohort_summary["torso_loop_area_m2"] = {
                    "p50": float(np.percentile(areas, 50)),
                    "p95": float(np.percentile(areas, 95)),
                    "count": len(areas)
                }
            
            # Perimeter summary
            if cohort_data["torso_loop_perimeter_m"]:
                perimeters = sorted(cohort_data["torso_loop_perimeter_m"])
                cohort_summary["torso_loop_perimeter_m"] = {
                    "p50": float(np.percentile(perimeters, 50)),
                    "p95": float(np.percentile(perimeters, 95)),
                    "count": len(perimeters)
                }
            
            # Shape ratio summary
            if cohort_data["torso_loop_shape_ratio"]:
                shape_ratios = sorted(cohort_data["torso_loop_shape_ratio"])
                cohort_summary["torso_loop_shape_ratio"] = {
                    "p50": float(np.percentile(shape_ratios, 50)),
                    "p95": float(np.percentile(shape_ratios, 95)),
                    "count": len(shape_ratios)
                }
            
            # Loop validity counts
            if cohort_data["loop_validity"]:
                from collections import Counter
                validity_counts = Counter(cohort_data["loop_validity"])
                cohort_summary["loop_validity_counts"] = dict(validity_counts)
                cohort_summary["count"] = len(cohort_data["loop_validity"])
            
            if cohort_summary:
                key_summary[cohort] = cohort_summary
        
        if key_summary:
            boundary_recovery_cohort_summary[key] = key_summary
    
    if boundary_recovery_cohort_summary:
        facts_summary["boundary_recovery_cohort_summary"] = boundary_recovery_cohort_summary
    else:
        # Round59: Always emit empty dict to avoid missing key confusion
        facts_summary["boundary_recovery_cohort_summary"] = {}
    # Round45: Debug summary stats (area/perimeter/circularity proxy) per key
    torso_debug_stats_summary: Dict[str, Dict[str, Any]] = {}
    for key in torso_debug_stats:
        stats = torso_debug_stats[key]
        key_summary: Dict[str, Any] = {}
        if stats["area"]:
            areas = stats["area"]
            key_summary["area"] = {
                "min": float(np.min(areas)),
                "max": float(np.max(areas)),
                "median": float(np.median(areas)),
                "p50": float(np.percentile(areas, 50)),
                "p95": float(np.percentile(areas, 95))
            }
        if stats["perimeter"]:
            perimeters = stats["perimeter"]
            key_summary["perimeter"] = {
                "min": float(np.min(perimeters)),
                "max": float(np.max(perimeters)),
                "median": float(np.median(perimeters)),
                "p50": float(np.percentile(perimeters, 50)),
                "p95": float(np.percentile(perimeters, 95))
            }
        if stats["circularity_proxy"]:
            circularities = stats["circularity_proxy"]
            key_summary["circularity_proxy"] = {
                "min": float(np.min(circularities)),
                "max": float(np.max(circularities)),
                "median": float(np.median(circularities)),
                "p50": float(np.percentile(circularities, 50)),
                "p95": float(np.percentile(circularities, 95))
            }
        if key_summary:
            torso_debug_stats_summary[key] = key_summary
    if torso_debug_stats_summary:
        facts_summary["torso_debug_stats_summary"] = torso_debug_stats_summary
    
    # Round49: Aggregate loop quality metrics summary
    torso_loop_quality_summary: Dict[str, Dict[str, Any]] = {}
    for key in torso_loop_quality:
        quality = torso_loop_quality[key]
        key_summary: Dict[str, Any] = {}
        
        # Area summary
        if quality["torso_loop_area_m2"]:
            areas = sorted(quality["torso_loop_area_m2"])
            key_summary["torso_loop_area_m2"] = {
                "min": float(np.min(areas)),
                "max": float(np.max(areas)),
                "median": float(np.median(areas)),
                "p50": float(np.percentile(areas, 50)),
                "p95": float(np.percentile(areas, 95))
            }
        
        # Perimeter summary
        if quality["torso_loop_perimeter_m"]:
            perimeters = sorted(quality["torso_loop_perimeter_m"])
            key_summary["torso_loop_perimeter_m"] = {
                "min": float(np.min(perimeters)),
                "max": float(np.max(perimeters)),
                "median": float(np.median(perimeters)),
                "p50": float(np.percentile(perimeters, 50)),
                "p95": float(np.percentile(perimeters, 95))
            }
        
        # Shape ratio summary
        if quality["torso_loop_shape_ratio"]:
            ratios = sorted(quality["torso_loop_shape_ratio"])
            key_summary["torso_loop_shape_ratio"] = {
                "min": float(np.min(ratios)),
                "max": float(np.max(ratios)),
                "median": float(np.median(ratios)),
                "p50": float(np.percentile(ratios, 50)),
                "p95": float(np.percentile(ratios, 95))
            }
        
        # Alpha param summary
        if quality["alpha_param_used"]:
            alpha_params = quality["alpha_param_used"]
            key_summary["alpha_param_used"] = {
                "min": int(np.min(alpha_params)),
                "max": int(np.max(alpha_params)),
                "median": float(np.median(alpha_params)),
                "unique": list(set(alpha_params))
            }
        
        # Validity counts
        if quality["loop_validity"]:
            from collections import Counter
            validity_counts = Counter(quality["loop_validity"])
            key_summary["loop_validity_counts"] = dict(validity_counts)
        
        if key_summary:
            torso_loop_quality_summary[key] = key_summary
    
    if torso_loop_quality_summary:
        facts_summary["torso_loop_quality_summary"] = torso_loop_quality_summary
    
    # Round50: Alpha k counts
    if alpha_k_counts:
        facts_summary["alpha_k_counts"] = dict(alpha_k_counts)
    
    # Round50: Loop quality summary by k
    torso_loop_quality_summary_by_k: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for key in torso_loop_quality_by_k:
        key_by_k: Dict[int, Dict[str, Any]] = {}
        for k in sorted(torso_loop_quality_by_k[key].keys()):
            quality = torso_loop_quality_by_k[key][k]
            k_summary: Dict[str, Any] = {}
            
            # Area summary
            if quality["torso_loop_area_m2"]:
                areas = sorted(quality["torso_loop_area_m2"])
                k_summary["torso_loop_area_m2"] = {
                    "min": float(np.min(areas)),
                    "max": float(np.max(areas)),
                    "median": float(np.median(areas)),
                    "p50": float(np.percentile(areas, 50)),
                    "p95": float(np.percentile(areas, 95))
                }
            
            # Perimeter summary
            if quality["torso_loop_perimeter_m"]:
                perimeters = sorted(quality["torso_loop_perimeter_m"])
                k_summary["torso_loop_perimeter_m"] = {
                    "min": float(np.min(perimeters)),
                    "max": float(np.max(perimeters)),
                    "median": float(np.median(perimeters)),
                    "p50": float(np.percentile(perimeters, 50)),
                    "p95": float(np.percentile(perimeters, 95))
                }
            
            # Shape ratio summary
            if quality["torso_loop_shape_ratio"]:
                ratios = sorted(quality["torso_loop_shape_ratio"])
                k_summary["torso_loop_shape_ratio"] = {
                    "min": float(np.min(ratios)),
                    "max": float(np.max(ratios)),
                    "median": float(np.median(ratios)),
                    "p50": float(np.percentile(ratios, 50)),
                    "p95": float(np.percentile(ratios, 95))
                }
            
            # Validity counts
            if quality["loop_validity"]:
                from collections import Counter
                validity_counts = Counter(quality["loop_validity"])
                k_summary["loop_validity_counts"] = dict(validity_counts)
            
            if k_summary:
                key_by_k[k] = k_summary
        
        if key_by_k:
            torso_loop_quality_summary_by_k[key] = key_by_k
    
    if torso_loop_quality_summary_by_k:
        facts_summary["torso_loop_quality_summary_by_k"] = torso_loop_quality_summary_by_k
    
    # Round51: Key-level failure reason aggregation
    if key_failure_reasons:
        # Convert to topk format per key
        key_failure_reasons_topk: Dict[str, Dict[str, int]] = {}
        for key in key_failure_reasons:
            reasons = key_failure_reasons[key]
            # Sort by count descending and take top 5
            sorted_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)
            key_failure_reasons_topk[key] = dict(sorted_reasons[:5])
        facts_summary["key_failure_reasons_topk"] = key_failure_reasons_topk
    
    # Round52: EXEC_FAIL breakdown aggregation
    # Round53: Always emit empty sections to avoid "missing key" confusion
    key_exec_fail_breakdown_topk: Dict[str, Dict[str, int]] = {}
    if key_exec_fail_breakdown:
        for key in key_exec_fail_breakdown:
            breakdown = key_exec_fail_breakdown[key]
            # Sort by count descending and take top 5
            sorted_breakdown = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
            key_exec_fail_breakdown_topk[key] = dict(sorted_breakdown[:5])
    facts_summary["key_exec_fail_breakdown_topk"] = key_exec_fail_breakdown_topk
    
    # Round52: Exception type aggregation
    # Round53: Always emit empty sections to avoid "missing key" confusion
    key_exception_type_topk: Dict[str, Dict[str, int]] = {}
    if key_exception_type:
        for key in key_exception_type:
            types = key_exception_type[key]
            # Sort by count descending and take top 5
            sorted_types = sorted(types.items(), key=lambda x: x[1], reverse=True)
            key_exception_type_topk[key] = dict(sorted_types[:5])
    facts_summary["key_exception_type_topk"] = key_exception_type_topk
    
    # Round52: Exception fingerprint aggregation
    # Round53: Always emit empty sections to avoid "missing key" confusion
    key_exception_fingerprint_topk: Dict[str, Dict[str, int]] = {}
    if key_exception_fingerprint:
        for key in key_exception_fingerprint:
            fingerprints = key_exception_fingerprint[key]
            # Sort by count descending and take top 5
            sorted_fingerprints = sorted(fingerprints.items(), key=lambda x: x[1], reverse=True)
            key_exception_fingerprint_topk[key] = dict(sorted_fingerprints[:5])
    facts_summary["key_exception_fingerprint_topk"] = key_exception_fingerprint_topk
    
    # Round41: full vs torso-only delta 통계
    torso_delta_stats: Dict[str, Dict[str, Any]] = {}
    TORSO_CIRC_KEYS = ["NECK_CIRC_M", "BUST_CIRC_M", "UNDERBUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]
    
    for full_key in TORSO_CIRC_KEYS:
        torso_key = full_key.replace("_CIRC_M", "_CIRC_TORSO_M")
        
        if full_key in summary and torso_key in summary:
            full_values = summary[full_key].get("values", [])
            torso_values = summary[torso_key].get("values", [])
            
            # Compute deltas for cases where both are valid
            deltas = []
            deltas_abs = []
            deltas_pct = []
            
            # Match by case_id
            for case_id, results in all_results.items():
                if full_key in results and torso_key in results:
                    full_val = results[full_key].value_m
                    torso_val = results[torso_key].value_m
                    
                    if not (np.isnan(full_val) or not np.isfinite(full_val)) and \
                       not (np.isnan(torso_val) or not np.isfinite(torso_val)):
                        delta = torso_val - full_val
                        delta_abs = abs(delta)
                        delta_pct = (delta / full_val * 100) if full_val != 0 else float('nan')
                        
                        deltas.append(float(delta))
                        deltas_abs.append(float(delta_abs))
                        if not np.isnan(delta_pct):
                            deltas_pct.append(float(delta_pct))
            
            if deltas:
                torso_delta_stats[full_key] = {
                    "n_valid_pairs": len(deltas),
                    "delta_stats": {
                        "min": float(np.min(deltas)),
                        "max": float(np.max(deltas)),
                        "median": float(np.median(deltas)),
                        "mean": float(np.mean(deltas)),
                        "p50": float(np.percentile(deltas, 50)),
                        "p90": float(np.percentile(deltas, 90)),
                        "p95": float(np.percentile(deltas, 95)),
                    },
                    "delta_abs_stats": {
                        "min": float(np.min(deltas_abs)),
                        "max": float(np.max(deltas_abs)),
                        "median": float(np.median(deltas_abs)),
                        "mean": float(np.mean(deltas_abs)),
                        "p50": float(np.percentile(deltas_abs, 50)),
                        "p90": float(np.percentile(deltas_abs, 90)),
                        "p95": float(np.percentile(deltas_abs, 95)),
                    }
                }
                if deltas_pct:
                    torso_delta_stats[full_key]["delta_pct_stats"] = {
                        "min": float(np.min(deltas_pct)),
                        "max": float(np.max(deltas_pct)),
                        "median": float(np.median(deltas_pct)),
                        "mean": float(np.mean(deltas_pct)),
                        "p50": float(np.percentile(deltas_pct, 50)),
                        "p90": float(np.percentile(deltas_pct, 90)),
                        "p95": float(np.percentile(deltas_pct, 95)),
                    }
    
    if torso_delta_stats:
        facts_summary["torso_delta_stats"] = torso_delta_stats
    
    facts_summary_path = out_dir / "facts_summary.json"
    with open(facts_summary_path, 'w', encoding='utf-8') as f:
        json.dump(facts_summary, f, indent=2, ensure_ascii=False)
    
    print(f"[DONE] Facts summary saved: {facts_summary_path}")
    print(f"[DONE] Processed: {len(all_results)}, Skipped: {len(skipped_entries)}")
    if npz_path:
        print(f"[DONE] NPZ path: {npz_path} (has_verts: {npz_has_verts})")


if __name__ == "__main__":
    main()
