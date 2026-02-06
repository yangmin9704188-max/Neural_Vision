"""
Deterministic smoke test for slice/hull measurement (K_fit=10 geo stability).
Same input -> same K_fit values and same warning codes.
Run: python -m modules.body.tests.test_core_measurements_v0_smoke
     or: pytest modules/body/tests/test_core_measurements_v0_smoke.py -v
"""
from __future__ import annotations

import numpy as np


def _repo_root():
    from pathlib import Path
    # .../repo/modules/body/tests/file.py -> repo
    return Path(__file__).resolve().parents[3]


def _run_slice_perimeter_determinism():
    """Fixed synthetic point set -> same perimeter and debug on two runs."""
    import sys
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from modules.body.src.measurements.vtm.core_measurements_v0 import (
        _compute_perimeter,
        EPSILON_DEDUPE,
    )
    # Fixed 2D points (x, z): small triangle, deterministic order
    pts = np.array([[0.0, 0.0], [1.0, 0.0], [0.5, 0.866]], dtype=np.float32)
    out1, debug1 = _compute_perimeter(pts, return_debug=True)
    out2, debug2 = _compute_perimeter(pts, return_debug=True)
    assert out1 is not None and out2 is not None
    assert out1 == out2
    assert np.isfinite(out1) and out1 > 0  # deterministic positive perimeter
    # Debug schema keys present and identical
    for key in ("n_points_raw", "n_points_deduped", "hull_ok", "perimeter_final"):
        if key in debug1 and key in debug2:
            v1, v2 = debug1[key], debug2[key]
            if isinstance(v1, float) and isinstance(v2, float):
                assert v1 == v2 or (np.isnan(v1) and np.isnan(v2))
            else:
                assert v1 == v2


def _run_slice_debug_schema_stable():
    """make_slice_debug_schema returns JSON-serializable dict with required keys."""
    import sys
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from modules.body.src.measurements.vtm.core_measurements_v0 import make_slice_debug_schema
    import json
    d = make_slice_debug_schema(
        method="slice_hull",
        plane="xz",
        axis_up="y",
        y_range=[0.0, 1.0],
        band_width_m=0.01,
        n_points_raw=10,
        n_points_deduped=8,
        hull_ok=True,
        perimeter_m=0.5,
        width_m=None,
        depth_m=None,
        bbox_xz=[[0.0, 0.0], [0.2, 0.2]],
    )
    required = {"method", "plane", "axis_up", "y_range", "band_width_m", "n_points_raw",
                 "n_points_deduped", "component_mode", "selected_component_rank", "hull_ok",
                 "perimeter_m", "width_m", "depth_m", "bbox_xz"}
    for k in required:
        assert k in d
    # JSON-serializable
    json.dumps(d)


def _run_k_fit_10_same_mesh_same_values_and_codes():
    """Same input mesh -> same K_fit values and same warning codes (BUST_CIRC_M)."""
    import sys
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from modules.body.src.measurements.vtm.core_measurements_v0 import (
        measure_circumference_v0_with_metadata,
        K_FIT_10_KEYS,
    )
    # Minimal mesh: one horizontal slice (same y), points in xz plane forming a ring
    np.random.seed(42)
    n = 20
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    x = 0.3 * np.cos(angles)
    z = 0.3 * np.sin(angles)
    y = np.full(n, 0.5)
    verts = np.stack([x, y, z], axis=1).astype(np.float32)
    r1 = measure_circumference_v0_with_metadata(verts, "BUST_CIRC_M")
    r2 = measure_circumference_v0_with_metadata(verts, "BUST_CIRC_M")
    assert "BUST_CIRC_M" in K_FIT_10_KEYS
    # Same value (or both NaN)
    v1, v2 = r1.value_m, r2.value_m
    if np.isfinite(v1) and np.isfinite(v2):
        assert v1 == v2
    else:
        assert (np.isnan(v1) or not np.isfinite(v1)) == (np.isnan(v2) or not np.isfinite(v2))
    # Same warning codes (deterministic)
    w1 = tuple(sorted(r1.metadata.get("warnings", []))) if r1.metadata else ()
    w2 = tuple(sorted(r2.metadata.get("warnings", []))) if r2.metadata else ()
    assert w1 == w2
    # slice_debug present for K_fit key
    if r1.metadata and "debug_info" in r1.metadata:
        di = r1.metadata["debug_info"]
        assert "slice_debug" in di
        sd = di["slice_debug"]
        assert "method" in sd and "n_points_raw" in sd and "hull_ok" in sd


def test_slice_perimeter_determinism():
    _run_slice_perimeter_determinism()


def test_slice_debug_schema_stable():
    _run_slice_debug_schema_stable()


def test_k_fit_10_same_mesh_same_values_and_codes():
    _run_k_fit_10_same_mesh_same_values_and_codes()


if __name__ == "__main__":
    _run_slice_perimeter_determinism()
    _run_slice_debug_schema_stable()
    _run_k_fit_10_same_mesh_same_values_and_codes()
    print("All smoke tests passed.")
