"""Regression: B2 unlock signal generator must be deterministic (double-run sha256 identical)."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import sys
_repo = Path(__file__).resolve().parents[1]
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))


class TestUnlockSignalB2Determinism(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.fixture_run = _repo / "tests" / "fixtures" / "beta_fit_summary"
        self.summary_path = self.fixture_run / "summary.json"

    def tearDown(self) -> None:
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_double_run_same_output_hash(self) -> None:
        """Run generator twice on same input with fixed created_at; unlock_signal.json must be identical."""
        self.assertTrue(self.summary_path.exists(), f"Fixture missing: {self.summary_path}")

        out1 = self.tmp / "run1"
        out2 = self.tmp / "run2"
        out1.mkdir()
        out2.mkdir()
        run_dir = self.tmp / "fake_run"
        run_dir.mkdir()
        import shutil
        shutil.copy(self.summary_path, run_dir / "summary.json")

        script = _repo / "tools" / "generate_unlock_signal_b2_v0.py"
        fixed_ts = "2026-02-07T12:00:00Z"

        def run_tool(out_dir: Path) -> __import__("subprocess").CompletedProcess:
            return __import__("subprocess").run(
                [
                    sys.executable, str(script),
                    "--run_dir", str(run_dir),
                    "--out_dir", str(out_dir),
                    "--threshold_score", "70",
                    "--threshold_residual_p90_cm", "1.0",
                    "--max_failures", "0",
                    "--created_at", fixed_ts,
                ],
                capture_output=True, text=True, cwd=str(_repo),
            )

        r1 = run_tool(out1)
        self.assertEqual(r1.returncode, 0, f"first run failed: {r1.stderr}")

        r2 = run_tool(out2)
        self.assertEqual(r2.returncode, 0, f"second run failed: {r2.stderr}")

        j1 = out1 / "unlock_signal.json"
        j2 = out2 / "unlock_signal.json"
        self.assertTrue(j1.exists(), "unlock_signal.json must exist")
        self.assertTrue(j2.exists(), "unlock_signal.json must exist")
        h1 = hashlib.sha256(j1.read_bytes()).hexdigest()
        h2 = hashlib.sha256(j2.read_bytes()).hexdigest()
        self.assertEqual(h1, h2, "unlock_signal.json must be identical across two runs (determinism)")


if __name__ == "__main__":
    unittest.main()
