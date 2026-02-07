"""Regression test: body_measurements_subset.json atomic write and stub-on-failure."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Import helper from runner (project root must be on path)
import sys
from pathlib import Path as P

_repo = P(__file__).resolve().parents[1]
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from modules.body.src.runners.run_geo_v0_s1_facts import (
    U1_KEYS,
    _write_body_subset_atomic,
)
from tools.utils.atomic_io import atomic_save_json


def _assert_valid_json(path: Path) -> dict:
    """Load and return parsed JSON; assert valid."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


class TestBodySubsetAtomicWrite(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        import shutil
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_atomic_write_success(self) -> None:
        """Normal write: valid full JSON."""
        body_subset = {
            "unit": "m",
            "pose_id": "PZ1",
            "keys": U1_KEYS,
            "cases": [{"case_id": "c1", "BUST_CIRC_M": 0.88, "WAIST_CIRC_M": 0.70, "HIP_CIRC_M": 0.95}],
            "warnings": [],
        }
        ok = _write_body_subset_atomic(self.tmp_dir, body_subset)
        self.assertTrue(ok)
        final = self.tmp_dir / "body_measurements_subset.json"
        self.assertTrue(final.exists())
        data = _assert_valid_json(final)
        self.assertEqual(data["unit"], "m")
        self.assertEqual(data["pose_id"], "PZ1")
        self.assertEqual(len(data["cases"]), 1)
        self.assertEqual(data.get("schema_version"), "body_measurements_subset.u1.v0")

    def test_atomic_write_stub_on_serialization_failure(self) -> None:
        """Simulate serialization failure: final file must be valid JSON stub, never partial."""
        body_subset = {
            "unit": "m",
            "pose_id": "PZ1",
            "keys": U1_KEYS,
            "cases": [{"case_id": "c1", "BUST_CIRC_M": 0.88, "WAIST_CIRC_M": 0.70, "HIP_CIRC_M": 0.95}],
            "warnings": [],
        }
        real_dump = __import__("json").dump
        call_count = [0]

        def dump_effect(obj, fp, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise TypeError("Object of type MeasurementResult is not JSON serializable")
            return real_dump(obj, fp, **kwargs)

        with patch("tools.utils.atomic_io.json.dump", side_effect=dump_effect):
            ok = _write_body_subset_atomic(self.tmp_dir, body_subset)
        self.assertFalse(ok)
        final = self.tmp_dir / "body_measurements_subset.json"
        self.assertTrue(final.exists())
        data = _assert_valid_json(final)
        self.assertEqual(data.get("schema_version"), "body_measurements_subset.u1.v0")
        self.assertEqual(data.get("unit"), "m")
        self.assertEqual(data.get("pose_id"), "PZ1")
        self.assertEqual(data.get("keys"), U1_KEYS)
        self.assertEqual(data.get("cases"), [])
        self.assertIn("U1_SUBSET_WRITE_FAILED", data.get("warnings", []))
        self.assertNotIn("error", data)

        diag = self.tmp_dir / "artifacts" / "diagnostics" / "u1_subset_write_error.json"
        self.assertTrue(diag.exists(), "diagnostics file must exist on failure")
        diag_data = _assert_valid_json(diag)
        self.assertEqual(diag_data.get("error_type"), "TypeError")

    def test_atomic_write_no_partial_file_on_failure(self) -> None:
        """Ensure no partial/invalid JSON remains when serialization fails."""
        body_subset = {"unit": "m", "pose_id": "PZ1", "keys": U1_KEYS, "cases": [], "warnings": []}
        real_dump = __import__("json").dump
        call_count = [0]

        def dump_effect(obj, fp, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("simulated")
            return real_dump(obj, fp, **kwargs)

        with patch("tools.utils.atomic_io.json.dump", side_effect=dump_effect):
            _write_body_subset_atomic(self.tmp_dir, body_subset)
        final = self.tmp_dir / "body_measurements_subset.json"
        raw = final.read_text(encoding="utf-8")
        self.assertIn("{", raw)
        self.assertIn("}", raw)
        json.loads(raw)


class TestAtomicSaveJson(unittest.TestCase):
    """Tests for tools.utils.atomic_io.atomic_save_json."""

    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        import shutil
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_atomic_save_json_success(self) -> None:
        """atomic_save_json writes valid JSON."""
        path = self.tmp_dir / "out.json"
        obj = {"a": 1, "b": [2, 3]}
        atomic_save_json(path, obj)
        self.assertTrue(path.exists())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data, obj)

    def test_atomic_save_json_exception_never_leaves_invalid_final(self) -> None:
        """On exception, final path is either unchanged or never written (no partial JSON)."""
        path = self.tmp_dir / "out.json"
        path.write_text('{"valid": true}', encoding="utf-8")
        original = path.read_text(encoding="utf-8")

        def failing_dump(obj, fp, **kwargs):
            raise OSError("simulated disk full")

        with patch("tools.utils.atomic_io.json.dump", side_effect=failing_dump):
            try:
                atomic_save_json(path, {"x": 1})
            except OSError:
                pass
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
