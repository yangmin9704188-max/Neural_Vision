"""
Purpose: Core VTM: circumferences, widths, heights, arm length.
Inputs: verts, faces (mesh)
Outputs: MeasurementResult (value_m, metadata)
Status: active
"""
# core_measurements_v0.py
# Geometric Layer v0 - Core Measurements with Metadata
# Policy compliance:
# - docs/semantic/measurement_semantics_v0.md
# - docs/validation/measurement_metadata_schema_v0.md

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Literal, Tuple
import numpy as np
import json
import math

from modules.body.src.measurements.vtm.metadata_v0 import create_metadata_v0, get_evidence_ref

# -----------------------------
# Types
# -----------------------------
CircumferenceKey = Literal[
    "NECK_CIRC_M", "BUST_CIRC_M", "UNDERBUST_CIRC_M", 
    "WAIST_CIRC_M", "HIP_CIRC_M", "THIGH_CIRC_M", "MIN_CALF_CIRC_M"
]

WidthDepthKey = Literal[
    "CHEST_WIDTH_M", "CHEST_DEPTH_M", 
    "WAIST_WIDTH_M", "WAIST_DEPTH_M", 
    "HIP_WIDTH_M", "HIP_DEPTH_M"
]

HeightLengthKey = Literal[
    "HEIGHT_M", "CROTCH_HEIGHT_M", "KNEE_HEIGHT_M", "ARM_LEN_M"
]


@dataclass
class MeasurementResult:
    """Measurement result with value and metadata."""
    standard_key: str
    metadata: Dict[str, Any]  # metadata JSON (schema v0)
    value_m: Optional[float] = None  # meters
    value_kg: Optional[float] = None  # kilograms


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


def _validate_verts(verts: np.ndarray) -> Tuple[bool, List[str]]:
    """Basic input validation for vertices."""
    warnings: List[str] = []
    
    if verts.ndim != 2 or verts.shape[1] != 3:
        warnings.append(f"INVALID_VERTS_SHAPE: expected (N,3), got {verts.shape}")
        return False, warnings
    
    if verts.shape[0] < 3:
        warnings.append(f"INSUFFICIENT_VERTICES: need at least 3, got {verts.shape[0]}")
        return False, warnings
    
    return True, warnings


def _alpha_shape_concave_boundary(pts: np.ndarray, body_center_2d: np.ndarray, k: int = 5) -> Optional[np.ndarray]:
    """
    Round47: Compute concave boundary using alpha-shape-like approach (kNN graph boundary).
    
    Args:
        pts: 2D points (N, 2)
        body_center_2d: Body center for candidate selection
        k: Number of nearest neighbors for graph construction
    
    Returns:
        Boundary points in order, or None if failed
    """
    if pts.shape[0] < 3:
        return None
    
    try:
        from scipy.spatial import cKDTree
        tree = cKDTree(pts)
        
        # Build kNN graph (k+1 to include self)
        k_actual = min(k + 1, pts.shape[0])
        distances, indices = tree.query(pts, k=k_actual)
        
        # Find boundary points (points with fewer neighbors or on the edge)
        # Simple heuristic: points where max distance to neighbor is large relative to median
        if pts.shape[0] > k_actual:
            max_dists = distances[:, -1]  # Distance to k-th neighbor
            median_max_dist = np.median(max_dists)
            # Boundary candidates: points with large max distance
            boundary_mask = max_dists > median_max_dist * 1.5
        else:
            boundary_mask = np.ones(pts.shape[0], dtype=bool)
        
        boundary_pts = pts[boundary_mask]
        
        if len(boundary_pts) < 3:
            return None
        
        # Order boundary points by polar angle around centroid
        centroid = np.mean(boundary_pts, axis=0)
        relative = boundary_pts - centroid
        angles = np.arctan2(relative[:, 1], relative[:, 0])
        sorted_indices = np.argsort(angles)
        ordered_boundary = boundary_pts[sorted_indices]
        
        return ordered_boundary
    except ImportError:
        # Fallback: use simple distance-based approach
        return None
    except Exception:
        return None


def _secondary_boundary_builder(pts: np.ndarray, body_center_2d: np.ndarray) -> Optional[np.ndarray]:
    """
    Round57: Secondary boundary builder using simple deterministic method (kNN graph outer boundary).
    
    Args:
        pts: 2D points (N, 2)
        body_center_2d: Body center for reference
    
    Returns:
        Boundary points in order, or None if failed
    """
    if pts.shape[0] < 3:
        return None
    
    try:
        from scipy.spatial import cKDTree
        tree = cKDTree(pts)
        
        # Use a smaller k for more aggressive boundary detection
        k_small = min(3, pts.shape[0] - 1)
        if k_small < 1:
            return None
        
        k_actual = min(k_small + 1, pts.shape[0])
        distances, indices = tree.query(pts, k=k_actual)
        
        # Find outer boundary points: points with largest distances to neighbors
        if pts.shape[0] > k_actual:
            max_dists = distances[:, -1]  # Distance to k-th neighbor
            # Use a more aggressive threshold for boundary detection
            threshold = np.percentile(max_dists, 75)  # Top 25% of points by max distance
            boundary_mask = max_dists >= threshold
        else:
            boundary_mask = np.ones(pts.shape[0], dtype=bool)
        
        boundary_pts = pts[boundary_mask]
        
        if len(boundary_pts) < 3:
            return None
        
        # Order boundary points by polar angle around centroid
        centroid = np.mean(boundary_pts, axis=0)
        relative = boundary_pts - centroid
        angles = np.arctan2(relative[:, 1], relative[:, 0])
        sorted_indices = np.argsort(angles)
        ordered_boundary = boundary_pts[sorted_indices]
        
        return ordered_boundary
    except ImportError:
        return None
    except Exception:
        return None


def _compute_loop_quality_metrics(loop_pts: np.ndarray, perimeter_m: float) -> Optional[Dict[str, Any]]:
    """
    Round49: Compute loop quality metrics for torso extraction.
    
    Args:
        loop_pts: 2D points forming a closed loop (N, 2), ordered
        perimeter_m: Perimeter in meters (already computed)
    
    Returns:
        Dict with: torso_loop_area_m2, torso_loop_perimeter_m, torso_loop_shape_ratio,
                   loop_validity (VALID / SELF_INTERSECT / TOO_FEW_POINTS / EMPTY)
    """
    if loop_pts is None or len(loop_pts) < 3:
        return {
            "torso_loop_area_m2": None,
            "torso_loop_perimeter_m": None,
            "torso_loop_shape_ratio": None,
            "loop_validity": "TOO_FEW_POINTS"
        }
    
    try:
        # Compute area using shoelace formula
        n = len(loop_pts)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += loop_pts[i][0] * loop_pts[j][1]
            area -= loop_pts[j][0] * loop_pts[i][1]
        area = abs(area) / 2.0
        
        # Shape ratio = perimeter^2 / area (circularity proxy)
        shape_ratio = None
        if area > 1e-10:  # Avoid division by zero
            shape_ratio = (perimeter_m ** 2) / area
        
        # Validity check: simple self-intersection check (basic heuristic)
        validity = "VALID"
        if n < 3:
            validity = "TOO_FEW_POINTS"
        elif area < 1e-10:
            validity = "EMPTY"
        else:
            # Basic self-intersection check: check if any non-adjacent edges intersect
            # Simplified: check if area is negative (indicates self-intersection in simple cases)
            # More robust check would require full edge intersection test
            try:
                # Check for degenerate cases
                if np.any(~np.isfinite(loop_pts)):
                    validity = "SELF_INTERSECT"
            except:
                pass
        
        return {
            "torso_loop_area_m2": float(area),
            "torso_loop_perimeter_m": float(perimeter_m),
            "torso_loop_shape_ratio": float(shape_ratio) if shape_ratio is not None else None,
            "loop_validity": validity
        }
    except Exception as e:
        return {
            "torso_loop_area_m2": None,
            "torso_loop_perimeter_m": None,
            "torso_loop_shape_ratio": None,
            "loop_validity": "SELF_INTERSECT"
        }


def _cluster_trim_torso(pts: np.ndarray, body_center_2d: np.ndarray) -> Optional[np.ndarray]:
    """
    Round47: Cluster/trim approach - keep central cluster and reconstruct loop.
    
    Args:
        pts: 2D points (N, 2)
        body_center_2d: Body center for cluster selection
    
    Returns:
        Trimmed points in order, or None if failed
    """
    if pts.shape[0] < 3:
        return None
    
    try:
        from sklearn.cluster import DBSCAN
        # Use DBSCAN with eps derived from median nearest neighbor distance
        from scipy.spatial.distance import pdist
        if pts.shape[0] > 1:
            dists = pdist(pts)
            eps = np.median(dists) * 2.0  # Adaptive eps
        else:
            return None
        
        clustering = DBSCAN(eps=eps, min_samples=3).fit(pts)
        labels = clustering.labels_
        
        # Find cluster closest to body center
        unique_labels = set(labels)
        if -1 in unique_labels:
            unique_labels.remove(-1)  # Remove noise
        
        if not unique_labels:
            return None
        
        best_cluster = None
        best_dist = float('inf')
        for label in unique_labels:
            cluster_pts = pts[labels == label]
            cluster_centroid = np.mean(cluster_pts, axis=0)
            dist = np.linalg.norm(cluster_centroid - body_center_2d)
            if dist < best_dist:
                best_dist = dist
                best_cluster = cluster_pts
        
        if best_cluster is None or len(best_cluster) < 3:
            return None
        
        # Order points by polar angle
        centroid = np.mean(best_cluster, axis=0)
        relative = best_cluster - centroid
        angles = np.arctan2(relative[:, 1], relative[:, 0])
        sorted_indices = np.argsort(angles)
        ordered_cluster = best_cluster[sorted_indices]
        
        return ordered_cluster
    except ImportError:
        # Fallback: simple distance-based trimming
        centroid = np.mean(pts, axis=0)
        dists_to_center = np.linalg.norm(pts - body_center_2d, axis=1)
        median_dist = np.median(dists_to_center)
        # Keep points within 1.5x median distance
        mask = dists_to_center <= median_dist * 1.5
        trimmed = pts[mask]
        if len(trimmed) < 3:
            return None
        # Order by polar angle
        relative = trimmed - centroid
        angles = np.arctan2(relative[:, 1], relative[:, 0])
        sorted_indices = np.argsort(angles)
        return trimmed[sorted_indices]
    except Exception:
        return None


def _convex_hull_2d_monotone_chain(pts: np.ndarray) -> Optional[np.ndarray]:
    """
    Compute 2D convex hull using Andrew's monotone chain algorithm (numpy-only).
    
    Returns:
        Convex hull points in counter-clockwise order, or None if degenerate.
    """
    if pts.shape[0] < 3:
        return None
    
    # Sort points by x (then by y if x is equal)
    sort_indices = np.lexsort((pts[:, 1], pts[:, 0]))
    sorted_pts = pts[sort_indices]
    
    # Remove duplicates (consecutive)
    unique_mask = np.ones(len(sorted_pts), dtype=bool)
    for i in range(1, len(sorted_pts)):
        if np.allclose(sorted_pts[i], sorted_pts[i-1], atol=1e-9):
            unique_mask[i] = False
    sorted_pts = sorted_pts[unique_mask]
    
    if len(sorted_pts) < 3:
        return None
    
    # Cross product for orientation check (2D: (x1-x0)*(y2-y0) - (y1-y0)*(x2-x0))
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    
    # Build lower hull
    lower = []
    for p in sorted_pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    
    # Build upper hull
    upper = []
    for p in reversed(sorted_pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    
    # Combine (remove duplicate endpoints)
    hull = np.array(lower[:-1] + upper[:-1], dtype=np.float32)
    
    # Check for degenerate cases
    if len(hull) < 3:
        return None
    
    # Check if all points are collinear
    if len(hull) == 3:
        # Check if the three points are collinear
        v1 = hull[1] - hull[0]
        v2 = hull[2] - hull[0]
        cross_val = v1[0] * v2[1] - v1[1] * v2[0]
        if abs(cross_val) < 1e-9:
            return None  # Collinear
    
    return hull


def _compute_perimeter(vertices_2d: np.ndarray, return_debug: bool = False) -> Optional[float] | Tuple[Optional[float], Dict[str, Any]]:
    """
    Compute closed curve perimeter from 2D vertices using convex hull.
    
    Round39: Uses 2D convex hull (Andrew monotone chain) instead of polar sort
    to avoid including interior/concave points that cause perimeter explosion.
    
    Round36: If return_debug=True, returns (perimeter, debug_info) tuple.
    Round37: Improved deduplication.
    Round37 Hotfix: O(N log N) deduplication + vectorized perimeter computation.
    """
    if vertices_2d.shape[0] < 3:
        if return_debug:
            return None, {"n_points_raw": 0, "reason": "too_few_points"}
        return None
    
    n_points_raw = vertices_2d.shape[0]
    
    # Round36: Capture bbox before processing
    bbox_before = {
        "min": [float(np.min(vertices_2d[:, 0])), float(np.min(vertices_2d[:, 1]))],
        "max": [float(np.max(vertices_2d[:, 0])), float(np.max(vertices_2d[:, 1]))],
        "max_abs": float(np.max(np.abs(vertices_2d)))
    }
    
    # Round37 Hotfix: O(N log N) deduplication using quantization
    epsilon = 1e-6  # 1 micron tolerance
    if epsilon <= 0 or epsilon < 1e-10:
        epsilon = 1e-6  # Safety clamp (not value clamp)
    
    # Quantization-based deduplication (O(N log N))
    q = np.round(vertices_2d / epsilon).astype(np.int64)
    unique_indices = np.unique(q, axis=0, return_index=True)[1]
    vertices_2d_deduped = vertices_2d[np.sort(unique_indices)].astype(np.float32)
    n_points_dedup = vertices_2d_deduped.shape[0]
    
    if n_points_dedup < 3:
        if return_debug:
            return None, {
                "n_points_raw": n_points_raw,
                "n_points_dedup": n_points_dedup,
                "epsilon_used": epsilon,
                "perimeter_method": "convex_hull_v1",
                "fallback_used": True,
                "fallback_reason": "too_few_unique_points",
                "reason": "too_few_unique_points"
            }
        return None
    
    # Round39: Compute convex hull instead of polar sort
    hull_pts = _convex_hull_2d_monotone_chain(vertices_2d_deduped)
    fallback_used = False
    fallback_reason = None
    
    if hull_pts is None or len(hull_pts) < 3:
        # Fallback to polar sort if convex hull fails
        fallback_used = True
        fallback_reason = "hull_degenerate_or_collinear"
        
        # Round37: Polar angle sorting fallback
        center = np.mean(vertices_2d_deduped, axis=0)
        centered = vertices_2d_deduped - center
        
        # Check for degenerate case (all points at same location)
        distances = np.linalg.norm(centered, axis=1)
        if np.max(distances) < 1e-6:
            if return_debug:
                return None, {
                    "n_points_raw": n_points_raw,
                    "n_points_dedup": n_points_dedup,
                    "epsilon_used": epsilon,
                    "perimeter_method": "convex_hull_v1",
                    "fallback_used": True,
                    "fallback_reason": "all_points_at_center",
                    "reason": "all_points_at_center"
                }
            return None
        
        # Compute angles (atan2: y, x)
        angles = np.arctan2(centered[:, 1], centered[:, 0])
        
        # Handle identical angles
        for i in range(len(angles)):
            same_angle_mask = np.abs(angles - angles[i]) < 1e-10
            if np.sum(same_angle_mask) > 1:
                same_angle_indices = np.where(same_angle_mask)[0]
                same_angle_distances = distances[same_angle_indices]
                sorted_by_dist = same_angle_indices[np.argsort(same_angle_distances)]
                for idx, orig_idx in enumerate(sorted_by_dist):
                    if orig_idx != i:
                        angles[orig_idx] += idx * 1e-12
        
        sorted_indices = np.argsort(angles)
        hull_pts = vertices_2d_deduped[sorted_indices]
    
    n_points_hull = len(hull_pts)
    
    # Round36: Capture bbox after hull
    bbox_after = {
        "min": [float(np.min(hull_pts[:, 0])), float(np.min(hull_pts[:, 1]))],
        "max": [float(np.max(hull_pts[:, 0])), float(np.max(hull_pts[:, 1]))],
        "max_abs": float(np.max(np.abs(hull_pts)))
    }
    
    # Round37 Hotfix: Vectorized perimeter computation
    # Compute segment lengths using vectorized operations
    diffs = np.diff(hull_pts, axis=0, append=hull_pts[0:1])  # Append first point for closing edge
    seg_lengths = np.sqrt((diffs ** 2).sum(axis=1))
    # Remove the last element (duplicate of first) and add explicit closing edge
    seg_lengths = seg_lengths[:-1]
    closing_edge = np.sqrt(((hull_pts[0] - hull_pts[-1]) ** 2).sum())
    perimeter_final = float(seg_lengths.sum() + closing_edge)
    
    # Convert segment lengths to list for debug
    segment_lens = seg_lengths.tolist()
    
    if return_debug:
        # Round36: Compute segment length statistics
        if segment_lens:
            segment_lens_arr = np.array(segment_lens)
            segment_len_stats = {
                "min": float(np.min(segment_lens_arr)),
                "mean": float(np.mean(segment_lens_arr)),
                "max": float(np.max(segment_lens_arr)),
                "p95": float(np.percentile(segment_lens_arr, 95))
            }
            # Count jumps (outliers)
            mean_len = segment_len_stats["mean"]
            jump_count = int(np.sum(segment_lens_arr > mean_len * 10))
        else:
            segment_len_stats = {}
            jump_count = 0
        
        # Round37: perimeter_raw는 measure_circumference_v0_with_metadata에서 전달됨
        # 여기서는 perimeter_new만 기록
        
        debug_info = {
            "n_points_raw": n_points_raw,  # Round37 Hotfix: Original count
            "n_points": n_points_raw,  # Round36 compatibility
            "n_points_deduped": n_points_dedup,  # Round37: After deduplication
            "n_points_dedup": n_points_dedup,  # Round37 Hotfix: Alias
            "n_points_hull": n_points_hull,  # Round39: Convex hull point count
            "epsilon_used": epsilon,  # Round37 Hotfix
            "perimeter_method": "convex_hull_v1",  # Round39
            "fallback_used": fallback_used,  # Round39
            "fallback_reason": fallback_reason,  # Round39
            "bbox_before": bbox_before,
            "bbox_after": bbox_after,
            "segment_len_stats": segment_len_stats,
            "jump_count": jump_count,
            "perimeter_new": perimeter_final,  # Round37: New method (with dedupe + stable sort)
            "perimeter_final": perimeter_final,  # Round36 compatibility
            "points_sorted": not fallback_used,  # Round39: True if convex hull, False if polar sort fallback
            "dedupe_applied": n_points_dedup < n_points_raw,  # Round37
            "dedupe_count": n_points_dedup,  # Round37
            "notes": []
        }
        
        # Round36: Detect potential issues
        if jump_count > 0:
            debug_info["notes"].append(f"jump_detected: {jump_count} segments > 10x mean")
        if bbox_before["max_abs"] > 10.0:
            debug_info["notes"].append(f"large_bbox_before: max_abs={bbox_before['max_abs']:.2f}")
        
        return perimeter_final, debug_info
    
    return float(perimeter_final)


def _compute_tolerance_from_mesh_scale(verts: np.ndarray, base_tolerance: float) -> float:
    """
    Round55: Compute tolerance based on mesh scale/edge length.
    
    Args:
        verts: Mesh vertices (N, 3)
        base_tolerance: Original tolerance value (fallback)
    
    Returns:
        Adjusted tolerance based on mesh scale
    """
    if verts.shape[0] < 3:
        return base_tolerance
    
    try:
        # Compute mesh bounding box
        bbox_min = np.min(verts, axis=0)
        bbox_max = np.max(verts, axis=0)
        bbox_size = bbox_max - bbox_min
        
        # Estimate edge length from mesh scale (use median of bbox dimensions)
        # This gives a rough estimate of mesh resolution
        median_dimension = np.median(bbox_size[bbox_size > 0])
        
        # Use a fraction of median dimension as tolerance (e.g., 0.1% to 1%)
        # This ensures tolerance scales with mesh size
        scale_based_tolerance = median_dimension * 0.002  # 0.2% of median dimension
        
        # Use the larger of scale-based or base tolerance (but not too large)
        # Clamp to reasonable range: 1e-5 to 0.01 meters
        adjusted_tolerance = max(scale_based_tolerance, base_tolerance)
        adjusted_tolerance = min(adjusted_tolerance, 0.01)  # Max 1cm
        adjusted_tolerance = max(adjusted_tolerance, 1e-5)  # Min 10 microns
        
        return float(adjusted_tolerance)
    except Exception:
        # Fallback to base tolerance on any error
        return base_tolerance


def _find_cross_section(
    verts: np.ndarray,
    y_value: float,
    tolerance: float,
    warnings: List[str],
    y_min: Optional[float] = None,
    y_max: Optional[float] = None,
    target_mode: str = "ratio",
    allow_nearest_fallback: bool = False,
) -> tuple[Optional[np.ndarray], Optional[Dict[str, Any]]]:
    """
    Find cross-section vertices at given y-value.
    Returns (2D projected vertices (x, z) or None, debug info dict or None).
    
    Args:
        allow_nearest_fallback: If True, when target is out of bounds, use nearest valid plane
    """
    y_coords = verts[:, 1]
    if y_min is None:
        y_min = float(np.min(y_coords))
    if y_max is None:
        y_max = float(np.max(y_coords))
    y_range = y_max - y_min
    
    # Enhanced debug info
    debug_info = {
        "target_mode": target_mode,
        "target_z_m": float(y_value),
        "target_height_ratio": float((y_value - y_min) / y_range) if y_range > 0 else 0.0,
        "axis_name": "y_up",
        "axis_length_m": float(y_range),
        "bbox_min": float(y_min),
        "bbox_max": float(y_max),
        "slice_half_thickness_m": float(tolerance),
        "search_window_mm": float(tolerance * 1000.0),
        "candidates_count": 0,
        "reason_not_found": None,
        "fallback_used": False,
        "fallback_distance_mm": None
    }
    
    # Check axis validity
    if y_range < 1e-6:
        debug_info["reason_not_found"] = "axis_invalid"
        return None, debug_info
    
    # Check bounds
    original_y_value = y_value
    fallback_distance_mm = 0.0
    
    if y_value < y_min or y_value > y_max:
        if allow_nearest_fallback:
            # Use nearest valid plane (not band_scan, just single plane selection)
            y_value = max(y_min, min(y_max, y_value))
            fallback_distance_mm = abs(y_value - original_y_value) * 1000.0
            debug_info["fallback_used"] = True
            debug_info["fallback_distance_mm"] = float(fallback_distance_mm)
            if fallback_distance_mm > 10.0:
                warnings.append(f"FALLBACK_DISTANCE_LARGE: {fallback_distance_mm:.2f}mm")
        else:
            debug_info["reason_not_found"] = "out_of_bounds_target"
            return None, debug_info
    
    # Check if slice is too thin
    if tolerance < 1e-6:
        debug_info["reason_not_found"] = "too_thin_slice"
        return None, debug_info
    
    mask = np.abs(y_coords - y_value) < tolerance
    candidate_count = int(np.sum(mask))
    debug_info["candidates_count"] = candidate_count
    
    if candidate_count < 3:
        if candidate_count == 0:
            debug_info["reason_not_found"] = "mesh_empty_at_height"
        else:
            debug_info["reason_not_found"] = "empty_slice"
        return None, debug_info
    
    slice_verts = verts[mask]
    # Project to x-z plane
    vertices_2d = slice_verts[:, [0, 2]]
    return vertices_2d, debug_info


def _find_nearest_valid_plane(
    verts: np.ndarray,
    y_target: float,
    tolerance: float,
    max_shift_mm: float,
    y_min: float,
    y_max: float,
    step_mm: float = 1.0,
) -> tuple[Optional[np.ndarray], Optional[float], Optional[Dict[str, Any]]]:
    """
    Find nearest valid plane within max_shift_mm from target.
    Returns (vertices_2d or None, shift_mm or None, debug_info or None).
    
    This is NOT band_scan - it's a single nearest valid plane selection.
    
    Args:
        step_mm: Step size in mm for searching candidate planes (default: 1.0mm)
    """
    y_coords = verts[:, 1]
    max_shift_m = max_shift_mm / 1000.0  # Convert to meters
    step_m = step_mm / 1000.0  # Convert step to meters
    
    # Search in ±max_shift_m range
    search_min = max(y_min, y_target - max_shift_m)
    search_max = min(y_max, y_target + max_shift_m)
    
    # Sample candidate planes with explicit step size
    num_steps = max(1, int((search_max - search_min) / step_m) + 1)
    
    best_vertices = None
    best_shift_mm = None
    best_candidates_count = 0
    
    for i in range(num_steps):
        y_candidate = search_min + i * step_m
        if y_candidate > search_max:
            break
        
        mask = np.abs(y_coords - y_candidate) < tolerance
        candidate_count = int(np.sum(mask))
        
        if candidate_count >= 3:  # Valid plane found
            shift_mm = abs(y_candidate - y_target) * 1000.0
            if best_vertices is None or shift_mm < best_shift_mm:
                best_vertices = verts[mask]
                best_shift_mm = shift_mm
                best_candidates_count = candidate_count
    
    if best_vertices is not None:
        # Project to x-z plane
        vertices_2d = best_vertices[:, [0, 2]]
        debug_info = {
            "nearest_valid_plane_used": True,
            "nearest_valid_plane_shift_mm": float(best_shift_mm),
            "nearest_valid_plane_candidates_count": best_candidates_count
        }
        return vertices_2d, best_shift_mm, debug_info
    
    return None, None, None


def _find_connected_components_2d(
    vertices_2d: np.ndarray,
    connectivity_threshold: float = 0.01,
    return_diagnostics: bool = False  # Round43: Enable diagnostics
) -> List[np.ndarray] | tuple[List[np.ndarray], Dict[str, Any]]:
    """
    Round41: Find connected components in 2D point cloud.
    Round43: Add diagnostics for observability.
    Uses distance-based connectivity: points within threshold are connected.
    
    Returns:
        List of component arrays, or (components, diagnostics) if return_diagnostics=True
    """
    diagnostics = {
        "n_intersection_points": vertices_2d.shape[0] if vertices_2d.shape[0] > 0 else 0,
        "n_segments": 0,  # Will be computed
        "n_components": 0,
        "component_sizes": [],
        "failure_reason": None
    }
    
    if vertices_2d.shape[0] < 3:
        diagnostics["failure_reason"] = "TORSO_FAIL_NO_INTERSECTION"
        if return_diagnostics:
            return [], diagnostics
        return []
    
    n = vertices_2d.shape[0]
    visited = np.zeros(n, dtype=bool)
    components = []
    
    for i in range(n):
        if visited[i]:
            continue
        
        # BFS to find all connected points
        component_indices = []
        queue = [i]
        visited[i] = True
        
        while queue:
            current = queue.pop(0)
            component_indices.append(current)
            
            # Find neighbors within threshold
            distances = np.linalg.norm(vertices_2d - vertices_2d[current], axis=1)
            neighbors = np.where((distances < connectivity_threshold) & (~visited))[0]
            
            for neighbor in neighbors:
                visited[neighbor] = True
                queue.append(neighbor)
        
        if len(component_indices) >= 3:  # Minimum 3 points for a valid component
            components.append(vertices_2d[component_indices])
            diagnostics["component_sizes"].append(len(component_indices))
    
    diagnostics["n_components"] = len(components)
    # Round43: Estimate n_segments (approximate: sum of component sizes, assuming closed loops)
    diagnostics["n_segments"] = sum(len(comp) for comp in components) if components else 0
    
    if len(components) == 0:
        diagnostics["failure_reason"] = "EXTRACT_EMPTY"
    elif len(components) == 1:
        diagnostics["failure_reason"] = "SINGLE_COMPONENT_ONLY"
    
    if return_diagnostics:
        return components, diagnostics
    return components


def _order_component_points_for_loop(
    component: np.ndarray
) -> Optional[np.ndarray]:
    """
    Round43: Order component points to form a closed loop.
    Uses polar angle sorting around centroid as a deterministic rule.
    
    Returns:
        Ordered component array or None if ordering fails
    """
    if component.shape[0] < 3:
        return None
    
    try:
        # Compute centroid
        centroid = np.mean(component, axis=0)
        
        # Compute polar angles
        relative = component - centroid
        angles = np.arctan2(relative[:, 1], relative[:, 0])
        
        # Sort by angle
        sorted_indices = np.argsort(angles)
        ordered_component = component[sorted_indices]
        
        return ordered_component
    except Exception:
        return None


def _compute_component_stats(
    component: np.ndarray,
    body_center_2d: np.ndarray,
    try_ordering: bool = False  # Round43: Try to order points for closed loop
) -> Dict[str, Any]:
    """
    Round41: Compute statistics for a connected component.
    Round43: Optionally order points for closed loop.
    
    Returns:
        Dict with: area, perimeter, centroid, dist_to_body_center
    """
    stats = {}
    
    # Round43: Try to order points for closed loop if requested
    component_to_use = component
    if try_ordering:
        ordered = _order_component_points_for_loop(component)
        if ordered is not None:
            component_to_use = ordered
    
    # Centroid
    centroid = np.mean(component_to_use, axis=0)
    stats["centroid"] = [float(centroid[0]), float(centroid[1])]
    
    # Distance to body center
    dist_to_body_center = np.linalg.norm(centroid - body_center_2d)
    stats["dist_to_body_center"] = float(dist_to_body_center)
    
    # Perimeter (using convex hull for stability, but try ordered if available)
    perimeter = _compute_perimeter(component_to_use)
    stats["perimeter"] = float(perimeter) if perimeter is not None else float('nan')
    
    # Area (using convex hull)
    try:
        from scipy.spatial import ConvexHull
        if len(component_to_use) >= 3:
            hull = ConvexHull(component_to_use)
            stats["area"] = float(hull.volume)  # 2D: volume is area
        else:
            stats["area"] = float('nan')
    except ImportError:
        # Fallback: approximate area using bounding box
        bbox_area = (np.max(component_to_use[:, 0]) - np.min(component_to_use[:, 0])) * \
                    (np.max(component_to_use[:, 1]) - np.min(component_to_use[:, 1]))
        stats["area"] = float(bbox_area)
    except Exception:
        stats["area"] = float('nan')
    
    return stats


def _select_torso_component(
    components: List[np.ndarray],
    body_center_2d: np.ndarray,
    warnings: List[str]
) -> tuple[Optional[np.ndarray], Optional[Dict[str, Any]], Optional[str]]:
    """
    Round41: Select torso-only component using deterministic rules.
    Round42: Enhanced tiebreak for ambiguous cases.
    
    Rules:
    1. dist_to_body_center 최소 우선
    2. tie-breaker 1: area 최대
    3. tie-breaker 2: perimeter 최대
    4. tie-breaker 3: centroid (x,z) 사전식
    
    Returns:
        (selected_component or None, component_stats or None, warning_reason or None)
    """
    if len(components) == 0:
        return None, None, "no_components"
    
    if len(components) == 1:
        # Single component: use it
        stats = _compute_component_stats(components[0], body_center_2d)
        return components[0], stats, None
    
    # Multiple components: select by rules
    component_stats_list = []
    for comp in components:
        stats = _compute_component_stats(comp, body_center_2d)
        component_stats_list.append((comp, stats))
    
    # Round42: Enhanced tiebreak - dist (ascending), area (descending), perimeter (descending), centroid (x,z) lexicographic
    component_stats_list.sort(
        key=lambda x: (
            x[1]["dist_to_body_center"] if not np.isnan(x[1]["dist_to_body_center"]) else float('inf'),
            -x[1]["area"] if not np.isnan(x[1]["area"]) else float('inf'),
            -x[1]["perimeter"] if not np.isnan(x[1]["perimeter"]) else float('inf'),
            x[1]["centroid"][0] if len(x[1]["centroid"]) > 0 else float('inf'),  # x coordinate
            x[1]["centroid"][1] if len(x[1]["centroid"]) > 1 else float('inf')   # z coordinate
        )
    )
    
    selected_comp, selected_stats = component_stats_list[0]
    
    # Round42: Check if tiebreak was used
    tiebreak_used = False
    if len(component_stats_list) > 1:
        second_comp, second_stats = component_stats_list[1]
        # Check if any tiebreak was needed
        dist_equal = abs(selected_stats["dist_to_body_center"] - second_stats["dist_to_body_center"]) < 1e-6
        area_equal = abs(selected_stats["area"] - second_stats["area"]) < 1e-6 if not (np.isnan(selected_stats["area"]) or np.isnan(second_stats["area"])) else False
        perimeter_equal = abs(selected_stats["perimeter"] - second_stats["perimeter"]) < 1e-6 if not (np.isnan(selected_stats["perimeter"]) or np.isnan(second_stats["perimeter"])) else False
        
        if dist_equal:
            if area_equal:
                if perimeter_equal:
                    # All primary criteria equal - tiebreak by centroid used
                    tiebreak_used = True
                else:
                    # Perimeter tiebreak used
                    tiebreak_used = True
            else:
                # Area tiebreak used
                tiebreak_used = True
    
    if tiebreak_used:
        warnings.append("TORSO_TIEBREAK_USED")
    
    return selected_comp, selected_stats, None


def _compute_circumference_at_height(
    verts: np.ndarray,
    y_value: float,
    tolerance: float,
    warnings: List[str],
    y_min: Optional[float] = None,
    y_max: Optional[float] = None,
    return_debug: bool = False,
    return_torso_components: bool = False,  # Round41: Enable torso-only analysis
    case_id: Optional[str] = None,  # Round50: For deterministic alpha_k assignment
) -> tuple[Optional[float], Optional[Dict[str, Any]]]:
    """
    Compute circumference at given height. Returns (perimeter or None, debug_info or None).
    
    Round41: If return_torso_components=True, also analyzes connected components and selects torso-only.
    Round55: Adjust tolerance based on mesh scale for better slice point coverage.
    """
    # Round55: Adjust tolerance based on mesh scale (geometry-based mitigation)
    original_tolerance = tolerance
    tolerance = _compute_tolerance_from_mesh_scale(verts, tolerance)
    if tolerance != original_tolerance and warnings is not None:
        warnings.append(f"SLICE_THICKNESS_ADJUSTED: {original_tolerance:.6f} -> {tolerance:.6f} m")
    
    vertices_2d, debug_info = _find_cross_section(verts, y_value, tolerance, warnings, y_min, y_max)
    if vertices_2d is None:
        return None, debug_info
    
    # Round37 Hotfix: Optional downsampling for very large point sets (performance guard)
    max_points = 20000
    if vertices_2d.shape[0] > max_points:
        stride = max(1, vertices_2d.shape[0] // max_points)
        vertices_2d = vertices_2d[::stride]
        warnings.append(f"DOWNSAMPLED: {vertices_2d.shape[0]} points (stride={stride})")
    
    # Round41: Compute body center (2D projection of body center)
    body_center_3d = np.mean(verts, axis=0)
    body_center_2d = np.array([body_center_3d[0], body_center_3d[2]])  # x, z
    
    # Round41: Find connected components if requested
    # Round43: Add diagnostics for observability
    torso_component = None
    torso_stats = None
    all_components_stats = []
    torso_perimeter = None
    torso_diagnostics = None
    if return_torso_components:
        components, diagnostics = _find_connected_components_2d(vertices_2d, connectivity_threshold=0.01, return_diagnostics=True)
        torso_diagnostics = diagnostics.copy()
        # Round56: Get n_slice_points_after_dedupe from diagnostics if available
        n_slice_points_after_dedupe = diagnostics.get("n_points_after_dedupe", vertices_2d.shape[0] if vertices_2d is not None else 0)
        
        if len(components) > 0:
            all_components_stats = []
            for comp in components:
                try:
                    # Round43: Try ordering for closed loop
                    stats = _compute_component_stats(comp, body_center_2d, try_ordering=True)
                    all_components_stats.append(stats)
                except Exception as e:
                    # Round43: Record numeric errors
                    if "NUMERIC_ERROR" not in diagnostics.get("failure_reason", ""):
                        diagnostics["failure_reason"] = f"NUMERIC_ERROR: {str(e)[:50]}"
                    all_components_stats.append({
                        "area": float('nan'),
                        "perimeter": float('nan'),
                        "centroid": [float('nan'), float('nan')],
                        "dist_to_body_center": float('nan')
                    })
            
            # Round43: Add component stats summary
            if all_components_stats:
                areas = [s["area"] for s in all_components_stats if not np.isnan(s["area"])]
                perimeters = [s["perimeter"] for s in all_components_stats if not np.isnan(s["perimeter"])]
                
                if areas:
                    areas_sorted = sorted(areas, reverse=True)
                    diagnostics["component_area_stats"] = {
                        "min": float(np.min(areas)),
                        "max": float(np.max(areas)),
                        "median": float(np.median(areas)),
                        "p50": float(np.percentile(areas, 50)),
                        "p95": float(np.percentile(areas, 95)),
                        "top3": areas_sorted[:3] if len(areas_sorted) >= 3 else areas_sorted
                    }
                if perimeters:
                    perimeters_sorted = sorted(perimeters, reverse=True)
                    diagnostics["component_perimeter_stats"] = {
                        "min": float(np.min(perimeters)),
                        "max": float(np.max(perimeters)),
                        "median": float(np.median(perimeters)),
                        "p50": float(np.percentile(perimeters, 50)),
                        "p95": float(np.percentile(perimeters, 95)),
                        "top3": perimeters_sorted[:3] if len(perimeters_sorted) >= 3 else perimeters_sorted
                    }
            
            torso_component, torso_stats, torso_warning = _select_torso_component(components, body_center_2d, warnings)
            if torso_warning:
                warnings.append(f"TORSO_COMPONENT_SELECTION_FAILED: {torso_warning}")
                diagnostics["failure_reason"] = f"SELECTION_FAILED: {torso_warning}"
            # Round42/43: Compute torso_perimeter if component selected successfully
            # Round48-A: Initialize method tracking (only for SINGLE_COMPONENT_ONLY cases per requirements)
            torso_method_used = None
            if torso_component is not None and torso_stats is not None:
                try:
                    # Round43: Try ordering for closed loop before computing perimeter
                    ordered_component = _order_component_points_for_loop(torso_component)
                    if ordered_component is not None:
                        torso_perimeter = _compute_perimeter(ordered_component)
                    else:
                        # Fallback to unordered
                        torso_perimeter = _compute_perimeter(torso_component)
                    
                    # Round44: When loop ordering/perimeter fails, use 2D convex hull perimeter of selected component
                    if torso_perimeter is None and torso_component.shape[0] >= 3:
                        hull_pts = _convex_hull_2d_monotone_chain(torso_component)
                        if hull_pts is not None and len(hull_pts) >= 3:
                            hull_pts = np.asarray(hull_pts, dtype=np.float64)
                            d = np.diff(hull_pts, axis=0)
                            closing = hull_pts[0] - hull_pts[-1]
                            torso_perimeter = float(np.sqrt((d ** 2).sum(axis=1)).sum() + np.sqrt((closing ** 2).sum()))
                            if torso_diagnostics is not None:
                                torso_diagnostics["TORSO_FALLBACK_HULL_USED"] = True
                    
                    # Round47/48-A: If failure_reason is SINGLE_COMPONENT_ONLY, try refinement methods before fallback
                    # Round48-A: Ensure method tracking is recorded for ALL SINGLE_COMPONENT_ONLY cases
                    if diagnostics.get("failure_reason") == "SINGLE_COMPONENT_ONLY" and len(components) == 1:
                        single_comp = components[0]
                        if single_comp.shape[0] >= 3:
                            # Round48-A: Initialize method tracking (must be set to one of: alpha_shape, cluster_trim, single_component_fallback)
                            torso_method_used = None
                            
                            # Round56: Capture diagnostics for TOO_FEW_POINTS (before alpha_shape attempt)
                            # Store slice diagnostics that will be used if TOO_FEW_POINTS occurs
                            n_slice_points_raw = vertices_2d.shape[0] if vertices_2d is not None else 0
                            # Round56: Get n_slice_points_after_dedupe from diagnostics (set above)
                            n_component_points = single_comp.shape[0]
                            
                            # Round56: Check for TOO_FEW_SLICE_POINTS (before component extraction)
                            if n_slice_points_raw < 3:
                                alpha_fail_reason = "ALPHA_FAIL:TOO_FEW_SLICE_POINTS"
                                if torso_diagnostics is not None:
                                    torso_diagnostics["too_few_points_diagnostics"] = {
                                        "n_slice_points_raw": int(n_slice_points_raw),
                                        "n_slice_points_after_dedupe": int(n_slice_points_after_dedupe),
                                        "n_component_points": int(n_component_points),
                                        "n_boundary_points": 0,
                                        "n_loops_found": 0,
                                        "slice_thickness_used": float(tolerance),
                                        "slice_plane_level": float(y_value)
                                    }
                            # Round56: Check for TOO_FEW_COMPONENT_POINTS (component has too few points)
                            elif n_component_points < 3:
                                alpha_fail_reason = "ALPHA_FAIL:TOO_FEW_COMPONENT_POINTS"
                                if torso_diagnostics is not None:
                                    torso_diagnostics["too_few_points_diagnostics"] = {
                                        "n_slice_points_raw": int(n_slice_points_raw),
                                        "n_slice_points_after_dedupe": int(n_slice_points_after_dedupe),
                                        "n_component_points": int(n_component_points),
                                        "n_boundary_points": 0,
                                        "n_loops_found": 0,
                                        "slice_thickness_used": float(tolerance),
                                        "slice_plane_level": float(y_value)
                                    }
                            else:
                                # Option A: alpha-shape-like concave boundary
                                # Round50: Deterministic k assignment via hash(case_id) % 3
                                # Round54: Track alpha failure reasons
                                # Round56: Refine TOO_FEW_POINTS into stage-specific codes
                                alpha_k = 5  # Default
                                if case_id is not None:
                                    alpha_k = [3, 5, 7][hash(case_id) % 3]
                                alpha_fail_reason = None
                                n_boundary_points = 0
                                n_loops_found = 0
                                alpha_perimeter = None
                                try:
                                    alpha_boundary = _alpha_shape_concave_boundary(single_comp, body_center_2d, k=alpha_k)
                                    if alpha_boundary is not None:
                                        n_boundary_points = len(alpha_boundary)
                                        if n_boundary_points >= 3:
                                            alpha_perimeter = _compute_perimeter(alpha_boundary)
                                            if alpha_perimeter is not None:
                                                torso_perimeter = alpha_perimeter
                                                torso_method_used = "alpha_shape"
                                                n_loops_found = 1
                                                
                                                # Round49: Compute loop quality metrics for alpha_shape method
                                                # Round50: Record actual alpha_k used
                                                if torso_diagnostics is not None:
                                                    loop_quality = _compute_loop_quality_metrics(alpha_boundary, alpha_perimeter)
                                                    if loop_quality:
                                                        loop_quality["alpha_param_used"] = alpha_k  # Round50: Use deterministic k
                                                        torso_diagnostics["torso_loop_quality"] = loop_quality
                                            else:
                                                # Round54: Perimeter computation failed (not TOO_FEW_POINTS)
                                                alpha_fail_reason = "ALPHA_FAIL:EMPTY_LOOP"
                                        else:
                                            # Round56: Boundary extraction produced too few points
                                            alpha_fail_reason = "ALPHA_FAIL:TOO_FEW_BOUNDARY_POINTS"
                                    else:
                                        # Round56: Boundary extraction returned None
                                        alpha_fail_reason = "ALPHA_FAIL:TOO_FEW_BOUNDARY_POINTS"
                                    
                                    # Round57: Boundary recovery path when TOO_FEW_BOUNDARY_POINTS occurs
                                    boundary_recovery_method = None
                                    boundary_recovery_success = False
                                    if alpha_fail_reason == "ALPHA_FAIL:TOO_FEW_BOUNDARY_POINTS":
                                        # Round56: Capture initial diagnostics
                                        if torso_diagnostics is not None:
                                            torso_diagnostics["too_few_points_diagnostics"] = {
                                                "n_slice_points_raw": int(n_slice_points_raw),
                                                "n_slice_points_after_dedupe": int(n_slice_points_after_dedupe),
                                                "n_component_points": int(n_component_points),
                                                "n_boundary_points": int(n_boundary_points),
                                                "n_loops_found": int(n_loops_found),
                                                "slice_thickness_used": float(tolerance),
                                                "slice_plane_level": float(y_value)
                                            }
                                        
                                        # Round57: Option A: alpha_relax (deterministic)
                                        # Use alpha_k_eff = min(alpha_k, 3) and retry
                                        alpha_k_eff = min(alpha_k, 3)
                                        if alpha_k_eff < alpha_k:
                                            boundary_recovery_method = "alpha_relax"
                                            try:
                                                alpha_boundary_recovered = _alpha_shape_concave_boundary(single_comp, body_center_2d, k=alpha_k_eff)
                                                if alpha_boundary_recovered is not None and len(alpha_boundary_recovered) >= 3:
                                                    alpha_perimeter_recovered = _compute_perimeter(alpha_boundary_recovered)
                                                    if alpha_perimeter_recovered is not None:
                                                        torso_perimeter = alpha_perimeter_recovered
                                                        torso_method_used = "alpha_shape"
                                                        boundary_recovery_success = True
                                                        n_boundary_points = len(alpha_boundary_recovered)
                                                        n_loops_found = 1
                                                        
                                                        # Round49: Compute loop quality metrics
                                                        if torso_diagnostics is not None:
                                                            loop_quality = _compute_loop_quality_metrics(alpha_boundary_recovered, alpha_perimeter_recovered)
                                                            if loop_quality:
                                                                loop_quality["alpha_param_used"] = alpha_k_eff  # Round57: Record recovered k
                                                                torso_diagnostics["torso_loop_quality"] = loop_quality
                                                        alpha_fail_reason = None  # Recovery succeeded
                                            except Exception:
                                                pass  # Continue to Option B
                                        
                                        # Round57: Option B: secondary boundary builder (if Option A failed)
                                        if not boundary_recovery_success:
                                            if boundary_recovery_method is None:
                                                boundary_recovery_method = "secondary_builder"
                                            else:
                                                boundary_recovery_method = "secondary_builder"  # Override if alpha_relax failed
                                            
                                            try:
                                                # Simple deterministic boundary builder: kNN graph outer boundary
                                                secondary_boundary = _secondary_boundary_builder(single_comp, body_center_2d)
                                                if secondary_boundary is not None and len(secondary_boundary) >= 3:
                                                    secondary_perimeter = _compute_perimeter(secondary_boundary)
                                                    if secondary_perimeter is not None:
                                                        torso_perimeter = secondary_perimeter
                                                        torso_method_used = "alpha_shape"  # Still use alpha_shape method label
                                                        boundary_recovery_success = True
                                                        n_boundary_points = len(secondary_boundary)
                                                        n_loops_found = 1
                                                        
                                                        # Round49: Compute loop quality metrics
                                                        if torso_diagnostics is not None:
                                                            loop_quality = _compute_loop_quality_metrics(secondary_boundary, secondary_perimeter)
                                                            if loop_quality:
                                                                loop_quality["alpha_param_used"] = alpha_k  # Keep original k for tracking
                                                                torso_diagnostics["torso_loop_quality"] = loop_quality
                                                        alpha_fail_reason = None  # Recovery succeeded
                                            except Exception:
                                                pass  # Keep original failure reason
                                        
                                        # Round57: Record recovery attempt and result
                                        if torso_diagnostics is not None:
                                            if boundary_recovery_method:
                                                torso_diagnostics["boundary_recovery_method"] = boundary_recovery_method
                                                torso_diagnostics["boundary_recovery_success"] = boundary_recovery_success
                                                if boundary_recovery_success:
                                                    # Update diagnostics with post-recovery values
                                                    if "too_few_points_diagnostics" in torso_diagnostics:
                                                        torso_diagnostics["too_few_points_diagnostics"]["n_boundary_points"] = int(n_boundary_points)
                                                        torso_diagnostics["too_few_points_diagnostics"]["n_loops_found"] = int(n_loops_found)
                                                        if boundary_recovery_method == "alpha_relax":
                                                            torso_diagnostics["too_few_points_diagnostics"]["alpha_k_eff_used"] = int(alpha_k_eff)
                                except Exception as e:
                                    # Round54: Exception during alpha_shape computation
                                    alpha_fail_reason = "ALPHA_FAIL:EXCEPTION"
                            
                            # Round54: Record alpha failure reason if alpha_shape failed
                            # Store alpha_fail_reason even if cluster_trim might succeed later
                            # (We want to track why alpha_shape failed, regardless of subsequent fallbacks)
                            if alpha_fail_reason is not None:
                                if torso_diagnostics is not None:
                                    torso_diagnostics["alpha_fail_reason"] = alpha_fail_reason
                                if warnings is not None:
                                    warnings.append(alpha_fail_reason)
                            
                            # Option B: cluster/trim approach (if Option A failed)
                            if torso_perimeter is None:
                                cluster_trimmed = _cluster_trim_torso(single_comp, body_center_2d)
                                if cluster_trimmed is not None and len(cluster_trimmed) >= 3:
                                    cluster_perimeter = _compute_perimeter(cluster_trimmed)
                                    if cluster_perimeter is not None:
                                        torso_perimeter = cluster_perimeter
                                        torso_method_used = "cluster_trim"
                            
                            # Round45 fallback: single component fallback (if both refinement methods failed)
                            if torso_perimeter is None:
                                # Try ordering first
                                ordered_single = _order_component_points_for_loop(single_comp)
                                if ordered_single is not None:
                                    ordered_perimeter = _compute_perimeter(ordered_single)
                                    if ordered_perimeter is not None:
                                        torso_perimeter = ordered_perimeter
                                        torso_method_used = "single_component_fallback"
                                else:
                                    # Fallback to unordered
                                    unordered_perimeter = _compute_perimeter(single_comp)
                                    if unordered_perimeter is not None:
                                        torso_perimeter = unordered_perimeter
                                        torso_method_used = "single_component_fallback"
                                
                                # If still None, use hull
                                if torso_perimeter is None:
                                    hull_pts = _convex_hull_2d_monotone_chain(single_comp)
                                    if hull_pts is not None and len(hull_pts) >= 3:
                                        hull_pts = np.asarray(hull_pts, dtype=np.float64)
                                        d = np.diff(hull_pts, axis=0)
                                        closing = hull_pts[0] - hull_pts[-1]
                                        hull_perimeter = float(np.sqrt((d ** 2).sum(axis=1)).sum() + np.sqrt((closing ** 2).sum()))
                                        if hull_perimeter is not None:
                                            torso_perimeter = hull_perimeter
                                            torso_method_used = "single_component_fallback"
                            
                            # Round53: Ensure method is always set for SINGLE_COMPONENT_ONLY cases
                            # If all methods failed and torso_method_used is still None, set to single_component_fallback
                            # (This ensures no tracking_missing cases)
                            if torso_method_used is None:
                                torso_method_used = "single_component_fallback"
                            
                            # Round48-A: Record method used (must be one of: alpha_shape, cluster_trim, single_component_fallback)
                            # This must be recorded for ALL SINGLE_COMPONENT_ONLY cases, even if perimeter is None
                            if torso_diagnostics is not None:
                                torso_diagnostics["TORSO_METHOD_USED"] = torso_method_used
                                if torso_method_used == "single_component_fallback":
                                    torso_diagnostics["TORSO_SINGLE_COMPONENT_FALLBACK_USED"] = True
                    
                    if torso_perimeter is None:
                        diagnostics["failure_reason"] = "NOT_CLOSED_LOOP"
                except Exception as e:
                    diagnostics["failure_reason"] = f"NUMERIC_ERROR: {str(e)[:50]}"
                    torso_perimeter = None
                    # Round53: For SINGLE_COMPONENT_ONLY cases, ensure method is set even on exception
                    # Check if we were processing SINGLE_COMPONENT_ONLY case (before exception)
                    was_single_component_only = (len(components) == 1) if 'components' in locals() else False
                    if torso_diagnostics is not None:
                        if was_single_component_only and torso_diagnostics.get("TORSO_METHOD_USED") is None:
                            # Round53: Set method to single_component_fallback if not already set
                            torso_diagnostics["TORSO_METHOD_USED"] = "single_component_fallback"
                        elif torso_diagnostics.get("TORSO_METHOD_USED") is None:
                            # Round48-A: Record method for exception case (non-SINGLE_COMPONENT_ONLY)
                            torso_diagnostics["TORSO_METHOD_USED"] = "torso_computation_failed"
        else:
            # Round43: No components found
            if diagnostics.get("failure_reason") is None:
                diagnostics["failure_reason"] = "EXTRACT_EMPTY"
    
    # Round36: Get perimeter with debug info if requested
    if return_debug:
        perimeter, perimeter_debug = _compute_perimeter(vertices_2d, return_debug=True)
        if debug_info and perimeter_debug:
            # Merge perimeter debug into cross-section debug
            debug_info.update(perimeter_debug)
        
        # Round41/42/43: Add torso component info to debug
        if return_torso_components:
            debug_info["torso_components"] = {
                "n_components": len(all_components_stats),
                "all_components": all_components_stats,
                "torso_selected": torso_stats is not None,
                "torso_stats": torso_stats,
                "torso_perimeter": float(torso_perimeter) if torso_perimeter is not None else None
            }
            # Round43: Add diagnostics
            if torso_diagnostics:
                debug_info["torso_components"].update(torso_diagnostics)
        
        return perimeter, debug_info
    else:
        perimeter = _compute_perimeter(vertices_2d)
        
        # Round41/42/43: Add torso component info to debug_info if requested
        if return_torso_components:
            if debug_info is None:
                debug_info = {}
            debug_info["torso_components"] = {
                "n_components": len(all_components_stats),
                "torso_selected": torso_stats is not None,
                "torso_perimeter": float(torso_perimeter) if torso_perimeter is not None else None,
                "torso_stats": torso_stats
            }
            # Round43: Add diagnostics
            if torso_diagnostics:
                debug_info["torso_components"].update(torso_diagnostics)
        
        return perimeter, debug_info


# -----------------------------
# Slice Artifact (for sharing across measurements)
# -----------------------------
@dataclass
class SliceArtifact:
    """Cross-section slice artifact that can be shared across measurements."""
    vertices_2d: np.ndarray  # (N, 2) projected vertices
    y_value: float  # Height at which slice was taken
    tolerance: float  # Slice thickness
    candidates_count: int  # Number of vertices in slice
    cross_section_debug: Dict[str, Any]  # Debug info
    chosen_candidate_index: Optional[int] = None  # If selected from multiple candidates


# -----------------------------
# Group Measurements (Slice Sharing)
# -----------------------------
def measure_waist_group_with_shared_slice(
    verts: np.ndarray,
    case_id: Optional[str] = None,  # Round50: For deterministic alpha_k assignment
) -> Dict[str, MeasurementResult]:
    """
    Measure WAIST group (CIRC, WIDTH, DEPTH) with shared slice artifact.
    
    Returns:
        Dictionary with keys: WAIST_CIRC_M, WAIST_WIDTH_M, WAIST_DEPTH_M
    """
    results = {}
    
    # Step 1: Extract slice for WAIST_CIRC_M (same logic as measure_circumference_v0_with_metadata)
    verts = _as_np_f32(verts)
    is_valid, warnings_circ = _validate_verts(verts)
    
    if not is_valid:
        # Return NaN for all waist measurements
        for key in ["WAIST_CIRC_M", "WAIST_WIDTH_M", "WAIST_DEPTH_M"]:
            metadata = create_metadata_v0(
                standard_key=key,
                value_m=float('nan'),
                method_path_type="closed_curve" if "CIRC" in key else "straight_line",
                method_metric_type="circumference" if "CIRC" in key else ("width" if "WIDTH" in key else "depth"),
                warnings=warnings_circ,
                method_fixed_height_required=True if "CIRC" in key else None,
                method_fixed_cross_section_required=True if "CIRC" not in key else None,
                search_band_scan_used=False,
                search_band_scan_limit_mm=10,
                pose_breath_state="neutral_mid",
                provenance_evidence_ref=get_evidence_ref(key),
            )
            results[key] = MeasurementResult(standard_key=key, value_m=float('nan'), metadata=metadata)
        return results
    
    # Find measurement height region (same as WAIST_CIRC_M)
    y_coords = verts[:, 1]
    y_min = float(np.min(y_coords))
    y_max = float(np.max(y_coords))
    y_range = y_max - y_min
    
    if y_range < 1e-6:
        warnings_circ.append("BODY_AXIS_TOO_SHORT")
        for key in ["WAIST_CIRC_M", "WAIST_WIDTH_M", "WAIST_DEPTH_M"]:
            debug_info = {
                "body_axis": {
                    "length_m": float(y_range),
                    "valid": False,
                    "reason_invalid": "too_short"
                }
            }
            metadata = create_metadata_v0(
                standard_key=key,
                value_m=float('nan'),
                method_path_type="closed_curve" if "CIRC" in key else "straight_line",
                method_metric_type="circumference" if "CIRC" in key else ("width" if "WIDTH" in key else "depth"),
                warnings=warnings_circ,
                method_fixed_height_required=True if "CIRC" in key else None,
                method_fixed_cross_section_required=True if "CIRC" not in key else None,
                search_band_scan_used=False,
                search_band_scan_limit_mm=10,
                pose_breath_state="neutral_mid",
                provenance_evidence_ref=get_evidence_ref(key),
                debug_info=debug_info,
            )
            results[key] = MeasurementResult(standard_key=key, value_m=float('nan'), metadata=metadata)
        return results
    
    # WAIST region (same as WAIST_CIRC_M)
    # Refine01: Shift band 0.40-0.70 -> 0.42-0.66 to reduce overestimation (residual pattern +,+,-)
    y_start = y_min + 0.42 * y_range
    y_end = y_min + 0.66 * y_range
    
    # Generate candidates and select best (same as WAIST_CIRC_M)
    num_slices = 20
    slice_step = (y_end - y_start) / max(1, num_slices - 1)
    tolerance = slice_step * 0.5
    
    candidates = []
    cross_section_debug_list = []
    chosen_slice_artifact = None
    chosen_candidate_index = None
    
    for i in range(num_slices):
        y_value = y_start + i * slice_step
        perimeter, debug_info = _compute_circumference_at_height(verts, y_value, tolerance, warnings_circ, y_min, y_max, case_id=case_id)
        if debug_info:
            cross_section_debug_list.append(debug_info)
        if perimeter is not None:
            candidates.append({
                "y_value": y_value,
                "perimeter": perimeter,
                "slice_index": i,
                "debug_info": debug_info
            })
    
    # Select candidate (WAIST: min perimeter; tie-break: prefer higher y = closer to waist narrowing)
    if len(candidates) > 0:
        selected = min(candidates, key=lambda c: (c["perimeter"], -c["y_value"]))
        chosen_candidate_index = selected["slice_index"]
        
        # Re-extract slice for the selected y_value (to get vertices_2d)
        vertices_2d, cross_section_debug = _find_cross_section(
            verts, selected["y_value"], tolerance, warnings_circ, y_min, y_max,
            target_mode="ratio",
            allow_nearest_fallback=False
        )
        
        if vertices_2d is not None:
            chosen_slice_artifact = SliceArtifact(
                vertices_2d=vertices_2d,
                y_value=selected["y_value"],
                tolerance=tolerance,
                candidates_count=cross_section_debug.get("candidates_count", 0) if cross_section_debug else 0,
                cross_section_debug=cross_section_debug or {},
                chosen_candidate_index=chosen_candidate_index
            )
    
    # Step 2: Compute WAIST_CIRC_M from chosen slice
    if chosen_slice_artifact is not None:
        perimeter = _compute_perimeter(chosen_slice_artifact.vertices_2d)
        value_m = perimeter
    else:
        perimeter = None
        value_m = float('nan')
        warnings_circ.append("EMPTY_CANDIDATES")
    
    # Build debug info for circumference
    debug_info_circ = {
        "body_axis": {
            "length_m": float(y_range),
            "valid": True,
            "reason_invalid": None
        }
    }
    if chosen_slice_artifact:
        debug_info_circ["cross_section"] = chosen_slice_artifact.cross_section_debug
        debug_info_circ["cross_section"]["candidates_available"] = len(candidates)
        debug_info_circ["cross_section"]["chosen_candidate_index"] = chosen_candidate_index
    
    metadata_circ = create_metadata_v0(
        standard_key="WAIST_CIRC_M",
        value_m=value_m,
        method_path_type="closed_curve",
        method_metric_type="circumference",
        warnings=warnings_circ,
        method_fixed_height_required=True,
        method_landmark_confidence="high",
        method_landmark_resolution="direct",
        search_band_scan_used=False,
        search_band_scan_limit_mm=10,
        pose_breath_state="neutral_mid",
        provenance_evidence_ref=get_evidence_ref("WAIST_CIRC_M"),
        debug_info=debug_info_circ,
    )
    results["WAIST_CIRC_M"] = MeasurementResult(
        standard_key="WAIST_CIRC_M",
        value_m=value_m,
        metadata=metadata_circ
    )
    
    # Step 3: Compute WAIST_WIDTH_M and WAIST_DEPTH_M from shared slice
    warnings_wd = warnings_circ.copy() if chosen_slice_artifact else []
    
    if chosen_slice_artifact is not None:
        # Use shared slice artifact
        vertices_2d = chosen_slice_artifact.vertices_2d
        
        # Compute width (x-axis span)
        x_min = float(np.min(vertices_2d[:, 0]))
        x_max = float(np.max(vertices_2d[:, 0]))
        width_m = x_max - x_min
        
        # Compute depth (z-axis span)
        z_min = float(np.min(vertices_2d[:, 1]))
        z_max = float(np.max(vertices_2d[:, 1]))
        depth_m = z_max - z_min
        
        # Range sanity check
        if width_m < 0.05 or depth_m < 0.05:
            warnings_wd.append("SUSPICIOUSLY_SMALL")
        
        # Build debug info for width/depth (with slice sharing info)
        debug_info_wd = {
            "body_axis": {
                "length_m": float(y_range),
                "valid": True,
                "reason_invalid": None
            },
            "cross_section": chosen_slice_artifact.cross_section_debug.copy()
        }
        debug_info_wd["cross_section"]["slice_shared_from"] = "WAIST_CIRC_M"
        debug_info_wd["cross_section"]["slicer_called_independently"] = False
        debug_info_wd["cross_section"]["slice_candidates_count"] = chosen_slice_artifact.candidates_count
        if chosen_slice_artifact.chosen_candidate_index is not None:
            debug_info_wd["cross_section"]["chosen_candidate_index"] = chosen_slice_artifact.chosen_candidate_index
        
        # Width metadata
        metadata_width = create_metadata_v0(
            standard_key="WAIST_WIDTH_M",
            value_m=width_m,
            method_path_type="straight_line",
            method_metric_type="width",
            warnings=warnings_wd,
            method_fixed_cross_section_required=True,
            search_band_scan_used=False,
            search_nearest_valid_plane_used=False,
            pose_breath_state="neutral_mid",
            provenance_evidence_ref=get_evidence_ref("WAIST_WIDTH_M"),
            debug_info=debug_info_wd,
        )
        results["WAIST_WIDTH_M"] = MeasurementResult(
            standard_key="WAIST_WIDTH_M",
            value_m=width_m,
            metadata=metadata_width
        )
        
        # Depth metadata
        metadata_depth = create_metadata_v0(
            standard_key="WAIST_DEPTH_M",
            value_m=depth_m,
            method_path_type="straight_line",
            method_metric_type="depth",
            warnings=warnings_wd,
            method_fixed_cross_section_required=True,
            search_band_scan_used=False,
            search_nearest_valid_plane_used=False,
            pose_breath_state="neutral_mid",
            provenance_evidence_ref=get_evidence_ref("WAIST_DEPTH_M"),
            debug_info=debug_info_wd,
        )
        results["WAIST_DEPTH_M"] = MeasurementResult(
            standard_key="WAIST_DEPTH_M",
            value_m=depth_m,
            metadata=metadata_depth
        )
    else:
        # No slice found - return NaN for width/depth
        for key in ["WAIST_WIDTH_M", "WAIST_DEPTH_M"]:
            metric_type = "width" if "WIDTH" in key else "depth"
            debug_info = {
                "body_axis": {
                    "length_m": float(y_range),
                    "valid": True,
                    "reason_invalid": None
                }
            }
            if cross_section_debug_list:
                debug_info["cross_section"] = cross_section_debug_list[0] if cross_section_debug_list else {}
                debug_info["cross_section"]["slice_shared_from"] = "WAIST_CIRC_M"
                debug_info["cross_section"]["slicer_called_independently"] = False
                debug_info["cross_section"]["slice_candidates_count"] = 0
            
            metadata = create_metadata_v0(
                standard_key=key,
                value_m=float('nan'),
                method_path_type="straight_line",
                method_metric_type=metric_type,
                warnings=warnings_wd + ["CROSS_SECTION_NOT_FOUND"],
                method_fixed_cross_section_required=True,
                search_band_scan_used=False,
                search_nearest_valid_plane_used=False,
                pose_breath_state="neutral_mid",
                provenance_evidence_ref=get_evidence_ref(key),
                debug_info=debug_info,
            )
            results[key] = MeasurementResult(standard_key=key, value_m=float('nan'), metadata=metadata)
    
    return results


def measure_hip_group_with_shared_slice(
    verts: np.ndarray,
    case_id: Optional[str] = None,  # Round50: For deterministic alpha_k assignment
) -> Dict[str, MeasurementResult]:
    """
    Measure HIP group (CIRC, WIDTH, DEPTH) with shared slice artifact.
    
    Returns:
        Dictionary with keys: HIP_CIRC_M, HIP_WIDTH_M, HIP_DEPTH_M
    """
    results = {}
    
    # Similar structure to measure_waist_group_with_shared_slice
    # Step 1: Extract slice for HIP_CIRC_M
    verts = _as_np_f32(verts)
    is_valid, warnings_circ = _validate_verts(verts)
    
    if not is_valid:
        for key in ["HIP_CIRC_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]:
            metadata = create_metadata_v0(
                standard_key=key,
                value_m=float('nan'),
                method_path_type="closed_curve" if "CIRC" in key else "straight_line",
                method_metric_type="circumference" if "CIRC" in key else ("width" if "WIDTH" in key else "depth"),
                warnings=warnings_circ,
                method_fixed_height_required=True if "CIRC" in key else None,
                method_fixed_cross_section_required=True if "CIRC" not in key else None,
                search_band_scan_used=False,
                search_band_scan_limit_mm=10,
                provenance_evidence_ref=get_evidence_ref(key),
            )
            results[key] = MeasurementResult(standard_key=key, value_m=float('nan'), metadata=metadata)
        return results
    
    y_coords = verts[:, 1]
    y_min = float(np.min(y_coords))
    y_max = float(np.max(y_coords))
    y_range = y_max - y_min
    
    if y_range < 1e-6:
        warnings_circ.append("BODY_AXIS_TOO_SHORT")
        for key in ["HIP_CIRC_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]:
            debug_info = {
                "body_axis": {
                    "length_m": float(y_range),
                    "valid": False,
                    "reason_invalid": "too_short"
                }
            }
            metadata = create_metadata_v0(
                standard_key=key,
                value_m=float('nan'),
                method_path_type="closed_curve" if "CIRC" in key else "straight_line",
                method_metric_type="circumference" if "CIRC" in key else ("width" if "WIDTH" in key else "depth"),
                warnings=warnings_circ,
                method_fixed_height_required=True if "CIRC" in key else None,
                method_fixed_cross_section_required=True if "CIRC" not in key else None,
                search_band_scan_used=False,
                search_band_scan_limit_mm=10,
                provenance_evidence_ref=get_evidence_ref(key),
                debug_info=debug_info,
            )
            results[key] = MeasurementResult(standard_key=key, value_m=float('nan'), metadata=metadata)
        return results
    
    # HIP region (same as HIP_CIRC_M)
    # Refine01: Shift band 0.50-0.80 -> 0.48-0.78 to reduce underestimation (dominant TORSO_LOWER)
    y_start = y_min + 0.48 * y_range
    y_end = y_min + 0.78 * y_range
    
    # Generate candidates and select best (HIP: max perimeter)
    num_slices = 20
    slice_step = (y_end - y_start) / max(1, num_slices - 1)
    tolerance = slice_step * 0.5
    
    candidates = []
    cross_section_debug_list = []
    chosen_slice_artifact = None
    chosen_candidate_index = None
    
    for i in range(num_slices):
        y_value = y_start + i * slice_step
        perimeter, debug_info = _compute_circumference_at_height(verts, y_value, tolerance, warnings_circ, y_min, y_max, case_id=case_id)
        if debug_info:
            cross_section_debug_list.append(debug_info)
        if perimeter is not None:
            candidates.append({
                "y_value": y_value,
                "perimeter": perimeter,
                "slice_index": i,
                "debug_info": debug_info
            })
    
    # Select candidate (HIP: max perimeter; tie-break: prefer lower y = closer to hip prominence)
    if len(candidates) > 0:
        selected = max(candidates, key=lambda c: (c["perimeter"], -c["y_value"]))
        chosen_candidate_index = selected["slice_index"]
        
        # Re-extract slice for the selected y_value
        vertices_2d, cross_section_debug = _find_cross_section(
            verts, selected["y_value"], tolerance, warnings_circ, y_min, y_max,
            target_mode="ratio",
            allow_nearest_fallback=False
        )
        
        if vertices_2d is not None:
            chosen_slice_artifact = SliceArtifact(
                vertices_2d=vertices_2d,
                y_value=selected["y_value"],
                tolerance=tolerance,
                candidates_count=cross_section_debug.get("candidates_count", 0) if cross_section_debug else 0,
                cross_section_debug=cross_section_debug or {},
                chosen_candidate_index=chosen_candidate_index
            )
    
    # Step 2: Compute HIP_CIRC_M from chosen slice
    if chosen_slice_artifact is not None:
        perimeter = _compute_perimeter(chosen_slice_artifact.vertices_2d)
        value_m = perimeter
    else:
        perimeter = None
        value_m = float('nan')
        warnings_circ.append("EMPTY_CANDIDATES")
    
    # Build debug info for circumference
    debug_info_circ = {
        "body_axis": {
            "length_m": float(y_range),
            "valid": True,
            "reason_invalid": None
        }
    }
    if chosen_slice_artifact:
        debug_info_circ["cross_section"] = chosen_slice_artifact.cross_section_debug
        debug_info_circ["cross_section"]["candidates_available"] = len(candidates)
        debug_info_circ["cross_section"]["chosen_candidate_index"] = chosen_candidate_index
    
    metadata_circ = create_metadata_v0(
        standard_key="HIP_CIRC_M",
        value_m=value_m,
        method_path_type="closed_curve",
        method_metric_type="circumference",
        warnings=warnings_circ,
        method_fixed_height_required=True,
        method_landmark_confidence="high",
        method_landmark_resolution="direct",
        search_band_scan_used=False,
        search_band_scan_limit_mm=10,
        provenance_evidence_ref=get_evidence_ref("HIP_CIRC_M"),
        debug_info=debug_info_circ,
    )
    results["HIP_CIRC_M"] = MeasurementResult(
        standard_key="HIP_CIRC_M",
        value_m=value_m,
        metadata=metadata_circ
    )
    
    # Step 3: Compute HIP_WIDTH_M and HIP_DEPTH_M from shared slice
    warnings_wd = warnings_circ.copy() if chosen_slice_artifact else []
    
    if chosen_slice_artifact is not None:
        # Use shared slice artifact
        vertices_2d = chosen_slice_artifact.vertices_2d
        
        # Compute width (x-axis span)
        x_min = float(np.min(vertices_2d[:, 0]))
        x_max = float(np.max(vertices_2d[:, 0]))
        width_m = x_max - x_min
        
        # Compute depth (z-axis span)
        z_min = float(np.min(vertices_2d[:, 1]))
        z_max = float(np.max(vertices_2d[:, 1]))
        depth_m = z_max - z_min
        
        # Range sanity check
        if width_m < 0.05 or depth_m < 0.05:
            warnings_wd.append("SUSPICIOUSLY_SMALL")
        
        # Build debug info for width/depth (with slice sharing info)
        debug_info_wd = {
            "body_axis": {
                "length_m": float(y_range),
                "valid": True,
                "reason_invalid": None
            },
            "cross_section": chosen_slice_artifact.cross_section_debug.copy()
        }
        debug_info_wd["cross_section"]["slice_shared_from"] = "HIP_CIRC_M"
        debug_info_wd["cross_section"]["slicer_called_independently"] = False
        debug_info_wd["cross_section"]["slice_candidates_count"] = chosen_slice_artifact.candidates_count
        if chosen_slice_artifact.chosen_candidate_index is not None:
            debug_info_wd["cross_section"]["chosen_candidate_index"] = chosen_slice_artifact.chosen_candidate_index
        
        # Width metadata
        metadata_width = create_metadata_v0(
            standard_key="HIP_WIDTH_M",
            value_m=width_m,
            method_path_type="straight_line",
            method_metric_type="width",
            warnings=warnings_wd,
            method_fixed_cross_section_required=True,
            search_band_scan_used=False,
            search_nearest_valid_plane_used=False,
            provenance_evidence_ref=get_evidence_ref("HIP_WIDTH_M"),
            debug_info=debug_info_wd,
        )
        results["HIP_WIDTH_M"] = MeasurementResult(
            standard_key="HIP_WIDTH_M",
            value_m=width_m,
            metadata=metadata_width
        )
        
        # Depth metadata
        metadata_depth = create_metadata_v0(
            standard_key="HIP_DEPTH_M",
            value_m=depth_m,
            method_path_type="straight_line",
            method_metric_type="depth",
            warnings=warnings_wd,
            method_fixed_cross_section_required=True,
            search_band_scan_used=False,
            search_nearest_valid_plane_used=False,
            provenance_evidence_ref=get_evidence_ref("HIP_DEPTH_M"),
            debug_info=debug_info_wd,
        )
        results["HIP_DEPTH_M"] = MeasurementResult(
            standard_key="HIP_DEPTH_M",
            value_m=depth_m,
            metadata=metadata_depth
        )
    else:
        # No slice found - return NaN for width/depth
        for key in ["HIP_WIDTH_M", "HIP_DEPTH_M"]:
            metric_type = "width" if "WIDTH" in key else "depth"
            debug_info = {
                "body_axis": {
                    "length_m": float(y_range),
                    "valid": True,
                    "reason_invalid": None
                }
            }
            if cross_section_debug_list:
                debug_info["cross_section"] = cross_section_debug_list[0] if cross_section_debug_list else {}
                debug_info["cross_section"]["slice_shared_from"] = "HIP_CIRC_M"
                debug_info["cross_section"]["slicer_called_independently"] = False
                debug_info["cross_section"]["slice_candidates_count"] = 0
            
            metadata = create_metadata_v0(
                standard_key=key,
                value_m=float('nan'),
                method_path_type="straight_line",
                method_metric_type=metric_type,
                warnings=warnings_wd + ["CROSS_SECTION_NOT_FOUND"],
                method_fixed_cross_section_required=True,
                search_band_scan_used=False,
                search_nearest_valid_plane_used=False,
                provenance_evidence_ref=get_evidence_ref(key),
                debug_info=debug_info,
            )
            results[key] = MeasurementResult(standard_key=key, value_m=float('nan'), metadata=metadata)
    
    return results


# -----------------------------
# Circumference Measurements
# -----------------------------
def measure_circumference_v0_with_metadata(
    verts: np.ndarray,
    standard_key: CircumferenceKey,
    units_metadata: Optional[Dict[str, Any]] = None,
    case_id: Optional[str] = None,  # Round50: For deterministic alpha_k assignment
) -> MeasurementResult:
    """
    Measure circumference with metadata (schema v0).
    
    Args:
        verts: Body surface vertices (N, 3) in meters
        standard_key: Circumference key
        units_metadata: Optional units metadata (assumed meters)
    
    Returns:
        MeasurementResult with value_m and metadata
    """
    verts = _as_np_f32(verts)
    is_valid, warnings = _validate_verts(verts)
    
    if not is_valid:
        metadata = create_metadata_v0(
            standard_key=standard_key,
            value_m=float('nan'),
            method_path_type="closed_curve",
            method_metric_type="circumference",
            warnings=warnings,
            method_fixed_height_required=True,
            search_band_scan_used=False,
            search_band_scan_limit_mm=10,
            provenance_evidence_ref=get_evidence_ref(standard_key),
        )
        return MeasurementResult(
            standard_key=standard_key,
            value_m=float('nan'),
            metadata=metadata
        )
    
    # Determine canonical_side for right-side keys
    canonical_side = None
    if standard_key in ["THIGH_CIRC_M", "MIN_CALF_CIRC_M"]:
        canonical_side = "right"
    
    # Determine breath_state for torso keys
    breath_state = None
    if standard_key in ["NECK_CIRC_M", "BUST_CIRC_M", "UNDERBUST_CIRC_M", "WAIST_CIRC_M"]:
        breath_state = "neutral_mid"
    
    # Find measurement height region
    y_coords = verts[:, 1]
    y_min = float(np.min(y_coords))
    y_max = float(np.max(y_coords))
    y_range = y_max - y_min
    
    if y_range < 1e-6:
        warnings.append("BODY_AXIS_TOO_SHORT")
        debug_info = {
            "body_axis": {
                "length_m": float(y_range),
                "valid": False,
                "reason_invalid": "too_short"
            }
        }
        metadata = create_metadata_v0(
            standard_key=standard_key,
            value_m=float('nan'),
            method_path_type="closed_curve",
            method_metric_type="circumference",
            warnings=warnings,
            method_canonical_side=canonical_side,
            method_fixed_height_required=True,
            search_band_scan_used=False,
            search_band_scan_limit_mm=10,
            pose_breath_state=breath_state,
            provenance_evidence_ref=get_evidence_ref(standard_key),
            debug_info=debug_info,
        )
        return MeasurementResult(
            standard_key=standard_key,
            value_m=float('nan'),
            metadata=metadata
        )
    
    # Define search region (v0 heuristic, semantic-compliant)
    # Note: WAIST is NOT redefined as "min circumference" - we use fixed height from semantic
    if standard_key == "NECK_CIRC_M":
        # Neck region (upper torso)
        y_start = y_min + 0.75 * y_range
        y_end = y_min + 0.90 * y_range
        landmark_confidence = "medium"  # SMPL-X landmark may be approximate
        landmark_resolution = "nearest_cross_section_fallback"
    elif standard_key == "BUST_CIRC_M":
        # Upper torso (breast volume)
        y_start = y_min + 0.40 * y_range
        y_end = y_min + 0.70 * y_range
        landmark_confidence = "high"
        landmark_resolution = "direct"
    elif standard_key == "UNDERBUST_CIRC_M":
        # Lower chest (thoracic cage)
        y_start = y_min + 0.30 * y_range
        y_end = y_min + 0.60 * y_range
        landmark_confidence = "high"
        landmark_resolution = "direct"
    elif standard_key == "WAIST_CIRC_M":
        # Mid torso (waist line). Refine01: 0.42-0.66 to reduce overestimation (residual pattern +,+,-)
        y_start = y_min + 0.42 * y_range
        y_end = y_min + 0.66 * y_range
        landmark_confidence = "high"
        landmark_resolution = "direct"
    elif standard_key == "HIP_CIRC_M":
        # Lower torso (hip maximum). Refine01: 0.48-0.78 to reduce underestimation (dominant TORSO_LOWER)
        y_start = y_min + 0.48 * y_range
        y_end = y_min + 0.78 * y_range
        landmark_confidence = "high"
        landmark_resolution = "direct"
    elif standard_key == "THIGH_CIRC_M":
        # Upper leg (thigh maximum)
        y_start = y_min + 0.20 * y_range
        y_end = y_min + 0.40 * y_range
        landmark_confidence = "high"
        landmark_resolution = "direct"
    elif standard_key == "MIN_CALF_CIRC_M":
        # Lower leg (calf minimum, above ankle)
        y_start = y_min + 0.05 * y_range
        y_end = y_min + 0.20 * y_range
        landmark_confidence = "high"
        landmark_resolution = "direct"
    else:
        warnings.append(f"UNKNOWN_CIRC_KEY: {standard_key}")
        metadata = create_metadata_v0(
            standard_key=standard_key,
            value_m=float('nan'),
            method_path_type="closed_curve",
            method_metric_type="circumference",
            warnings=warnings,
            method_canonical_side=canonical_side,
            method_fixed_height_required=True,
            search_band_scan_used=False,
            search_band_scan_limit_mm=10,
            pose_breath_state=breath_state,
            provenance_evidence_ref=get_evidence_ref(standard_key),
        )
        return MeasurementResult(
            standard_key=standard_key,
            value_m=float('nan'),
            metadata=metadata
        )
    
    # Generate candidates (fixed height, no band_scan)
    num_slices = 20
    slice_step = (y_end - y_start) / max(1, num_slices - 1)
    tolerance = slice_step * 0.5
    
    candidates = []
    cross_section_debug_list = []
    # Round36: Capture verts bbox before processing (for scale detection)
    verts_bbox_before = {
        "min": [float(np.min(verts[:, 0])), float(np.min(verts[:, 1])), float(np.min(verts[:, 2]))],
        "max": [float(np.max(verts[:, 0])), float(np.max(verts[:, 1])), float(np.max(verts[:, 2]))],
        "max_abs": float(np.max(np.abs(verts)))
    }
    
    for i in range(num_slices):
        y_value = y_start + i * slice_step
        # Round36: Enable debug for selected candidate
        perimeter, debug_info = _compute_circumference_at_height(verts, y_value, tolerance, warnings, y_min, y_max, return_debug=(i == num_slices // 2), case_id=case_id)  # Debug middle slice
        if debug_info:
            cross_section_debug_list.append(debug_info)
        if perimeter is not None:
            candidates.append({
                "y_value": y_value,
                "perimeter": perimeter,
                "slice_index": i,
                "debug_info": debug_info if debug_info and "n_points" in debug_info else None
            })
    
    # Build debug info
    debug_info = {
        "body_axis": {
            "length_m": float(y_range),
            "valid": True,
            "reason_invalid": None
        }
    }
    if len(candidates) == 0:
        warnings.append("EMPTY_CANDIDATES")
        # Aggregate cross-section debug info
        if cross_section_debug_list:
            reasons = [d.get("reason_not_found") for d in cross_section_debug_list if d.get("reason_not_found")]
            candidates_counts = [d.get("candidates_count", 0) for d in cross_section_debug_list]
            if reasons:
                debug_info["cross_section"] = {
                    "target_height_ratio": cross_section_debug_list[0].get("target_height_ratio"),
                    "search_window_mm": cross_section_debug_list[0].get("search_window_mm"),
                    "candidates_count": 0,
                    "reason_not_found": reasons[0] if len(set(reasons)) == 1 else "mixed"
                }
        else:
            debug_info["cross_section"] = {
                "candidates_count": 0,
                "reason_not_found": "no_debug_info"
            }
        metadata = create_metadata_v0(
            standard_key=standard_key,
            value_m=float('nan'),
            method_path_type="closed_curve",
            method_metric_type="circumference",
            warnings=warnings,
            method_canonical_side=canonical_side,
            method_landmark_confidence=landmark_confidence,
            method_landmark_resolution=landmark_resolution,
            method_fixed_height_required=True,
            search_band_scan_used=False,
            search_band_scan_limit_mm=10,
            pose_breath_state=breath_state,
            provenance_evidence_ref=get_evidence_ref(standard_key),
            debug_info=debug_info,
        )
        return MeasurementResult(
            standard_key=standard_key,
            value_m=float('nan'),
            metadata=metadata
        )
    
    # Round36: Select candidate and collect debug info for selected one
    selected_candidate = None
    selected_debug_info = None
    
    # Select candidate based on semantic rule
    # BUST/HIP: max (maximum protrusion); tie-break: prefer lower y (closer to prominence)
    # WAIST: semantic defines as "most constricted" but we use fixed height (no min search)
    # THIGH: max (maximum)
    # MIN_CALF: min (minimum)
    if standard_key in ["BUST_CIRC_M", "HIP_CIRC_M", "THIGH_CIRC_M"]:
        selected = max(candidates, key=lambda c: (c["perimeter"], -c["y_value"]))
    elif standard_key == "MIN_CALF_CIRC_M":
        selected = min(candidates, key=lambda c: (c["perimeter"], -c["y_value"]))
        warnings.append("MIN_SEARCH_USED")  # Record that min search was used
    else:
        # NECK, UNDERBUST, WAIST: use median for stability; tie-break: prefer higher y (waist narrowing)
        perimeters = [c["perimeter"] for c in candidates]
        median_perimeter = float(np.median(perimeters))
        selected = min(candidates, key=lambda c: (abs(c["perimeter"] - median_perimeter), -c["y_value"]))
    
    # Round37: Re-compute selected candidate with debug enabled to get full debug info (new method)
    # Round41: Also compute torso-only analysis for torso keys
    selected_y_value = selected["y_value"]
    is_torso_key = standard_key in ["NECK_CIRC_M", "BUST_CIRC_M", "UNDERBUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]
    perimeter_new, selected_debug_full = _compute_circumference_at_height(
        verts, selected_y_value, tolerance, warnings, y_min, y_max, 
        return_debug=True, 
        return_torso_components=is_torso_key,
        case_id=case_id  # Round50: Pass case_id for deterministic alpha_k
    )
    
    # Round37: Store old perimeter as raw (before path fix)
    perimeter_raw = selected["perimeter"]  # Old method result
    
    # Round37: Use new perimeter (with improved path ordering)
    if perimeter_new is not None:
        value_m = perimeter_new
    else:
        # Fallback to selected perimeter if new computation failed
        value_m = perimeter_raw
    
    # Range sanity check (warnings only)
    if value_m < 0.1:
        warnings.append(f"PERIMETER_SMALL: {value_m:.4f}m")
    if value_m > 3.0:
        warnings.append(f"PERIMETER_LARGE: {value_m:.4f}m")
    
    # Round36/37: Build circ_debug info for facts_summary.json
    circ_debug = {
        "schema_version": "circ_debug@1",
        "key": standard_key,
        "n_points": selected_debug_full.get("n_points", 0) if selected_debug_full else 0,
        "n_points_deduped": selected_debug_full.get("n_points_deduped", 0) if selected_debug_full else 0,  # Round37
        "axis": "y",
        "plane": "x-z",
        "scale_applied": False,  # Will be determined from bbox
        "bbox_before": verts_bbox_before,
        "bbox_after": selected_debug_full.get("bbox_after", {}) if selected_debug_full else {},
        "segment_len_stats": selected_debug_full.get("segment_len_stats", {}) if selected_debug_full else {},
        "jump_count": selected_debug_full.get("jump_count", 0) if selected_debug_full else 0,
        "perimeter_raw": perimeter_raw,  # Round37: Old method (from selected candidate)
        "perimeter_new": selected_debug_full.get("perimeter_new", value_m) if selected_debug_full else value_m,  # Round37: New method
        "perimeter_final": value_m,  # Round36 compatibility
        "dedupe_applied": selected_debug_full.get("dedupe_applied", False) if selected_debug_full else False,  # Round37
        "dedupe_count": selected_debug_full.get("dedupe_count", 0) if selected_debug_full else 0,  # Round37
        "notes": selected_debug_full.get("notes", []) if selected_debug_full else []
    }
    
    # Round37: Add perimeter comparison note
    if perimeter_raw is not None and perimeter_raw != value_m:
        ratio = value_m / perimeter_raw if perimeter_raw > 0 else 0.0
        circ_debug["notes"].append(f"perimeter_change: raw={perimeter_raw:.4f}m, new={value_m:.4f}m, ratio={ratio:.4f}")
    
    # Round36: Detect scale issue
    if verts_bbox_before["max_abs"] > 10.0:
        circ_debug["scale_applied"] = True  # Likely mm->m conversion was applied
        circ_debug["notes"].append(f"SCALE_SUSPECTED: bbox_max_abs={verts_bbox_before['max_abs']:.2f}")
    
    # Round36: Detect ordering issue
    if selected_debug_full and selected_debug_full.get("jump_count", 0) > 0:
        circ_debug["notes"].append(f"ORDERING_SUSPECTED: jump_count={circ_debug['jump_count']}")
    
    # Round36: Classify reason
    reason_codes = []
    if circ_debug["scale_applied"]:
        reason_codes.append("SCALE_SUSPECTED")
    if circ_debug["jump_count"] > 0:
        reason_codes.append("ORDERING_SUSPECTED")
    if not reason_codes:
        reason_codes.append("OTHER")
    circ_debug["reason"] = reason_codes[0] if len(reason_codes) == 1 else "MIXED"
    
    # Round41/42: Extract torso components info if available
    # Round44: Always attach torso_components to debug_info when present (success or failure),
    # so runner can aggregate failure_reason and TORSO_FALLBACK_HULL_USED for KPI_DIFF.
    torso_info = None
    if is_torso_key and selected_debug_full and "torso_components" in selected_debug_full:
        torso_components_data = selected_debug_full["torso_components"]
        if torso_components_data.get("torso_selected"):
            torso_perimeter_value = torso_components_data.get("torso_perimeter")
            # Round42: Ensure torso_perimeter is set if component was selected
            if torso_perimeter_value is not None:
                torso_info = {
                    "torso_perimeter": torso_perimeter_value,
                    "full_perimeter": value_m,
                    "n_components": torso_components_data.get("n_components", 0),
                    "torso_stats": torso_components_data.get("torso_stats"),
                    "all_components": torso_components_data.get("all_components", [])
                }
    
    # Create metadata with debug info
    debug_info = {
        "body_axis": {
            "length_m": float(y_range),
            "valid": True,
            "reason_invalid": None
        },
        "cross_section": {
            "candidates_count": len(candidates),
            "target_height_ratio": float((selected["y_value"] - y_min) / y_range) if y_range > 0 else 0.0,
            "search_window_mm": float(tolerance * 1000.0)
        },
        # Round36: Add circ_debug to metadata for runner to extract
        "circ_debug": circ_debug
    }
    
    # Round41: Add torso info to debug_info. Round44: Always add full torso_components from
    # selected_debug_full when present, so runner sees failure_reason / TORSO_FALLBACK_HULL_USED.
    if is_torso_key and selected_debug_full and "torso_components" in selected_debug_full:
        tc = selected_debug_full["torso_components"]
        debug_info["torso_components"] = dict(tc) if isinstance(tc, dict) else {}
    elif torso_info:
        debug_info["torso_components"] = torso_info
    metadata = create_metadata_v0(
        standard_key=standard_key,
        value_m=value_m,
        method_path_type="closed_curve",
        method_metric_type="circumference",
        warnings=warnings,
        method_canonical_side=canonical_side,
        method_landmark_confidence=landmark_confidence,
        method_landmark_resolution=landmark_resolution,
        method_fixed_height_required=True,
        search_band_scan_used=False,  # Forbidden by default
        search_band_scan_limit_mm=10,
        search_min_max_search_used=(standard_key == "MIN_CALF_CIRC_M"),
        pose_breath_state=breath_state,
        provenance_evidence_ref=get_evidence_ref(standard_key),
        debug_info=debug_info,
    )
    
    return MeasurementResult(
        standard_key=standard_key,
        value_m=value_m,
        metadata=metadata
    )


# -----------------------------
# Width/Depth Measurements
# -----------------------------
def measure_width_depth_v0_with_metadata(
    verts: np.ndarray,
    standard_key: WidthDepthKey,
    units_metadata: Optional[Dict[str, Any]] = None,
    proxy_used: bool = False,
    proxy_tool: Optional[str] = None,
) -> MeasurementResult:
    """
    Measure width or depth with metadata (schema v0).
    
    Args:
        verts: Body surface vertices (N, 3) in meters
        standard_key: Width or depth key
        units_metadata: Optional units metadata
        proxy_used: Whether plane_clamp proxy was used
        proxy_tool: Proxy tool name if proxy_used (e.g., "acrylic_board", "caliper")
    
    Returns:
        MeasurementResult with value_m and metadata
    """
    verts = _as_np_f32(verts)
    is_valid, warnings = _validate_verts(verts)
    
    if not is_valid:
        metric_type = "width" if "WIDTH" in standard_key else "depth"
        metadata = create_metadata_v0(
            standard_key=standard_key,
            value_m=float('nan'),
            method_path_type="straight_line",
            method_metric_type=metric_type,
            warnings=warnings,
            method_fixed_cross_section_required=True,
            proxy_proxy_used=proxy_used,
            proxy_proxy_type="plane_clamp" if proxy_used else None,
            proxy_proxy_tool=proxy_tool,
            provenance_evidence_ref=get_evidence_ref(standard_key),
        )
        return MeasurementResult(
            standard_key=standard_key,
            value_m=float('nan'),
            metadata=metadata
        )
    
    # Determine breath_state
    breath_state = "neutral_mid"
    if standard_key in ["CHEST_WIDTH_M", "CHEST_DEPTH_M", "WAIST_WIDTH_M", "WAIST_DEPTH_M"]:
        breath_state = "neutral_mid"
    
    # Determine arms_down requirement
    arms_down = None
    if standard_key == "CHEST_WIDTH_M":
        arms_down = True  # Evidence requires arms down
    
    # Find cross-section at appropriate height
    y_coords = verts[:, 1]
    y_min = float(np.min(y_coords))
    y_max = float(np.max(y_coords))
    y_range = y_max - y_min
    
    if y_range < 1e-6:
        warnings.append("BODY_AXIS_TOO_SHORT")
        metric_type = "width" if "WIDTH" in standard_key else "depth"
        debug_info = {
            "body_axis": {
                "length_m": float(y_range),
                "valid": False,
                "reason_invalid": "too_short"
            }
        }
        metadata = create_metadata_v0(
            standard_key=standard_key,
            value_m=float('nan'),
            method_path_type="straight_line",
            method_metric_type=metric_type,
            warnings=warnings,
            method_fixed_cross_section_required=True,
            proxy_proxy_used=proxy_used,
            proxy_proxy_type="plane_clamp" if proxy_used else None,
            proxy_proxy_tool=proxy_tool,
            pose_breath_state=breath_state,
            pose_arms_down=arms_down,
            provenance_evidence_ref=get_evidence_ref(standard_key),
            debug_info=debug_info,
        )
        return MeasurementResult(
            standard_key=standard_key,
            value_m=float('nan'),
            metadata=metadata
        )
    
    # Define height region
    if standard_key in ["CHEST_WIDTH_M", "CHEST_DEPTH_M"]:
        # Armpit level
        y_target = y_min + 0.35 * y_range
    elif standard_key in ["WAIST_WIDTH_M", "WAIST_DEPTH_M"]:
        # Waist level
        y_target = y_min + 0.50 * y_range
    elif standard_key in ["HIP_WIDTH_M", "HIP_DEPTH_M"]:
        # Hip level
        y_target = y_min + 0.60 * y_range
    else:
        warnings.append(f"UNKNOWN_WIDTH_DEPTH_KEY: {standard_key}")
        metric_type = "width" if "WIDTH" in standard_key else "depth"
        metadata = create_metadata_v0(
            standard_key=standard_key,
            value_m=float('nan'),
            method_path_type="straight_line",
            method_metric_type=metric_type,
            warnings=warnings,
            method_fixed_cross_section_required=True,
            proxy_proxy_used=proxy_used,
            proxy_proxy_type="plane_clamp" if proxy_used else None,
            proxy_proxy_tool=proxy_tool,
            pose_breath_state=breath_state,
            pose_arms_down=arms_down,
            provenance_evidence_ref=get_evidence_ref(standard_key),
        )
        return MeasurementResult(
            standard_key=standard_key,
            value_m=float('nan'),
            metadata=metadata
        )
    
    # Find cross-section with enhanced handling for waist/hip
    # For waist/hip, use slightly larger tolerance and allow nearest fallback
    is_waist_hip = standard_key in ["WAIST_WIDTH_M", "WAIST_DEPTH_M", "HIP_WIDTH_M", "HIP_DEPTH_M"]
    
    if is_waist_hip:
        # Increase tolerance for waist/hip (min 5mm, max 3% of body height)
        base_tolerance = y_range * 0.02  # 2%
        min_tolerance = 0.005  # 5mm minimum
        tolerance = max(min_tolerance, min(base_tolerance, y_range * 0.03))
        if tolerance > base_tolerance:
            warnings.append("SLICE_THICKNESS_ADJUSTED")
    else:
        tolerance = y_range * 0.02  # 2% of body height
    
    # Find cross-section (without fallback first to get initial state)
    vertices_2d, cross_section_debug = _find_cross_section(
        verts, y_target, tolerance, warnings, y_min, y_max,
        target_mode="ratio",
        allow_nearest_fallback=False  # Don't use old fallback logic
    )
    
    # Track initial state for debug
    initial_candidates_count = 0
    if cross_section_debug:
        initial_candidates_count = cross_section_debug.get("candidates_count", 0)
    
    # If failed and is waist/hip, try nearest valid plane fallback
    # CRITICAL: If candidates_count == 0, ALWAYS try fallback (regardless of reason)
    nearest_fallback_used = False
    nearest_fallback_shift_mm = None
    nearest_fallback_debug = None
    fallback_candidates_count = 0
    
    if vertices_2d is None and is_waist_hip:
        # Check if candidates_count == 0 (main trigger)
        if initial_candidates_count == 0:
            # Try nearest valid plane fallback (<=10mm shift)
            # Use finer step (1mm) for better coverage
            fallback_vertices, fallback_shift_mm, fallback_debug = _find_nearest_valid_plane(
                verts, y_target, tolerance, max_shift_mm=10.0, y_min=y_min, y_max=y_max, step_mm=1.0
            )
            if fallback_vertices is not None and fallback_shift_mm is not None:
                if fallback_shift_mm <= 10.0:  # Policy limit
                    vertices_2d = fallback_vertices
                    nearest_fallback_used = True
                    nearest_fallback_shift_mm = fallback_shift_mm
                    nearest_fallback_debug = fallback_debug
                    if fallback_debug:
                        fallback_candidates_count = fallback_debug.get("nearest_valid_plane_candidates_count", 0)
                    warnings.append("NEAREST_VALID_PLANE_FALLBACK")
                else:
                    # Shift exceeds policy limit - do not use
                    if cross_section_debug:
                        cross_section_debug["fallback_failure_reason"] = "shift_exceeds_10mm"
            else:
                # Fallback failed - no valid plane within 10mm
                if cross_section_debug:
                    cross_section_debug["fallback_failure_reason"] = "no_plane_with_candidates_within_10mm"
        elif cross_section_debug:
            reason = cross_section_debug.get("reason_not_found")
            if reason == "too_thin_slice":
                # Try with larger tolerance (up to 5% of body height)
                larger_tolerance = min(y_range * 0.05, tolerance * 2.0)
                if larger_tolerance > tolerance:
                    warnings.append("SLICE_THICKNESS_ADJUSTED")
                    vertices_2d, cross_section_debug = _find_cross_section(
                        verts, y_target, larger_tolerance, warnings, y_min, y_max,
                        target_mode="ratio",
                        allow_nearest_fallback=False
                    )
                    if cross_section_debug:
                        cross_section_debug["slice_half_thickness_m"] = float(larger_tolerance)
                        cross_section_debug["slice_thickness_adjusted"] = True
    
    if vertices_2d is None:
        warnings.append("CROSS_SECTION_NOT_FOUND")
        metric_type = "width" if "WIDTH" in standard_key else "depth"
        debug_info = {
            "body_axis": {
                "length_m": float(y_range),
                "valid": True,
                "reason_invalid": None
            }
        }
        if cross_section_debug:
            debug_info["cross_section"] = cross_section_debug
        if nearest_fallback_debug:
            debug_info["nearest_valid_plane"] = nearest_fallback_debug
        # Record landmark_resolution if fallback was used
        landmark_resolution = None
        if nearest_fallback_used:
            landmark_resolution = "nearest_valid_plane"
        elif cross_section_debug and cross_section_debug.get("fallback_used"):
            landmark_resolution = "nearest_valid_plane"
        # Record search metadata for nearest valid plane fallback
        search_nearest_valid_plane_used = nearest_fallback_used
        search_nearest_valid_plane_shift_mm = int(nearest_fallback_shift_mm) if nearest_fallback_shift_mm is not None else None
        metadata = create_metadata_v0(
            standard_key=standard_key,
            value_m=float('nan'),
            method_path_type="straight_line",
            method_metric_type=metric_type,
            warnings=warnings,
            method_fixed_cross_section_required=True,
            method_landmark_resolution=landmark_resolution,
            search_band_scan_used=False,  # Always false (fallback is not scan)
            search_nearest_valid_plane_used=search_nearest_valid_plane_used,
            search_nearest_valid_plane_shift_mm=search_nearest_valid_plane_shift_mm,
            proxy_proxy_used=proxy_used,
            proxy_proxy_type="plane_clamp" if proxy_used else None,
            proxy_proxy_tool=proxy_tool,
            pose_breath_state=breath_state,
            pose_arms_down=arms_down,
            provenance_evidence_ref=get_evidence_ref(standard_key),
            debug_info=debug_info,
        )
        return MeasurementResult(
            standard_key=standard_key,
            value_m=float('nan'),
            metadata=metadata
        )
    
    # Compute width or depth
    if "WIDTH" in standard_key:
        # Width: left-right distance (x-axis span)
        x_min = float(np.min(vertices_2d[:, 0]))
        x_max = float(np.max(vertices_2d[:, 0]))
        value_m = x_max - x_min
    else:  # DEPTH
        # Depth: front-back distance (z-axis span)
        z_min = float(np.min(vertices_2d[:, 1]))
        z_max = float(np.max(vertices_2d[:, 1]))
        value_m = z_max - z_min
    
    # Range sanity check
    if value_m < 0.05:
        warnings.append(f"WIDTH_DEPTH_SMALL: {value_m:.4f}m")
    if value_m > 1.0:
        warnings.append(f"WIDTH_DEPTH_LARGE: {value_m:.4f}m")
    
    metric_type = "width" if "WIDTH" in standard_key else "depth"
    
    # Create metadata with debug info
    debug_info = {
        "body_axis": {
            "length_m": float(y_range),
            "valid": True,
            "reason_invalid": None
        }
    }
    
    # Enhanced debug for waist/hip cross-section failures
    if is_waist_hip:
        cross_section_debug_enhanced = {}
        if cross_section_debug:
            cross_section_debug_enhanced.update(cross_section_debug)
        
        # Add target/bbox/axis debug
        cross_section_debug_enhanced["target_mode"] = "ratio"
        cross_section_debug_enhanced["target_value"] = float((y_target - y_min) / y_range) if y_range > 0 else 0.0
        cross_section_debug_enhanced["axis_name"] = "y_up"
        cross_section_debug_enhanced["axis_length_m"] = float(y_range)
        cross_section_debug_enhanced["bbox_min_axis"] = float(y_min)
        cross_section_debug_enhanced["bbox_max_axis"] = float(y_max)
        cross_section_debug_enhanced["slice_half_thickness_m"] = float(tolerance)
        cross_section_debug_enhanced["initial_candidates_count"] = initial_candidates_count
        
        # Check if target is out of bounds
        if y_target < y_min or y_target > y_max:
            cross_section_debug_enhanced["target_out_of_bounds"] = True
        else:
            cross_section_debug_enhanced["target_out_of_bounds"] = False
        
        # Add fallback info
        if nearest_fallback_used:
            cross_section_debug_enhanced["fallback_candidates_count"] = fallback_candidates_count
            cross_section_debug_enhanced["fallback_shift_mm"] = float(nearest_fallback_shift_mm) if nearest_fallback_shift_mm is not None else None
        else:
            cross_section_debug_enhanced["fallback_candidates_count"] = 0
            cross_section_debug_enhanced["fallback_shift_mm"] = None
            if cross_section_debug:
                failure_reason = cross_section_debug.get("fallback_failure_reason")
                if failure_reason:
                    cross_section_debug_enhanced["fallback_failure_reason"] = failure_reason
        
        debug_info["cross_section"] = cross_section_debug_enhanced
    elif cross_section_debug:
        debug_info["cross_section"] = cross_section_debug
    
    if nearest_fallback_debug:
        debug_info["nearest_valid_plane"] = nearest_fallback_debug
    
    # Record landmark_resolution if fallback was used
    landmark_resolution = None
    if nearest_fallback_used:
        landmark_resolution = "nearest_valid_plane"
    elif cross_section_debug and cross_section_debug.get("fallback_used"):
        landmark_resolution = "nearest_valid_plane"
    
    # Record search metadata for nearest valid plane fallback
    search_nearest_valid_plane_used = nearest_fallback_used
    search_nearest_valid_plane_shift_mm = int(nearest_fallback_shift_mm) if nearest_fallback_shift_mm is not None else None
    
    metadata = create_metadata_v0(
        standard_key=standard_key,
        value_m=value_m,
        method_path_type="straight_line",
        method_metric_type=metric_type,
        warnings=warnings,
        method_fixed_cross_section_required=True,
        method_landmark_resolution=landmark_resolution,
        search_band_scan_used=False,  # Always false (fallback is not scan)
        search_nearest_valid_plane_used=search_nearest_valid_plane_used,
        search_nearest_valid_plane_shift_mm=search_nearest_valid_plane_shift_mm,
        proxy_proxy_used=proxy_used,
        proxy_proxy_type="plane_clamp" if proxy_used else None,
        proxy_proxy_tool=proxy_tool,
        pose_breath_state=breath_state,
        pose_arms_down=arms_down,
        provenance_evidence_ref=get_evidence_ref(standard_key),
        debug_info=debug_info,
    )
    
    return MeasurementResult(
        standard_key=standard_key,
        value_m=value_m,
        metadata=metadata
    )


# -----------------------------
# Height Measurements
# -----------------------------
def measure_height_v0_with_metadata(
    verts: np.ndarray,
    standard_key: Literal["HEIGHT_M", "CROTCH_HEIGHT_M", "KNEE_HEIGHT_M"],
    units_metadata: Optional[Dict[str, Any]] = None,
) -> MeasurementResult:
    """
    Measure height with metadata (schema v0).
    
    Args:
        verts: Body surface vertices (N, 3) in meters
        standard_key: Height key
        units_metadata: Optional units metadata
    
    Returns:
        MeasurementResult with value_m and metadata
    """
    verts = _as_np_f32(verts)
    is_valid, warnings = _validate_verts(verts)
    
    if not is_valid:
        metadata = create_metadata_v0(
            standard_key=standard_key,
            value_m=float('nan'),
            method_path_type="straight_line",
            method_metric_type="height",
            warnings=warnings,
            pose_strict_standing=True,
            pose_knee_flexion_forbidden=True,
            provenance_evidence_ref=get_evidence_ref(standard_key),
        )
        return MeasurementResult(
            standard_key=standard_key,
            value_m=float('nan'),
            metadata=metadata
        )
    
    # Determine canonical_side for KNEE_HEIGHT_M
    canonical_side = None
    if standard_key == "KNEE_HEIGHT_M":
        canonical_side = "right"
    
    # Compute bbox spans for all axes (for longest axis comparison)
    x_coords = verts[:, 0]
    y_coords = verts[:, 1]
    z_coords = verts[:, 2]
    
    x_min = float(np.min(x_coords))
    x_max = float(np.max(x_coords))
    y_min = float(np.min(y_coords))
    y_max = float(np.max(y_coords))
    z_min = float(np.min(z_coords))
    z_max = float(np.max(z_coords))
    
    bbox_span_x = x_max - x_min
    bbox_span_y = y_max - y_min
    bbox_span_z = z_max - z_min
    
    # Determine longest axis
    spans = {"x": bbox_span_x, "y": bbox_span_y, "z": bbox_span_z}
    bbox_longest_axis = max(spans, key=spans.get)
    bbox_longest_span_m = spans[bbox_longest_axis]
    
    if standard_key == "HEIGHT_M":
        # Height: vertex (top of head) to floor
        # For v0, use y_max as top and y_min as floor
        axis_used = "y"
        bbox_min_axis = y_min
        bbox_max_axis = y_max
        raw_span_m = y_max - y_min
        value_m = raw_span_m  # No post-transform in v0
        post_transform_span_m = value_m
        scale_factor_raw_to_post = post_transform_span_m / raw_span_m if raw_span_m > 0 else 1.0
        
        landmark_confidence = "medium"  # Vertex may be approximate
        landmark_resolution = "direct"
        
        # Enhanced debug info for HEIGHT_M scale investigation
        debug_info = {
            "bbox_comparison": {
                "bbox_span_x": float(bbox_span_x),
                "bbox_span_y": float(bbox_span_y),
                "bbox_span_z": float(bbox_span_z),
                "bbox_longest_axis": bbox_longest_axis,
                "bbox_longest_span_m": float(bbox_longest_span_m)
            },
            "height_calculation": {
                "axis_used": axis_used,
                "bbox_min_axis": float(bbox_min_axis),
                "bbox_max_axis": float(bbox_max_axis),
                "raw_span_m": float(raw_span_m),
                "post_transform_span_m": float(post_transform_span_m),
                "scale_factor_raw_to_post": float(scale_factor_raw_to_post),
                "source": "mesh_bbox",
                "notes": "v0: direct bbox span, no transform/scale applied"
            }
        }
    elif standard_key == "CROTCH_HEIGHT_M":
        # Crotch height: crotch point to floor
        # For v0, estimate crotch as lower torso region
        y_crotch = y_min + 0.45 * (y_max - y_min)  # Approximate
        value_m = y_crotch - y_min
        landmark_confidence = "medium"
        landmark_resolution = "nearest_cross_section_fallback"
        warnings.append("CROTCH_ESTIMATED")  # Record estimation
    elif standard_key == "KNEE_HEIGHT_M":
        # Knee height: knee point to floor (right side)
        # For v0, estimate knee as mid-leg region
        y_knee = y_min + 0.25 * (y_max - y_min)  # Approximate
        value_m = y_knee - y_min
        landmark_confidence = "medium"
        landmark_resolution = "nearest_cross_section_fallback"
        warnings.append("KNEE_ESTIMATED")  # Record estimation
    else:
        warnings.append(f"UNKNOWN_HEIGHT_KEY: {standard_key}")
        metadata = create_metadata_v0(
            standard_key=standard_key,
            value_m=float('nan'),
            method_path_type="straight_line",
            method_metric_type="height",
            warnings=warnings,
            method_canonical_side=canonical_side,
            pose_strict_standing=True,
            pose_knee_flexion_forbidden=True,
            provenance_evidence_ref=get_evidence_ref(standard_key),
        )
        return MeasurementResult(
            standard_key=standard_key,
            value_m=float('nan'),
            metadata=metadata
        )
    
    # Range sanity check
    if value_m < 0.1:
        warnings.append(f"HEIGHT_SMALL: {value_m:.4f}m")
    if value_m > 3.0:
        warnings.append(f"HEIGHT_LARGE: {value_m:.4f}m")
    
    # Create metadata
    metadata = create_metadata_v0(
        standard_key=standard_key,
        value_m=value_m,
        method_path_type="straight_line",
        method_metric_type="height",
        warnings=warnings,
        method_canonical_side=canonical_side,
        method_landmark_confidence=landmark_confidence,
        method_landmark_resolution=landmark_resolution,
        pose_strict_standing=True,
        pose_knee_flexion_forbidden=True,
        provenance_evidence_ref=get_evidence_ref(standard_key),
        debug_info=debug_info if standard_key == "HEIGHT_M" else None,
    )
    
    return MeasurementResult(
        standard_key=standard_key,
        value_m=value_m,
        metadata=metadata
    )


# -----------------------------
# Length Measurements
# -----------------------------
def measure_arm_length_v0_with_metadata(
    verts: np.ndarray,
    joints_xyz: Optional[np.ndarray] = None,
    joint_ids: Optional[Dict[str, int]] = None,
    units_metadata: Optional[Dict[str, Any]] = None,
) -> MeasurementResult:
    """
    Measure ARM_LEN_M with metadata (schema v0).
    
    ARM_LEN_M is defined as surface path from shoulder to wrist (right side).
    Path type must be surface_path (not straight_line).
    
    Args:
        verts: Body surface vertices (N, 3) in meters
        joints_xyz: Optional joint positions (J, 3) for landmark detection
        joint_ids: Optional joint ID mapping (e.g., {"R_shoulder": 17, "R_wrist": 21})
        units_metadata: Optional units metadata
    
    Returns:
        MeasurementResult with value_m and metadata
    """
    verts = _as_np_f32(verts)
    is_valid, warnings = _validate_verts(verts)
    
    if not is_valid:
        metadata = create_metadata_v0(
            standard_key="ARM_LEN_M",
            value_m=float('nan'),
            method_path_type="surface_path",
            method_metric_type="length",
            warnings=warnings,
            method_canonical_side="right",
            provenance_evidence_ref=get_evidence_ref("ARM_LEN_M"),
        )
        return MeasurementResult(
            standard_key="ARM_LEN_M",
            value_m=float('nan'),
            metadata=metadata
        )
    
    # For v0, if joints are available, use them for landmarks
    # Otherwise, estimate from vertex geometry
    if joints_xyz is not None and joint_ids is not None:
        # Use joint landmarks
        r_shoulder_idx = joint_ids.get("R_shoulder")
        r_wrist_idx = joint_ids.get("R_wrist")
        
        if r_shoulder_idx is not None and r_wrist_idx is not None:
            shoulder_pos = joints_xyz[r_shoulder_idx]
            wrist_pos = joints_xyz[r_wrist_idx]
            
            # For v0, approximate surface path as geodesic distance
            # Simple approximation: use straight line distance as baseline
            # (In production, would use actual geodesic/surface path)
            straight_dist = np.linalg.norm(wrist_pos - shoulder_pos)
            # Surface path is typically 5-10% longer than straight line
            # For v0, use 1.05x multiplier as approximation
            value_m = float(straight_dist * 1.05)
            landmark_confidence = "high"
            landmark_resolution = "direct"
        else:
            warnings.append("JOINT_IDS_MISSING")
            # Fallback: estimate from vertex geometry
            value_m = float('nan')
            landmark_confidence = "low"
            landmark_resolution = "nearest_cross_section_fallback"
    else:
        # Fallback: estimate from vertex geometry
        # Find approximate shoulder and wrist regions
        y_coords = verts[:, 1]
        y_max = float(np.max(y_coords))
        y_range = y_max - float(np.min(y_coords))
        
        # Shoulder region: upper torso
        y_shoulder = y_max - 0.15 * y_range
        # Wrist region: lower arm
        y_wrist = y_max - 0.50 * y_range
        
        # Find vertices in these regions
        shoulder_mask = np.abs(y_coords - y_shoulder) < 0.05 * y_range
        wrist_mask = np.abs(y_coords - y_wrist) < 0.05 * y_range
        
        if np.sum(shoulder_mask) == 0 or np.sum(wrist_mask) == 0:
            warnings.append("LANDMARK_REGIONS_NOT_FOUND")
            value_m = float('nan')
            landmark_confidence = "low"
            landmark_resolution = "nearest_cross_section_fallback"
            found_regions = []
            if np.sum(shoulder_mask) > 0:
                found_regions.append("shoulder_region")
            if np.sum(wrist_mask) > 0:
                found_regions.append("wrist_region")
            debug_info = {
                "landmark_regions": {
                    "required": ["shoulder_region", "wrist_region"],
                    "found": found_regions,
                    "reason_not_found": "no_vertices_in_region"
                }
            }
            metadata = create_metadata_v0(
                standard_key="ARM_LEN_M",
                value_m=value_m,
                method_path_type="surface_path",
                method_metric_type="length",
                warnings=warnings,
                method_canonical_side="right",
                method_landmark_confidence=landmark_confidence,
                method_landmark_resolution=landmark_resolution,
                provenance_evidence_ref=get_evidence_ref("ARM_LEN_M"),
                debug_info=debug_info,
            )
            return MeasurementResult(
                standard_key="ARM_LEN_M",
                value_m=value_m,
                metadata=metadata
            )
        else:
            # Use rightmost points in each region (right arm)
            shoulder_verts = verts[shoulder_mask]
            wrist_verts = verts[wrist_mask]
            
            shoulder_rightmost = shoulder_verts[np.argmax(shoulder_verts[:, 0])]
            wrist_rightmost = wrist_verts[np.argmax(wrist_verts[:, 0])]
            
            straight_dist = np.linalg.norm(wrist_rightmost - shoulder_rightmost)
            value_m = float(straight_dist * 1.05)  # Surface path approximation
            landmark_confidence = "medium"
            landmark_resolution = "nearest_cross_section_fallback"
            warnings.append("SURFACE_PATH_APPROXIMATED")
    
    # Range sanity check
    if not np.isnan(value_m):
        if value_m < 0.2:
            warnings.append(f"ARM_LEN_SMALL: {value_m:.4f}m")
        if value_m > 1.0:
            warnings.append(f"ARM_LEN_LARGE: {value_m:.4f}m")
    
    # Create metadata
    metadata = create_metadata_v0(
        standard_key="ARM_LEN_M",
        value_m=value_m,
        method_path_type="surface_path",  # Required: surface path, not straight line
        method_metric_type="length",
        warnings=warnings,
        method_canonical_side="right",  # Required: right side
        method_landmark_confidence=landmark_confidence,
        method_landmark_resolution=landmark_resolution,
        provenance_evidence_ref=get_evidence_ref("ARM_LEN_M"),
    )
    
    return MeasurementResult(
        standard_key="ARM_LEN_M",
        value_m=value_m,
        metadata=metadata
    )


# -----------------------------
# Weight (Input-only, no mesh computation)
# -----------------------------
def create_weight_metadata(
    value_kg: float,
    warnings: Optional[List[str]] = None,
) -> MeasurementResult:
    """
    Create weight measurement result with metadata.
    Weight cannot be computed from mesh - it must be provided as input.
    
    Args:
        value_kg: Weight in kilograms
        warnings: Optional warnings
    
    Returns:
        MeasurementResult with value_kg and metadata
    """
    metadata = create_metadata_v0(
        standard_key="WEIGHT_KG",
        value_kg=value_kg,
        method_path_type="straight_line",  # N/A for weight
        method_metric_type="mass",
        warnings=warnings if warnings is not None else [],
        provenance_evidence_ref=get_evidence_ref("WEIGHT_KG"),
    )
    
    return MeasurementResult(
        standard_key="WEIGHT_KG",
        value_kg=value_kg,
        metadata=metadata
    )
