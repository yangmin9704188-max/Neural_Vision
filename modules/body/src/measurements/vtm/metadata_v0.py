# metadata_v0.py
# Metadata Schema v0 - Helper utilities for generating measurement metadata
# Purpose: Generate metadata JSON according to docs/validation/measurement_metadata_schema_v0.md

from __future__ import annotations
from typing import Dict, List, Optional, Any, Literal
import json


def create_metadata_v0(
    standard_key: str,
    method_path_type: Literal["straight_line", "surface_path", "closed_curve"],
    method_metric_type: Literal["circumference", "width", "depth", "height", "length", "mass"],
    value_m: Optional[float] = None,
    value_kg: Optional[float] = None,
    warnings: Optional[List[str]] = None,
    # Optional fields
    method_canonical_side: Optional[Literal["right", "left", "bilateral"]] = None,
    method_landmark_confidence: Optional[Literal["high", "medium", "low"]] = None,
    method_landmark_resolution: Optional[Literal["direct", "nearest_cross_section_fallback"]] = None,
    method_fixed_height_required: Optional[bool] = None,
    method_fixed_cross_section_required: Optional[bool] = None,
    search_band_scan_used: bool = False,
    search_band_scan_limit_mm: int = 10,
    search_min_max_search_used: bool = False,
    search_nearest_valid_plane_used: bool = False,
    search_nearest_valid_plane_shift_mm: Optional[int] = None,
    proxy_proxy_used: bool = False,
    proxy_proxy_type: Optional[Literal["plane_clamp", "other"]] = None,
    proxy_proxy_tool: Optional[str] = None,
    pose_breath_state: Optional[Literal["neutral_mid", "unknown"]] = None,
    pose_arms_down: Optional[bool | Literal["unknown"]] = None,
    pose_strict_standing: Optional[bool | Literal["unknown"]] = None,
    pose_knee_flexion_forbidden: Optional[bool | Literal["unknown"]] = None,
    provenance_evidence_ref: Optional[str] = None,
    debug_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create metadata JSON according to measurement_metadata_schema_v0.md.
    
    Args:
        standard_key: Standard key name (e.g., "BUST_CIRC_M")
        value_m: Value in meters (for length/circumference/width/depth/height)
        value_kg: Value in kilograms (for weight)
        method_path_type: Path type enum
        method_metric_type: Metric type enum
        warnings: List of warning strings (empty list if None)
        ... (other optional fields)
    
    Returns:
        Metadata dictionary conforming to schema v0
    """
    # Determine unit and value key
    if value_kg is not None:
        unit = "kg"
        value_key = "value_kg"
        value = value_kg
    else:
        unit = "m"
        value_key = "value_m"
        value = value_m if value_m is not None else float('nan')
    
    # Build method dict
    method: Dict[str, Any] = {
        "path_type": method_path_type,
        "metric_type": method_metric_type,
    }
    if method_canonical_side is not None:
        method["canonical_side"] = method_canonical_side
    if method_landmark_confidence is not None:
        method["landmark_confidence"] = method_landmark_confidence
    if method_landmark_resolution is not None:
        method["landmark_resolution"] = method_landmark_resolution
    if method_fixed_height_required is not None:
        method["fixed_height_required"] = method_fixed_height_required
    if method_fixed_cross_section_required is not None:
        method["fixed_cross_section_required"] = method_fixed_cross_section_required
    
    # Build search dict
    search: Dict[str, Any] = {
        "band_scan_used": search_band_scan_used,
        "band_scan_limit_mm": search_band_scan_limit_mm,
        "min_max_search_used": search_min_max_search_used,
    }
    if search_nearest_valid_plane_used:
        search["nearest_valid_plane_used"] = True
        if search_nearest_valid_plane_shift_mm is not None:
            search["nearest_valid_plane_shift_mm"] = search_nearest_valid_plane_shift_mm
    
    # Build proxy dict
    proxy: Dict[str, Any] = {
        "proxy_used": proxy_proxy_used,
    }
    if proxy_proxy_type is not None:
        proxy["proxy_type"] = proxy_proxy_type
    if proxy_proxy_tool is not None:
        proxy["proxy_tool"] = proxy_proxy_tool
    
    # Build pose dict
    pose: Dict[str, Any] = {}
    if pose_breath_state is not None:
        pose["breath_state"] = pose_breath_state
    if pose_arms_down is not None:
        pose["arms_down"] = pose_arms_down
    if pose_strict_standing is not None:
        pose["strict_standing"] = pose_strict_standing
    if pose_knee_flexion_forbidden is not None:
        pose["knee_flexion_forbidden"] = pose_knee_flexion_forbidden
    
    # Build provenance dict
    provenance: Dict[str, Any] = {
        "source": "sizekorea",
    }
    if provenance_evidence_ref is not None:
        provenance["evidence_ref"] = provenance_evidence_ref
    
    # Build version dict
    version: Dict[str, Any] = {
        "semantic_tag": "semantic-v0",
        "schema_version": "metadata-schema-v0",
    }
    
    # Assemble metadata
    metadata: Dict[str, Any] = {
        "standard_key": standard_key,
        value_key: value,
        "unit": unit,
        "precision": 0.001,
        "method": method,
        "search": search,
        "proxy": proxy,
        "provenance": provenance,
        "warnings": warnings if warnings is not None else [],
        "version": version,
    }
    
    # Add pose only if it has content
    if pose:
        metadata["pose"] = pose
    
    # Add debug info if provided
    if debug_info:
        metadata["debug"] = debug_info
    
    return metadata


def get_evidence_ref(standard_key: str) -> str:
    """
    Get evidence reference path for a standard key.
    Returns path like: docs/semantic/evidence/sizekorea_measurement_methods_v0.md#key_name
    """
    key_lower = standard_key.lower()
    return f"docs/semantic/evidence/sizekorea_measurement_methods_v0.md#{key_lower}"
