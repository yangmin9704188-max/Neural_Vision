"""
Purpose: Map anthropometric measurements to SMPL-X parameters.
Inputs: measurements, SMPL-X model
Outputs: optimized betas/joints
Status: active
"""
# smart_mapper_v001.py
# Policy: Uses frozen A-Pose and Shoulder Width v1.1.2
#
# IMPORTANT: This module uses measurement function API results only.
# It does NOT duplicate or reference measurement policy parameters.

from __future__ import annotations

import os
import time
import traceback
import json
import numpy as np
import torch
import torch.optim as optim
import smplx
from typing import Optional, Dict, Tuple, Any

from core.pose_policy import PoseNormalizer
from core.policy.smart_mapper_policy import SMART_MAPPER_POLICY
from core.measurements.shoulder_width_v112 import measure_shoulder_width_v112
from core.policy.shoulder_width_v112_policy import get_cfg as get_shoulder_width_cfg

# SMPL-X joint IDs for shoulder width measurement
SMPLX_JOINT_IDS = {
    "L_shoulder": 16,
    "R_shoulder": 17,
    "L_elbow": 18,
    "R_elbow": 19,
    "L_wrist": 20,
    "R_wrist": 21,
}


def load_beta_means(data_dir: str) -> Dict[str, np.ndarray]:
    """
    Load beta means from step1_output.
    
    Returns:
        Dict with keys 'male' and 'female', values are (num_betas,) arrays
    """
    male_path = os.path.join(data_dir, "init_betas_male.npy")
    female_path = os.path.join(data_dir, "init_betas_female.npy")
    
    if not os.path.exists(male_path) or not os.path.exists(female_path):
        raise FileNotFoundError(
            f"Beta mean files not found. Expected:\n"
            f"  - {male_path}\n"
            f"  - {female_path}\n"
            f"Run step1_execute.py first to generate these files."
        )
    
    male_betas = np.load(male_path)  # (N, num_betas)
    female_betas = np.load(female_path)  # (N, num_betas)
    
    return {
        "male": np.mean(male_betas, axis=0).astype(np.float32),
        "female": np.mean(female_betas, axis=0).astype(np.float32),
    }


def compute_canonical_height(model: smplx.SMPLX, device: torch.device) -> float:
    """Compute canonical height (robust quantile-based) for a model."""
    model.eval()
    with torch.no_grad():
        betas = torch.zeros((1, model.num_betas), dtype=torch.float32, device=device)
        out = model(betas=betas)
        verts = out.vertices[0]  # (N, 3)
        
        y = verts[:, 1]
        y_low = torch.quantile(y, 0.005)
        y_high = torch.quantile(y, 0.995)
        height_m = (y_high - y_low).item()
    
    return height_m


def get_init_betas(
    sex: str,
    height_m: float,
    weight_kg: float,
    beta_means: Dict[str, np.ndarray],
    policy: Any,
) -> np.ndarray:
    """
    Deterministic initialization:
    1. Start from beta_mean(sex)
    2. Apply BMI-based beta0 correction (clamped)
    """
    if sex not in ["male", "female"]:
        raise ValueError(f"sex must be 'male' or 'female', got '{sex}'")
    
    beta_init = beta_means[sex].copy()
    
    # BMI-based beta0 correction
    h_cm = height_m * 100.0
    if h_cm > 0:
        bmi = weight_kg / ((h_cm / 100.0) ** 2)
        if np.isfinite(bmi):
            beta0_raw = (bmi - policy.bmi_ref) * policy.beta0_scale
            beta0_clipped = np.clip(beta0_raw, -policy.beta0_clip, policy.beta0_clip)
            beta_init[0] = beta0_clipped
    
    return beta_init


class SmartMapper:
    """
    Smart Mapper v0.1
    
    Maps anthropometric measurements to SMPL-X parameters using
    deterministic initialization + LBFGS optimization.
    
    Policy compliance:
    - Uses A-Pose normalization via core.pose_policy.PoseNormalizer
    - Uses shoulder width measurement via core.measurements.shoulder_width_v112
      (uses default config, does NOT duplicate policy parameters)
    """
    
    def __init__(
        self,
        model_path: str,
        beta_means: Dict[str, np.ndarray],
        device: Optional[torch.device] = None,
        policy: Any = None,
    ):
        """
        Args:
            model_path: Path to SMPL-X model directory
            beta_means: Dict with 'male' and 'female' beta means
            device: torch device (default: cuda if available, else cpu)
            policy: SmartMapperPolicy instance (default: SMART_MAPPER_POLICY)
        """
        self.device = device if device is not None else torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.policy = policy if policy is not None else SMART_MAPPER_POLICY
        self.beta_means = beta_means
        
        # Store model path (will load per-request by sex)
        self.model_path = model_path
        self.num_betas = len(beta_means["male"])
        self._models = {}  # Cache models by sex
        
        # Pose normalizer (A-Pose policy)
        self.pose_normalizer = PoseNormalizer(device=self.device)
        
        # Cache canonical heights
        self._canonical_heights = {}
    
    def _get_model(self, sex: str) -> smplx.SMPLX:
        """Get SMPL-X model for sex (cached)."""
        if sex not in self._models:
            gender_map = {"male": "male", "female": "female"}
            model = smplx.create(
                self.model_path,
                model_type="smplx",
                gender=gender_map[sex],
                use_pca=False,
                num_betas=self.num_betas,
                ext="pkl",
            ).to(self.device)
            model.eval()
            self._models[sex] = model
        return self._models[sex]
    
    def _get_canonical_height(self, sex: str) -> float:
        """Get cached canonical height for sex."""
        if sex not in self._canonical_heights:
            model = self._get_model(sex)
            self._canonical_heights[sex] = compute_canonical_height(model, self.device)
        
        return self._canonical_heights[sex]
    
    def optimize(
        self,
        sex: str,
        age: Optional[int],
        height_m: float,
        weight_kg: float,
        target_shoulder_width_m: Optional[float] = None,
        debug_output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Optimize SMPL-X parameters for given measurements.
        
        Args:
            sex: 'male' or 'female'
            age: Age in years (optional, not used in v0.1)
            height_m: Target height in meters
            weight_kg: Target weight in kg
            target_shoulder_width_m: Target shoulder width in meters (optional)
        
        Returns:
            Dict with keys:
                - scale: float, global scale factor
                - betas: np.ndarray, optimized betas
                - beta_init: np.ndarray, initial betas
                - predicted_shoulder_width_m: float or None
                - loss_total: float, final total loss
                - loss_measurement: float or None
                - loss_anchor: float
                - loss_beta_mag: float
                - n_iter: int, number of iterations
                - trace: list of dicts with iteration info
        """
        # 1. Compute global scale
        base_height = self._get_canonical_height(sex)
        scale = height_m / base_height
        
        # 2. Initialize betas
        beta_init = get_init_betas(sex, height_m, weight_kg, self.beta_means, self.policy)
        beta_init_t = torch.tensor(beta_init, dtype=torch.float32, device=self.device, requires_grad=True)
        
        # 3. Setup optimizer
        optimizer = optim.LBFGS(
            [beta_init_t],
            lr=0.1,
            max_iter=20,  # Per-call max_iter
            tolerance_grad=1e-7,
            tolerance_change=1e-9,
            line_search_fn="strong_wolfe",
        )
        
        # Get model for this sex
        model = self._get_model(sex)
        
        # Store scale as tensor for closure
        scale_t = torch.tensor(scale, dtype=torch.float32, device=self.device)
        
        # Track measurement failure
        measurement_failed = False
        fail_reason = None
        fail_info = None
        
        # 4. Optimization loop
        trace = []
        prev_loss = float("inf")
        prev_beta = beta_init_t.detach().clone()
        
        def _log_measurement_exception(
            e: Exception,
            verts_np: np.ndarray,
            lbs_weights_np: np.ndarray,
            joints_np: np.ndarray,
            joint_ids: Dict[str, int],
        ) -> Dict[str, Any]:
            """Log detailed exception information."""
            exc_type = type(e).__name__
            exc_msg = str(e)
            exc_traceback = traceback.format_exc()
            
            # Input summary
            input_summary = {
                "verts": {
                    "shape": list(verts_np.shape),
                    "dtype": str(verts_np.dtype),
                    "min": float(np.nanmin(verts_np)),
                    "max": float(np.nanmax(verts_np)),
                    "has_nan": bool(np.any(np.isnan(verts_np))),
                },
                "lbs_weights": {
                    "shape": list(lbs_weights_np.shape),
                    "dtype": str(lbs_weights_np.dtype),
                    "min": float(np.nanmin(lbs_weights_np)),
                    "max": float(np.nanmax(lbs_weights_np)),
                    "has_nan": bool(np.any(np.isnan(lbs_weights_np))),
                },
                "joints_xyz": {
                    "shape": list(joints_np.shape),
                    "dtype": str(joints_np.dtype),
                    "min": float(np.nanmin(joints_np)),
                    "max": float(np.nanmax(joints_np)),
                    "has_nan": bool(np.any(np.isnan(joints_np))),
                },
                "joint_ids": {
                    "keys": list(joint_ids.keys()),
                    "required": ["L_shoulder", "R_shoulder", "L_elbow", "R_elbow", "L_wrist", "R_wrist"],
                    "has_all_required": all(k in joint_ids for k in ["L_shoulder", "R_shoulder", "L_elbow", "R_elbow", "L_wrist", "R_wrist"]),
                },
            }
            
            return {
                "exception_type": exc_type,
                "exception_message": exc_msg,
                "stack_trace": exc_traceback,
                "input_summary": input_summary,
            }
        
        def closure():
            optimizer.zero_grad()
            
            # Forward pass with A-Pose (via policy)
            # Call path: core.pose_policy.PoseNormalizer.run_forward()
            out = self.pose_normalizer.run_forward(
                model,
                beta_init_t.unsqueeze(0),  # (1, num_betas)
                {},
                enforce_policy_apose=True,
            )
            
            # Loss components
            loss_meas = torch.tensor(0.0, device=self.device)
            loss_anchor = torch.tensor(0.0, device=self.device)
            loss_beta_mag = torch.tensor(0.0, device=self.device)
            
            # Measurement loss (shoulder width)
            # Call path: core.measurements.shoulder_width_v112.measure_shoulder_width_v112()
            # Uses default config (cfg=None), does NOT duplicate policy parameters
            if target_shoulder_width_m is not None:
                # Apply global scale to vertices
                verts_scaled = out.vertices[0] * scale_t
                
                # Convert to numpy for measurement
                verts_np = verts_scaled.detach().cpu().numpy()
                lbs_weights_np = model.lbs_weights.detach().cpu().numpy()
                
                # Get joints from model output and apply scale
                # SMPL-X outputs joints: (B, J, 3) where J=127 (body + hand + face)
                # But lbs_weights has 55 joints (body + hand roots)
                # Use first 55 joints to match lbs_weights
                with torch.no_grad():
                    joints_full = out.joints  # (1, 127, 3)
                    num_joints_weights = lbs_weights_np.shape[1]  # Should be 55
                    
                    # Assert: joint_ids indices are within first 55 joints
                    max_joint_idx = max(SMPLX_JOINT_IDS.values())
                    assert max_joint_idx < num_joints_weights, (
                        f"joint_ids max index {max_joint_idx} >= num_joints_weights {num_joints_weights}"
                    )
                    
                    # Use first 55 joints (body + hand roots) to match lbs_weights
                    # Apply scale ONCE
                    joints_scaled = joints_full[0, :num_joints_weights, :] * scale_t
                    joints_np = joints_scaled.detach().cpu().numpy()
                
                try:
                    # Use frozen policy config
                    sw_cfg = get_shoulder_width_cfg()
                    pred_width = measure_shoulder_width_v112(
                        verts=verts_np,
                        lbs_weights=lbs_weights_np,
                        joints_xyz=joints_np,
                        joint_ids=SMPLX_JOINT_IDS,
                        cfg=sw_cfg,  # Use frozen policy config
                        return_debug=False,
                    )
                    pred_width_t = torch.tensor(pred_width, dtype=torch.float32, device=self.device)
                    target_width_t = torch.tensor(target_shoulder_width_m, dtype=torch.float32, device=self.device)
                    loss_meas = self.policy.weight_measurement * (pred_width_t - target_width_t) ** 2
                except Exception as e:
                    # Log detailed exception information
                    nonlocal measurement_failed, fail_reason, fail_info
                    measurement_failed = True
                    fail_reason = f"{type(e).__name__}: {str(e)}"
                    fail_info = _log_measurement_exception(e, verts_np, lbs_weights_np, joints_np, SMPLX_JOINT_IDS)
                    
                    # Save to artifacts if output dir provided
                    if debug_output_dir:
                        os.makedirs(debug_output_dir, exist_ok=True)
                        error_file = os.path.join(debug_output_dir, "measurement_error.json")
                        with open(error_file, "w", encoding="utf-8") as f:
                            json.dump(fail_info, f, indent=2)
                    
                    # Raise to stop optimization immediately
                    raise RuntimeError(f"Measurement failed: {fail_reason}")
            
            # Anchor prior: ||beta - beta_init||^2
            beta_init_ref = torch.tensor(beta_init, dtype=torch.float32, device=self.device)
            loss_anchor = self.policy.weight_anchor * torch.sum((beta_init_t - beta_init_ref) ** 2)
            
            # Beta magnitude: ||beta||^2
            loss_beta_mag = self.policy.weight_beta_mag * torch.sum(beta_init_t ** 2)
            
            # Total loss
            loss_total = loss_meas + loss_anchor + loss_beta_mag
            loss_total.backward()
            
            return loss_total
        
        n_iter = 0
        for iter_idx in range(self.policy.max_iter):
            iter_start = time.perf_counter()
            
            try:
                loss_total = optimizer.step(closure)
                loss_val = loss_total.item()
            except RuntimeError as e:
                # Measurement failed - stop immediately
                if "Measurement failed" in str(e):
                    break
                else:
                    raise
            
            # Check if measurement failed (raised exception)
            if measurement_failed:
                break
            
            # Check early stopping
            loss_improvement = prev_loss - loss_val
            beta_change = torch.norm(beta_init_t.detach() - prev_beta).item()
            
            iter_time_ms = (time.perf_counter() - iter_start) * 1000.0
            
            # Get current loss components (approximate)
            with torch.no_grad():
                out = self.pose_normalizer.run_forward(
                    model,
                    beta_init_t.unsqueeze(0),
                    {},
                    enforce_policy_apose=True,
                )
                
                # Approximate loss components
                beta_init_ref = torch.tensor(beta_init, dtype=torch.float32, device=self.device)
                loss_anchor_val = self.policy.weight_anchor * torch.sum((beta_init_t - beta_init_ref) ** 2).item()
                loss_beta_mag_val = self.policy.weight_beta_mag * torch.sum(beta_init_t ** 2).item()
                
                loss_meas_val = None
                if target_shoulder_width_m is not None:
                    try:
                        # Apply scale
                        verts_scaled = out.vertices[0] * scale_t
                        verts_np = verts_scaled.detach().cpu().numpy()
                        lbs_weights_np = model.lbs_weights.detach().cpu().numpy()
                        joints_full = out.joints
                        num_joints_weights = lbs_weights_np.shape[1]
                        
                        # Use first 55 joints, apply scale ONCE
                        joints_scaled = joints_full[0, :num_joints_weights, :] * scale_t
                        joints_np = joints_scaled.detach().cpu().numpy()
                        
                        # Use frozen policy config
                        sw_cfg = get_shoulder_width_cfg()
                        pred_width = measure_shoulder_width_v112(
                            verts=verts_np,
                            lbs_weights=lbs_weights_np,
                            joints_xyz=joints_np,
                            joint_ids=SMPLX_JOINT_IDS,
                            cfg=sw_cfg,  # Use frozen policy config
                            return_debug=False,
                        )
                        pred_width_t = torch.tensor(pred_width, dtype=torch.float32, device=self.device)
                        target_width_t = torch.tensor(target_shoulder_width_m, dtype=torch.float32, device=self.device)
                        loss_meas_val = self.policy.weight_measurement * (pred_width_t - target_width_t) ** 2
                        loss_meas_val = loss_meas_val.item()
                    except Exception:
                        loss_meas_val = None
            
            trace.append({
                "iter": iter_idx + 1,
                "loss_total": loss_val,
                "loss_meas": loss_meas_val if loss_meas_val is not None else 0.0,
                "loss_anchor": loss_anchor_val,
                "loss_beta_mag": loss_beta_mag_val,
                "dt_ms": iter_time_ms,
            })
            
            n_iter = iter_idx + 1
            
            # Early stopping
            if loss_improvement < self.policy.tol_loss and beta_change < self.policy.tol_beta:
                break
            
            prev_loss = loss_val
            prev_beta = beta_init_t.detach().clone()
        
        # Final prediction and sanity checks
        with torch.no_grad():
            out_final = self.pose_normalizer.run_forward(
                model,
                beta_init_t.unsqueeze(0),
                {},
                enforce_policy_apose=True,
            )
            
            # Apply scale ONCE to vertices and joints
            verts_scaled = out_final.vertices[0] * scale_t
            verts_np = verts_scaled.detach().cpu().numpy()
            lbs_weights_np = model.lbs_weights.detach().cpu().numpy()
            joints_full = out_final.joints
            num_joints_weights = lbs_weights_np.shape[1]
            
            # Use first 55 joints, apply scale ONCE
            joints_scaled = joints_full[0, :num_joints_weights, :] * scale_t
            joints_np = joints_scaled.detach().cpu().numpy()
            
            # Sanity checks
            # 1. Height prediction (scale applied)
            y_coords = verts_np[:, 1]
            height_pred_m = float(np.nanmax(y_coords) - np.nanmin(y_coords))
            
            # 2. Joint-based shoulder width (scale applied)
            L_shoulder_idx = SMPLX_JOINT_IDS["L_shoulder"]
            R_shoulder_idx = SMPLX_JOINT_IDS["R_shoulder"]
            L_shoulder_pos = joints_np[L_shoulder_idx, :]
            R_shoulder_pos = joints_np[R_shoulder_idx, :]
            joint_sw_m = float(np.linalg.norm(L_shoulder_pos - R_shoulder_pos))
            
            # 3. Measured shoulder width
            pred_shoulder_width = None
            if target_shoulder_width_m is not None:
                try:
                    # Use frozen policy config
                    sw_cfg = get_shoulder_width_cfg()
                    pred_shoulder_width = measure_shoulder_width_v112(
                        verts=verts_np,
                        lbs_weights=lbs_weights_np,
                        joints_xyz=joints_np,
                        joint_ids=SMPLX_JOINT_IDS,
                        cfg=sw_cfg,  # Use frozen policy config
                        return_debug=False,
                    )
                except Exception:
                    pass
        
        return {
            "scale": float(scale),
            "betas": beta_init_t.detach().cpu().numpy().astype(np.float32),
            "beta_init": beta_init.astype(np.float32),
            "predicted_shoulder_width_m": float(pred_shoulder_width) if pred_shoulder_width is not None else None,
            "loss_total": float(loss_val) if n_iter > 0 else None,
            "loss_measurement": None if measurement_failed else (float(loss_meas_val) if loss_meas_val is not None else None),
            "loss_anchor": float(loss_anchor_val) if n_iter > 0 else None,
            "loss_beta_mag": float(loss_beta_mag_val) if n_iter > 0 else None,
            "n_iter": n_iter,
            "trace": trace,
            "status": "MEAS_FAILED" if measurement_failed else "SUCCESS",
            "fail_reason": fail_reason,
            # Sanity checks
            "height_pred_m": height_pred_m,
            "joint_sw_m": joint_sw_m,
            "measured_sw_m": float(pred_shoulder_width) if pred_shoulder_width is not None else None,
        }
