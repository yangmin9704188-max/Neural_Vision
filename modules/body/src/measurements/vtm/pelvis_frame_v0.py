"""
Refine04: Pelvis/body frame for HIP measurement (pelvis-relative height).
Deterministic: pelvis_origin + up_axis; h = dot(v - pelvis_origin, up_axis).
Fallback: return None with warning HIP_FRAME_FALLBACK_TO_WORLD_Y.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np


def get_pelvis_frame(
    verts: np.ndarray,
    joints_xyz: Optional[np.ndarray] = None,
    joint_ids: Optional[dict] = None,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], List[str]]:
    """
    Compute stable body frame (pelvis origin, up axis) for pelvis-relative height.

    - If joints provided and "pelvis" in joint_ids: use pelvis joint position.
    - Else: pelvis_origin = centroid of vertices in lower-torso band
      (y in [y_min + 0.45*y_range, y_min + 0.55*y_range]); deterministic.
    - up_axis = (0, 1, 0) (world Y).

    Returns:
        (pelvis_origin (3,) or None, up_axis (3,) or None, warnings).
        If frame cannot be computed, returns (None, None, ["HIP_FRAME_FALLBACK_TO_WORLD_Y"]).
    """
    warnings: List[str] = []
    verts = np.asarray(verts, dtype=np.float32)
    if verts.ndim != 2 or verts.shape[1] != 3:
        warnings.append("HIP_FRAME_FALLBACK_TO_WORLD_Y")
        return None, None, warnings

    up_axis = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    if joints_xyz is not None and joint_ids is not None:
        pelvis_idx = joint_ids.get("pelvis", 0)
        joints_xyz = np.asarray(joints_xyz, dtype=np.float32)
        if joints_xyz.ndim >= 2 and 0 <= pelvis_idx < joints_xyz.shape[0]:
            pelvis_origin = np.array(
                joints_xyz[pelvis_idx, :3], dtype=np.float32
            )
            return pelvis_origin, up_axis, warnings

    y_coords = verts[:, 1]
    y_min = float(np.min(y_coords))
    y_max = float(np.max(y_coords))
    y_range = y_max - y_min
    if y_range < 1e-6:
        warnings.append("HIP_FRAME_FALLBACK_TO_WORLD_Y")
        return None, None, warnings

    y_lo = y_min + 0.45 * y_range
    y_hi = y_min + 0.55 * y_range
    mask = (y_coords >= y_lo) & (y_coords <= y_hi)
    band = verts[mask]
    if band.shape[0] < 3:
        warnings.append("HIP_FRAME_FALLBACK_TO_WORLD_Y")
        return None, None, warnings

    pelvis_origin = np.mean(band, axis=0).astype(np.float32)
    return pelvis_origin, up_axis, warnings
