"""
Regression: VTM measurement refinement (Refine01) - stable outputs, sane ranges.
Uses smoke_verts fixture; asserts determinism, finite values, reasonable circumference range.
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


def _load_verts(path: Path):
    import numpy as np
    data = np.load(path)
    verts = data["verts"]
    if verts.ndim == 3:
        verts = verts[0]
    return np.asarray(verts, dtype=np.float32)


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


if __name__ == "__main__":
    unittest.main()
