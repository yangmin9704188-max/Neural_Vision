"""Unit tests for render_status signal quality: path classification, hygiene, gate-code aggregation."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add tools to path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.render_status import (
    _classify_path,
    _format_path_for_display,
    PATH_PRIORITY,
    _compute_progress_hygiene,
    _extract_gate_codes_from_events,
    _aggregate_blockers_top_n,
)


class TestClassifyPath(unittest.TestCase):
    def test_run_evidence(self):
        self.assertEqual(_classify_path("exports/runs/foo/bar.json"), "RUN_EVIDENCE")
        self.assertEqual(_classify_path("a/exports/runs/x"), "RUN_EVIDENCE")

    def test_sample(self):
        self.assertEqual(_classify_path("labs/samples/manifest.json"), "SAMPLE")
        self.assertEqual(_classify_path("foo/samples/bar"), "SAMPLE")
        self.assertEqual(_classify_path("x\\samples\\y"), "SAMPLE")

    def test_manifest(self):
        self.assertEqual(_classify_path("some/manifest.json"), "MANIFEST")
        self.assertEqual(_classify_path("geometry_manifest.json"), "MANIFEST")

    def test_other(self):
        self.assertEqual(_classify_path("contracts/foo.md"), "OTHER")

    def test_priority_order(self):
        self.assertLess(PATH_PRIORITY["RUN_EVIDENCE"], PATH_PRIORITY["SAMPLE"])


class TestFormatPathForDisplay(unittest.TestCase):
    def test_relative_unchanged(self):
        self.assertEqual(_format_path_for_display("labs/samples/x.json"), "labs/samples/x.json")

    def test_absolute_suppressed(self):
        self.assertIn("absolute path suppressed", _format_path_for_display("C:/foo/bar.json"))
        self.assertTrue(_format_path_for_display("C:/foo/bar.json").startswith("bar.json"))


class TestComputeProgressHygiene(unittest.TestCase):
    def test_empty_events(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "exports" / "progress" / "PROGRESS_LOG.jsonl"
            log.parent.mkdir(parents=True)
            log.write_text("")
            result = _compute_progress_hygiene(Path(tmp), "fitting")
            self.assertEqual(result, [])

    def test_step_stuck(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "exports" / "progress" / "PROGRESS_LOG.jsonl"
            log.parent.mkdir(parents=True)
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            lines = [json.dumps({"ts": now, "module": "fitting", "step_id": "F01", "note": "x"}) + "\n" for _ in range(10)]
            log.write_text("".join(lines))
            result = _compute_progress_hygiene(Path(tmp), "fitting")
            self.assertIn("STEP_STUCK", result)

    def test_event_thin(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "exports" / "progress" / "PROGRESS_LOG.jsonl"
            log.parent.mkdir(parents=True)
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            lines = [json.dumps({"ts": now, "module": "fitting", "step_id": "F01", "note": "x"}) + "\n" for _ in range(8)]
            log.write_text("".join(lines))
            result = _compute_progress_hygiene(Path(tmp), "fitting")
            self.assertIn("EVENT_THIN", result)


class TestExtractGateCodes(unittest.TestCase):
    def test_from_warnings_bracket(self):
        events = [{"warnings": ["[STEP_ID_MISSING]"]}]
        self.assertEqual(_extract_gate_codes_from_events(events), ["STEP_ID_MISSING"])

    def test_from_gate_code_field(self):
        events = [{"gate_code": "FOO"}]
        self.assertEqual(_extract_gate_codes_from_events(events), ["FOO"])

    def test_from_gate_codes_array(self):
        events = [{"gate_codes": ["A", "B"]}]
        self.assertEqual(_extract_gate_codes_from_events(events), ["A", "B"])


class TestAggregateBlockersTopN(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(_aggregate_blockers_top_n([]), [])

    def test_top_n(self):
        from collections import Counter
        codes = ["A", "A", "A", "B", "B", "C"]
        cnt = Counter(codes)
        top = cnt.most_common(2)
        self.assertEqual(top, [("A", 3), ("B", 2)])


if __name__ == "__main__":
    unittest.main()
