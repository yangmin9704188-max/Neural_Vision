"""
Purpose: Pose normalization policy (A-Pose for measurements).
Inputs: shape(betas), device
Outputs: normalized pose tensors
Status: active
"""
import torch

class PoseNormalizer:
    """
    Pose Normalization Policy (FROZEN)

    목적:
      - 모든 측정 전, 입력 shape(betas)에 대해 동일한 A-Pose를 강제한다.
      - 배치(B>1)에서도 동일 정책으로 동작한다.
      - dtype/device 정책을 강제한다 (no float64).

    변경 원칙:
      - 아래 APPOSE_* 상수는 "정책"이며, 변경 시 step2_verify_pose.py 회귀 테스트를 반드시 통과해야 한다.
    """

    # -------------------------
    # Core constants
    # -------------------------
    NUM_JOINTS = 21
    NUM_BODY_POSE = 63
    ALLOWED_DTYPES = (torch.float32, torch.float16, torch.bfloat16)

    # =========================
    # 🔒 FROZEN A-POSE POLICY
    # =========================
    APPOSE_ANGLE_DEG = 30.0
    APPOSE_AXIS = 'y'
    APPOSE_L_IDX = 16
    APPOSE_R_IDX = 17
    APPOSE_SIGN_L = +1.0
    APPOSE_SIGN_R = -1.0

    def __init__(self, device='cpu'):
        self.default_device = self._safe_device(device)

    # -------------------------
    # Guards
    # -------------------------
    def _safe_device(self, device):
        try:
            return torch.device(device)
        except Exception as e:
            raise TypeError(f"Invalid device '{device}': {str(e)}")

    def _validate_dtype(self, dtype):
        if dtype not in self.ALLOWED_DTYPES:
            raise TypeError(f"dtype {dtype} not allowed. Allowed: {self.ALLOWED_DTYPES}")

    # -------------------------
    # Public API: policy A-pose
    # -------------------------
    def get_policy_a_pose(self, batch_size, device=None, dtype=None):
        """
        ✅ 프로덕션에서 사용할 유일한 A-Pose 생성 API
        - 외부에서 axis/sign/joint를 바꾸지 못하도록 정책을 봉인한다.
        """
        if batch_size <= 0:
            raise ValueError("Batch size must be > 0")

        target_device = self._safe_device(device) if device is not None else self.default_device
        target_dtype = dtype if dtype is not None else torch.float32
        self._validate_dtype(target_dtype)

        return self._build_a_pose(
            batch_size=batch_size,
            angle_deg=self.APPOSE_ANGLE_DEG,
            axis=self.APPOSE_AXIS,
            device=target_device,
            dtype=target_dtype,
            l_idx=self.APPOSE_L_IDX,
            r_idx=self.APPOSE_R_IDX,
            sign_l=self.APPOSE_SIGN_L,
            sign_r=self.APPOSE_SIGN_R,
        )

    # -------------------------
    # Internal builder (kept minimal)
    # -------------------------
    def _build_a_pose(self, batch_size, angle_deg, axis, device, dtype, l_idx, r_idx, sign_l, sign_r):
        # strict validation
        if axis not in ('x', 'y', 'z'):
            raise ValueError("axis must be x/y/z")
        if sign_l not in (-1.0, 1.0) or sign_r not in (-1.0, 1.0):
            raise ValueError("sign_l/sign_r must be ±1")
        if not (0 <= l_idx < self.NUM_JOINTS) or not (0 <= r_idx < self.NUM_JOINTS):
            raise ValueError("Index out of bounds (0-20)")
        angle = float(angle_deg)
        if not (0.0 <= angle <= 90.0):
            raise ValueError("angle_deg must be 0~90")

        body_pose = torch.zeros((batch_size, self.NUM_BODY_POSE), device=device, dtype=dtype)
        angle_rad = torch.tensor(angle, device=device, dtype=dtype) * (torch.pi / 180.0)
        offset = {'x': 0, 'y': 1, 'z': 2}[axis]

        body_pose[:, l_idx * 3 + offset] = sign_l * angle_rad
        body_pose[:, r_idx * 3 + offset] = sign_r * angle_rad
        return body_pose

    # -------------------------
    # Batch-safe forward wrapper
    # -------------------------
    def run_forward(self, model, betas, pose_params=None, enforce_policy_apose=True):
        """
        안전한 Forward Wrapper

        - enforce_policy_apose=True:
            pose_params에 body_pose가 없으면 정책 A-Pose를 자동 삽입 (권장)
        - 배치 확장 허용:
            (D,), (1,D) -> (B,D) 로 확장
        - SMPL-X 내부 default(batch=1) 생성 방지:
            transl/expression/hand/face 등을 항상 (B,*)로 명시 전달
        """
        if not torch.is_tensor(betas):
            raise TypeError("betas must be a torch.Tensor")
        if betas.ndim != 2:
            raise ValueError(f"betas must be (B, num_betas), got {betas.shape}")
        if betas.dtype not in self.ALLOWED_DTYPES:
            raise TypeError(f"Betas dtype {betas.dtype} not allowed. Allowed: {self.ALLOWED_DTYPES}")

        B = betas.shape[0]
        device = betas.device
        dtype = betas.dtype
        pose_params = pose_params or {}

        def _to_tensor(val):
            if torch.is_tensor(val):
                return val.to(device=device, dtype=dtype)
            return torch.as_tensor(val, device=device, dtype=dtype)

        def prep(key, shape):
            """
            shape=(B,D)
            허용:
              - (B,D)
              - (1,D) -> expand
              - (D,)  -> (1,D) -> expand
            """
            val = pose_params.get(key, None)
            if val is None:
                return torch.zeros(shape, device=device, dtype=dtype)

            val = _to_tensor(val)

            if val.ndim == 1:
                if val.shape[0] != shape[1]:
                    raise ValueError(f"{key} shape mismatch: {val.shape} vs ({shape[1]},)")
                return val.view(1, shape[1]).expand(*shape)

            if val.ndim == 2:
                if val.shape == shape:
                    return val
                if val.shape == (1, shape[1]):
                    return val.expand(*shape)
                raise ValueError(f"{key} shape mismatch: {val.shape} vs {shape}")

            raise ValueError(f"{key} invalid ndim: {val.ndim}, expected 1 or 2")

        # body_pose: 정책 강제
        if enforce_policy_apose and ('body_pose' not in pose_params or pose_params.get('body_pose') is None):
            body_pose = self.get_policy_a_pose(B, device=device, dtype=dtype)
        else:
            body_pose = prep('body_pose', (B, self.NUM_BODY_POSE))

        global_orient = prep('global_orient', (B, 3))
        transl = prep('transl', (B, 3))

        extra = {}
        # SMPL-X 감지(특징 기반)
        is_smplx = hasattr(model, 'num_expression_coeffs')

        if is_smplx:
            extra['jaw_pose'] = prep('jaw_pose', (B, 3))
            extra['leye_pose'] = prep('leye_pose', (B, 3))
            extra['reye_pose'] = prep('reye_pose', (B, 3))

            expr_dim = int(getattr(model, 'num_expression_coeffs', 10))
            extra['expression'] = prep('expression', (B, expr_dim))

            # use_pca=False 가정 시 45, PCA면 comps
            use_pca = bool(getattr(model, 'use_pca', False))
            hand_dim = int(getattr(model, 'num_pca_comps', 6)) if use_pca else 45

            extra['left_hand_pose'] = prep('left_hand_pose', (B, hand_dim))
            extra['right_hand_pose'] = prep('right_hand_pose', (B, hand_dim))

        return model(
            betas=betas,
            body_pose=body_pose,
            global_orient=global_orient,
            transl=transl,
            **extra
        )
