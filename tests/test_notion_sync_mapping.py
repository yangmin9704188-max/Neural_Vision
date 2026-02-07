"""Tests for notion_sync: master_plan unlock->plan_id mapping, events parse, cursor (no real Notion API)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.ops.notion_sync import (
    unlock_id_to_plan_ids,
    _load_events,
    _load_cursor,
    _save_cursor,
    MASTER_PLAN_PATH,
    HUB_EVENTS_PATH,
    CURSOR_PATH,
)


class TestUnlockToPlanIdMapping(unittest.TestCase):
    """master_plan unlock -> plan_id mapping (maps_to_plan_ids) parsing."""

    def test_maps_to_plan_ids_from_master_plan(self):
        if not MASTER_PLAN_PATH.exists():
            self.skipTest("contracts/master_plan_v1.json not present")
        from tools.ops.render_hub_state import _load_master_plan
        plan, _ = _load_master_plan()
        mapping = unlock_id_to_plan_ids(plan)
        self.assertIsInstance(mapping, dict)
        self.assertIn("U1.FITTING_READY", mapping)
        self.assertEqual(mapping["U1.FITTING_READY"], ["P0.fitting.u1_ready"])

    def test_empty_plan_returns_empty_mapping(self):
        mapping = unlock_id_to_plan_ids({})
        self.assertEqual(mapping, {})

    def test_unlock_without_maps_to_plan_ids_has_empty_list(self):
        plan = {"unlocks": [{"unlock_id": "U2.X", "title": "X"}]}
        mapping = unlock_id_to_plan_ids(plan)
        self.assertEqual(mapping.get("U2.X"), [])


class TestEventsParseAndCursor(unittest.TestCase):
    """Events parsing + cursor: only new events (after cursor) are considered."""

    def test_load_events_unlocked_only(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"event_type":"UNLOCKED","unlock_id":"U1.FITTING_READY"}\n')
            f.write('{"event_type":"note"}\n')
            f.write('{"event_type":"UNLOCKED","unlock_id":"U2.X"}\n')
            path = Path(f.name)
        try:
            events = _load_events(path)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0][0], 0)
            self.assertEqual(events[0][1].get("unlock_id"), "U1.FITTING_READY")
            self.assertEqual(events[1][0], 2)
        finally:
            path.unlink(missing_ok=True)

    def test_cursor_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            cursor_file = Path(tmp) / "cursor.json"
            import tools.ops.notion_sync as mod
            orig_cursor = mod.CURSOR_PATH
            try:
                mod.CURSOR_PATH = cursor_file
                _save_cursor(3)
                idx = _load_cursor()
                self.assertEqual(idx, 3)
            finally:
                mod.CURSOR_PATH = orig_cursor

    def test_new_events_after_cursor_only(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"event_type":"UNLOCKED","unlock_id":"U1"}\n')
            f.write('{"event_type":"UNLOCKED","unlock_id":"U2"}\n')
            f.write('{"event_type":"UNLOCKED","unlock_id":"U3"}\n')
            path = Path(f.name)
        try:
            events = _load_events(path)
            cursor = 1
            new_events = [(i, ev) for i, ev in events if i > cursor]
            self.assertEqual(len(new_events), 1)
            self.assertEqual(new_events[0][1].get("unlock_id"), "U3")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
