"""Regression: B2 unlock recommendations mode must be deterministic; backward-compat without --recommend_thresholds."""
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


class TestUnlockSignalB2RecommendationsDeterminism(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.fixture_run = _repo / "tests" / "fixtures" / "beta_fit_summary"
        self.summary_path = self.fixture_run / "summary.json"
        self.script = _repo / "tools" / "generate_unlock_signal_b2_v0.py"
        self.fixed_ts = "2026-02-07T12:00:00Z"

    def tearDown(self) -> None:
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_dir(self) -> Path:
        run_dir = self.tmp / "fake_run"
        run_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(self.summary_path, run_dir / "summary.json")
        return run_dir

    def test_recommendations_double_run_same_hash(self) -> None:
        """Run twice with --recommend_thresholds and fixed created_at; unlock_signal.json sha256 identical."""
        self.assertTrue(self.summary_path.exists(), f"Fixture missing: {self.summary_path}")
        run_dir = self._run_dir()
        out1 = self.tmp / "out1"
        out2 = self.tmp / "out2"
        out1.mkdir()
        out2.mkdir()

        def run_tool(out_dir: Path) -> __import__("subprocess").CompletedProcess:
            return __import__("subprocess").run(
                [
                    sys.executable, str(self.script),
                    "--run_dir", str(run_dir),
                    "--out_dir", str(out_dir),
                    "--threshold_score", "70",
                    "--threshold_residual_p90_cm", "1.0",
                    "--max_failures", "0",
                    "--created_at", self.fixed_ts,
                    "--recommend_thresholds",
                ],
                capture_output=True, text=True, cwd=str(_repo),
            )

        r1 = run_tool(out1)
        self.assertEqual(r1.returncode, 0, f"first run failed: {r1.stderr}")
        r2 = run_tool(out2)
        self.assertEqual(r2.returncode, 0, f"second run failed: {r2.stderr}")

        j1 = out1 / "unlock_signal.json"
        j2 = out2 / "unlock_signal.json"
        self.assertTrue(j1.exists())
        self.assertTrue(j2.exists())
        h1 = hashlib.sha256(j1.read_bytes()).hexdigest()
        h2 = hashlib.sha256(j2.read_bytes()).hexdigest()
        self.assertEqual(h1, h2, "unlock_signal.json must be identical (recommendations determinism)")

    def test_without_recommend_thresholds_no_recommendations_key(self) -> None:
        """Without --recommend_thresholds, output must not contain recommendations section (backward compat)."""
        self.assertTrue(self.summary_path.exists())
        run_dir = self._run_dir()
        out = self.tmp / "out"
        out.mkdir()
        r = __import__("subprocess").run(
            [
                sys.executable, str(self.script),
                "--run_dir", str(run_dir),
                "--out_dir", str(out),
                "--threshold_score", "70",
                "--threshold_residual_p90_cm", "1.0",
                "--max_failures", "0",
                "--created_at", self.fixed_ts,
            ],
            capture_output=True, text=True, cwd=str(_repo),
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        jpath = out / "unlock_signal.json"
        self.assertTrue(jpath.exists())
        data = json.loads(jpath.read_text(encoding="utf-8"))
        self.assertNotIn("recommendations", data, "recommendations must be absent when --recommend_thresholds not set")


if __name__ == "__main__":
    unittest.main()
