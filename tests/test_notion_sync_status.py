"""Tests for notion_sync_status.json creation (skip cases: config missing, token empty)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import tools.ops.notion_sync as mod


class TestNotionSyncStatusCreation(unittest.TestCase):
    """notion_sync writes ops/notion_sync_status.json at every run."""

    def test_status_written_when_config_missing(self):
        """When ops/notion.local.json is absent, status has mode=skipped, reason=missing_config."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Create minimal master_plan, hub_events with UNLOCKED, cursor behind
            master = tmp_path / "master_plan_v1.json"
            master.write_text(json.dumps({
                "schema_version": "master_plan.v1",
                "unlocks": [{"unlock_id": "U1.TEST", "maps_to_plan_ids": ["P0.test"]}],
            }))
            events = tmp_path / "hub_events_v1.jsonl"
            events.write_text('{"event_type":"UNLOCKED","unlock_id":"U1.TEST"}\n')
            cursor = tmp_path / "cursor.json"
            cursor.write_text('{"last_processed_line_index": -1}')
            status_out = tmp_path / "notion_sync_status.json"
            # Point notion config to non-existent path
            notion_config = tmp_path / "notion.local.json"  # does not exist
            orig_master = mod.MASTER_PLAN_PATH
            orig_events = mod.HUB_EVENTS_PATH
            orig_cursor = mod.CURSOR_PATH
            orig_config = mod.NOTION_CONFIG_PATH
            orig_status = mod.STATUS_PATH
            try:
                mod.MASTER_PLAN_PATH = master
                mod.HUB_EVENTS_PATH = events
                mod.CURSOR_PATH = cursor
                mod.NOTION_CONFIG_PATH = notion_config
                mod.STATUS_PATH = status_out
                exit_code = mod.main()
                self.assertEqual(exit_code, 0)
                self.assertTrue(status_out.exists())
                st = json.loads(status_out.read_text())
                self.assertEqual(st.get("mode"), "skipped")
                self.assertIn(st.get("reason"), ("missing_config", "empty_token"))
                self.assertEqual(st.get("processed"), 0)
                self.assertEqual(st.get("updated"), 0)
            finally:
                mod.MASTER_PLAN_PATH = orig_master
                mod.HUB_EVENTS_PATH = orig_events
                mod.CURSOR_PATH = orig_cursor
                mod.NOTION_CONFIG_PATH = orig_config
                mod.STATUS_PATH = orig_status

    def test_status_written_when_token_empty(self):
        """When token/database_id empty in config, status has mode=skipped, reason=empty_token."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            master = tmp_path / "master_plan_v1.json"
            master.write_text(json.dumps({
                "schema_version": "master_plan.v1",
                "unlocks": [{"unlock_id": "U1.TEST", "maps_to_plan_ids": ["P0.test"]}],
            }))
            events = tmp_path / "hub_events_v1.jsonl"
            events.write_text('{"event_type":"UNLOCKED","unlock_id":"U1.TEST"}\n')
            cursor = tmp_path / "cursor.json"
            cursor.write_text('{"last_processed_line_index": -1}')
            notion_config = tmp_path / "notion.local.json"
            notion_config.write_text(json.dumps({"token": "", "database_id": ""}))
            status_out = tmp_path / "notion_sync_status.json"
            orig_master = mod.MASTER_PLAN_PATH
            orig_events = mod.HUB_EVENTS_PATH
            orig_cursor = mod.CURSOR_PATH
            orig_config = mod.NOTION_CONFIG_PATH
            orig_status = mod.STATUS_PATH
            try:
                mod.MASTER_PLAN_PATH = master
                mod.HUB_EVENTS_PATH = events
                mod.CURSOR_PATH = cursor
                mod.NOTION_CONFIG_PATH = notion_config
                mod.STATUS_PATH = status_out
                exit_code = mod.main()
                self.assertEqual(exit_code, 0)
                self.assertTrue(status_out.exists())
                st = json.loads(status_out.read_text())
                self.assertEqual(st.get("mode"), "skipped")
                self.assertEqual(st.get("reason"), "empty_token")
                self.assertEqual(st.get("processed"), 0)
                self.assertEqual(st.get("updated"), 0)
            finally:
                mod.MASTER_PLAN_PATH = orig_master
                mod.HUB_EVENTS_PATH = orig_events
                mod.CURSOR_PATH = orig_cursor
                mod.NOTION_CONFIG_PATH = orig_config
                mod.STATUS_PATH = orig_status

    def test_status_schema_fields_present(self):
        """Status JSON has required schema fields (no_new_events path)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            master = tmp_path / "master_plan_v1.json"
            master.write_text(json.dumps({"schema_version": "master_plan.v1", "unlocks": []}))
            events = tmp_path / "hub_events_v1.jsonl"
            events.write_text("")
            cursor = tmp_path / "cursor.json"
            cursor.write_text('{"last_processed_line_index": 999}')
            notion_config = tmp_path / "notion.local.json"
            notion_config.write_text(json.dumps({"token": "", "database_id": ""}))
            status_out = tmp_path / "notion_sync_status.json"
            orig_master = mod.MASTER_PLAN_PATH
            orig_events = mod.HUB_EVENTS_PATH
            orig_cursor = mod.CURSOR_PATH
            orig_config = mod.NOTION_CONFIG_PATH
            orig_status = mod.STATUS_PATH
            try:
                mod.MASTER_PLAN_PATH = master
                mod.HUB_EVENTS_PATH = events
                mod.CURSOR_PATH = cursor
                mod.NOTION_CONFIG_PATH = notion_config
                mod.STATUS_PATH = status_out
                mod.main()
                st = json.loads(status_out.read_text())
                self.assertEqual(st.get("schema_version"), "notion_sync_status.v1")
                self.assertIn("updated_at", st)
                self.assertIn("mode", st)
                self.assertIn("reason", st)
                self.assertIn("processed", st)
                self.assertIn("updated", st)
                self.assertIn("skipped", st)
                self.assertIn("error_count", st)
                self.assertIn("cursor", st)
            finally:
                mod.MASTER_PLAN_PATH = orig_master
                mod.HUB_EVENTS_PATH = orig_events
                mod.CURSOR_PATH = orig_cursor
                mod.NOTION_CONFIG_PATH = orig_config
                mod.STATUS_PATH = orig_status


if __name__ == "__main__":
    unittest.main()
