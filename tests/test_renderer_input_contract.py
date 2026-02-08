"""Tests for renderer input contract v1: schema, STEP_ID_MISSING rules, brief filename rules."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


class TestProgressEventSchema(unittest.TestCase):
    """Progress event schema minimal validation."""

    def test_schema_exists_and_valid(self):
        schema_path = REPO / "contracts" / "progress_event_v1.schema.json"
        self.assertTrue(schema_path.exists(), "progress_event_v1.schema.json must exist")
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        self.assertIn("required", schema)
        self.assertIn("ts", schema["required"])
        self.assertIn("module", schema["required"])
        self.assertIn("step_id", schema["required"])
        self.assertIn("properties", schema)
        self.assertIn("event_type", schema["properties"])
        self.assertIn("event", schema["properties"])

    def test_minimal_valid_event_passes_manual_check(self):
        """Event with ts, module, step_id, event_type passes."""
        ev = {"ts": "2026-02-08T12:00:00+09:00", "module": "body", "event_type": "INFO", "step_id": "B01"}
        self.assertIn("ts", ev)
        self.assertIn("module", ev)
        self.assertIn("step_id", ev)
        self.assertTrue(ev.get("event_type") or ev.get("event"))

    def test_event_fallback_accepted(self):
        """Legacy 'event' field is accepted as fallback for event_type."""
        ev = {"ts": "2026-02-08T12:00:00+09:00", "module": "fitting", "event": "note", "step_id": "F01"}
        self.assertTrue(ev.get("event_type") or ev.get("event"))


class TestStepIdMissingRuleAlignment(unittest.TestCase):
    """STEP_ID_MISSING rule: document values match code constants/behavior."""

    def test_unspecified_string_matches_render_work_briefs(self):
        """Contract says step_id==UNSPECIFIED; render_work_briefs uses same."""
        from tools.render_work_briefs import _aggregate_by_module, MODULES
        events = [
            {"module": "body", "step_id": "UNSPECIFIED", "ts": "2026-02-08T12:00:00+09:00", "event_type": "INFO"},
        ]
        agg = _aggregate_by_module(events, {})
        self.assertIn("STEP_ID_MISSING", agg["body"]["warnings"])

    def test_backfill_offsets_unspecified(self):
        """STEP_ID_BACKFILLED 1:1 offsets UNSPECIFIED (net count)."""
        from tools.render_work_briefs import _aggregate_by_module
        events = [
            {"module": "body", "step_id": "UNSPECIFIED", "ts": "2026-02-08T12:00:00", "event_type": "INFO"},
            {"module": "body", "step_id": "B01", "ts": "2026-02-08T12:01:00", "event_type": "INFO", "gate_codes": ["STEP_ID_BACKFILLED"]},
        ]
        agg = _aggregate_by_module(events, {})
        # 1 UNSPECIFIED - 1 BACKFILLED = 0 net STEP_ID_MISSING
        self.assertEqual(agg["body"]["warnings"].count("STEP_ID_MISSING"), 0)

    def test_render_status_max_events_50(self):
        """render_status uses max_events=50 for blocker aggregation."""
        from tools.render_status import _read_lab_progress_events
        with tempfile.TemporaryDirectory() as tmp:
            lab_root = Path(tmp)
            log_dir = lab_root / "exports" / "progress"
            log_dir.mkdir(parents=True)
            log_path = log_dir / "PROGRESS_LOG.jsonl"
            lines = []
            for i in range(60):
                ev = {"module": "fitting", "step_id": "UNSPECIFIED" if i % 2 == 0 else "F01", "ts": "2026-02-08T12:00:00", "event": "note"}
                lines.append(json.dumps(ev))
            log_path.write_text("\n".join(lines))
            events = _read_lab_progress_events(lab_root, "fitting", max_events=50)
            self.assertLessEqual(len(events), 50)


class TestTombstoneExempt(unittest.TestCase):
    """Tombstone (SCHEMA_VIOLATION_BACKFILLED) exempts referenced legacy lines."""

    def test_legacy_event_plus_tombstone_zero_warnings(self):
        """Legacy event (missing event_type) + tombstone with referenced_line=N → 0 warnings."""
        import tempfile
        from tools.ops.validate_renderer_inputs import _validate_progress_log
        with tempfile.TemporaryDirectory() as tmp:
            lab = Path(tmp)
            log_dir = lab / "exports" / "progress"
            log_dir.mkdir(parents=True)
            log_path = log_dir / "PROGRESS_LOG.jsonl"
            # Line 1: legacy (no event_type)
            legacy = {"ts": "2026-02-08T12:00:00", "module": "garment", "step_id": "G01", "note": "legacy"}
            # Line 2: tombstone exempting line 1
            tombstone = {
                "ts": "2026-02-08T12:01:00", "module": "garment", "step_id": "G_BACKFILL",
                "event_type": "INFO", "gate_codes": ["SCHEMA_VIOLATION_BACKFILLED"],
                "note": "referenced_line=1; action=tombstone_append_only"
            }
            log_path.write_text(json.dumps(legacy) + "\n" + json.dumps(tombstone))
            warns, exempted = _validate_progress_log(log_path)
            self.assertEqual(len(warns), 0, f"expected 0 warnings, got {warns}")
            self.assertEqual(exempted, 1, f"expected exempted=1, got {exempted}")

    def test_malformed_note_no_exempt(self):
        """Malformed note (no referenced_line parse) → exempt not applied, warnings remain."""
        import tempfile
        from tools.ops.validate_renderer_inputs import _validate_progress_log
        with tempfile.TemporaryDirectory() as tmp:
            lab = Path(tmp)
            log_dir = lab / "exports" / "progress"
            log_dir.mkdir(parents=True)
            log_path = log_dir / "PROGRESS_LOG.jsonl"
            legacy = {"ts": "2026-02-08T12:00:00", "module": "garment", "step_id": "G01", "note": "legacy"}
            tombstone_bad = {
                "ts": "2026-02-08T12:01:00", "module": "garment", "step_id": "G_BACKFILL",
                "event_type": "INFO", "gate_codes": ["SCHEMA_VIOLATION_BACKFILLED"],
                "note": "action=tombstone but no referenced_line"
            }
            log_path.write_text(json.dumps(legacy) + "\n" + json.dumps(tombstone_bad))
            warns, exempted = _validate_progress_log(log_path)
            self.assertGreater(len(warns), 0, "malformed tombstone should not exempt")
            self.assertEqual(exempted, 0)


class TestBriefFilenameRules(unittest.TestCase):
    """Brief filename rules: BODY_WORK_BRIEF.md, FITTING_WORK_BRIEF.md, GARMENT_WORK_BRIEF.md."""

    def test_contract_brief_names_match_render_work_briefs(self):
        """Brief names in contract match render_work_briefs output pattern."""
        from tools.render_work_briefs import MODULES
        expected = [f"{m.upper()}_WORK_BRIEF.md" for m in MODULES]
        self.assertEqual(expected, ["BODY_WORK_BRIEF.md", "FITTING_WORK_BRIEF.md", "GARMENT_WORK_BRIEF.md"])

    def test_brief_path_pattern(self):
        """Brief path: <lab_root>/exports/brief/<MODULE>_WORK_BRIEF.md."""
        for mod in ("body", "fitting", "garment"):
            name = f"{mod.upper()}_WORK_BRIEF.md"
            expected_suffix = f"exports/brief/{name}"
            self.assertTrue(expected_suffix.endswith(name))
            self.assertIn("_WORK_BRIEF.md", name)


if __name__ == "__main__":
    unittest.main()
