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
    _warn_m1,
    _collect_global_observed_paths,
    _check_run_minset,
    _check_round_end_missing,
    _evaluate_m1_checks,
    _check_m1_ledger,
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

    def test_check_m1_ledger_fails_on_bad_manifest(self):
        import tools.render_status as mod

        with tempfile.TemporaryDirectory() as tmp:
            lab_root = Path(tmp) / "fitting_lab"
            geo_path = lab_root / "exports" / "runs" / "_smoke" / "r1" / "geometry_manifest.json"
            geo_path.parent.mkdir(parents=True)
            geo_path.write_text('{"version":"v0"}')
            orig_repo = getattr(mod, "REPO_ROOT", None)
            ledger = {
                "rows": [{
                    "id": "dep-test",
                    "consumer_module": "fitting",
                    "producer_module": "body",
                    "required_paths_any": ["exports/runs/**/geometry_manifest.json"],
                    "hint_path": "exports/runs/<lane>/<run_id>/geometry_manifest.json",
                    "m1_checks": {"require_fields": ["schema_version"], "schema_version_exact": "geometry_manifest.v1"},
                }],
            }
            try:
                mod.REPO_ROOT = Path(tmp)
                observed = {"exports/runs/_smoke/r1/geometry_manifest.json"}
                lab_roots = [(lab_root, "fitting")]
                result = mod._check_m1_ledger(ledger, observed, lab_roots)
                self.assertIn("FITTING", result)
                self.assertGreaterEqual(len(result["FITTING"]), 1)
                self.assertIn("M1_CHECK_FAILED", result["FITTING"][0])
            finally:
                if orig_repo is not None:
                    mod.REPO_ROOT = orig_repo

    def test_check_m1_ledger_inputs_fingerprint_alias_passes(self):
        """Manifest with inputs_fingerprint (legacy alias) passes m1_checks, no M1_CHECK_FAILED."""
        import tools.render_status as mod

        with tempfile.TemporaryDirectory() as tmp:
            lab_root = Path(tmp) / "fitting_lab"
            geo_path = lab_root / "exports" / "runs" / "_smoke" / "r2" / "geometry_manifest.json"
            geo_path.parent.mkdir(parents=True)
            geo_path.write_text(
                '{"schema_version":"geometry_manifest.v1","inputs_fingerprint":"sha256:abc123"}'
            )
            orig_repo = getattr(mod, "REPO_ROOT", None)
            ledger = {
                "rows": [{
                    "id": "dep-test",
                    "consumer_module": "fitting",
                    "producer_module": "body",
                    "required_paths_any": ["exports/runs/**/geometry_manifest.json"],
                    "hint_path": "exports/runs/<lane>/<run_id>/geometry_manifest.json",
                    "m1_checks": {
                        "require_fields": ["schema_version"],
                        "require_any_fields": [["fingerprint", "inputs_fingerprint"]],
                        "schema_version_exact": "geometry_manifest.v1",
                    },
                }],
            }
            try:
                mod.REPO_ROOT = Path(tmp)
                observed = {"exports/runs/_smoke/r2/geometry_manifest.json"}
                lab_roots = [(lab_root, "fitting")]
                result = mod._check_m1_ledger(ledger, observed, lab_roots)
                self.assertIn("FITTING", result)
                m1_warnings = [w for w in result["FITTING"] if "M1_CHECK_FAILED" in w and "fingerprint" in w]
                self.assertEqual(len(m1_warnings), 0, "inputs_fingerprint should satisfy fingerprint check")
            finally:
                if orig_repo is not None:
                    mod.REPO_ROOT = orig_repo

    def test_warn_m1_format(self):
        w = _warn_m1("dep-id", "exports/runs/x/y/z.json", "missing_field:schema_version")
        self.assertIn("M1_CHECK_FAILED", w)
        self.assertIn("dep-id", w)
        self.assertIn("expected=", w)
        self.assertIn("detail=", w)

    def test_warn_dep_without_hint_path_outputs_path_na(self):
        w = _warn_dep("SOME_CODE", "dependency", None)
        self.assertIn("path=N/A", w)
        w2 = _warn_dep("SOME_CODE", "dependency", "")
        self.assertIn("path=N/A", w2)

    def test_ledger_rows_have_m1_checks(self):
        ledger = _load_dependency_ledger()
        if not ledger:
            self.skipTest("dependency_ledger not found")
        for row in ledger.get("rows") or []:
            self.assertIn("m1_checks", row)
            self.assertIsInstance(row["m1_checks"], dict)

    def test_evaluate_m1_checks_require_fields(self):
        self.assertEqual(_evaluate_m1_checks({"require_fields": ["schema_version"]}, {}), ["missing_field:schema_version"])
        self.assertEqual(_evaluate_m1_checks({"require_fields": ["schema_version"]}, {"schema_version": "v1"}), [])

    def test_evaluate_m1_checks_schema_version_exact(self):
        self.assertEqual(
            _evaluate_m1_checks({"schema_version_exact": "geometry_manifest.v1"}, {"schema_version": "v0"}),
            ["schema_version:'v0'!='geometry_manifest.v1'"],
        )
        self.assertEqual(
            _evaluate_m1_checks({"schema_version_exact": "geometry_manifest.v1"}, {"schema_version": "geometry_manifest.v1"}),
            [],
        )

    def test_evaluate_m1_checks_require_keys_any(self):
        self.assertEqual(
            _evaluate_m1_checks({"require_keys_any": ["BUST", "WAIST"]}, {"other": 1}),
            ["require_keys_any:['BUST', 'WAIST']"],
        )
        self.assertEqual(
            _evaluate_m1_checks({"require_keys_any": ["BUST", "WAIST"]}, {"BUST": 1}),
            [],
        )

    def test_evaluate_m1_checks_require_any_fields_alias_pass(self):
        """inputs_fingerprint (legacy alias) satisfies fingerprint requirement -> no M1_CHECK_FAILED."""
        m1 = {"require_fields": ["schema_version"], "require_any_fields": [["fingerprint", "inputs_fingerprint"]], "schema_version_exact": "geometry_manifest.v1"}
        data = {"schema_version": "geometry_manifest.v1", "inputs_fingerprint": "abc123"}
        self.assertEqual(_evaluate_m1_checks(m1, data), [])

    def test_evaluate_m1_checks_require_any_fields_canonical_pass(self):
        """Canonical fingerprint present -> pass."""
        m1 = {"require_fields": ["schema_version"], "require_any_fields": [["fingerprint", "inputs_fingerprint"]], "schema_version_exact": "geometry_manifest.v1"}
        data = {"schema_version": "geometry_manifest.v1", "fingerprint": "abc123"}
        self.assertEqual(_evaluate_m1_checks(m1, data), [])

    def test_evaluate_m1_checks_require_any_fields_neither_fails(self):
        """Neither fingerprint nor inputs_fingerprint -> M1 failure."""
        m1 = {"require_fields": ["schema_version"], "require_any_fields": [["fingerprint", "inputs_fingerprint"]], "schema_version_exact": "geometry_manifest.v1"}
        data = {"schema_version": "geometry_manifest.v1"}
        self.assertIn("require_any_fields:", str(_evaluate_m1_checks(m1, data)[0]))

    def test_ledger_geometry_manifest_m1_checks(self):
        ledger = _load_dependency_ledger()
        if not ledger:
            self.skipTest("dependency_ledger not found")
        for row in ledger.get("rows") or []:
            if row.get("artifact_kind") == "geometry_manifest":
                mc = row.get("m1_checks") or {}
                self.assertIn("require_fields", mc)
                self.assertIn("require_any_fields", mc, "geometry_manifest must use require_any_fields for fingerprint/inputs_fingerprint")
                self.assertIn("schema_version_exact", mc)
                break
        else:
            self.skipTest("no geometry_manifest row")


class TestRunMinsetAndRoundEnd(unittest.TestCase):
    def test_check_run_minset_missing_dir_adds_expected(self):
        import tools.render_status as mod

        with tempfile.TemporaryDirectory() as tmp:
            ops_dir = Path(tmp) / "ops"
            ops_dir.mkdir()
            registry = ops_dir / "run_registry.jsonl"
            lab_root = Path(tmp) / "fitting_lab"
            lab_root.mkdir()
            registry.write_text(
                json.dumps({
                    "module": "fitting",
                    "lane": "_smoke",
                    "run_id": "nonexistent_run",
                    "evidence_paths": [],
                }) + "\n",
                encoding="utf-8",
            )
            orig_repo = getattr(mod, "REPO_ROOT", None)
            try:
                mod.REPO_ROOT = Path(tmp)
                lab_roots = [(lab_root, "fitting")]
                minset_result, _ = mod._check_run_minset(lab_roots)
                self.assertIn("FITTING", minset_result)
                self.assertGreaterEqual(len(minset_result["FITTING"]), 1)
                self.assertIn("exports/runs/", minset_result["FITTING"][0])
            finally:
                if orig_repo is not None:
                    mod.REPO_ROOT = orig_repo

    def test_check_run_minset_with_fixture(self):
        import tools.render_status as mod

        with tempfile.TemporaryDirectory() as tmp:
            lab_root = Path(tmp) / "fitting_lab"
            run_dir = lab_root / "exports" / "runs" / "_smoke" / "test_run"
            run_dir.mkdir(parents=True)
            (run_dir / "geometry_manifest.json").write_text("{}")
            ops_dir = Path(tmp) / "ops"
            ops_dir.mkdir()
            registry = ops_dir / "run_registry.jsonl"
            registry.write_text(
                json.dumps({
                    "module": "fitting",
                    "lane": "_smoke",
                    "run_id": "test_run",
                    "evidence_paths": [],
                }) + "\n",
                encoding="utf-8",
            )
            orig_repo = getattr(mod, "REPO_ROOT", None)
            try:
                mod.REPO_ROOT = Path(tmp)
                lab_roots = [(lab_root, "fitting")]
                minset_result, _ = mod._check_run_minset(lab_roots)
                self.assertIn("FITTING", minset_result)
                self.assertGreaterEqual(
                    len(minset_result["FITTING"]),
                    1,
                    msg="run with only geometry_manifest (1/3) should get RUN_MINSET_MISSING",
                )
            finally:
                if orig_repo is not None:
                    mod.REPO_ROOT = orig_repo

    def test_check_run_minset_root_missing_when_geo_in_subdir_only(self):
        """When geometry_manifest exists in subdir but not at run root, add RUN_MANIFEST_ROOT_MISSING."""
        import tools.render_status as mod

        with tempfile.TemporaryDirectory() as tmp:
            lab_root = Path(tmp) / "fitting_lab"
            run_dir = lab_root / "exports" / "runs" / "_smoke" / "test_root"
            subdir = run_dir / "fitting_smoke_v1"
            subdir.mkdir(parents=True)
            (subdir / "geometry_manifest.json").write_text("{}")
            (run_dir / "RUN_README.md").write_text("ok")
            ops_dir = Path(tmp) / "ops"
            ops_dir.mkdir()
            registry = ops_dir / "run_registry.jsonl"
            registry.write_text(
                json.dumps({
                    "module": "fitting",
                    "lane": "_smoke",
                    "run_id": "test_root",
                    "evidence_paths": [],
                }) + "\n",
                encoding="utf-8",
            )
            orig_repo = getattr(mod, "REPO_ROOT", None)
            try:
                mod.REPO_ROOT = Path(tmp)
                lab_roots = [(lab_root, "fitting")]
                _, root_result = mod._check_run_minset(lab_roots)
                self.assertIn("FITTING", root_result)
                self.assertGreaterEqual(
                    len(root_result["FITTING"]),
                    1,
                    msg="geo in subdir only -> RUN_MANIFEST_ROOT_MISSING",
                )
                self.assertIn("geometry_manifest.json", root_result["FITTING"][0])
            finally:
                if orig_repo is not None:
                    mod.REPO_ROOT = orig_repo

    def test_check_round_end_missing_start_gt_end(self):
        import tools.render_status as mod
        from datetime import datetime, timezone, timedelta

        with tempfile.TemporaryDirectory() as tmp:
            lab_root = Path(tmp) / "fitting_lab"
            progress_dir = lab_root / "exports" / "progress"
            progress_dir.mkdir(parents=True)
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            log = progress_dir / "PROGRESS_LOG.jsonl"
            log.write_text(
                "\n".join([
                    json.dumps({"ts": now, "module": "fitting", "event": "round_start", "round_id": "r1"}),
                    json.dumps({"ts": now, "module": "fitting", "event": "round_start", "round_id": "r2"}),
                    json.dumps({"ts": now, "module": "fitting", "event": "round_end", "round_id": "r1"}),
                ]) + "\n",
                encoding="utf-8",
            )
            lab_roots = [(lab_root, "fitting")]
            result = mod._check_round_end_missing(lab_roots, hours=24)
            self.assertIn("FITTING", result)
            self.assertGreater(len(result["FITTING"]), 0, "2 start, 1 end -> ROUND_END_MISSING")


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
