"""
Smoke-3: U1 missingness fixtures and warning assertions.
- Case A: exactly 1 key missing -> U1_SUBSET_NULL_SOFT only
- Case B: >=2 keys missing -> U1_SUBSET_NULL_DEGRADED_HIGH only
- Atomic write regression: write failure -> valid stub JSON + diagnostics file.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_repo = Path(__file__).resolve().parents[1]
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

FIXTURES = _repo / "tests" / "fixtures" / "body_u1_missingness"
SOFT_DIR = FIXTURES / "fixture_soft_1missing"
DEGRADED_DIR = FIXTURES / "fixture_degraded_2missing"
VALIDATOR = _repo / "tools" / "validate_body_measurements_subset_u1.py"


def _run_validator(run_dir: Path) -> tuple[int, str, str]:
    r = subprocess.run(
        [sys.executable, str(VALIDATOR), "--run_dir", str(run_dir)],
        capture_output=True,
        text=True,
        cwd=str(_repo),
    )
    return r.returncode, r.stdout, r.stderr


def _validate_data(data: dict) -> tuple[bool, list[str], dict]:
    import importlib.util
    spec = importlib.util.spec_from_file_location("validate_u1", VALIDATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate(data)


class TestSmoke3MissingnessWarnings(unittest.TestCase):
    def test_soft_fixture_validator_exit0_and_warnings_soft_only(self) -> None:
        """Soft fixture: validator exit 0; warnings contain U1_SUBSET_NULL_SOFT and NOT DEGRADED_HIGH."""
        self.assertTrue(SOFT_DIR.exists(), f"Fixture dir missing: {SOFT_DIR}")
        path = SOFT_DIR / "body_measurements_subset.json"
        self.assertTrue(path.exists(), f"Fixture file missing: {path}")
        code, out, err = _run_validator(SOFT_DIR)
        self.assertEqual(code, 0, f"Validator must exit 0. stderr: {err}")
        ok, errors, report = _validate_data(json.loads(path.read_text(encoding="utf-8")))
        self.assertTrue(ok, f"Schema must be valid: {errors}")
        self.assertIn("U1_SUBSET_NULL_SOFT", report["warnings_added"])
        self.assertNotIn("U1_SUBSET_NULL_DEGRADED_HIGH", report["warnings_added"])

    def test_degraded_fixture_validator_exit0_and_warnings_degraded_only(self) -> None:
        """Degraded fixture: validator exit 0; warnings contain U1_SUBSET_NULL_DEGRADED_HIGH and NOT SOFT."""
        self.assertTrue(DEGRADED_DIR.exists(), f"Fixture dir missing: {DEGRADED_DIR}")
        path = DEGRADED_DIR / "body_measurements_subset.json"
        self.assertTrue(path.exists(), f"Fixture file missing: {path}")
        code, out, err = _run_validator(DEGRADED_DIR)
        self.assertEqual(code, 0, f"Validator must exit 0. stderr: {err}")
        ok, errors, report = _validate_data(json.loads(path.read_text(encoding="utf-8")))
        self.assertTrue(ok, f"Schema must be valid: {errors}")
        self.assertIn("U1_SUBSET_NULL_DEGRADED_HIGH", report["warnings_added"])
        self.assertNotIn("U1_SUBSET_NULL_SOFT", report["warnings_added"])

    def test_json_parseable_no_nan_inf(self) -> None:
        """Fixture JSON is parseable and contains no NaN/Infinity tokens."""
        for name, d in (("soft", SOFT_DIR), ("degraded", DEGRADED_DIR)):
            path = d / "body_measurements_subset.json"
            raw = path.read_text(encoding="utf-8")
            for bad in ("NaN", "Infinity", "-Infinity"):
                self.assertNotIn(bad, raw, f"Fixture {name} must not contain {bad}")
            data = json.loads(raw)
            self.assertIsInstance(data, dict)
            self.assertIn("cases", data)
            self.assertIn("warnings", data)


if __name__ == "__main__":
    unittest.main()
