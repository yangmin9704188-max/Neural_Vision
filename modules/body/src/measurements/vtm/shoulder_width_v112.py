# shoulder_width_v112.py
# Shoulder Width v1.1.2 - pure measurement function
# Policy:
# 1) distal arm removal by LBS weights (elbow+wrist)
# 2) arm-axis geometric filter (shoulder->elbow direction)
# 3) robust landmark from remaining shoulder-cap (quantile/centroid)
# 4) distance between left/right landmarks = shoulder width

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any
import numpy as np

# -----------------------------
# Config
# -----------------------------
@dataclass(frozen=True)
class ShoulderWidthV112Config:
    # Step1: distal arm removal
    distal_w_threshold: float = 0.55

    # Step2: arm-axis geometric filter (cone/frustum around shoulder->elbow axis)
    s_min_ratio: float = 0.02
    s_max_ratio: float = 0.95
    r0_ratio: float = 0.33   # Critical knob: deltoid vs acromion bite
    r1_ratio: float = 0.22

    # Step3: robust landmark
    cap_quantile: float = 0.92
    min_cap_points: int = 60

    # Numeric stability
    eps: float = 1e-12
    min_axis_len: float = 1e-6  # explicit guardrail


# -----------------------------
# Utilities
# -----------------------------
def _as_np_f32(x: np.ndarray) -> np.ndarray:
    if not isinstance(x, np.ndarray):
        x = np.array(x)
    if x.dtype != np.float32:
        x = x.astype(np.float32, copy=False)
    return x


def _unit_or_raise(v: np.ndarray, eps: float) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < eps:
        raise ValueError("Zero-length vector encountered while normalizing.")
    return v / n


def _project_along_axis(
    points: np.ndarray,
    origin: np.ndarray,
    axis_u: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    p = points - origin[None, :]
    s = p @ axis_u
    perp = p - s[:, None] * axis_u[None, :]
    d = np.linalg.norm(perp, axis=1)
    return s, d


def _cone_radius(s: np.ndarray, L: float, r0: float, r1: float) -> np.ndarray:
    # Safe division with explicit denom
    denom = L if L > 1e-9 else 1e-9
    t = np.clip(s / denom, 0.0, 1.0)
    return r0 + (r1 - r0) * t


def _robust_cap_landmark(
    points: np.ndarray,
    shoulder: np.ndarray,
    lateral_u: np.ndarray,
    quantile: float,
    min_points: int
) -> np.ndarray:
    """
    Centroid of 'most lateral' points.
    Fallbacks:
      - if points empty: return shoulder
      - if too few after quantile relaxation: take top-k by score (k up to 10), else shoulder
    """
    if points.shape[0] == 0:
        return shoulder

    v = points - shoulder[None, :]
    score = v @ lateral_u

    q = quantile
    keep_mask = None

    for _ in range(6):
        thr = np.quantile(score, q)
        keep_mask = score >= thr
        if int(np.sum(keep_mask)) >= min_points:
            break
        q = max(0.60, q - 0.05)

    kept = points[keep_mask]

    if kept.shape[0] >= 5:
        return kept.mean(axis=0)

    # fallback: top-k
    k = min(10, points.shape[0])
    idx = np.argsort(score)[-k:]
    return points[idx].mean(axis=0)


# -----------------------------
# Main API
# -----------------------------
def measure_shoulder_width_v112(
    verts: np.ndarray,
    lbs_weights: np.ndarray,
    joints_xyz: np.ndarray,
    joint_ids: Dict[str, int],
    cfg: Optional[ShoulderWidthV112Config] = None,
    return_debug: bool = False,
) -> Tuple[float, Dict[str, Any]] | float:

    if cfg is None:
        cfg = ShoulderWidthV112Config()

    verts = _as_np_f32(verts)
    lbs_weights = _as_np_f32(lbs_weights)
    joints_xyz = _as_np_f32(joints_xyz)

    # Basic validation
    if verts.ndim != 2 or verts.shape[1] != 3:
        raise ValueError(f"verts must be (N,3), got {verts.shape}")
    if lbs_weights.ndim != 2:
        raise ValueError(f"lbs_weights must be (N,J), got {lbs_weights.shape}")
    if joints_xyz.ndim != 2 or joints_xyz.shape[1] != 3:
        raise ValueError(f"joints_xyz must be (J,3), got {joints_xyz.shape}")
    if lbs_weights.shape[0] != verts.shape[0]:
        raise ValueError("lbs_weights and verts must have same N.")
    if lbs_weights.shape[1] != joints_xyz.shape[0]:
        raise ValueError("lbs_weights J must match joints_xyz J.")

    required = ["L_shoulder","R_shoulder","L_elbow","R_elbow","L_wrist","R_wrist"]
    missing = [k for k in required if k not in joint_ids]
    if missing:
        raise KeyError(f"joint_ids missing required keys: {missing}")

    # -------------------------
    # Step1) distal arm removal (LBS)
    # -------------------------
    L_elb, L_wri = joint_ids["L_elbow"], joint_ids["L_wrist"]
    R_elb, R_wri = joint_ids["R_elbow"], joint_ids["R_wrist"]

    distal_w = (lbs_weights[:, L_elb] + lbs_weights[:, L_wri] +
                lbs_weights[:, R_elb] + lbs_weights[:, R_wri])

    mask_keep_1 = distal_w < cfg.distal_w_threshold

    # -------------------------
    # Step2) arm-axis geometric filter (per side)
    # IMPORTANT: apply only to mask_keep_1 survivors to preserve "2-stage defense" semantics.
    # -------------------------
    mask_keep_2 = mask_keep_1.copy()

    for side in ("L", "R"):
        sh = joints_xyz[joint_ids[f"{side}_shoulder"]]
        el = joints_xyz[joint_ids[f"{side}_elbow"]]

        axis = el - sh
        L = float(np.linalg.norm(axis))
        if L < cfg.min_axis_len:
            # data is corrupted; do NOT silently proceed with zero vector
            raise ValueError(f"{side} shoulder-elbow axis too short (L={L}).")

        u = _unit_or_raise(axis, cfg.eps)

        s, d = _project_along_axis(verts, sh, u)

        s_min = cfg.s_min_ratio * L
        s_max = cfg.s_max_ratio * L
        r0 = cfg.r0_ratio * L
        r1 = cfg.r1_ratio * L
        r = _cone_radius(s, L, r0, r1)

        is_arm_bulge = (s >= s_min) & (s <= s_max) & (d <= r)
        is_arm_bulge = is_arm_bulge & mask_keep_1  # keep stage semantics
        mask_keep_2 = mask_keep_2 & (~is_arm_bulge)

    # -------------------------
    # Step3) robust landmarks
    # -------------------------
    L_sh = joints_xyz[joint_ids["L_shoulder"]]
    R_sh = joints_xyz[joint_ids["R_shoulder"]]
    mid = 0.5 * (L_sh + R_sh)

    # Known limitation (v1.1.2): lateral_u uses shoulder-mid, may be affected by shrug in diverse poses.
    lat_L = _unit_or_raise(L_sh - mid, cfg.eps)
    lat_R = _unit_or_raise(R_sh - mid, cfg.eps)

    pts = verts[mask_keep_2]
    if pts.shape[0] == 0:
        # Emergency fallback: no geometry left -> return joint-based shoulder distance
        width = float(np.linalg.norm(L_sh - R_sh))
        if not return_debug:
            return width
        return width, {
            "mask_keep_step1": mask_keep_1,
            "mask_keep_step2": mask_keep_2,
            "landmark_L": L_sh,
            "landmark_R": R_sh,
            "fallback": np.array([1], dtype=np.int32),
        }

    # Split by nearest shoulder (Voronoi)
    dL = np.linalg.norm(pts - L_sh[None, :], axis=1)
    dR = np.linalg.norm(pts - R_sh[None, :], axis=1)
    pts_L = pts[dL <= dR]
    pts_R = pts[dR < dL]

    lm_L = _robust_cap_landmark(pts_L, L_sh, lat_L, cfg.cap_quantile, cfg.min_cap_points)
    lm_R = _robust_cap_landmark(pts_R, R_sh, lat_R, cfg.cap_quantile, cfg.min_cap_points)

    width = float(np.linalg.norm(lm_L - lm_R))

    if not return_debug:
        return width

    return width, {
        "mask_keep_step1": mask_keep_1,
        "mask_keep_step2": mask_keep_2,
        "landmark_L": lm_L,
        "landmark_R": lm_R,
        "L_shoulder": L_sh,
        "R_shoulder": R_sh,
        "fallback": np.array([0], dtype=np.int32),
    }
