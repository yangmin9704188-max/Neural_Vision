"""Regression: Step2 centroid generator must be deterministic (double-run hash match)."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import sys
_repo = Path(__file__).resolve().parents[1]
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))


class TestGenerate384CentroidsDeterminism(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_double_run_same_output_hash(self) -> None:
        """Run tool twice on same input; centroids.json must be identical (same hash)."""
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas required for centroid determinism test")
        parquet_path = self.tmp / "curated.parquet"
        # Minimal curated: subject_id + U1 keys (small n, k=2 for speed)
        df = pd.DataFrame({
            "subject_id": [f"s{i:04d}" for i in range(20)],
            "BUST_CIRC_M": [0.8 + i * 0.01 for i in range(20)],
            "WAIST_CIRC_M": [0.7 + i * 0.01 for i in range(20)],
            "HIP_CIRC_M": [0.9 + i * 0.01 for i in range(20)],
        })
        df.to_parquet(parquet_path, index=False)

        out1 = self.tmp / "run1"
        out2 = self.tmp / "run2"
        out1.mkdir()
        out2.mkdir()

        import subprocess
        script = _repo / "tools" / "generate_384_centroids_v0.py"
        def run(out_dir: Path) -> subprocess.CompletedProcess:
            return subprocess.run(
                [sys.executable, str(script), "--curated_parquet", str(parquet_path),
                 "--out_dir", str(out_dir), "--seed", "42", "--k", "2", "--id_col", "subject_id"],
                capture_output=True, text=True, cwd=str(_repo),
            )
        r1 = run(out1)
        self.assertEqual(r1.returncode, 0, f"first run failed: {r1.stderr}")

        r2 = run(out2)
        self.assertEqual(r2.returncode, 0, f"second run failed: {r2.stderr}")

        c1 = out1 / "centroids.json"
        c2 = out2 / "centroids.json"
        self.assertTrue(c1.exists())
        self.assertTrue(c2.exists())
        h1 = hashlib.sha256(c1.read_bytes()).hexdigest()
        h2 = hashlib.sha256(c2.read_bytes()).hexdigest()
        self.assertEqual(h1, h2, "centroids.json must be identical across two runs (determinism)")


if __name__ == "__main__":
    unittest.main()
