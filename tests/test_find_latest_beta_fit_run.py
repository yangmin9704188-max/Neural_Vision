"""Regression: latest beta_fit_v0 run discovery picks by run_id timestamp then mtime."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys
_repo = Path(__file__).resolve().parents[1]
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))


class TestFindLatestBetaFitRun(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_latest_by_run_id_timestamp(self) -> None:
        """Two run dirs with run_YYYYMMDD_HHMMSS; discover picks the newer timestamp."""
        base = self.tmp / "exports" / "runs" / "facts" / "beta_fit_v0"
        run_older = base / "run_20260207_162505"
        run_newer = base / "run_20260207_162506"
        run_older.mkdir(parents=True)
        run_newer.mkdir(parents=True)
        summary = {"schema_version": "beta_fit_v0", "k": 1}
        (run_older / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (run_newer / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

        from tools.ops.find_latest_beta_fit_run import find_latest_beta_fit_run
        result = find_latest_beta_fit_run(self.tmp)
        self.assertIsNotNone(result)
        self.assertEqual(result, run_newer, "latest must be run_20260207_162506 (newer timestamp)")

    def test_excludes_verification(self) -> None:
        """Paths under verification/ are excluded."""
        base = self.tmp / "exports" / "runs"
        (base / "facts" / "beta_fit_v0" / "run_20260207_162505").mkdir(parents=True)
        (base / "verification" / "beta_fit_v0" / "run_20260207_162506").mkdir(parents=True)
        summary = {"schema_version": "beta_fit_v0"}
        (base / "facts" / "beta_fit_v0" / "run_20260207_162505" / "summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        (base / "verification" / "beta_fit_v0" / "run_20260207_162506" / "summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )

        from tools.ops.find_latest_beta_fit_run import find_latest_beta_fit_run
        result = find_latest_beta_fit_run(self.tmp)
        self.assertIsNotNone(result)
        self.assertIn("facts", str(result))
        self.assertNotIn("verification", str(result))

    def test_none_when_no_runs(self) -> None:
        """Returns None when exports/runs has no beta_fit_v0 summary.json."""
        (self.tmp / "exports" / "runs").mkdir(parents=True)
        from tools.ops.find_latest_beta_fit_run import find_latest_beta_fit_run
        result = find_latest_beta_fit_run(self.tmp)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
