"""Unit tests for run registry lane/run_id extraction and dependency_ledger matching."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.ops.update_run_registry import _extract_lane_run_id, _get_paths_from_event, _is_round_end
from tools.render_status import (
    _load_dependency_ledger,
    _path_matches_glob,
    _check_dependency_ledger,
    _warn_dep,
    _collect_global_observed_paths,
)


class TestExtractLaneRunId(unittest.TestCase):
    def test_standard_pattern(self):
        self.assertEqual(
            _extract_lane_run_id("exports/runs/fitting_v0/abc123/geometry_manifest.json"),
            ("fitting_v0", "abc123"),
        )
        self.assertEqual(
            _extract_lane_run_id("exports/runs/_smoke/20260206_171040/fitting_smoke_v1/geometry_manifest.json"),
            ("_smoke", "20260206_171040"),
        )

    def test_backslash_path(self):
        self.assertEqual(
            _extract_lane_run_id("exports\\runs\\lane1\\run2\\file.json"),
            ("lane1", "run2"),
        )

    def test_no_match(self):
        self.assertIsNone(_extract_lane_run_id("labs/samples/manifest.json"))
        self.assertIsNone(_extract_lane_run_id("exports/runs/only_one_segment"))
        self.assertIsNone(_extract_lane_run_id(""))


class TestRoundEndAndPaths(unittest.TestCase):
    def test_is_round_end_event_type(self):
        self.assertTrue(_is_round_end({"event_type": "ROUND_END"}))
        self.assertTrue(_is_round_end({"event_type": "round_end"}))
        self.assertFalse(_is_round_end({"event_type": "ROUND_START"}))
        self.assertFalse(_is_round_end({"event_type": "note"}))

    def test_is_round_end_event_field(self):
        self.assertTrue(_is_round_end({"event": "round_end"}))
        self.assertTrue(_is_round_end({"event": "ROUND_END"}))

    def test_get_paths_from_event(self):
        ev = {
            "observed_paths": ["a.json"],
            "evidence": ["exports/runs/x/y/z.json"],
            "artifacts_touched": [],
        }
        paths = _get_paths_from_event(ev)
        self.assertIn("a.json", paths)
        self.assertIn("exports/runs/x/y/z.json", paths)


class TestDependencyLedger(unittest.TestCase):
    def test_load_ledger(self):
        ledger = _load_dependency_ledger()
        self.assertIsNotNone(ledger)
        self.assertIn("rows", ledger)
        self.assertIn("schema_version", ledger)

    def test_path_matches_glob(self):
        self.assertTrue(_path_matches_glob("exports/runs/_smoke/20260206/geometry_manifest.json", "exports/runs/**/geometry_manifest.json"))
        self.assertTrue(_path_matches_glob("geometry_manifest.json", "geometry_manifest.json"))
        self.assertFalse(_path_matches_glob("other/file.json", "exports/runs/**/geometry_manifest.json"))

    def test_check_dependency_ledger_matched(self):
        ledger = _load_dependency_ledger()
        if not ledger:
            self.skipTest("dependency_ledger not found")
        observed = {
            "exports/runs/_smoke/20260206/fitting_smoke_v1/geometry_manifest.json",
        }
        result = _check_dependency_ledger(ledger, observed)
        self.assertIsInstance(result, dict)
        self.assertIn("FITTING", result)
        self.assertIn("BODY", result)

    def test_check_dependency_ledger_empty_observed(self):
        ledger = _load_dependency_ledger()
        if not ledger:
            self.skipTest("dependency_ledger not found")
        result = _check_dependency_ledger(ledger, set())
        self.assertIsInstance(result, dict)
        for mod in ("BODY", "FITTING", "GARMENT"):
            self.assertIn(mod, result)

    def test_check_dependency_ledger_returns_hint_path(self):
        ledger = _load_dependency_ledger()
        if not ledger:
            self.skipTest("dependency_ledger not found")
        result = _check_dependency_ledger(ledger, set())
        for mod_entries in result.values():
            for item in mod_entries:
                self.assertIsInstance(item, tuple)
                self.assertEqual(len(item), 2)
                gate, hint = item
                self.assertIsInstance(gate, str)
                self.assertTrue(gate)

    def test_warn_dep_with_hint_path_outputs_expected(self):
        w = _warn_dep("BODY_SUBSET_MISSING_OR_INVALID", "dependency", "exports/runs/<lane>/<run_id>/body_measurements_subset.json")
        self.assertIn("expected=", w)
        self.assertIn("exports/runs/<lane>/<run_id>/body_measurements_subset.json", w)
        self.assertNotIn("path=N/A", w)

    def test_warn_dep_without_hint_path_outputs_path_na(self):
        w = _warn_dep("SOME_CODE", "dependency", None)
        self.assertIn("path=N/A", w)
        w2 = _warn_dep("SOME_CODE", "dependency", "")
        self.assertIn("path=N/A", w2)


class TestRunRegistryIntegration(unittest.TestCase):
    """Integration test: ROUND_END with exports/runs path -> registry append."""

    def test_round_end_with_run_path_produces_registry_record(self):
        import tools.ops.update_run_registry as mod

        with tempfile.TemporaryDirectory() as tmp:
            lab_root = Path(tmp) / "fitting_lab"
            progress_dir = lab_root / "exports" / "progress"
            progress_dir.mkdir(parents=True)
            log_path = progress_dir / "PROGRESS_LOG.jsonl"
            ev = {
                "ts": "2026-02-07T12:00:00+00:00",
                "module": "fitting",
                "event": "round_end",
                "round_id": "fitting_20260207_120000_test",
                "step_id": "F08",
                "evidence": ["exports/runs/_smoke/20260207_120000/fitting_smoke_v1/geometry_manifest.json"],
            }
            log_path.write_text(json.dumps(ev) + "\n", encoding="utf-8")

            registry_path = Path(tmp) / "run_registry.jsonl"
            orig_registry = getattr(mod, "RUN_REGISTRY", None)
            orig_roots = getattr(mod, "LAB_ROOTS_PATH", None)
            try:
                mod.RUN_REGISTRY = registry_path
                mod.LAB_ROOTS_PATH = Path(tmp) / "lab_roots.json"
                mod.LAB_ROOTS_PATH.write_text(
                    json.dumps({"FITTING_LAB_ROOT": str(lab_root)}),
                    encoding="utf-8",
                )
                mod.REPO_ROOT = Path(tmp)
                mod.main()
            finally:
                if orig_registry is not None:
                    mod.RUN_REGISTRY = orig_registry
                if orig_roots is not None:
                    mod.LAB_ROOTS_PATH = orig_roots

            lines = [ln.strip() for ln in registry_path.read_text().splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1, "Expected 1 registry record")
            rec = json.loads(lines[0])
            self.assertEqual(rec["module"], "fitting")
            self.assertEqual(rec["lane"], "_smoke")
            self.assertEqual(rec["run_id"], "20260207_120000")
            self.assertEqual(rec["round_id"], "fitting_20260207_120000_test")

    def test_round_id_empty_normalized_to_na_with_registry_incomplete(self):
        import tools.ops.update_run_registry as mod

        with tempfile.TemporaryDirectory() as tmp:
            lab_root = Path(tmp) / "fitting_lab"
            progress_dir = lab_root / "exports" / "progress"
            progress_dir.mkdir(parents=True)
            log_path = progress_dir / "PROGRESS_LOG.jsonl"
            ev = {
                "ts": "2026-02-07T12:00:00+00:00",
                "module": "fitting",
                "event": "round_end",
                "round_id": "",
                "step_id": "F08",
                "evidence": ["exports/runs/_smoke/20260207_120001/fitting_smoke_v1/geometry_manifest.json"],
            }
            log_path.write_text(json.dumps(ev) + "\n", encoding="utf-8")

            registry_path = Path(tmp) / "run_registry.jsonl"
            orig_registry = getattr(mod, "RUN_REGISTRY", None)
            orig_roots = getattr(mod, "LAB_ROOTS_PATH", None)
            try:
                mod.RUN_REGISTRY = registry_path
                mod.LAB_ROOTS_PATH = Path(tmp) / "lab_roots.json"
                mod.LAB_ROOTS_PATH.write_text(json.dumps({"FITTING_LAB_ROOT": str(lab_root)}), encoding="utf-8")
                mod.REPO_ROOT = Path(tmp)
                mod.main()
            finally:
                if orig_registry is not None:
                    mod.RUN_REGISTRY = orig_registry
                if orig_roots is not None:
                    mod.LAB_ROOTS_PATH = orig_roots

            lines = [ln.strip() for ln in registry_path.read_text().splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1)
            rec = json.loads(lines[0])
            self.assertEqual(rec["round_id"], "N/A")
            self.assertIn("REGISTRY_INCOMPLETE", rec.get("gate_codes", []))

    def test_manifest_prefix_match_no_mismatch_code(self):
        import tools.ops.update_run_registry as mod

        with tempfile.TemporaryDirectory() as tmp:
            lab_root = Path(tmp) / "fitting_lab"
            progress_dir = lab_root / "exports" / "progress"
            progress_dir.mkdir(parents=True)
            log_path = progress_dir / "PROGRESS_LOG.jsonl"
            ev = {
                "ts": "2026-02-07T12:00:00+00:00",
                "module": "fitting",
                "event": "round_end",
                "round_id": "fitting_20260207_120002_test",
                "step_id": "F08",
                "evidence": ["exports/runs/_smoke/20260207_120002/fitting_smoke_v1/geometry_manifest.json"],
            }
            log_path.write_text(json.dumps(ev) + "\n", encoding="utf-8")

            registry_path = Path(tmp) / "run_registry.jsonl"
            orig_registry = getattr(mod, "RUN_REGISTRY", None)
            orig_roots = getattr(mod, "LAB_ROOTS_PATH", None)
            try:
                mod.RUN_REGISTRY = registry_path
                mod.LAB_ROOTS_PATH = Path(tmp) / "lab_roots.json"
                mod.LAB_ROOTS_PATH.write_text(json.dumps({"FITTING_LAB_ROOT": str(lab_root)}), encoding="utf-8")
                mod.REPO_ROOT = Path(tmp)
                mod.main()
            finally:
                if orig_registry is not None:
                    mod.RUN_REGISTRY = orig_registry
                if orig_roots is not None:
                    mod.LAB_ROOTS_PATH = orig_roots

            lines = [ln.strip() for ln in registry_path.read_text().splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1)
            rec = json.loads(lines[0])
            self.assertNotIn("REGISTRY_MANIFEST_MISMATCH", rec.get("gate_codes", []))

    def test_manifest_from_different_run_adds_mismatch_code(self):
        """When manifest is from a different run than lane/run_id, add REGISTRY_MANIFEST_MISMATCH."""
        import tools.ops.update_run_registry as mod

        with tempfile.TemporaryDirectory() as tmp:
            lab_root = Path(tmp) / "fitting_lab"
            progress_dir = lab_root / "exports" / "progress"
            progress_dir.mkdir(parents=True)
            log_path = progress_dir / "PROGRESS_LOG.jsonl"
            ev = {
                "ts": "2026-02-07T12:00:00+00:00",
                "module": "fitting",
                "event": "round_end",
                "round_id": "fitting_20260207_120003_test",
                "step_id": "F08",
                "evidence": [
                    "exports/runs/_smoke/RUN_B/fitting_smoke_v1/geometry_manifest.json",
                    "exports/runs/_smoke/RUN_A/README.txt",
                ],
            }
            log_path.write_text(json.dumps(ev) + "\n", encoding="utf-8")

            registry_path = Path(tmp) / "run_registry.jsonl"
            orig_registry = getattr(mod, "RUN_REGISTRY", None)
            orig_roots = getattr(mod, "LAB_ROOTS_PATH", None)
            try:
                mod.RUN_REGISTRY = registry_path
                mod.LAB_ROOTS_PATH = Path(tmp) / "lab_roots.json"
                mod.LAB_ROOTS_PATH.write_text(json.dumps({"FITTING_LAB_ROOT": str(lab_root)}), encoding="utf-8")
                mod.REPO_ROOT = Path(tmp)
                mod.main()
            finally:
                if orig_registry is not None:
                    mod.RUN_REGISTRY = orig_registry
                if orig_roots is not None:
                    mod.LAB_ROOTS_PATH = orig_roots

            lines = [ln.strip() for ln in registry_path.read_text().splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1)
            rec = json.loads(lines[0])
            self.assertEqual(rec["lane"], "_smoke")
            self.assertEqual(rec["run_id"], "RUN_A")
            self.assertIn("REGISTRY_MANIFEST_MISMATCH", rec.get("gate_codes", []))


if __name__ == "__main__":
    unittest.main()
