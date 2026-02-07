"""Regression: Step2 centroid generator must be deterministic (double-run hash + assignment summary match)."""
from __future__ import annotations

import hashlib
import json
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
        """Run tool twice on same input; centroids_v0.json must be identical (same hash and assignment_summary)."""
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas required for centroid determinism test")
        parquet_path = self.tmp / "curated.parquet"
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
                [
                    sys.executable, str(script),
                    "--curated_parquet", str(parquet_path),
                    "--out_dir", str(out_dir),
                    "--seed", "42", "--k", "2",
                    "--id_col", "subject_id",
                ],
                capture_output=True, text=True, cwd=str(_repo),
            )
        r1 = run(out1)
        self.assertEqual(r1.returncode, 0, f"first run failed: {r1.stderr}")

        r2 = run(out2)
        self.assertEqual(r2.returncode, 0, f"second run failed: {r2.stderr}")

        c1 = out1 / "centroids_v0.json"
        c2 = out2 / "centroids_v0.json"
        self.assertTrue(c1.exists(), "centroids_v0.json must exist")
        self.assertTrue(c2.exists(), "centroids_v0.json must exist")
        h1 = hashlib.sha256(c1.read_bytes()).hexdigest()
        h2 = hashlib.sha256(c2.read_bytes()).hexdigest()
        self.assertEqual(h1, h2, "centroids_v0.json must be identical across two runs (determinism)")

        d1 = json.loads(c1.read_text(encoding="utf-8"))
        d2 = json.loads(c2.read_text(encoding="utf-8"))
        self.assertEqual(d1.get("assignment_summary"), d2.get("assignment_summary"), "assignment_summary must match")


if __name__ == "__main__":
    unittest.main()
