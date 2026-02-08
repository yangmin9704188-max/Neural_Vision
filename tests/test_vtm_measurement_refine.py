"""
Regression: VTM measurement refinement (Refine01/02) - stable outputs, sane ranges.
Uses smoke_verts fixture; asserts determinism, finite values, reasonable circumference range.
Refine02: HIP band sweep experiment (deterministic).
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

_repo = Path(__file__).resolve().parents[1]
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

VTM_MESH_FIXTURE = _repo / "tests" / "fixtures" / "vtm_mesh" / "smoke_verts.npz"
U1_KEYS = ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]
# Sane range for human torso circumferences (meters): 0.4 - 2.5
CIRC_MIN_M = 0.4
CIRC_MAX_M = 2.5

# Refine02: HIP band configs (match core_measurements_v0)
HIP_BAND_CONFIG_IDS = ["A", "B", "C", "D", "E", "B_high"]


def _load_verts(path: Path):
    import numpy as np
    data = np.load(path)
    verts = data["verts"]
    if verts.ndim == 3:
        verts = verts[0]
    return np.asarray(verts, dtype=np.float32)


def _make_mesh_fixture_set(seed_verts, count: int = 3):
    """Refine02: Create >=3 mesh variants (deterministic scales) for sweep experiment."""
    import numpy as np
    verts = np.asarray(seed_verts, dtype=np.float32)
    if verts.ndim == 3:
        verts = verts[0]
    centroid = np.mean(verts, axis=0)
    scales = [1.0, 1.01, 0.99][:count]
    return [(verts - centroid) * s + centroid for s in scales]


def _measure_u1_with_metadata(verts) -> dict[str, tuple[float | None, list]]:
    from modules.body.src.measurements.vtm.core_measurements_v0 import measure_circumference_v0_with_metadata
    out = {}
    for key in U1_KEYS:
        res = measure_circumference_v0_with_metadata(verts, key)
        v = getattr(res, "value_m", None)
        warnings = (res.metadata or {}).get("warnings", []) if hasattr(res, "metadata") else []
        if v is not None and (math.isnan(v) or math.isinf(v)):
            out[key] = (None, warnings)
        else:
            out[key] = (v, warnings)
    return out


class TestVTMMeasurementRefine(unittest.TestCase):
    """Refine01: stable outputs, sane ranges, no regression."""

    def setUp(self) -> None:
        self.assertTrue(VTM_MESH_FIXTURE.exists(), f"Mesh fixture missing: {VTM_MESH_FIXTURE}")

    def test_refine01_determinism_unchanged(self) -> None:
        """Determinism: run twice, values must match."""
        verts = _load_verts(VTM_MESH_FIXTURE)
        run1 = _measure_u1_with_metadata(verts)
        run2 = _measure_u1_with_metadata(verts)
        for key in U1_KEYS:
            v1, _ = run1[key]
            v2, _ = run2[key]
            if v1 is None and v2 is None:
                continue
            self.assertIsNotNone(v1, f"{key} run1 should be value or null")
            self.assertIsNotNone(v2, f"{key} run2 should be value or null")
            self.assertAlmostEqual(v1, v2, delta=1e-9, msg=f"{key} must be deterministic")

    def test_refine01_values_finite_or_null(self) -> None:
        """Each U1 key must produce finite value or null (no NaN/Inf without null)."""
        verts = _load_verts(VTM_MESH_FIXTURE)
        out = _measure_u1_with_metadata(verts)
        for key in U1_KEYS:
            v, _ = out[key]
            self.assertIn(key, out)
            self.assertTrue(
                v is None or (isinstance(v, (int, float)) and math.isfinite(v)),
                f"{key} must be null or finite number"
            )

    def test_refine01_circumferences_in_sane_range(self) -> None:
        """If value present, circumference must be in reasonable range (0.4m - 2.5m)."""
        verts = _load_verts(VTM_MESH_FIXTURE)
        out = _measure_u1_with_metadata(verts)
        for key in U1_KEYS:
            v, _ = out[key]
            if v is not None:
                self.assertGreaterEqual(v, CIRC_MIN_M, f"{key}={v} below sane min")
                self.assertLessEqual(v, CIRC_MAX_M, f"{key}={v} above sane max")


class TestHIPBandSweep(unittest.TestCase):
    """Refine02: HIP band sweep experiment - determinism, stability, sane range."""

    def setUp(self) -> None:
        self.assertTrue(VTM_MESH_FIXTURE.exists(), f"Mesh fixture missing: {VTM_MESH_FIXTURE}")

    def test_hip_sweep_all_configs_deterministic(self) -> None:
        """For each band config, HIP circumference is deterministic across 2 runs."""
        from modules.body.src.measurements.vtm.core_measurements_v0 import (
            HIP_BAND_CONFIGS,
            _hip_circumference_sweep_evaluate,
        )
        verts = _load_verts(VTM_MESH_FIXTURE)
        for cfg_id, cfg in HIP_BAND_CONFIGS.items():
            v1, _ = _hip_circumference_sweep_evaluate(
                verts, cfg["y_start"], cfg["y_end"], cfg["tie_prefer_lower_y"]
            )
            v2, _ = _hip_circumference_sweep_evaluate(
                verts, cfg["y_start"], cfg["y_end"], cfg["tie_prefer_lower_y"]
            )
            self.assertFalse(
                v1 is not None and (math.isnan(v1) or math.isinf(v1)),
                f"{cfg_id}: HIP must not be NaN/Inf"
            )
            if v1 is not None:
                self.assertAlmostEqual(v1, v2, delta=1e-9, msg=f"{cfg_id} must be deterministic")

    def test_hip_sweep_fixture_set_stable(self) -> None:
        """HIP sweep on >=3 mesh variants: all finite, sane range, no NaN/Inf."""
        from modules.body.src.measurements.vtm.core_measurements_v0 import (
            HIP_BAND_CONFIGS,
            _hip_circumference_sweep_evaluate,
        )
        base = _load_verts(VTM_MESH_FIXTURE)
        meshes = _make_mesh_fixture_set(base, count=3)
        for cfg_id, cfg in HIP_BAND_CONFIGS.items():
            for i, verts in enumerate(meshes):
                v, warnings = _hip_circumference_sweep_evaluate(
                    verts, cfg["y_start"], cfg["y_end"], cfg["tie_prefer_lower_y"]
                )
                self.assertIsNotNone(v, f"{cfg_id} mesh{i}: must return value or null")
                if v is not None:
                    self.assertFalse(math.isnan(v) or math.isinf(v), f"{cfg_id} mesh{i}: no NaN/Inf")
                    self.assertGreaterEqual(v, CIRC_MIN_M, f"{cfg_id} mesh{i}={v} below min")
                    self.assertLessEqual(v, CIRC_MAX_M, f"{cfg_id} mesh{i}={v} above max")

    def test_hip_sweep_overrides_main_path(self) -> None:
        """When override set, main HIP path uses sweep config; clear restores default."""
        from modules.body.src.measurements.vtm.core_measurements_v0 import (
            measure_circumference_v0_with_metadata,
            set_hip_band_override,
            clear_hip_band_override,
        )
        verts = _load_verts(VTM_MESH_FIXTURE)
        res_default = measure_circumference_v0_with_metadata(verts, "HIP_CIRC_M")
        v_default = getattr(res_default, "value_m", None)
        set_hip_band_override("D")
        res_d = measure_circumference_v0_with_metadata(verts, "HIP_CIRC_M")
        v_d = getattr(res_d, "value_m", None)
        clear_hip_band_override()
        res_restored = measure_circumference_v0_with_metadata(verts, "HIP_CIRC_M")
        v_restored = getattr(res_restored, "value_m", None)
        self.assertAlmostEqual(v_default, v_restored, delta=1e-9, msg="clear must restore default")
        if v_default is not None and v_d is not None:
            self.assertGreater(abs(v_default - v_d), 1e-6, "config D must differ from default B")


if __name__ == "__main__":
    unittest.main()
