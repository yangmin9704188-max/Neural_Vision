"""
Purpose: Bust/underbust circumference measurement.
Inputs: verts, faces (mesh)
Outputs: BustUnderbustResult
Status: active
"""
# bust_underbust_v0.py
# Policy compliance:
# - SEMANTIC_DEFINITION_BUST_VNEXT.md / SEMANTIC_DEFINITION_UNDERBUST_VNEXT.md
# - CONTRACT_INTERFACE_BUST_UNDERBUST_V0.md

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Literal
import numpy as np
import json
import re
import math

# -----------------------------
# Types
# -----------------------------
MeasurementKey = Literal["UNDERBUST", "BUST"]


@dataclass
class BustUnderbustResult:
    """Interface contract output structure."""
    measurement_key: str
    circumference_m: float  # meters or NaN
    section_id: str  # JSON-serializable, reproducible
    method_tag: str
    warnings: List[str]


# -----------------------------
# Constants (from Contract)
# -----------------------------
BAND_CM_MIN = 65
BAND_CM_MAX = 90
ALLOWED_CUPS = ["A", "B", "C", "D", "E", "F"]
CUP_DELTA_CM = {
    "A": 10.0,
    "B": 12.5,
    "C": 15.0,
    "D": 17.5,
    "E": 20.0,
    "F": 22.5,
}


# -----------------------------
# Utilities
# -----------------------------
def _as_np_f32(x: np.ndarray) -> np.ndarray:
    """Convert to float32 numpy array."""
    if not isinstance(x, np.ndarray):
        x = np.array(x)
    if x.dtype != np.float32:
        x = x.astype(np.float32, copy=False)
    return x


def _parse_bra_size(bra_size_token: str) -> tuple[Optional[int], Optional[str], List[str]]:
    """
    Parse bra size token (e.g., "75A").
    Returns: (band_cm, cup, warnings)
    Contract Violation: Returns (None, None, warnings) instead of raising exception.
    """
    warnings: List[str] = []
    
    if not isinstance(bra_size_token, str):
        warnings.append("FORMAT_VIOLATION")
        return None, None, warnings
    
    # Pattern: digits + single letter
    match = re.match(r'^(\d+)([A-F])$', bra_size_token.upper())
    if not match:
        warnings.append("FORMAT_VIOLATION")
        return None, None, warnings
    
    band_cm = int(match.group(1))
    cup = match.group(2)
    
    # Range check
    if band_cm < BAND_CM_MIN or band_cm > BAND_CM_MAX:
        warnings.append("RANGE_VIOLATION")
        return None, None, warnings
    
    # Cup check
    if cup not in ALLOWED_CUPS:
        warnings.append("CUP_UNKNOWN")
        return None, None, warnings
    
    return band_cm, cup, warnings


def _compute_from_bra_size(band_cm: int, cup: str) -> tuple[float, float]:
    """
    Compute UNDERBUST_CIRC_M and BUST_CIRC_M from bra size.
    Contract: meters conversion.
    """
    underbust_circ_m = band_cm / 100.0
    delta_cm = CUP_DELTA_CM[cup]
    bust_circ_m = underbust_circ_m + (delta_cm / 100.0)
    return underbust_circ_m, bust_circ_m


def _validate_inputs(verts: np.ndarray, measurement_key: str) -> tuple[bool, List[str]]:
    """
    Basic input validation.
    Contract Violation: Returns (False, warnings) instead of raising exception.
    """
    warnings: List[str] = []
    
    if verts.ndim != 2 or verts.shape[1] != 3:
        warnings.append("INPUT_CONTRACT_FAIL")
        return False, warnings
    
    if measurement_key not in ["UNDERBUST", "BUST"]:
        warnings.append("MEASUREMENT_KEY_MISMATCH")
        return False, warnings
    
    return True, warnings


def _generate_section_id(plane_axis: str, plane_value: float, slice_index: int, measurement_key: str) -> str:
    """
    Generate reproducible section_id.
    Format: JSON string with plane_axis, plane_value (meters), slice_index, measurement_key.
    """
    section_data = {
        "plane_axis": plane_axis,
        "plane_value": float(plane_value),
        "slice_index": int(slice_index),
        "measurement_key": measurement_key
    }
    return json.dumps(section_data, sort_keys=True)


def _order_points_polar(points_2d: np.ndarray) -> Optional[np.ndarray]:
    """
    Order 2D points by polar angle around centroid.
    Returns ordered points or None if degenerate.
    """
    if points_2d.shape[0] < 3:
        return None
    
    # Check for NaN/inf
    if not np.all(np.isfinite(points_2d)):
        return None
    
    # Compute centroid
    centroid = np.mean(points_2d, axis=0)
    
    # Check for degenerate case (all points same or very close)
    centered = points_2d - centroid
    distances = np.linalg.norm(centered, axis=1)
    if np.max(distances) < 1e-6:
        return None  # All points at same location
    
    # Compute angles (atan2: y=z, x=x for xz plane)
    # For xz plane: x is first column, z is second column
    angles = np.arctan2(centered[:, 1], centered[:, 0])  # atan2(z, x)
    
    # Sort by angle
    sorted_indices = np.argsort(angles)
    ordered_points = points_2d[sorted_indices]
    
    return ordered_points


def _compute_perimeter(vertices_2d: np.ndarray) -> Optional[float]:
    """
    Compute closed curve perimeter from 2D vertices.
    Points are ordered by polar angle around centroid before computing perimeter.
    Returns None if computation fails (degenerate case).
    """
    if vertices_2d.shape[0] < 3:
        return None
    
    # Order points by polar angle
    ordered_points = _order_points_polar(vertices_2d)
    if ordered_points is None:
        return None
    
    # Compute perimeter from ordered points
    n = ordered_points.shape[0]
    perimeter = 0.0
    
    for i in range(n):
        j = (i + 1) % n
        edge_len = np.linalg.norm(ordered_points[j] - ordered_points[i])
        perimeter += edge_len
    
    return float(perimeter)


def _generate_candidates(
    verts: np.ndarray,
    measurement_key: str,
    warnings: List[str]
) -> List[Dict[str, Any]]:
    """
    Generate cross-section candidates.
    Returns list of candidates, each with:
    - plane_axis: str
    - plane_value: float (meters)
    - slice_index: int
    - vertices_2d: np.ndarray (N, 2) - projected vertices on plane
    - perimeter: Optional[float] - computed perimeter or None
    """
    candidates = []
    
    # v0: Simple y-axis slicing (body vertical axis)
    y_coords = verts[:, 1]  # y-axis coordinates
    
    y_min = float(np.min(y_coords))
    y_max = float(np.max(y_coords))
    y_range = y_max - y_min
    
    if y_range < 1e-6:
        warnings.append("BODY_AXIS_TOO_SHORT")
        warnings.append("DEGEN_FAIL")
        return candidates
    
    # Define search region based on measurement key
    if measurement_key == "UNDERBUST":
        # Lower chest region (thoracic cage)
        y_start = y_min + 0.3 * y_range
        y_end = y_min + 0.6 * y_range
    elif measurement_key == "BUST":
        # Upper torso region (breast volume)
        y_start = y_min + 0.4 * y_range
        y_end = y_min + 0.7 * y_range
    else:
        warnings.append("UNKNOWN_KEY")
        return candidates
    
    # Generate slices (v0: fixed step size)
    num_slices = 20
    slice_step = (y_end - y_start) / max(1, num_slices - 1)
    
    for i in range(num_slices):
        y_value = y_start + i * slice_step
        
        # Find vertices near this plane
        tolerance = slice_step * 0.5
        mask = np.abs(y_coords - y_value) < tolerance
        
        if np.sum(mask) < 3:
            continue  # Skip degenerate slices
        
        slice_verts = verts[mask]
        
        # Project to 2D (x-z plane, y is constant)
        vertices_2d = slice_verts[:, [0, 2]]  # x, z coordinates
        
        # Compute perimeter
        perimeter = _compute_perimeter(vertices_2d)
        
        if perimeter is None:
            warnings.append(f"PERIMETER_COMPUTE_FAILED: slice_index={i}")
            continue
        
        # Range sanity check (warnings only, no judgment)
        if perimeter < 0.1:  # < 10cm
            warnings.append(f"PERIMETER_SMALL: {perimeter:.4f}m at slice_index={i}")
        if perimeter > 3.0:  # > 3m
            warnings.append(f"PERIMETER_LARGE: {perimeter:.4f}m at slice_index={i}")
            warnings.append("UNIT_FAIL")
        
        candidates.append({
            "plane_axis": "y",
            "plane_value": float(y_value),
            "slice_index": i,
            "vertices_2d": vertices_2d,
            "perimeter": perimeter
        })
    
    return candidates


def _select_candidate(
    candidates: List[Dict[str, Any]],
    measurement_key: str
) -> Optional[Dict[str, Any]]:
    """
    Select candidate based on selection rule.
    UNDERBUST: median perimeter (structural stability)
    BUST: max perimeter (volume maximum)
    """
    if len(candidates) == 0:
        return None
    
    if measurement_key == "UNDERBUST":
        # Median perimeter (structural stability)
        perimeters = [c["perimeter"] for c in candidates]
        median_perimeter = np.median(perimeters)
        # Find candidate closest to median
        selected = min(candidates, key=lambda c: abs(c["perimeter"] - median_perimeter))
    elif measurement_key == "BUST":
        # Max perimeter (volume maximum)
        selected = max(candidates, key=lambda c: c["perimeter"])
    else:
        return None
    
    return selected


# -----------------------------
# Main API
# -----------------------------
def measure_underbust_v0(
    verts: np.ndarray,
    bra_size_token: Optional[str] = None,
    is_male: Optional[bool] = None,
    units_metadata: Optional[Dict[str, Any]] = None,
) -> BustUnderbustResult:
    """
    Geometric Layer v0: UNDERBUST measurement.
    
    Args:
        verts: Body surface representation (N, 3) in meters
        bra_size_token: Optional bra size string (e.g., "75A")
        is_male: Optional flag for male-specific warnings
        units_metadata: Optional metadata (assumed meters if not provided)
    
    Returns:
        BustUnderbustResult with:
        - measurement_key: "UNDERBUST"
        - circumference_m: float (meters) or NaN
        - section_id: str (JSON, reproducible)
        - method_tag: str
        - warnings: List[str]
    
    Contract compliance:
    - Contract Violation: NaN + warnings (no exceptions)
    - No PASS/FAIL judgment
    - No accuracy evaluation
    """
    verts = _as_np_f32(verts)
    is_valid, warnings = _validate_inputs(verts, "UNDERBUST")
    
    if not is_valid:
        return BustUnderbustResult(
            measurement_key="UNDERBUST",
            circumference_m=float('nan'),
            section_id=json.dumps({"validation_failed": True}),
            method_tag="underbust_v0_validation_failed",
            warnings=warnings
        )
    
    # If bra_size_token provided, use it (Contract: input normalization)
    if bra_size_token is not None:
        band_cm, cup, parse_warnings = _parse_bra_size(bra_size_token)
        warnings.extend(parse_warnings)
        
        if band_cm is None or cup is None:
            # Contract Violation: return NaN + warnings
            return BustUnderbustResult(
                measurement_key="UNDERBUST",
                circumference_m=float('nan'),
                section_id=json.dumps({"bra_parse_failed": True}),
                method_tag="underbust_v0_bra_parse_failed",
                warnings=warnings
            )
        
        # Compute from bra size
        underbust_circ_m, _ = _compute_from_bra_size(band_cm, cup)
        
        return BustUnderbustResult(
            measurement_key="UNDERBUST",
            circumference_m=underbust_circ_m,
            section_id=json.dumps({
                "source": "bra_size",
                "band_cm": band_cm,
                "cup": cup
            }),
            method_tag="underbust_v0_bra_size",
            warnings=warnings
        )
    
    # Geometric measurement: try verts-based computation
    # v0 heuristic: use y-axis slicing with median perimeter selection (structural stability)
    candidates = _generate_candidates(verts, "UNDERBUST", warnings)
    
    if len(candidates) == 0:
        warnings.append("EMPTY_CANDIDATES")
        warnings.append("DEGEN_FAIL")
        warnings.append("UNDERBUST_MEASUREMENT_FAILED")
        return BustUnderbustResult(
            measurement_key="UNDERBUST",
            circumference_m=float('nan'),
            section_id=json.dumps({"empty_candidates": True}),
            method_tag="underbust_v0_empty",
            warnings=warnings
        )
    
    # Select candidate (UNDERBUST: median perimeter for structural stability)
    selected = _select_candidate(candidates, "UNDERBUST")
    
    if selected is None:
        warnings.append("SELECTION_FAILED")
        warnings.append("UNDERBUST_MEASUREMENT_FAILED")
        return BustUnderbustResult(
            measurement_key="UNDERBUST",
            circumference_m=float('nan'),
            section_id=json.dumps({"selection_failed": True}),
            method_tag="underbust_v0_failed",
            warnings=warnings
        )
    
    # Generate section_id
    section_id = _generate_section_id(
        selected["plane_axis"],
        selected["plane_value"],
        selected["slice_index"],
        "UNDERBUST"
    )
    
    # Generate method_tag
    method_tag = f"underbust_v0_y_slice_median"
    
    return BustUnderbustResult(
        measurement_key="UNDERBUST",
        circumference_m=selected["perimeter"],
        section_id=section_id,
        method_tag=method_tag,
        warnings=warnings
    )


def measure_bust_v0(
    verts: np.ndarray,
    bra_size_token: Optional[str] = None,
    is_male: Optional[bool] = None,
    units_metadata: Optional[Dict[str, Any]] = None,
) -> BustUnderbustResult:
    """
    Geometric Layer v0: BUST measurement.
    
    Args:
        verts: Body surface representation (N, 3) in meters
        bra_size_token: Optional bra size string (e.g., "75A")
        is_male: Optional flag for male-specific warnings
        units_metadata: Optional metadata (assumed meters if not provided)
    
    Returns:
        BustUnderbustResult with:
        - measurement_key: "BUST"
        - circumference_m: float (meters) or NaN
        - section_id: str (JSON, reproducible)
        - method_tag: str
        - warnings: List[str]
    
    Contract compliance:
    - Contract Violation: NaN + warnings (no exceptions)
    - No PASS/FAIL judgment
    - No accuracy evaluation
    """
    verts = _as_np_f32(verts)
    is_valid, warnings = _validate_inputs(verts, "BUST")
    
    if not is_valid:
        return BustUnderbustResult(
            measurement_key="BUST",
            circumference_m=float('nan'),
            section_id=json.dumps({"validation_failed": True}),
            method_tag="bust_v0_validation_failed",
            warnings=warnings
        )
    
    # If bra_size_token provided, use it (Contract: input normalization)
    if bra_size_token is not None:
        band_cm, cup, parse_warnings = _parse_bra_size(bra_size_token)
        warnings.extend(parse_warnings)
        
        if band_cm is None or cup is None:
            # Contract Violation: return NaN + warnings
            return BustUnderbustResult(
                measurement_key="BUST",
                circumference_m=float('nan'),
                section_id=json.dumps({"bra_parse_failed": True}),
                method_tag="bust_v0_bra_parse_failed",
                warnings=warnings
            )
        
        # Compute from bra size
        _, bust_circ_m = _compute_from_bra_size(band_cm, cup)
        
        return BustUnderbustResult(
            measurement_key="BUST",
            circumference_m=bust_circ_m,
            section_id=json.dumps({
                "source": "bra_size",
                "band_cm": band_cm,
                "cup": cup
            }),
            method_tag="bust_v0_bra_size",
            warnings=warnings
        )
    
    # Geometric measurement: try verts-based computation
    candidates = _generate_candidates(verts, "BUST", warnings)
    
    if len(candidates) == 0:
        warnings.append("EMPTY_CANDIDATES")
        warnings.append("DEGEN_FAIL")
        return BustUnderbustResult(
            measurement_key="BUST",
            circumference_m=float('nan'),
            section_id=json.dumps({"empty_candidates": True}),
            method_tag="bust_v0_empty",
            warnings=warnings
        )
    
    # Select candidate (BUST: max perimeter)
    selected = _select_candidate(candidates, "BUST")
    
    if selected is None:
        warnings.append("SELECTION_FAILED")
        return BustUnderbustResult(
            measurement_key="BUST",
            circumference_m=float('nan'),
            section_id=json.dumps({"selection_failed": True}),
            method_tag="bust_v0_failed",
            warnings=warnings
        )
    
    # Generate section_id
    section_id = _generate_section_id(
        selected["plane_axis"],
        selected["plane_value"],
        selected["slice_index"],
        "BUST"
    )
    
    # Generate method_tag
    method_tag = f"bust_v0_y_slice_max"
    
    return BustUnderbustResult(
        measurement_key="BUST",
        circumference_m=selected["perimeter"],
        section_id=section_id,
        method_tag=method_tag,
        warnings=warnings
    )
