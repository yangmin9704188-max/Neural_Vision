# circumference_v0.py
# Geometric Layer v0 - Circumference Measurement
# Purpose: Interface contract fulfillment (form-only, no judgment)
# Policy compliance:
# - Body Measurement Meta-Policy v1.3 (Semantic)
# - BUST/WAIST/HIP selection rules (max/min)

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Literal
import numpy as np
import json
import math

# -----------------------------
# Types
# -----------------------------
MeasurementKey = Literal["BUST", "WAIST", "HIP"]


@dataclass
class CircumferenceResult:
    """Interface contract output structure."""
    measurement_key: str
    circumference_m: float  # meters or NaN
    section_id: str  # JSON-serializable, reproducible
    method_tag: str
    warnings: List[str]


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


def _validate_inputs(verts: np.ndarray, measurement_key: str) -> None:
    """Basic input validation."""
    if verts.ndim != 2 or verts.shape[1] != 3:
        raise ValueError(f"verts must be (N,3), got {verts.shape}")
    if measurement_key not in ["BUST", "WAIST", "HIP"]:
        raise ValueError(f"measurement_key must be BUST/WAIST/HIP, got {measurement_key}")


def _generate_section_id(plane_axis: str, plane_value: float, slice_index: int) -> str:
    """
    Generate reproducible section_id.
    Format: JSON string with plane_axis, plane_value (meters), slice_index.
    """
    section_data = {
        "plane_axis": plane_axis,
        "plane_value": float(plane_value),
        "slice_index": int(slice_index)
    }
    return json.dumps(section_data, sort_keys=True)


def _compute_perimeter(vertices_2d: np.ndarray) -> Optional[float]:
    """
    Compute closed curve perimeter from 2D vertices.
    Returns None if computation fails (degenerate case).
    """
    if vertices_2d.shape[0] < 3:
        return None
    
    # Simple perimeter: sum of edge lengths in order
    # For v0, assume vertices are ordered along the curve
    n = vertices_2d.shape[0]
    perimeter = 0.0
    
    for i in range(n):
        j = (i + 1) % n
        edge_len = np.linalg.norm(vertices_2d[j] - vertices_2d[i])
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
    # Assume y-axis is the body's long axis
    y_coords = verts[:, 1]  # y-axis coordinates
    
    y_min = float(np.min(y_coords))
    y_max = float(np.max(y_coords))
    y_range = y_max - y_min
    
    if y_range < 1e-6:
        warnings.append("BODY_AXIS_TOO_SHORT: y-range < 1e-6m")
        return candidates
    
    # Define search region based on measurement key
    # These are approximate regions (v0 heuristic)
    if measurement_key == "BUST":
        # Upper torso region
        y_start = y_min + 0.3 * y_range
        y_end = y_min + 0.6 * y_range
    elif measurement_key == "WAIST":
        # Mid torso region
        y_start = y_min + 0.4 * y_range
        y_end = y_min + 0.7 * y_range
    elif measurement_key == "HIP":
        # Lower torso region
        y_start = y_min + 0.5 * y_range
        y_end = y_min + 0.8 * y_range
    else:
        warnings.append(f"UNKNOWN_KEY: {measurement_key}")
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
        # For v0, simple projection: (x, z) coordinates
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
    BUST/HIP: max perimeter
    WAIST: min perimeter
    """
    if len(candidates) == 0:
        return None
    
    if measurement_key in ["BUST", "HIP"]:
        # Max perimeter
        selected = max(candidates, key=lambda c: c["perimeter"])
    elif measurement_key == "WAIST":
        # Min perimeter
        selected = min(candidates, key=lambda c: c["perimeter"])
    else:
        return None
    
    return selected


# -----------------------------
# Main API
# -----------------------------
def measure_circumference_v0(
    verts: np.ndarray,
    measurement_key: MeasurementKey,
    units_metadata: Optional[Dict[str, Any]] = None,
) -> CircumferenceResult:
    """
    Geometric Layer v0: Circumference measurement.
    
    Args:
        verts: Body surface representation (N, 3) in meters
        measurement_key: "BUST", "WAIST", or "HIP"
        units_metadata: Optional metadata (assumed meters if not provided)
    
    Returns:
        CircumferenceResult with:
        - measurement_key: str
        - circumference_m: float (meters) or NaN
        - section_id: str (JSON, reproducible)
        - method_tag: str
        - warnings: List[str]
    
    Contract compliance:
    - No exceptions for empty candidates (returns NaN)
    - No PASS/FAIL judgment
    - No accuracy evaluation
    """
    verts = _as_np_f32(verts)
    _validate_inputs(verts, measurement_key)
    
    warnings: List[str] = []
    
    # Generate candidates
    candidates = _generate_candidates(verts, measurement_key, warnings)
    
    # Empty candidates fallback
    if len(candidates) == 0:
        warnings.append("EMPTY_CANDIDATES")
        return CircumferenceResult(
            measurement_key=measurement_key,
            circumference_m=float('nan'),
            section_id=json.dumps({"empty": True}),
            method_tag="circumference_v0_empty",
            warnings=warnings
        )
    
    # Select candidate
    selected = _select_candidate(candidates, measurement_key)
    
    if selected is None:
        warnings.append("SELECTION_FAILED")
        return CircumferenceResult(
            measurement_key=measurement_key,
            circumference_m=float('nan'),
            section_id=json.dumps({"selection_failed": True}),
            method_tag="circumference_v0_failed",
            warnings=warnings
        )
    
    # Generate section_id
    section_id = _generate_section_id(
        selected["plane_axis"],
        selected["plane_value"],
        selected["slice_index"]
    )
    
    # Generate method_tag
    method_tag = f"circumference_v0_y_slice_{selected['slice_index']}"
    
    return CircumferenceResult(
        measurement_key=measurement_key,
        circumference_m=selected["perimeter"],
        section_id=section_id,
        method_tag=method_tag,
        warnings=warnings
    )
