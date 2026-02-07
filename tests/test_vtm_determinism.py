"""
VTM determinism: identical mesh input => identical BUST/WAIST/HIP outputs.
Uses fixed mesh fixture; runs measurement twice and compares values (exact or tiny epsilon).
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
EPS = 1e-9


def _load_verts(path: Path):
    import numpy as np
    data = np.load(path)
    verts = data["verts"]
    if verts.ndim == 3:
        verts = verts[0]
    return np.asarray(verts, dtype=np.float32)


def _measure_u1(verts) -> dict[str, float | None]:
    from modules.body.src.measurements.vtm.core_measurements_v0 import measure_circumference_v0_with_metadata
    out = {}
    for key in U1_KEYS:
        res = measure_circumference_v0_with_metadata(verts, key)
        v = getattr(res, "value_m", None)
        if v is not None and (math.isnan(v) or math.isinf(v)):
            out[key] = None
        else:
            out[key] = v
    return out


class TestVTMDeterminism(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(VTM_MESH_FIXTURE.exists(), f"Mesh fixture missing: {VTM_MESH_FIXTURE}")

    def test_bust_waist_hip_same_process_twice(self) -> None:
        """Run BUST/WAIST/HIP measurement twice in same process; values must match (or both null)."""
        verts = _load_verts(VTM_MESH_FIXTURE)
        run1 = _measure_u1(verts)
        run2 = _measure_u1(verts)
        for key in U1_KEYS:
            v1, v2 = run1[key], run2[key]
            if v1 is None and v2 is None:
                continue
            self.assertIsNotNone(v1, f"{key} run1 should be value or null")
            self.assertIsNotNone(v2, f"{key} run2 should be value or null")
            self.assertAlmostEqual(v1, v2, delta=EPS, msg=f"{key} must be deterministic")

    def test_bust_waist_hip_fixture_produces_values_or_null(self) -> None:
        """Fixed mesh fixture produces value or null for each U1 key (facts-only; no throw)."""
        verts = _load_verts(VTM_MESH_FIXTURE)
        out = _measure_u1(verts)
        for key in U1_KEYS:
            self.assertIn(key, out)
            self.assertTrue(out[key] is None or (isinstance(out[key], (int, float)) and math.isfinite(out[key])),
                            f"{key} must be null or finite number")


if __name__ == "__main__":
    unittest.main()
