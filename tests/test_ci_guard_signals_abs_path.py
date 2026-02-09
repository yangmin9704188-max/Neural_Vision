"""Tests for ops/signals absolute path guardrails in ci_guard."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.ci.ci_guard import FAIL, check_signals_no_abs_windows_paths


class TestCiGuardSignalsAbsPath(unittest.TestCase):
    def test_windows_absolute_path_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rel = "ops/signals/m1/body/LATEST.json"
            file_path = root / rel
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(
                json.dumps(
                    {
                        "schema_version": "m1_signal.v1",
                        "module": "body",
                        "m_level": "M1",
                        "run_id": "run1",
                        "run_dir_rel": "data/shared_m1/body/run1",
                        "notes": r"C:\\Users\\someone\\Desktop\\run1",
                    }
                ),
                encoding="utf-8",
            )

            results = check_signals_no_abs_windows_paths(root, [rel])
            self.assertTrue(any(r.severity == FAIL for r in results))

    def test_run_dir_rel_colon_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rel = "ops/signals/m1/garment/LATEST.json"
            file_path = root / rel
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(
                json.dumps(
                    {
                        "schema_version": "m1_signal.v1",
                        "module": "garment",
                        "m_level": "M1",
                        "run_id": "run2",
                        "run_dir_rel": "data/shared_m1/garment:run2",
                    }
                ),
                encoding="utf-8",
            )

            results = check_signals_no_abs_windows_paths(root, [rel])
            self.assertTrue(any(r.severity == FAIL for r in results))


if __name__ == "__main__":
    unittest.main()
