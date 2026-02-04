# shoulder_width_v12.py
# Shoulder Width v1.2 - Joint-Anchored Torso Cross-Section (PROTOTYPE)
#
# Semantic Definition:
# - Use L/R shoulder joints as anchors
# - Define a torso plane at shoulder joint level (perpendicular to vertical axis)
# - Extract cross-section vertices in this plane
# - Explicitly exclude upper arm geometry by removing projection along (shoulder -> elbow)
# - Measure maximal lateral distance on the remaining torso cross-section
#
# Key Difference from v1.1.x:
# - Explicit arm exclusion via directional filtering (not geometric cone filter)
# - Plane-based cross-section (not landmark-based)
# - More interpretable: "torso width at shoulder level"

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any
import numpy as np


@dataclass(frozen=True)
class ShoulderWidthV12Config:
    """Configuration for v1.2 measurement (prototype, not frozen)."""
    # Torso plane definition
    plane_height_tolerance: float = 0.08  # meters - tolerance around shoulder joint Y-level (increased from 0.05)
    
    # Arm exclusion
    arm_direction_exclusion_threshold: float = 0.5  # cosine threshold for arm direction filtering (increased from 0.3 for less aggressive exclusion)
    arm_distance_threshold: float = 0.15  # meters - distance from shoulder before checking arm alignment (default 15cm)
    
    # Cross-section lateral measurement
    lateral_quantile: float = 0.95  # Use top quantile for maximal lateral distance
    
    # Numeric stability
    eps: float = 1e-12
    min_points: int = 30  # Minimum points required in cross-section (reduced from 50)


def _as_np_f32(x: np.ndarray) -> np.ndarray:
    """Convert to float32 numpy array."""
    if not isinstance(x, np.ndarray):
        x = np.array(x)
    if x.dtype != np.float32:
        x = x.astype(np.float32, copy=False)
    return x


def _unit_or_raise(v: np.ndarray, eps: float) -> np.ndarray:
    """Normalize vector or raise if zero-length."""
    n = float(np.linalg.norm(v))
    if n < eps:
        raise ValueError("Zero-length vector encountered while normalizing.")
    return v / n


def measure_shoulder_width_v12(
    verts: np.ndarray,
    lbs_weights: np.ndarray,
    joints_xyz: np.ndarray,
    joint_ids: Dict[str, int],
    cfg: Optional[ShoulderWidthV12Config] = None,
    return_debug: bool = False,
) -> Tuple[float, Dict[str, Any]] | float:
    """
    Measure shoulder width v1.2 using joint-anchored torso cross-section.
    
    Args:
        verts: (N, 3) vertices in meters
        lbs_weights: (N, J) LBS weights (not used in v1.2, kept for API compatibility)
        joints_xyz: (J, 3) joint positions in meters
        joint_ids: Dict mapping joint names to indices
        cfg: Configuration (uses defaults if None)
        return_debug: If True, return debug info
        
    Returns:
        width (float) or (width, debug_dict)
    """
    if cfg is None:
        cfg = ShoulderWidthV12Config()
    
    verts = _as_np_f32(verts)
    joints_xyz = _as_np_f32(joints_xyz)
    
    # Validate inputs
    if verts.ndim != 2 or verts.shape[1] != 3:
        raise ValueError(f"verts must be (N,3), got {verts.shape}")
    if joints_xyz.ndim != 2 or joints_xyz.shape[1] != 3:
        raise ValueError(f"joints_xyz must be (J,3), got {joints_xyz.shape}")
    
    required_joints = ["L_shoulder", "R_shoulder", "L_elbow", "R_elbow"]
    missing = [k for k in required_joints if k not in joint_ids]
    if missing:
        raise KeyError(f"joint_ids missing required keys: {missing}")
    
    L_sh_idx = joint_ids["L_shoulder"]
    R_sh_idx = joint_ids["R_shoulder"]
    L_el_idx = joint_ids["L_elbow"]
    R_el_idx = joint_ids["R_elbow"]
    
    # Get joint positions
    L_shoulder = joints_xyz[L_sh_idx, :]
    R_shoulder = joints_xyz[R_sh_idx, :]
    L_elbow = joints_xyz[L_el_idx, :]
    R_elbow = joints_xyz[R_el_idx, :]
    
    # Step 1: Define torso plane at shoulder joint level
    # Use average Y-coordinate (vertical) of shoulder joints as plane height
    shoulder_midpoint = 0.5 * (L_shoulder + R_shoulder)
    plane_height = float(shoulder_midpoint[1])  # Y-coordinate
    
    # Extract vertices near the torso plane
    y_coords = verts[:, 1]
    height_mask = np.abs(y_coords - plane_height) <= cfg.plane_height_tolerance
    torso_candidates = verts[height_mask, :]
    
    if torso_candidates.shape[0] < cfg.min_points:
        # Fallback: use joint-based distance
        width = float(np.linalg.norm(L_shoulder - R_shoulder))
        if not return_debug:
            return width
        return width, {
            "fallback": True,
            "reason": f"insufficient_points_in_plane: {torso_candidates.shape[0]} < {cfg.min_points}",
            "torso_candidates_count": int(torso_candidates.shape[0]),
            "cross_section_vertices": None,
            "arm_excluded_vertices": None,
            "measurement_direction": None,
        }
    
    # Step 2: Explicitly exclude upper arm geometry
    # Compute arm direction vectors (shoulder -> elbow)
    L_arm_dir = L_elbow - L_shoulder
    R_arm_dir = R_elbow - R_shoulder
    L_arm_len = float(np.linalg.norm(L_arm_dir))
    R_arm_len = float(np.linalg.norm(R_arm_dir))
    L_arm_dir_norm = _unit_or_raise(L_arm_dir, cfg.eps)
    R_arm_dir_norm = _unit_or_raise(R_arm_dir, cfg.eps)
    
    # For each candidate vertex, exclude if it's "along the arm" (projection along arm direction)
    # AND far enough from shoulder (beyond torso region)
    # This avoids excluding points near the shoulder that naturally align with arm direction
    arm_exclusion_mask = np.ones(torso_candidates.shape[0], dtype=bool)
    
    for i, v in enumerate(torso_candidates):
        # Vector from shoulder to vertex
        vec_L = v - L_shoulder
        vec_R = v - R_shoulder
        
        # Project vertex onto arm direction
        # If projection is significant AND cosine similarity is high, it's likely arm geometry
        dist_from_L = float(np.linalg.norm(vec_L))
        dist_from_R = float(np.linalg.norm(vec_R))
        
        # Check left arm
        if dist_from_L > cfg.eps and dist_from_L > cfg.arm_distance_threshold:  # Only check if vertex is beyond threshold from shoulder
            cos_L = np.abs(np.dot(_unit_or_raise(vec_L, cfg.eps), L_arm_dir_norm))
            # Projection along arm direction (in arm length units)
            proj_L = np.dot(vec_L, L_arm_dir_norm) / L_arm_len if L_arm_len > cfg.eps else 0.0
            # Exclude if strongly aligned AND projected along arm (not away from arm)
            if cos_L > cfg.arm_direction_exclusion_threshold and proj_L > 0.2:
                arm_exclusion_mask[i] = False
                continue
        
        # Check right arm
        if dist_from_R > cfg.eps and dist_from_R > cfg.arm_distance_threshold:  # Only check if vertex is beyond threshold from shoulder
            cos_R = np.abs(np.dot(_unit_or_raise(vec_R, cfg.eps), R_arm_dir_norm))
            # Projection along arm direction (in arm length units)
            proj_R = np.dot(vec_R, R_arm_dir_norm) / R_arm_len if R_arm_len > cfg.eps else 0.0
            # Exclude if strongly aligned AND projected along arm (not away from arm)
            if cos_R > cfg.arm_direction_exclusion_threshold and proj_R > 0.2:
                arm_exclusion_mask[i] = False
    
    torso_cross_section = torso_candidates[arm_exclusion_mask, :]
    arm_excluded_count = int(np.sum(~arm_exclusion_mask))
    
    if torso_cross_section.shape[0] < cfg.min_points:
        # Fallback: use joint-based distance
        width = float(np.linalg.norm(L_shoulder - R_shoulder))
        if not return_debug:
            return width
        return width, {
            "fallback": True,
            "reason": f"insufficient_points_after_arm_exclusion: {torso_cross_section.shape[0]} < {cfg.min_points}",
            "torso_candidates_count": int(torso_candidates.shape[0]),
            "arm_excluded_count": arm_excluded_count,
            "cross_section_vertices": None,
            "arm_excluded_vertices": torso_candidates[~arm_exclusion_mask, :].tolist() if arm_excluded_count > 0 else None,
            "measurement_direction": None,
        }
    
    # Step 3: Compute lateral direction (L_shoulder -> R_shoulder)
    shoulder_vector = R_shoulder - L_shoulder
    lateral_direction = _unit_or_raise(shoulder_vector, cfg.eps)
    
    # Step 4: Project cross-section vertices onto lateral direction
    # Compute signed distance from L_shoulder along lateral direction
    cross_section_relative = torso_cross_section - L_shoulder[None, :]
    lateral_projections = cross_section_relative @ lateral_direction
    
    # Step 5: Measure maximal lateral distance
    # Use quantile-based approach for robustness
    lateral_min = float(np.quantile(lateral_projections, 1.0 - cfg.lateral_quantile))
    lateral_max = float(np.quantile(lateral_projections, cfg.lateral_quantile))
    width = lateral_max - lateral_min
    
    # Alternative: Simple min-max (commented for reference)
    # lateral_min = float(np.min(lateral_projections))
    # lateral_max = float(np.max(lateral_projections))
    # width = lateral_max - lateral_min
    
    if not return_debug:
        return width
    
    # Debug info
    debug_info = {
        "fallback": False,
        "plane_height": float(plane_height),
        "plane_height_tolerance": float(cfg.plane_height_tolerance),
        "torso_candidates_count": int(torso_candidates.shape[0]),
        "arm_excluded_count": arm_excluded_count,
        "cross_section_vertices_count": int(torso_cross_section.shape[0]),
        "cross_section_vertices": torso_cross_section.tolist(),  # All vertices in cross-section
        "arm_excluded_vertices": torso_candidates[~arm_exclusion_mask, :].tolist() if arm_excluded_count > 0 else [],
        "measurement_direction": lateral_direction.tolist(),
        "lateral_projection_stats": {
            "min": float(np.min(lateral_projections)),
            "max": float(np.max(lateral_projections)),
            "mean": float(np.mean(lateral_projections)),
            "quantile_min": lateral_min,
            "quantile_max": lateral_max,
        },
        "shoulder_joints": {
            "L_shoulder": L_shoulder.tolist(),
            "R_shoulder": R_shoulder.tolist(),
        },
        "arm_directions": {
            "L_arm_dir": L_arm_dir_norm.tolist(),
            "R_arm_dir": R_arm_dir_norm.tolist(),
        },
        "arm_exclusion_threshold": float(cfg.arm_direction_exclusion_threshold),
    }
    
    return width, debug_info
