#!/usr/bin/env python3
"""
Purpose: geo v0 facts round1: mesh/verts → measurement facts.
Inputs: manifest, out_dir
Outputs: facts_summary.json, artifacts/
Status: active
"""

from __future__ import annotations

import os
import sys
import json
import argparse
import numpy as np
import csv
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
import subprocess

# Add project root to path (4 levels up: runners -> src -> body -> modules -> repo)
project_root = str(Path(__file__).resolve().parents[4])
sys.path.insert(0, project_root)

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

# This round's keys
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


def load_npz_dataset(npz_path: str) -> tuple[List[np.ndarray], List[str], List[str], Optional[List[Dict[str, Any]]]]:
    """Load NPZ dataset and return (verts_list, case_ids, case_classes, case_metadata).
    
    Returns:
        verts_list: List of vertex arrays
        case_ids: List of case identifiers
        case_classes: List of case classes ("valid" or "expected_fail")
        case_metadata: Optional list of metadata dicts (scale normalization info)
    """
    npz_path_abs = Path(npz_path).resolve()
    print(f"[NPZ LOAD] Loading NPZ from: {npz_path_abs}")
    print(f"[NPZ LOAD] File exists: {npz_path_abs.exists()}")
    if npz_path_abs.exists():
        file_stat = npz_path_abs.stat()
        print(f"[NPZ LOAD] File size: {file_stat.st_size / 1024:.1f} KB")
        print(f"[NPZ LOAD] File mtime: {file_stat.st_mtime}")
    
    data = np.load(npz_path, allow_pickle=True)
    
    # Print NPZ structure
    loaded_keys = list(data.files)
    print(f"[NPZ LOAD] Loaded NPZ keys: {loaded_keys}")
    for key in loaded_keys:
        arr = data[key]
        print(f"[NPZ LOAD]   {key}: shape={arr.shape}, dtype={arr.dtype}")
    
    if "verts" in data:
        verts_array = data["verts"]
        if verts_array.dtype == object:
            # Variable-length arrays
            verts_list = [verts_array[i] for i in range(len(verts_array))]
        else:
            # Fixed shape: (N, V, 3) -> list of (V, 3)
            if verts_array.ndim == 3:
                verts_list = [verts_array[i] for i in range(verts_array.shape[0])]
            else:
                verts_list = [verts_array]
        
        case_ids = data.get("case_id", None)
        if case_ids is not None:
            if case_ids.dtype == object:
                case_ids = [str(case_ids[i]) for i in range(len(case_ids))]
            else:
                case_ids = [str(cid) for cid in case_ids]
        else:
            case_ids = [f"case_{i}" for i in range(len(verts_list))]
        
        # Load case_class if available (for backward compatibility)
        case_classes = data.get("case_class", None)
        if case_classes is not None:
            if case_classes.dtype == object:
                case_classes = [str(case_classes[i]) for i in range(len(case_classes))]
            else:
                case_classes = [str(cc) for cc in case_classes]
        else:
            # Fallback: infer from case_id pattern
            case_classes = []
            for cid in case_ids:
                if cid.startswith("normal_") or cid.startswith("varied_"):
                    case_classes.append("valid")
                else:
                    case_classes.append("expected_fail")
        
        # Load case_metadata if available (for scale normalization info)
        case_metadata_list = None
        case_metadata = data.get("case_metadata", None)
        if case_metadata is not None:
            if case_metadata.dtype == object:
                case_metadata_list = [case_metadata[i] for i in range(len(case_metadata))]
            else:
                case_metadata_list = [dict(meta) if isinstance(meta, dict) else {} for meta in case_metadata]
        
        return verts_list, case_ids, case_classes, case_metadata_list
    else:
        raise ValueError(f"NPZ file missing 'verts' key. Found keys: {list(data.keys())}")


def measure_all_keys(verts: np.ndarray, case_id: str) -> Dict[str, MeasurementResult]:
    """Measure all keys for a single case."""
    results = {}
    
    # WAIST group: Use shared slice (CIRC, WIDTH, DEPTH)
    try:
        waist_results = measure_waist_group_with_shared_slice(verts)
        results.update(waist_results)
    except Exception as e:
        for key in ["WAIST_CIRC_M", "WAIST_WIDTH_M", "WAIST_DEPTH_M"]:
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
    
    # HIP group: Use shared slice (CIRC, WIDTH, DEPTH)
    try:
        hip_results = measure_hip_group_with_shared_slice(verts)
        results.update(hip_results)
    except Exception as e:
        for key in ["HIP_CIRC_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]:
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
    
    # Other circumference keys (excluding WAIST/HIP which are already done)
    for key in CIRCUMFERENCE_KEYS:
        if key in ["WAIST_CIRC_M", "HIP_CIRC_M"]:
            continue  # Already measured above
        try:
            result = measure_circumference_v0_with_metadata(verts, key)
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
    
    # Other width/depth keys (excluding WAIST/HIP which are already done)
    for key in WIDTH_DEPTH_KEYS:
        if key in ["WAIST_WIDTH_M", "WAIST_DEPTH_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]:
            continue  # Already measured above
        try:
            result = measure_width_depth_v0_with_metadata(verts, key, proxy_used=False)
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
    
    # Height group
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
    
    # ARM_LEN_M (requires joints, simplified for now)
    try:
        result = measure_arm_length_v0_with_metadata(verts, joints_xyz=None, joint_ids=None)
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
    
    # WEIGHT_KG (input-only, skip for now - would need input data)
    # results["WEIGHT_KG"] = create_weight_metadata(70.0)  # Placeholder
    
    return results


def is_valid_case(case_id: str, case_class: Optional[str] = None) -> bool:
    """Check if case is valid (normal_* or varied_*, or case_class='valid')."""
    if case_class is not None:
        return case_class == "valid"
    return case_id.startswith("normal_") or case_id.startswith("varied_")


def aggregate_results(
    all_results: List[Dict[str, MeasurementResult]],
    case_ids: List[str],
    case_classes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Aggregate results across all cases, with separate valid/expected_fail aggregation."""
    summary = {}
    if case_classes is None:
        # Fallback to pattern-based detection
        valid_case_indices = [i for i, cid in enumerate(case_ids) if is_valid_case(cid)]
        expected_fail_case_indices = [i for i, cid in enumerate(case_ids) if not is_valid_case(cid)]
    else:
        valid_case_indices = [i for i, cc in enumerate(case_classes) if is_valid_case(case_ids[i], cc)]
        expected_fail_case_indices = [i for i, cc in enumerate(case_classes) if not is_valid_case(case_ids[i], cc)]
    
    for key in ALL_KEYS:
        # Separate valid and expected fail results
        all_key_results = [r.get(key) for r in all_results if key in r]
        valid_key_results = [all_key_results[i] for i in valid_case_indices if i < len(all_key_results)]
        expected_fail_key_results = [all_key_results[i] for i in expected_fail_case_indices if i < len(all_key_results)]
        
        if not all_key_results:
            continue
        
        # Aggregate valid cases (for DoD)
        key_results = valid_key_results
        if not key_results:
            continue
        
        # Extract values
        values = []
        nan_count = 0
        warnings_all = []
        proxy_used_count = 0
        proxy_types = defaultdict(int)
        band_scan_used_count = 0
        band_scan_limits = []
        canonical_sides = defaultdict(int)
        pose_unknown_counts = defaultdict(int)
        pose_total_counts = defaultdict(int)
        
        # Debug aggregation variables
        cross_section_reasons = defaultdict(int)
        cross_section_candidates_counts = []
        body_axis_reasons = defaultdict(int)
        landmark_reasons = defaultdict(int)
        nearest_valid_plane_used_count = 0
        nearest_valid_plane_shifts = []
        target_out_of_bounds_count = 0
        initial_candidates_counts = []
        fallback_candidates_counts = []
        slice_shared_count = 0
        slicer_independent_false_count = 0
        slice_shared_from_keys = defaultdict(int)
        height_calculation_list = []
        bbox_comparison_list = []
        
        for result in key_results:
            if result is None:
                continue
            
            # Value
            value = result.value_m if result.value_m is not None else result.value_kg
            if value is not None and not np.isnan(value):
                values.append(float(value))
            else:
                nan_count += 1
            
            # Warnings
            meta = result.metadata
            warnings = meta.get("warnings", [])
            warnings_all.extend(warnings)
            
            # Proxy
            proxy = meta.get("proxy", {})
            if proxy.get("proxy_used", False):
                proxy_used_count += 1
                proxy_type = proxy.get("proxy_type")
                if proxy_type:
                    proxy_types[proxy_type] += 1
            
            # Band scan
            search = meta.get("search", {})
            if search.get("band_scan_used", False):
                band_scan_used_count += 1
                limit = search.get("band_scan_limit_mm")
                if limit is not None:
                    band_scan_limits.append(limit)
            
            # Canonical side
            method = meta.get("method", {})
            canonical_side = method.get("canonical_side")
            if canonical_side:
                canonical_sides[canonical_side] += 1
            
            # Pose unknown
            pose = meta.get("pose", {})
            for pose_key in ["breath_state", "arms_down", "strict_standing", "knee_flexion_forbidden"]:
                if pose_key in pose:
                    pose_total_counts[pose_key] += 1
                    if pose[pose_key] == "unknown":
                        pose_unknown_counts[pose_key] += 1
            
            # Nearest valid plane fallback
            search = meta.get("search", {})
            if search.get("nearest_valid_plane_used", False):
                nearest_valid_plane_used_count += 1
                shift_mm = search.get("nearest_valid_plane_shift_mm")
                if shift_mm is not None:
                    nearest_valid_plane_shifts.append(float(shift_mm))
            
            # Slice sharing info (for waist/hip width/depth)
            debug = meta.get("debug", {})
            cross_section = debug.get("cross_section", {}) if debug else {}
            slice_shared_from = cross_section.get("slice_shared_from")
            slicer_called_independently = cross_section.get("slicer_called_independently", True)
            
            if slice_shared_from:
                slice_shared_count += 1
                slice_shared_from_keys[slice_shared_from] += 1
            
            if slicer_called_independently is False:
                slicer_independent_false_count += 1
            
            # HEIGHT_M debug aggregation
            if key == "HEIGHT_M":
                debug = meta.get("debug", {})
                if debug:
                    bbox_comp = debug.get("bbox_comparison", {})
                    height_calc = debug.get("height_calculation", {})
                    if bbox_comp or height_calc:
                        if "height_calculation_list" not in locals():
                            height_calculation_list = []
                        if "bbox_comparison_list" not in locals():
                            bbox_comparison_list = []
                        if height_calc:
                            height_calculation_list.append(height_calc)
                        if bbox_comp:
                            bbox_comparison_list.append(bbox_comp)
            
            # Debug info aggregation
            debug = meta.get("debug", {})
            if debug:
                # Cross-section debug
                cross_section = debug.get("cross_section", {})
                if cross_section:
                    reason = cross_section.get("reason_not_found")
                    if reason:
                        cross_section_reasons[reason] += 1
                    candidates_count = cross_section.get("candidates_count", 0)
                    cross_section_candidates_counts.append(candidates_count)
                    # Record empty_slice_reason details
                    if reason == "empty_slice":
                        # Check if it's actually mesh_empty_at_height (candidates_count == 0)
                        if candidates_count == 0:
                            cross_section_reasons["mesh_empty_at_height"] += 1
                            cross_section_reasons["empty_slice"] -= 1  # Avoid double counting
                    
                    # Track target out of bounds for waist/hip
                    target_out_of_bounds = cross_section.get("target_out_of_bounds", False)
                    if target_out_of_bounds:
                        target_out_of_bounds_count += 1
                    
                    # Track initial and fallback candidates counts
                    initial_count = cross_section.get("initial_candidates_count")
                    if initial_count is not None:
                        initial_candidates_counts.append(initial_count)
                    fallback_count = cross_section.get("fallback_candidates_count")
                    if fallback_count is not None and fallback_count > 0:
                        fallback_candidates_counts.append(fallback_count)
                
                # Body axis debug
                body_axis = debug.get("body_axis", {})
                if body_axis:
                    if not body_axis.get("valid", True):
                        reason = body_axis.get("reason_invalid", "unknown")
                        body_axis_reasons[reason] += 1
                
                # Landmark regions debug
                landmark_regions = debug.get("landmark_regions", {})
                if landmark_regions:
                    reason = landmark_regions.get("reason_not_found")
                    if reason:
                        landmark_reasons[reason] += 1
        
        # Compute statistics
        total_count = len(key_results)
        nan_rate = nan_count / total_count if total_count > 0 else 0.0
        
        value_stats = {}
        if values:
            value_stats = {
                "min": float(np.min(values)),
                "median": float(np.median(values)),
                "max": float(np.max(values)),
                "count": len(values)
            }
        
        # Warnings Top 5
        warning_counts = defaultdict(int)
        for w in warnings_all:
            # Extract warning type (before colon if exists)
            w_type = w.split(":")[0] if ":" in w else w
            warning_counts[w_type] += 1
        warnings_top5 = sorted(warning_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Debug aggregation
        debug_summary = {}
        if cross_section_reasons:
            debug_summary["cross_section_reasons"] = dict(cross_section_reasons)
        if cross_section_candidates_counts:
            debug_summary["cross_section_candidates_counts"] = {
                "min": int(np.min(cross_section_candidates_counts)),
                "median": float(np.median(cross_section_candidates_counts)),
                "max": int(np.max(cross_section_candidates_counts)),
                "zero_count": sum(1 for c in cross_section_candidates_counts if c == 0)
            }
        if body_axis_reasons:
            debug_summary["body_axis_reasons"] = dict(body_axis_reasons)
        if landmark_reasons:
            debug_summary["landmark_reasons"] = dict(landmark_reasons)
        
        # HEIGHT_M debug aggregation
        if key == "HEIGHT_M":
            # Bbox comparison stats
            if bbox_comparison_list:
                longest_axes = [b.get("bbox_longest_axis") for b in bbox_comparison_list if b.get("bbox_longest_axis")]
                longest_spans = [b.get("bbox_longest_span_m") for b in bbox_comparison_list if b.get("bbox_longest_span_m") is not None]
                span_x_list = [b.get("bbox_span_x") for b in bbox_comparison_list if b.get("bbox_span_x") is not None]
                span_y_list = [b.get("bbox_span_y") for b in bbox_comparison_list if b.get("bbox_span_y") is not None]
                span_z_list = [b.get("bbox_span_z") for b in bbox_comparison_list if b.get("bbox_span_z") is not None]
                
                if longest_axes and longest_spans:
                    longest_axis_dist = defaultdict(int)
                    for ax in longest_axes:
                        longest_axis_dist[ax] += 1
                    
                    debug_summary["bbox_comparison"] = {
                        "bbox_longest_axis_distribution": dict(longest_axis_dist),
                        "bbox_longest_span_m": {
                            "min": float(np.min(longest_spans)),
                            "median": float(np.median(longest_spans)),
                            "max": float(np.max(longest_spans))
                        },
                        "bbox_span_x": {
                            "min": float(np.min(span_x_list)) if span_x_list else None,
                            "median": float(np.median(span_x_list)) if span_x_list else None,
                            "max": float(np.max(span_x_list)) if span_x_list else None
                        },
                        "bbox_span_y": {
                            "min": float(np.min(span_y_list)) if span_y_list else None,
                            "median": float(np.median(span_y_list)) if span_y_list else None,
                            "max": float(np.max(span_y_list)) if span_y_list else None
                        },
                        "bbox_span_z": {
                            "min": float(np.min(span_z_list)) if span_z_list else None,
                            "median": float(np.median(span_z_list)) if span_z_list else None,
                            "max": float(np.max(span_z_list)) if span_z_list else None
                        }
                    }
            
            # Height calculation stats
            if height_calculation_list:
                axis_used_list = [h.get("axis_used") for h in height_calculation_list if h.get("axis_used")]
                raw_spans = [h.get("raw_span_m") for h in height_calculation_list if h.get("raw_span_m") is not None]
                post_spans = [h.get("post_transform_span_m") for h in height_calculation_list if h.get("post_transform_span_m") is not None]
                scale_factors = [h.get("scale_factor_raw_to_post") for h in height_calculation_list if h.get("scale_factor_raw_to_post") is not None]
                
                if axis_used_list and raw_spans and post_spans and scale_factors:
                    axis_used_dist = defaultdict(int)
                    for ax in axis_used_list:
                        axis_used_dist[ax] += 1
                    
                    # Count suspicious scale factors (1.0, 0.5, 0.1, 0.01, 10, 100 ±2%)
                    suspicious_counts = {
                        "near_1.0": sum(1 for s in scale_factors if abs(s - 1.0) < 0.02),
                        "near_0.5": sum(1 for s in scale_factors if abs(s - 0.5) < 0.01),
                        "near_0.1": sum(1 for s in scale_factors if abs(s - 0.1) < 0.002),
                        "near_0.01": sum(1 for s in scale_factors if abs(s - 0.01) < 0.0002),
                        "near_10": sum(1 for s in scale_factors if abs(s - 10.0) < 0.2),
                        "near_100": sum(1 for s in scale_factors if abs(s - 100.0) < 2.0)
                    }
                    
                    debug_summary["height_calculation"] = {
                        "axis_used_distribution": dict(axis_used_dist),
                        "raw_span_m": {
                            "min": float(np.min(raw_spans)),
                            "median": float(np.median(raw_spans)),
                            "max": float(np.max(raw_spans))
                        },
                        "post_transform_span_m": {
                            "min": float(np.min(post_spans)),
                            "median": float(np.median(post_spans)),
                            "max": float(np.max(post_spans))
                        },
                        "scale_factor_raw_to_post": {
                            "min": float(np.min(scale_factors)),
                            "median": float(np.median(scale_factors)),
                            "max": float(np.max(scale_factors))
                        },
                        "suspicious_scale_factor_counts": suspicious_counts
                    }
        
        # Nearest valid plane fallback stats
        nearest_valid_plane_stats = {}
        if nearest_valid_plane_used_count > 0:
            nearest_valid_plane_stats["used_count"] = nearest_valid_plane_used_count
            if nearest_valid_plane_shifts:
                nearest_valid_plane_stats["shift_mm"] = {
                    "min": int(np.min(nearest_valid_plane_shifts)),
                    "median": float(np.median(nearest_valid_plane_shifts)),
                    "max": int(np.max(nearest_valid_plane_shifts))
                }
        
        # Target/bbox debug stats (for waist/hip)
        target_bbox_stats = {}
        if target_out_of_bounds_count > 0:
            target_bbox_stats["target_out_of_bounds_count"] = target_out_of_bounds_count
            target_bbox_stats["target_out_of_bounds_rate"] = target_out_of_bounds_count / total_count if total_count > 0 else 0.0
        if initial_candidates_counts:
            target_bbox_stats["initial_candidates_count"] = {
                "min": int(np.min(initial_candidates_counts)),
                "median": float(np.median(initial_candidates_counts)),
                "max": int(np.max(initial_candidates_counts)),
                "zero_count": sum(1 for c in initial_candidates_counts if c == 0)
            }
        if fallback_candidates_counts:
            target_bbox_stats["fallback_candidates_count"] = {
                "min": int(np.min(fallback_candidates_counts)),
                "median": float(np.median(fallback_candidates_counts)),
                "max": int(np.max(fallback_candidates_counts))
            }
        
        # Aggregate expected fail cases separately
        expected_fail_nan_count = 0
        expected_fail_total = len(expected_fail_key_results)
        for result in expected_fail_key_results:
            if result is None:
                continue
            value = result.value_m if result.value_m is not None else result.value_kg
            if value is None or np.isnan(value):
                expected_fail_nan_count += 1
        
        summary[key] = {
            "total_count": total_count,
            "nan_count": nan_count,
            "nan_rate": nan_rate,
            "value_stats": value_stats,
            "warnings_top5": warnings_top5,
            "proxy_used_count": proxy_used_count,
            "proxy_types": dict(proxy_types),
            "band_scan_used_count": band_scan_used_count,
            "band_scan_limits": list(set(band_scan_limits)) if band_scan_limits else [],
            "canonical_sides": dict(canonical_sides),
            "pose_unknown_rates": {
                k: pose_unknown_counts[k] / pose_total_counts[k] 
                if pose_total_counts[k] > 0 else 0.0
                for k in pose_total_counts
            },
            "debug_summary": debug_summary if debug_summary else {},
            "nearest_valid_plane_stats": nearest_valid_plane_stats if nearest_valid_plane_stats else {},
            "target_bbox_stats": target_bbox_stats if target_bbox_stats else {},
            "slice_sharing_stats": {
                "slice_shared_count": slice_shared_count,
                "slice_shared_rate": slice_shared_count / total_count if total_count > 0 else 0.0,
                "slicer_independent_false_count": slicer_independent_false_count,
                "slicer_independent_false_rate": slicer_independent_false_count / total_count if total_count > 0 else 0.0,
                "slice_shared_from_keys": dict(slice_shared_from_keys)
            } if slice_shared_count > 0 or slicer_independent_false_count > 0 else {},
            # Valid/Expected fail split
            "valid_cases": {
                "total_count": len(valid_key_results),
                "nan_count": nan_count,
                "nan_rate": nan_rate
            },
            "expected_fail_cases": {
                "total_count": expected_fail_total,
                "nan_count": expected_fail_nan_count,
                "nan_rate": expected_fail_nan_count / expected_fail_total if expected_fail_total > 0 else 0.0
            }
        }
    
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Geometric v0 Facts-Only Runner (Round 1)"
    )
    parser.add_argument(
        "--npz",
        type=str,
        default="verification/datasets/golden/core_measurements_v0/s0_synthetic_cases.npz",
        help="Input NPZ dataset path"
    )
    parser.add_argument(
        "--n_samples",
        type=int,
        default=None,
        help="Number of samples to process (None = all)"
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        default=None,
        help="Output directory (default: exports/runs/geo_v0/round1_<timestamp>)"
    )
    args = parser.parse_args()
    
    # Load dataset
    npz_path_abs = Path(args.npz).resolve()
    print(f"\n{'='*60}")
    print(f"Loading dataset: {args.npz}")
    print(f"  [PROOF] NPZ absolute path: {npz_path_abs}")
    print(f"{'='*60}")
    load_result = load_npz_dataset(args.npz)
    if len(load_result) == 4:
        verts_list, case_ids, case_classes, case_metadata_list = load_result
    else:
        verts_list, case_ids, case_classes = load_result
        case_metadata_list = None
    print(f"  Loaded {len(verts_list)} cases")
    print(f"  Valid cases: {sum(1 for cc in case_classes if cc == 'valid')}")
    print(f"  Expected fail cases: {sum(1 for cc in case_classes if cc == 'expected_fail')}")
    if case_metadata_list:
        scale_applied_count = sum(1 for m in case_metadata_list if m and m.get("scale_applied", False))
        print(f"  Scale normalization applied: {scale_applied_count} cases")
        
        # Hard proof: Verify loaded vertices match metadata
        print(f"\n[PROOF] Verifying loaded vertices match scale metadata (sample 3 valid cases):")
        valid_indices = [i for i, cc in enumerate(case_classes) if cc == "valid"][:3]
        for i in valid_indices:
            meta = case_metadata_list[i] if case_metadata_list and i < len(case_metadata_list) else None
            if meta and meta.get("scale_applied"):
                verts_loaded = verts_list[i]
                y_coords = verts_loaded[:, 1]
                bbox_span_y_loaded = float(np.max(y_coords) - np.min(y_coords))
                target_height = meta.get("target_height_m")
                scale_factor = meta.get("scale_factor_applied")
                print(f"  {case_ids[i]}: loaded_span={bbox_span_y_loaded:.4f}m, "
                      f"target={target_height:.4f}m, scale={scale_factor:.4f}")
    
    # Limit samples
    if args.n_samples is not None:
        if args.n_samples < len(verts_list):
            verts_list = verts_list[:args.n_samples]
            case_ids = case_ids[:args.n_samples]
            case_classes = case_classes[:args.n_samples]
            if case_metadata_list:
                case_metadata_list = case_metadata_list[:args.n_samples]
            print(f"  Limited to {args.n_samples} samples")
        elif args.n_samples > len(verts_list):
            print(f"  Warning: n_samples ({args.n_samples}) > available cases ({len(verts_list)}), using all {len(verts_list)} cases")
    
    # Process all cases
    print("\nProcessing cases...")
    all_results = []
    for i, (verts, case_id) in enumerate(zip(verts_list, case_ids)):
        print(f"  [{i+1}/{len(verts_list)}] {case_id}")
        try:
            results = measure_all_keys(verts, case_id)
            all_results.append(results)
        except Exception as e:
            print(f"    ERROR: {e}")
            traceback.print_exc()
            # Continue with empty results
            all_results.append({})
    
    # Aggregate
    print("\nAggregating results...")
    summary = aggregate_results(all_results, case_ids, case_classes)
    
    # Get git SHA
    git_sha = get_git_sha()
    
    # Save raw results (JSON)
    if args.out_dir is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(project_root) / "exports" / "runs" / "geo_v0" / f"round1_{timestamp}"
    else:
        out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Save summary JSON
    from datetime import datetime
    summary_json = {
        "git_sha": git_sha,
        "dataset_path": args.npz,
        "n_samples": len(verts_list),
        "case_ids": case_ids,
        "summary": summary,
        "timestamp": datetime.now().isoformat()
    }
    
    summary_path = out_dir / "facts_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2, ensure_ascii=False)
    print(f"\nSaved summary: {summary_path}")
    
    # Generate markdown report (detect round from out_dir)
    if "round17" in str(out_dir).lower():
        report_filename = "geo_v0_facts_round17_valid10_expanded.md"
    elif "round16" in str(out_dir).lower():
        report_filename = "geo_v0_facts_round16_waist_hip_verts_aligned_normal1.md"
    elif "round15" in str(out_dir).lower():
        report_filename = "geo_v0_facts_round15_bust_verts_aligned_normal1.md"
    elif "round10" in str(out_dir).lower():
        report_filename = "geo_v0_facts_round10_s0_scale_proof.md"
    elif "round9" in str(out_dir).lower():
        report_filename = "geo_v0_facts_round9_s0_scale_fix.md"
    else:
        report_filename = "geo_v0_facts_round1.md"
    report_path = out_dir / report_filename
    generate_report(summary_json, report_path)
    print(f"Saved report: {report_path}")
    
    # Also save to reports directory for PR (round15 -> round15 file only; do not overwrite round1)
    reports_dir = Path("reports/validation")
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_final_path = reports_dir / report_filename
    generate_report(summary_json, report_final_path)
    print(f"Saved report (for PR): {report_final_path}")


def generate_report(summary_json: Dict[str, Any], output_path: Path):
    """Generate markdown report from summary JSON."""
    git_sha = summary_json.get("git_sha", "unknown")
    dataset_path = summary_json.get("dataset_path", "unknown")
    n_samples = summary_json.get("n_samples", 0)
    summary = summary_json.get("summary", {})
    
    lines = []
    is_round9 = "round9" in str(output_path).lower()
    is_round10 = "round10" in str(output_path).lower()
    is_round11 = "round11" in str(output_path).lower()
    is_round12 = "round12" in str(output_path).lower()
    is_round13 = "round13" in str(output_path).lower()
    is_round15 = "round15" in str(output_path).lower()
    is_round16 = "round16" in str(output_path).lower()
    is_round17 = "round17" in str(output_path).lower()
    
    if is_round17:
        lines.append("# Geometric v0 Facts-Only Summary (Round 17 - Valid 10 Expanded)")
    elif is_round16:
        lines.append("# Geometric v0 Facts-Only Summary (Round 16 - Waist/Hip Verts Aligned, Fastmode normal_1)")
    elif is_round15:
        lines.append("# Geometric v0 Facts-Only Summary (Round 15 - Bust Verts Aligned, Fastmode normal_1)")
    elif is_round13:
        lines.append("# Geometric v0 Facts-Only Summary (Round 13 - Bust Invariant Fix)")
    elif is_round12:
        lines.append("# Geometric v0 Facts-Only Summary (Round 12 - Post Generator Fix)")
    elif is_round11:
        lines.append("# Geometric v0 Facts-Only Summary (Round 11 - S0 Scale Re-open Proof)")
    elif is_round10:
        lines.append("# Geometric v0 Facts-Only Summary (Round 10 - S0 Scale Proof)")
    elif is_round9:
        lines.append("# Geometric v0 Facts-Only Summary (Round 9 - S0 Scale Fix)")
    else:
        lines.append("# Geometric v0 Facts-Only Summary")
    lines.append("")
    lines.append("## 1. 실행 조건")
    lines.append("")
    lines.append(f"- **샘플 수**: {n_samples}")
    lines.append(f"- **입력 데이터셋**: `{dataset_path}`")
    lines.append(f"- **Git SHA**: `{git_sha}`")
    lines.append(f"- **실행 일시**: {summary_json.get('timestamp', 'N/A')}")
    lines.append("")
    
    # Add scale statistics if available
    if "HEIGHT_M" in summary:
        height_stats = summary["HEIGHT_M"].get("value_stats", {})
        if height_stats:
            lines.append("### 1.1 S0 Dataset Scale Statistics")
            lines.append("")
            lines.append(f"- **HEIGHT_M**: min={height_stats.get('min', 'N/A'):.3f}m, "
                        f"median={height_stats.get('median', 'N/A'):.3f}m, "
                        f"max={height_stats.get('max', 'N/A'):.3f}m")
            
            # Calculate circumference to height ratios
            for key in ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]:
                if key in summary:
                    circ_stats = summary[key].get("value_stats", {})
                    if circ_stats and height_stats.get("median"):
                        circ_median = circ_stats.get("median")
                        height_median = height_stats.get("median")
                        ratio = circ_median / height_median if height_median > 0 else None
                        if ratio is not None:
                            lines.append(f"- **{key}**: median={circ_median:.3f}m, "
                                        f"{key.split('_')[0]}/height ratio={ratio:.3f}")
            lines.append("")
    
    # Round15 / Round16: Bust (and waist/hip) verts alignment facts (from s0_circ_synth_trace_normal_1.json)
    if is_round15 or is_round16:
        _trace_path = Path(project_root) / "verification" / "datasets" / "runs" / "debug" / "s0_circ_synth_trace_normal_1.json"
        _sec = "Bust/waist/hip verts alignment (normal_1, fastmode)" if is_round16 else "Bust verts alignment (normal_1, fastmode)"
        if _trace_path.exists():
            try:
                with open(_trace_path, "r", encoding="utf-8") as _f:
                    _trace = json.load(_f)
                _im = _trace.get("intermediates", {})
                lines.append(f"### 1.2 {_sec}")
                lines.append("")
                lines.append("| Field | Value |")
                lines.append("|-------|-------|")
                _keys = (
                    ["bust_circ_after_scale_theoretical", "bust_circ_from_verts_before", "bust_circ_from_verts_after",
                     "waist_circ_from_verts_before", "waist_circ_from_verts_after",
                     "hip_circ_from_verts_before", "hip_circ_from_verts_after",
                     "bust_xz_scale_factor", "waist_xz_scale_factor", "hip_xz_scale_factor",
                     "torso_xz_scale_factor"]
                    if is_round16
                    else ["bust_circ_after_scale_theoretical", "bust_circ_from_verts_before",
                          "bust_circ_from_verts_after", "torso_xz_scale_factor"]
                )
                for _k in _keys:
                    _v = _im.get(_k)
                    if _v is not None:
                        _s = f"{_v:.4f}m" if "circ" in _k and "factor" not in _k else f"{_v:.4f}"
                        lines.append(f"| {_k} | {_s} |")
                _ca = _trace.get("clamp_applied", None)
                if _ca is not None:
                    lines.append(f"| clamp_applied | {_ca} |")
                lines.append("")
            except Exception as _e:
                lines.append(f"### 1.2 {_sec}")
                lines.append("")
                lines.append(f"(Trace read failed: {_e})")
                lines.append("")
        else:
            lines.append(f"### 1.2 {_sec}")
            lines.append("")
            lines.append("(Trace file not found.)")
            lines.append("")
    
    # Section 2: Key별 요약 테이블 (Valid Cases Only for DoD)
    lines.append("## 2. Key별 요약 (Valid Cases Only - DoD 평가 기준)")
    lines.append("")
    lines.append("**Valid Cases**: normal_* + varied_* (10개)")
    lines.append("")
    lines.append("| Key | Valid Total | Valid NaN | Valid NaN Rate | Min | Median | Max | DoD (<=40%) |")
    lines.append("|-----|-------------|-----------|----------------|-----|--------|-----|-------------|")
    
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        valid_cases = s.get("valid_cases", {})
        valid_total = valid_cases.get("total_count", 0)
        valid_nan = valid_cases.get("nan_count", 0)
        valid_nan_rate = valid_cases.get("nan_rate", 0.0)
        value_stats = s.get("value_stats", {})
        
        # DoD check for waist/hip width/depth
        dod_status = "N/A"
        if key in ["WAIST_WIDTH_M", "WAIST_DEPTH_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]:
            if valid_nan_rate <= 0.40:
                dod_status = "✅ PASS"
            else:
                dod_status = f"❌ FAIL ({valid_nan_rate:.1%})"
        
        if value_stats:
            lines.append(
                f"| {key} | {valid_total} | {valid_nan} | "
                f"{valid_nan_rate:.2%} | {value_stats.get('min', 'N/A'):.4f} | "
                f"{value_stats.get('median', 'N/A'):.4f} | {value_stats.get('max', 'N/A'):.4f} | {dod_status} |"
            )
        else:
            lines.append(
                f"| {key} | {valid_total} | {valid_nan} | "
                f"{valid_nan_rate:.2%} | N/A | N/A | N/A | {dod_status} |"
            )
    lines.append("")
    
    # Section 2.1: Expected Fail Cases (사실 기록만)
    lines.append("## 2.1 Expected Fail Cases (사실 기록)")
    lines.append("")
    lines.append("**Expected Fail Cases**: degenerate_y_range, minimal_vertices, scale_error_suspected, random_noise_seed123, tall_thin (5개)")
    lines.append("")
    lines.append("| Key | Expected Fail Total | Expected Fail NaN | Expected Fail NaN Rate |")
    lines.append("|-----|---------------------|-------------------|------------------------|")
    
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        expected_fail_cases = s.get("expected_fail_cases", {})
        ef_total = expected_fail_cases.get("total_count", 0)
        ef_nan = expected_fail_cases.get("nan_count", 0)
        ef_nan_rate = expected_fail_cases.get("nan_rate", 0.0)
        lines.append(
            f"| {key} | {ef_total} | {ef_nan} | {ef_nan_rate:.2%} |"
        )
    lines.append("")
    
    # Section 3: Warnings Top 리스트
    lines.append("## 3. Warnings Top 리스트")
    lines.append("")
    
    # Overall warnings
    all_warnings = defaultdict(int)
    for key, s in summary.items():
        for w_type, count in s.get("warnings_top5", []):
            all_warnings[w_type] += count
    
    lines.append("### 3.1 전체 Warnings Top 10")
    lines.append("")
    lines.append("| Warning Type | Count |")
    lines.append("|--------------|-------|")
    for w_type, count in sorted(all_warnings.items(), key=lambda x: x[1], reverse=True)[:10]:
        lines.append(f"| {w_type} | {count} |")
    lines.append("")
    
    # Key별 warnings
    lines.append("### 3.2 Key별 Warnings Top 5")
    lines.append("")
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        warnings_top5 = s.get("warnings_top5", [])
        if warnings_top5:
            lines.append(f"**{key}**:")
            for w_type, count in warnings_top5:
                lines.append(f"- `{w_type}`: {count}")
            lines.append("")
    
    # Section 4: Proxy/Band Scan/Side 기록 통계
    lines.append("## 4. Proxy/Band Scan/Side 기록 통계")
    lines.append("")
    
    lines.append("### 4.1 Proxy 사용")
    lines.append("")
    lines.append("| Key | Proxy Used Count | Proxy Types |")
    lines.append("|-----|------------------|-------------|")
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        proxy_types = s.get("proxy_types", {})
        proxy_types_str = ", ".join([f"{k}: {v}" for k, v in proxy_types.items()]) if proxy_types else "N/A"
        lines.append(f"| {key} | {s.get('proxy_used_count', 0)} | {proxy_types_str} |")
    lines.append("")
    
    lines.append("### 4.2 Band Scan 사용")
    lines.append("")
    lines.append("| Key | Band Scan Used Count | Band Scan Limits |")
    lines.append("|-----|----------------------|------------------|")
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        limits = s.get("band_scan_limits", [])
        limits_str = ", ".join([str(l) for l in limits]) if limits else "N/A"
        lines.append(f"| {key} | {s.get('band_scan_used_count', 0)} | {limits_str} |")
    lines.append("")
    
    lines.append("### 4.3 Canonical Side 기록")
    lines.append("")
    lines.append("| Key | Canonical Sides |")
    lines.append("|-----|-----------------|")
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        sides = s.get("canonical_sides", {})
        sides_str = ", ".join([f"{k}: {v}" for k, v in sides.items()]) if sides else "N/A"
        lines.append(f"| {key} | {sides_str} |")
    lines.append("")
    
    lines.append("### 4.4 Pose Unknown 비율")
    lines.append("")
    lines.append("| Key | Breath State Unknown | Arms Down Unknown | Strict Standing Unknown | Knee Flexion Unknown |")
    lines.append("|-----|----------------------|-------------------|------------------------|----------------------|")
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        pose_unknown = s.get("pose_unknown_rates", {})
        lines.append(
            f"| {key} | "
            f"{pose_unknown.get('breath_state', 0.0):.2%} | "
            f"{pose_unknown.get('arms_down', 0.0):.2%} | "
            f"{pose_unknown.get('strict_standing', 0.0):.2%} | "
            f"{pose_unknown.get('knee_flexion_forbidden', 0.0):.2%} |"
        )
    lines.append("")
    
    # Section 4.5: Debug 정보 (실패 원인 분해)
    lines.append("### 4.5 Debug 정보 (실패 원인 분해)")
    lines.append("")
    
    # Cross-section reasons with detailed breakdown
    lines.append("#### 4.5.1 CROSS_SECTION_NOT_FOUND 원인 분포")
    lines.append("")
    lines.append("| Key | Reason | Count | Percentage |")
    lines.append("|-----|--------|-------|------------|")
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        debug_summary = s.get("debug_summary", {})
        cross_section_reasons = debug_summary.get("cross_section_reasons", {})
        total_count = s.get("total_count", 0)
        if cross_section_reasons:
            for reason, count in sorted(cross_section_reasons.items(), key=lambda x: x[1], reverse=True):
                pct = (count / total_count * 100) if total_count > 0 else 0.0
                lines.append(f"| {key} | {reason} | {count} | {pct:.1f}% |")
        else:
            # Check if CROSS_SECTION_NOT_FOUND warning exists
            warnings_top5 = s.get("warnings_top5", [])
            if any("CROSS_SECTION_NOT_FOUND" in w[0] for w in warnings_top5):
                lines.append(f"| {key} | (no debug info) | - | - |")
    lines.append("")
    
    # Cross-section candidates count
    lines.append("#### 4.5.2 Cross-section Candidates Count 통계")
    lines.append("")
    lines.append("| Key | Min | Median | Max | Zero Count |")
    lines.append("|-----|-----|--------|-----|-----------|")
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        debug_summary = s.get("debug_summary", {})
        candidates_stats = debug_summary.get("cross_section_candidates_counts", {})
        if candidates_stats:
            lines.append(
                f"| {key} | {candidates_stats.get('min', 0)} | "
                f"{candidates_stats.get('median', 0.0):.1f} | "
                f"{candidates_stats.get('max', 0)} | "
                f"{candidates_stats.get('zero_count', 0)} |"
            )
    lines.append("")
    
    # Body axis reasons
    lines.append("#### 4.5.3 BODY_AXIS_TOO_SHORT 원인 분포")
    lines.append("")
    lines.append("| Key | Reason | Count |")
    lines.append("|-----|--------|-------|")
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        debug_summary = s.get("debug_summary", {})
        body_axis_reasons = debug_summary.get("body_axis_reasons", {})
        if body_axis_reasons:
            for reason, count in body_axis_reasons.items():
                lines.append(f"| {key} | {reason} | {count} |")
    lines.append("")
    
    # Landmark regions reasons
    lines.append("#### 4.5.4 LANDMARK_REGIONS_NOT_FOUND 원인 분포")
    lines.append("")
    lines.append("| Key | Reason | Count |")
    lines.append("|-----|--------|-------|")
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        debug_summary = s.get("debug_summary", {})
        landmark_reasons = debug_summary.get("landmark_reasons", {})
        if landmark_reasons:
            for reason, count in landmark_reasons.items():
                lines.append(f"| {key} | {reason} | {count} |")
    lines.append("")
    
    # Section 5: Nearest Valid Plane Fallback 통계 (Valid Cases)
    lines.append("## 5. Nearest Valid Plane Fallback 통계 (Valid Cases)")
    lines.append("")
    lines.append("| Key | Used Count | Used Rate | Shift Min (mm) | Shift Median (mm) | Shift Max (mm) |")
    lines.append("|-----|------------|-----------|----------------|------------------|----------------|")
    
    for key in ["WAIST_WIDTH_M", "WAIST_DEPTH_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]:
        if key not in summary:
            continue
        s = summary[key]
        nvp_stats = s.get("nearest_valid_plane_stats", {})
        valid_total = s.get("valid_cases", {}).get("total_count", 0)
        used_count = nvp_stats.get("used_count", 0)
        used_rate = used_count / valid_total if valid_total > 0 else 0.0
        shift_stats = nvp_stats.get("shift_mm", {})
        
        if shift_stats:
            lines.append(
                f"| {key} | {used_count} | {used_rate:.2%} | "
                f"{shift_stats.get('min', 'N/A')} | {shift_stats.get('median', 'N/A'):.1f} | "
                f"{shift_stats.get('max', 'N/A')} |"
            )
        else:
            lines.append(
                f"| {key} | {used_count} | {used_rate:.2%} | N/A | N/A | N/A |"
            )
    lines.append("")
    
    # Section 5.1: Slice Sharing 통계 (Valid Cases)
    lines.append("### 5.1 Slice Sharing 통계 (Valid Cases)")
    lines.append("")
    lines.append("| Key | Slice Shared Count | Slice Shared Rate | Slicer Independent False | Shared From |")
    lines.append("|-----|-------------------|-------------------|--------------------------|-------------|")
    
    for key in ["WAIST_WIDTH_M", "WAIST_DEPTH_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]:
        if key not in summary:
            continue
        s = summary[key]
        slice_stats = s.get("slice_sharing_stats", {})
        valid_total = s.get("valid_cases", {}).get("total_count", 0)
        
        shared_count = slice_stats.get("slice_shared_count", 0)
        shared_rate = slice_stats.get("slice_shared_rate", 0.0)
        independent_false = slice_stats.get("slicer_independent_false_count", 0)
        shared_from = slice_stats.get("slice_shared_from_keys", {})
        shared_from_str = ", ".join([f"{k}:{v}" for k, v in shared_from.items()]) if shared_from else "N/A"
        
        lines.append(
            f"| {key} | {shared_count} | {shared_rate:.2%} | {independent_false} | {shared_from_str} |"
        )
    lines.append("")
    
    # Section 5.2: Target/Bbox Debug 통계 (Valid Cases)
    lines.append("### 5.2 Target/Bbox Debug 통계 (Valid Cases)")
    lines.append("")
    lines.append("| Key | Target Out of Bounds Count | Out of Bounds Rate | Initial Candidates (Zero Count) | Fallback Candidates (Median) |")
    lines.append("|-----|---------------------------|-------------------|--------------------------------|------------------------------|")
    
    for key in ["WAIST_WIDTH_M", "WAIST_DEPTH_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]:
        if key not in summary:
            continue
        s = summary[key]
        tbb_stats = s.get("target_bbox_stats", {})
        valid_total = s.get("valid_cases", {}).get("total_count", 0)
        
        out_of_bounds_count = tbb_stats.get("target_out_of_bounds_count", 0)
        out_of_bounds_rate = tbb_stats.get("target_out_of_bounds_rate", 0.0)
        
        initial_stats = tbb_stats.get("initial_candidates_count", {})
        initial_zero_count = initial_stats.get("zero_count", 0) if initial_stats else 0
        
        fallback_stats = tbb_stats.get("fallback_candidates_count", {})
        fallback_median = fallback_stats.get("median", "N/A") if fallback_stats else "N/A"
        
        lines.append(
            f"| {key} | {out_of_bounds_count} | {out_of_bounds_rate:.2%} | "
            f"{initial_zero_count} | {fallback_median} |"
        )
    lines.append("")
    
    # Section 5.3: HEIGHT_M Debug 통계 (Valid Cases)
    lines.append("### 5.3 HEIGHT_M Debug 통계 (Valid Cases)")
    lines.append("")
    if "HEIGHT_M" in summary:
        s = summary["HEIGHT_M"]
        debug_summary = s.get("debug_summary", {})
        bbox_comp = debug_summary.get("bbox_comparison", {})
        height_calc = debug_summary.get("height_calculation", {})
        
        # Bbox comparison
        if bbox_comp:
            lines.append("#### 5.3.1 Bbox 최장축 비교")
            lines.append("")
            longest_axis_dist = bbox_comp.get("bbox_longest_axis_distribution", {})
            if longest_axis_dist:
                lines.append("| Longest Axis | Count | Percentage |")
                lines.append("|--------------|-------|------------|")
                total = sum(longest_axis_dist.values())
                for axis, count in sorted(longest_axis_dist.items(), key=lambda x: x[1], reverse=True):
                    pct = (count / total * 100) if total > 0 else 0.0
                    lines.append(f"| {axis} | {count} | {pct:.1f}% |")
                lines.append("")
            
            longest_span = bbox_comp.get("bbox_longest_span_m", {})
            if longest_span:
                lines.append("**Bbox Longest Span**: ")
                lines.append(f"min={longest_span.get('min', 'N/A'):.4f}m, ")
                lines.append(f"median={longest_span.get('median', 'N/A'):.4f}m, ")
                lines.append(f"max={longest_span.get('max', 'N/A'):.4f}m")
                lines.append("")
            
            # Span comparison table
            lines.append("| Axis | Span Min (m) | Span Median (m) | Span Max (m) |")
            lines.append("|------|--------------|-----------------|--------------|")
            for axis in ["x", "y", "z"]:
                span_key = f"bbox_span_{axis}"
                span_stats = bbox_comp.get(span_key, {})
                if span_stats:
                    lines.append(
                        f"| {axis} | {span_stats.get('min', 'N/A'):.4f} | "
                        f"{span_stats.get('median', 'N/A'):.4f} | {span_stats.get('max', 'N/A'):.4f} |"
                    )
                else:
                    lines.append(f"| {axis} | N/A | N/A | N/A |")
            lines.append("")
        
        # Height calculation
        if height_calc:
            lines.append("#### 5.3.2 HEIGHT_M 계산 통계")
            lines.append("")
            axis_used_dist = height_calc.get("axis_used_distribution", {})
            if axis_used_dist:
                lines.append("| Axis Used | Count | Percentage |")
                lines.append("|-----------|-------|------------|")
                total = sum(axis_used_dist.values())
                for axis, count in sorted(axis_used_dist.items(), key=lambda x: x[1], reverse=True):
                    pct = (count / total * 100) if total > 0 else 0.0
                    lines.append(f"| {axis} | {count} | {pct:.1f}% |")
                lines.append("")
            
            raw_span = height_calc.get("raw_span_m", {})
            post_span = height_calc.get("post_transform_span_m", {})
            scale_factor = height_calc.get("scale_factor_raw_to_post", {})
            
            if raw_span:
                lines.append("**Raw Span (m)**: ")
                lines.append(f"min={raw_span.get('min', 'N/A'):.4f}, ")
                lines.append(f"median={raw_span.get('median', 'N/A'):.4f}, ")
                lines.append(f"max={raw_span.get('max', 'N/A'):.4f}")
                lines.append("")
            
            if post_span:
                lines.append("**Post-Transform Span (m)**: ")
                lines.append(f"min={post_span.get('min', 'N/A'):.4f}, ")
                lines.append(f"median={post_span.get('median', 'N/A'):.4f}, ")
                lines.append(f"max={post_span.get('max', 'N/A'):.4f}")
                lines.append("")
            
            if scale_factor:
                lines.append("**Scale Factor (raw->post)**: ")
                lines.append(f"min={scale_factor.get('min', 'N/A'):.4f}, ")
                lines.append(f"median={scale_factor.get('median', 'N/A'):.4f}, ")
                lines.append(f"max={scale_factor.get('max', 'N/A'):.4f}")
                lines.append("")
            
            # Suspicious scale factor counts
            suspicious = height_calc.get("suspicious_scale_factor_counts", {})
            if suspicious:
                lines.append("**의심 배율 카운트**: ")
                lines.append(f"near 1.0: {suspicious.get('near_1.0', 0)}, ")
                lines.append(f"near 0.5: {suspicious.get('near_0.5', 0)}, ")
                lines.append(f"near 0.1: {suspicious.get('near_0.1', 0)}, ")
                lines.append(f"near 0.01: {suspicious.get('near_0.01', 0)}, ")
                lines.append(f"near 10: {suspicious.get('near_10', 0)}, ")
                lines.append(f"near 100: {suspicious.get('near_100', 0)}")
                lines.append("")
        
        # Cause classification
        if bbox_comp and height_calc:
            lines.append("#### 5.3.3 원인 분류 (Facts 기반)")
            lines.append("")
            longest_axis_dist = bbox_comp.get("bbox_longest_axis_distribution", {})
            axis_used_dist = height_calc.get("axis_used_distribution", {})
            
            # Case A: Axis selection error
            case_a_evidence = []
            if longest_axis_dist and axis_used_dist:
                longest_axis = max(longest_axis_dist.items(), key=lambda x: x[1])[0] if longest_axis_dist else None
                used_axis = max(axis_used_dist.items(), key=lambda x: x[1])[0] if axis_used_dist else None
                if longest_axis != used_axis:
                    case_a_evidence.append(f"bbox_longest_axis={longest_axis} != axis_used={used_axis}")
            
            # Case B: Scale conversion error
            case_b_evidence = []
            raw_span = height_calc.get("raw_span_m", {})
            post_span = height_calc.get("post_transform_span_m", {})
            scale_factor = height_calc.get("scale_factor_raw_to_post", {})
            if raw_span and post_span and scale_factor:
                raw_median = raw_span.get("median")
                post_median = post_span.get("median")
                scale_median = scale_factor.get("median")
                if raw_median and post_median and scale_median:
                    if 1.4 <= raw_median <= 2.0 and post_median < 1.0:
                        case_b_evidence.append(f"raw_span={raw_median:.3f}m (human-like) but post_span={post_median:.3f}m (shrunk)")
                    if abs(scale_median - 1.0) > 0.02:
                        case_b_evidence.append(f"scale_factor={scale_median:.4f} != 1.0")
            
            # Case C: S0 coordinates already shrunk
            case_c_evidence = []
            if raw_span:
                raw_median = raw_span.get("median")
                if raw_median and raw_median < 1.0:
                    case_c_evidence.append(f"raw_span_median={raw_median:.3f}m < 1.0m (mesh already shrunk)")
            
            lines.append("| Case | Evidence |")
            lines.append("|------|----------|")
            if case_a_evidence:
                lines.append(f"| **Case A (Axis Selection Error)** | {'; '.join(case_a_evidence)} |")
            if case_b_evidence:
                lines.append(f"| **Case B (Scale Conversion Error)** | {'; '.join(case_b_evidence)} |")
            if case_c_evidence:
                lines.append(f"| **Case C (S0 Coordinates Shrunk)** | {'; '.join(case_c_evidence)} |")
            if not case_a_evidence and not case_b_evidence and not case_c_evidence:
                lines.append("| (원인 분류 불가 - 추가 분석 필요) | |")
            lines.append("")
        else:
            lines.append("(HEIGHT_M debug info not available)")
    else:
        lines.append("(HEIGHT_M not in summary)")
    lines.append("")
    
    # Section 6: S0 Scale Normalization 통계 (Valid Cases) - Round 9/10/11/12/13
    if is_round9 or is_round10 or is_round11 or is_round12 or is_round13:
        lines.append("## 6. S0 Scale Normalization 통계 (Valid Cases)")
        lines.append("")
        lines.append("### 6.1 HEIGHT_M 및 Bbox Span 통계")
        lines.append("")
        if "HEIGHT_M" in summary:
            s = summary["HEIGHT_M"]
            value_stats = s.get("value_stats", {})
            valid_cases = s.get("valid_cases", {})
            if value_stats:
                if is_round12:
                    lines.append("| Statistic | Round 8/9/10/11 (Before) | Round 12 (After Generator Fix) |")
                    lines.append("|-----------|--------------------------|-------------------------------|")
                    lines.append(f"| HEIGHT_M Median | 0.8625m | {value_stats.get('median', 'N/A'):.4f}m |")
                    lines.append(f"| HEIGHT_M Min | 0.765m | {value_stats.get('min', 'N/A'):.4f}m |")
                    lines.append(f"| HEIGHT_M Max | 0.960m | {value_stats.get('max', 'N/A'):.4f}m |")
                elif is_round11:
                    lines.append("| Statistic | Round 8 (Before) | Round 9/10 (No Change) | Round 11 (After Re-open Proof) |")
                    lines.append("|-----------|------------------|----------------------|------------------------------|")
                    lines.append(f"| HEIGHT_M Median | 0.8625m | 0.8625m | {value_stats.get('median', 'N/A'):.4f}m |")
                    lines.append(f"| HEIGHT_M Min | 0.765m | 0.765m | {value_stats.get('min', 'N/A'):.4f}m |")
                    lines.append(f"| HEIGHT_M Max | 0.960m | 0.960m | {value_stats.get('max', 'N/A'):.4f}m |")
                elif is_round10:
                    lines.append("| Statistic | Round 8 (Before) | Round 9 (No Change) | Round 10 (After Fix) |")
                    lines.append("|-----------|------------------|-------------------|---------------------|")
                    lines.append(f"| HEIGHT_M Median | 0.8625m | 0.8625m | {value_stats.get('median', 'N/A'):.4f}m |")
                    lines.append(f"| HEIGHT_M Min | 0.765m | 0.765m | {value_stats.get('min', 'N/A'):.4f}m |")
                    lines.append(f"| HEIGHT_M Max | 0.960m | 0.960m | {value_stats.get('max', 'N/A'):.4f}m |")
                else:
                    lines.append("| Statistic | Round 8 (Before) | Round 9 (After) |")
                    lines.append("|-----------|------------------|----------------|")
                    lines.append(f"| HEIGHT_M Median | 0.8625m | {value_stats.get('median', 'N/A'):.4f}m |")
                    lines.append(f"| HEIGHT_M Min | 0.765m | {value_stats.get('min', 'N/A'):.4f}m |")
                    lines.append(f"| HEIGHT_M Max | 0.960m | {value_stats.get('max', 'N/A'):.4f}m |")
            lines.append("")
            
            # Bbox span statistics
            debug_summary = s.get("debug_summary", {})
            bbox_comp = debug_summary.get("bbox_comparison", {})
            if bbox_comp:
                longest_span = bbox_comp.get("bbox_longest_span_m", {})
                span_y = bbox_comp.get("bbox_span_y", {})
                if longest_span and span_y:
                    lines.append("**Bbox Longest Span (m)**: ")
                    lines.append(f"min={longest_span.get('min', 'N/A'):.4f}, ")
                    lines.append(f"median={longest_span.get('median', 'N/A'):.4f}, ")
                    lines.append(f"max={longest_span.get('max', 'N/A'):.4f}")
                    lines.append("")
                    lines.append("**Bbox Span Y (m)**: ")
                    lines.append(f"min={span_y.get('min', 'N/A'):.4f}, ")
                    lines.append(f"median={span_y.get('median', 'N/A'):.4f}, ")
                    lines.append(f"max={span_y.get('max', 'N/A'):.4f}")
                    lines.append("")
        
        # Scale factor statistics
        if "HEIGHT_M" in summary:
            s = summary["HEIGHT_M"]
            debug_summary = s.get("debug_summary", {})
            height_calc = debug_summary.get("height_calculation", {})
            if height_calc:
                scale_factor = height_calc.get("scale_factor_raw_to_post", {})
                if scale_factor:
                    lines.append("**Scale Factor (raw->post)**: ")
                    lines.append(f"min={scale_factor.get('min', 'N/A'):.4f}, ")
                    lines.append(f"median={scale_factor.get('median', 'N/A'):.4f}, ")
                    lines.append(f"max={scale_factor.get('max', 'N/A'):.4f}")
                    lines.append("")
                    lines.append("(정상: scale_factor=1.0, mesh 좌표가 이미 정규화됨)")
                    lines.append("")
        
        # Circumference to height ratios
        lines.append("### 6.2 둘레/키 비율 (Valid Cases)")
        lines.append("")
        lines.append("| Ratio | Min | Median | Max |")
        lines.append("|-------|-----|--------|-----|")
        if "HEIGHT_M" in summary:
            height_stats = summary["HEIGHT_M"].get("value_stats", {})
            height_median = height_stats.get("median")
            if height_median:
                for key in ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]:
                    if key in summary:
                        circ_stats = summary[key].get("value_stats", {})
                        if circ_stats and height_median:
                            circ_median = circ_stats.get("median")
                            ratio = circ_median / height_median if height_median > 0 else None
                            if ratio is not None:
                                # Calculate min/max ratios
                                circ_min = circ_stats.get("min")
                                circ_max = circ_stats.get("max")
                                height_min = height_stats.get("min")
                                height_max = height_stats.get("max")
                                ratio_min = circ_min / height_max if circ_min and height_max and height_max > 0 else None
                                ratio_max = circ_max / height_min if circ_max and height_min and height_min > 0 else None
                                
                                ratio_name = key.split("_")[0].lower()
                                if ratio_min is not None and ratio_max is not None:
                                    lines.append(
                                        f"| {ratio_name}/height | "
                                        f"{ratio_min:.3f} | {ratio:.3f} | {ratio_max:.3f} |"
                                    )
        lines.append("")
        
        # Round 10/11: Scale application proof logs summary
        if is_round10 or is_round11:
            lines.append("### 6.3 Scale 적용 증거 로그 요약")
            lines.append("")
            lines.append("(create_s0_dataset.py 실행 로그에서 다음 정보 확인)")
            lines.append("")
            lines.append("| Case ID | bbox_span_y_before | target_height_m | scale_factor | bbox_span_y_after |")
            lines.append("|---------|-------------------|-----------------|--------------|------------------|")
            lines.append("| (로그에서 샘플 2~3개 복사) |")
            lines.append("")
            lines.append("**확인 사항**:")
            lines.append("- scale_factor가 1.0이 아님")
            lines.append("- bbox_span_y_after ≈ target_height_m (tolerance 5cm)")
            lines.append("- NPZ 저장 경로가 runner 로드 경로와 일치")
            lines.append("")
        
        # Round 11: Re-open proof summary
        if is_round11:
            lines.append("### 6.4 Re-open Proof 통과 여부")
            lines.append("")
            lines.append("(create_s0_dataset.py 실행 로그에서 `[RE-OPEN PROOF]` 섹션 확인)")
            lines.append("")
            lines.append("**핵심 검증**:")
            lines.append("- NPZ 저장 직후 `np.load()`로 파일을 다시 열어서 검증")
            lines.append("- `assert bbox_span_y_reloaded ≈ target_height_m` (tolerance 5cm)")
            lines.append("- 모든 valid cases에서 assert 통과 여부 확인")
            lines.append("")
            lines.append("| Case ID | bbox_span_y_before | target_height_m | bbox_span_y_reloaded | scale_factor | diff |")
            lines.append("|---------|-------------------|-----------------|---------------------|--------------|------|")
            lines.append("| (로그에서 샘플 2~3개 복사) |")
            lines.append("")
            lines.append("**DoD**: Re-open proof assert가 모든 valid cases에서 통과해야 함")
            lines.append("")
        
        # Section 7: Round 7 회귀 체크 (Valid Cases 기준)
        lines.append("## 7. Round 7 Slice-Sharing 회귀 체크 (Valid Cases 기준)")
        lines.append("")
        lines.append("### 7.1 Waist/Hip NaN율 (회귀 확인)")
        lines.append("")
        if is_round11:
            round_label = "Round 11"
        elif is_round10:
            round_label = "Round 10"
        else:
            round_label = "Round 9"
        lines.append(f"| Key | Round 7 NaN율 | {round_label} NaN율 | 변화 |")
        lines.append("|-----|---------------|---------------|------|")
        for key in ["WAIST_CIRC_M", "WAIST_WIDTH_M", "WAIST_DEPTH_M", "HIP_CIRC_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]:
            if key not in summary:
                continue
            s = summary[key]
            valid_cases = s.get("valid_cases", {})
            valid_nan_rate = valid_cases.get("nan_rate", 0.0)
            lines.append(f"| {key} | (Round 7) | {valid_nan_rate:.2%} | - |")
        lines.append("")
        lines.append("### 7.2 Slice Sharing 유지 확인 (Valid Cases)")
        lines.append("")
        lines.append("| Key | Slice Shared Rate | Slicer Independent False Rate |")
        lines.append("|-----|-------------------|-------------------------------|")
        for key in ["WAIST_WIDTH_M", "WAIST_DEPTH_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]:
            if key not in summary:
                continue
            s = summary[key]
            slice_stats = s.get("slice_sharing_stats", {})
            shared_rate = slice_stats.get("slice_shared_rate", 0.0)
            independent_false_rate = slice_stats.get("slicer_independent_false_rate", 0.0)
            lines.append(f"| {key} | {shared_rate:.2%} | {independent_false_rate:.2%} |")
        lines.append("")
    else:
        # Fallback for other rounds
        lines.append("## 6. Round Comparison")
        lines.append("")
        lines.append("(Round comparison data not available)")
        lines.append("")
    
    # Section 8: 이슈 분류
    lines.append("## 8. 이슈 분류")
    lines.append("")
    
    issues = {
        "GEO_BUG": [],
        "POSE/PROXY": [],
        "COVERAGE/UNKNOWN": []
    }
    
    for key in ALL_KEYS:
        if key not in summary:
            continue
        s = summary[key]
        
        # GEO_BUG: 물리적으로 말이 안 되는 범위
        value_stats = s.get("value_stats", {})
        if value_stats:
            min_val = value_stats.get("min", 0)
            max_val = value_stats.get("max", 0)
            # Check for unreasonable ranges
            if "CIRC" in key:
                if max_val > 3.0:  # > 3m circumference
                    issues["GEO_BUG"].append(f"{key}: max circumference {max_val:.4f}m > 3.0m")
                if min_val < 0.1:  # < 10cm circumference
                    issues["GEO_BUG"].append(f"{key}: min circumference {min_val:.4f}m < 0.1m")
            elif "HEIGHT" in key or key == "ARM_LEN_M":
                if max_val > 3.0:  # > 3m height/length
                    issues["GEO_BUG"].append(f"{key}: max {max_val:.4f}m > 3.0m")
                if min_val < 0.1:  # < 10cm
                    issues["GEO_BUG"].append(f"{key}: min {min_val:.4f}m < 0.1m")
            elif "WIDTH" in key or "DEPTH" in key:
                if max_val > 1.0:  # > 1m width/depth
                    issues["GEO_BUG"].append(f"{key}: max {max_val:.4f}m > 1.0m")
                if min_val < 0.05:  # < 5cm
                    issues["GEO_BUG"].append(f"{key}: min {min_val:.4f}m < 0.05m")
        
        # POSE/PROXY: proxy_used가 높음
        if s.get("proxy_used_count", 0) > s.get("total_count", 1) * 0.5:
            issues["POSE/PROXY"].append(f"{key}: proxy_used rate {s.get('proxy_used_count', 0)/s.get('total_count', 1):.2%}")
        
        # COVERAGE/UNKNOWN: 메타 unknown 과다
        pose_unknown = s.get("pose_unknown_rates", {})
        for pose_key, rate in pose_unknown.items():
            if rate > 0.5:  # > 50% unknown
                issues["COVERAGE/UNKNOWN"].append(f"{key}: {pose_key} unknown rate {rate:.2%}")
    
    for issue_type, issue_list in issues.items():
        if issue_list:
            lines.append(f"### {issue_type}")
            lines.append("")
            for issue in issue_list:
                lines.append(f"- {issue}")
            lines.append("")
        else:
            lines.append(f"### {issue_type}")
            lines.append("")
            lines.append("- (없음)")
            lines.append("")
    
    # Write report
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
