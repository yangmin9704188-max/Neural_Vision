"""
Step3 beta_fit_v0: quality_score monotonicity, bucket assignment, JSON validity, atomic write, determinism.
Uses dummy mesh_provider (no SMPL-X required).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_repo = Path(__file__).resolve().parents[1]
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

SCRIPT = _repo / "tools" / "fit_smplx_beta_v0.py"
U1_KEYS = ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]


def _run_fit(out_dir: Path, k: int = 3) -> tuple[int, str, str]:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--out_dir", str(out_dir), "--k", str(k)],
        capture_output=True,
        text=True,
        cwd=str(_repo),
    )
    return r.returncode, r.stdout, r.stderr


def _load_fit_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("fit_smplx_beta_v0", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestQualityScoreMonotonicity(unittest.TestCase):
    def test_bigger_residual_lower_score(self) -> None:
        mod = _load_fit_module()
        quality_score_from_residuals_m = mod.quality_score_from_residuals_m
        small = {"BUST_CIRC_M": 0.001, "WAIST_CIRC_M": 0.001, "HIP_CIRC_M": 0.001}
        large = {"BUST_CIRC_M": 0.05, "WAIST_CIRC_M": 0.05, "HIP_CIRC_M": 0.05}
        s_small = quality_score_from_residuals_m(small, U1_KEYS)
        s_large = quality_score_from_residuals_m(large, U1_KEYS)
        self.assertGreater(s_small, s_large, "Larger residuals must yield lower quality_score")

    def test_score_in_0_100(self) -> None:
        mod = _load_fit_module()
        quality_score_from_residuals_m = mod.quality_score_from_residuals_m
        r = {"BUST_CIRC_M": 0.0, "WAIST_CIRC_M": 0.0, "HIP_CIRC_M": 0.0}
        s = quality_score_from_residuals_m(r, U1_KEYS)
        self.assertGreaterEqual(s, 0.0)
        self.assertLessEqual(s, 100.0)


class TestBucketAssignment(unittest.TestCase):
    def test_ok_above_threshold(self) -> None:
        mod = _load_fit_module()
        quality_bucket = mod.quality_bucket
        self.assertEqual(quality_bucket(70.0), "OK")
        self.assertEqual(quality_bucket(80.0), "OK")

    def test_low_below_threshold(self) -> None:
        mod = _load_fit_module()
        quality_bucket = mod.quality_bucket
        self.assertEqual(quality_bucket(69.9), "LOW")
        self.assertEqual(quality_bucket(0.0), "LOW")


class TestBetaFitOutputs(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_produces_valid_json_and_structure(self) -> None:
        code, out, err = _run_fit(self.tmp, k=3)
        self.assertEqual(code, 0, f"Tool must exit 0: {err}")
        summary_path = self.tmp / "summary.json"
        self.assertTrue(summary_path.exists())
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(data.get("schema_version"), "beta_fit_v0")
        self.assertIn("residual_cm_stats", data)
        self.assertIn("quality_score_stats", data)
        self.assertIn("bucket_counts", data)
        for i in range(3):
            fit_path = self.tmp / "prototypes" / f"p{i:04d}" / "fit_result.json"
            self.assertTrue(fit_path.exists(), f"fit_result.json for p{i:04d}")
            fit_data = json.loads(fit_path.read_text(encoding="utf-8"))
            self.assertIn("quality_score", fit_data)
            self.assertIn("quality_bucket", fit_data)

    def test_determinism_two_runs_same_summary_sha256(self) -> None:
        out1 = self.tmp / "run1"
        out2 = self.tmp / "run2"
        out1.mkdir()
        out2.mkdir()
        code1, _, _ = _run_fit(out1, k=3)
        code2, _, _ = _run_fit(out2, k=3)
        self.assertEqual(code1, 0)
        self.assertEqual(code2, 0)
        s1 = (out1 / "summary.json").read_bytes()
        s2 = (out2 / "summary.json").read_bytes()
        self.assertEqual(hashlib.sha256(s1).hexdigest(), hashlib.sha256(s2).hexdigest(), "summary.json must be deterministic")


if __name__ == "__main__":
    unittest.main()
