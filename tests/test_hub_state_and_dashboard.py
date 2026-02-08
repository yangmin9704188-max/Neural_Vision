"""Tests for master_plan loading, artifact_observed glob, newly_unlocked diff, dashboard render."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.ops.render_hub_state import (
    _load_master_plan,
    _eval_logic,
    _artifact_observed,
    _compute_artifacts_observed,
    _compute_unlocks,
    _newly_unlocked,
    _render_dashboard,
    _render_notion_sync_section,
    _plan_items_not_done,
    _blocker_warnings,
    MASTER_PLAN_PATH,
    NOTION_SYNC_STATUS_PATH,
)


class TestMasterPlanLoading(unittest.TestCase):
    def test_load_master_plan(self):
        if not MASTER_PLAN_PATH.exists():
            self.skipTest("contracts/master_plan_v1.json not present")
        plan, warnings = _load_master_plan()
        self.assertIsInstance(plan, dict)
        self.assertEqual(plan.get("schema_version"), "master_plan.v1")
        self.assertIn("artifacts", plan)
        self.assertIn("maturity_levels", plan)
        self.assertIn("plan_items", plan)
        self.assertIn("unlocks", plan)
        self.assertIn("dashboard", plan)
        self.assertGreaterEqual(len(plan.get("plan_items", [])), 3)
        self.assertGreaterEqual(len(plan.get("unlocks", [])), 1)
        unlocks = plan.get("unlocks", [])
        ids = [u.get("unlock_id") for u in unlocks if u.get("unlock_id")]
        self.assertIn("U1.FITTING_READY", ids)


class TestArtifactObservedGlob(unittest.TestCase):
    def test_artifact_observed_dummy_dir(self):
        if not MASTER_PLAN_PATH.exists():
            self.skipTest("contracts/master_plan_v1.json not present")
        plan, _ = _load_master_plan()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "exports" / "runs" / "lane1" / "run1"
            runs.mkdir(parents=True)
            (runs / "body_measurements_subset.json").write_text("{}")
            (runs / "garment_proxy_meta.json").write_text("{}")
            observed = _compute_artifacts_observed(plan, [root])
            self.assertTrue(observed.get("body_subset_m0"))
            self.assertTrue(observed.get("garment_proxy_meta_m0"))

    def test_artifact_observed_empty_dir(self):
        if not MASTER_PLAN_PATH.exists():
            self.skipTest("contracts/master_plan_v1.json not present")
        plan, _ = _load_master_plan()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            observed = _compute_artifacts_observed(plan, [root])
            self.assertFalse(observed.get("body_subset_m0"))
            self.assertFalse(observed.get("garment_proxy_meta_m0"))


class TestEvalLogic(unittest.TestCase):
    def test_and_logic(self):
        plan = {}
        observed_ids = {"a"}  # only a is observed; b is not
        logic = {"type": "and", "items": [
            {"type": "artifact_observed", "artifact_id": "a"},
            {"type": "artifact_observed", "artifact_id": "b"},
        ]}
        self.assertFalse(_eval_logic(plan, logic, observed_ids))

    def test_or_logic(self):
        plan = {}
        logic = {"type": "or", "items": [
            {"type": "artifact_observed", "artifact_id": "x"},
            {"type": "artifact_observed", "artifact_id": "y"},
        ]}
        self.assertFalse(_eval_logic(plan, logic, set()))
        self.assertTrue(_eval_logic(plan, logic, {"y"}))

    def test_artifact_observed(self):
        plan = {}
        self.assertTrue(_eval_logic(plan, {"type": "artifact_observed", "artifact_id": "a"}, {"a"}))
        self.assertFalse(_eval_logic(plan, {"type": "artifact_observed", "artifact_id": "a"}, set()))


class TestNewlyUnlocked(unittest.TestCase):
    def test_newly_unlocked_diff(self):
        current = {"U1.FITTING_READY": True, "U2.X": False}
        previous = {}
        self.assertEqual(_newly_unlocked(current, previous), ["U1.FITTING_READY"])

    def test_newly_unlocked_no_new(self):
        current = {"U1.FITTING_READY": True}
        previous = {"unlocks": {"U1.FITTING_READY": True}}
        self.assertEqual(_newly_unlocked(current, previous), [])

    def test_newly_unlocked_previous_state(self):
        current = {"U1.FITTING_READY": True}
        previous = {"unlocks": {"U1.FITTING_READY": False}}
        self.assertEqual(_newly_unlocked(current, previous), ["U1.FITTING_READY"])


class TestDashboardRenderEmpty(unittest.TestCase):
    def test_dashboard_empty_data_no_crash(self):
        """Dashboard render with empty/minimal data must not raise."""
        plan = {
            "schema_version": "master_plan.v1",
            "dashboard": {"title": "Test", "limits": {"newly_unlocked": 10, "blockers": 10, "next_actions_per_module": 3}},
            "unlocks": [],
            "plan_items": [],
            "artifacts": {},
        }
        artifacts_observed = {}
        unlocks = {}
        newly_unlocked = []
        warnings = []
        out = _render_dashboard(plan, artifacts_observed, unlocks, newly_unlocked, warnings)
        self.assertIn("# Test", out)
        self.assertIn("새로 언락됨", out)
        self.assertIn("막힌 것", out)
        self.assertIn("할 일", out)
        self.assertIn("모듈 상태", out)

    def test_dashboard_with_unlocks_and_plan_items(self):
        if not MASTER_PLAN_PATH.exists():
            self.skipTest("contracts/master_plan_v1.json not present")
        plan, _ = _load_master_plan()
        artifacts_observed = {k: False for k in (plan.get("artifacts") or {})}
        unlocks = {u["unlock_id"]: False for u in (plan.get("unlocks") or []) if u.get("unlock_id")}
        newly_unlocked = []
        out = _render_dashboard(plan, artifacts_observed, unlocks, newly_unlocked, [])
        self.assertIn("Neural Vision Dashboard", out)
        self.assertIn("(없음)" if not newly_unlocked else "✅", out)


class TestNotionSyncSection(unittest.TestCase):
    """DASHBOARD includes Notion Sync status section."""

    def test_render_notion_sync_section_no_file(self):
        """When ops/notion_sync_status.json does not exist, show (no status file)."""
        with tempfile.TemporaryDirectory() as tmp:
            status_path = Path(tmp) / "notion_sync_status.json"
            self.assertFalse(status_path.exists())
            import tools.ops.render_hub_state as rh
            orig = rh.NOTION_SYNC_STATUS_PATH
            try:
                rh.NOTION_SYNC_STATUS_PATH = status_path
                lines = _render_notion_sync_section()
            finally:
                rh.NOTION_SYNC_STATUS_PATH = orig
            self.assertIn("## 🔁 Notion Sync 상태", lines)
            joined = "\n".join(lines)
            self.assertIn("(no status file)", joined)

    def test_render_notion_sync_section_with_status(self):
        """When status file exists, dashboard shows updated_at, mode, reason, processed."""
        with tempfile.TemporaryDirectory() as tmp:
            status_path = Path(tmp) / "notion_sync_status.json"
            status_path.write_text(json.dumps({
                "schema_version": "notion_sync_status.v1",
                "updated_at": "2026-02-08T02:10:00+0900",
                "mode": "skipped",
                "reason": "missing_config",
                "processed": 0,
                "updated": 0,
                "skipped": 0,
                "error_count": 0,
                "cursor": None,
            }))
            import tools.ops.render_hub_state as rh
            orig = rh.NOTION_SYNC_STATUS_PATH
            try:
                rh.NOTION_SYNC_STATUS_PATH = status_path
                lines = _render_notion_sync_section()
            finally:
                rh.NOTION_SYNC_STATUS_PATH = orig
            joined = "\n".join(lines)
            self.assertIn("## 🔁 Notion Sync 상태", joined)
            self.assertIn("skipped", joined)
            self.assertIn("missing_config", joined)
            self.assertIn("processed=", joined)
            self.assertIn("error_count=", joined)

    def test_dashboard_includes_notion_sync_section(self):
        """Full dashboard render includes Notion Sync section."""
        plan = {
            "schema_version": "master_plan.v1",
            "dashboard": {"title": "Test", "limits": {"newly_unlocked": 10, "blockers": 10, "next_actions_per_module": 3}},
            "unlocks": [],
            "plan_items": [],
            "artifacts": {},
        }
        out = _render_dashboard(plan, {}, {}, [], [])
        self.assertIn("## 🔁 Notion Sync 상태", out)


class TestDashboardP02UX(unittest.TestCase):
    """P0.2: brief paths only in unlock sections; next_actions has no brief_path."""

    def test_dashboard_next_actions_has_no_brief_path(self):
        """Next_actions section must not contain '복붙 파일:'."""
        if not MASTER_PLAN_PATH.exists():
            self.skipTest("contracts/master_plan_v1.json not present")
        plan, _ = _load_master_plan()
        artifacts_observed = {k: False for k in (plan.get("artifacts") or {})}
        unlocks = {u["unlock_id"]: False for u in (plan.get("unlocks") or []) if u.get("unlock_id")}
        newly_unlocked = []
        out = _render_dashboard(plan, artifacts_observed, unlocks, newly_unlocked, [])
        if "## 👉 지금 할 일" in out:
            start = out.index("## 👉 지금 할 일")
            rest = out[start:]
            end = rest.find("\n## ", 1)
            next_actions_block = rest[: end if end != -1 else len(rest)]
            self.assertNotIn("복붙 파일:", next_actions_block, "👉 지금 할 일 섹션에 복붙 파일이 있으면 안 됨")

    def test_dashboard_unlocked_shows_brief_path(self):
        """Unlocked section must show brief_path when on_unlocked has brief_path."""
        if not MASTER_PLAN_PATH.exists():
            self.skipTest("contracts/master_plan_v1.json not present")
        plan, _ = _load_master_plan()
        artifacts_observed = {k: True for k in (plan.get("artifacts") or {})}
        unlocks = {u["unlock_id"]: True for u in (plan.get("unlocks") or []) if u.get("unlock_id")}
        newly_unlocked = []
        out = _render_dashboard(plan, artifacts_observed, unlocks, newly_unlocked, [])
        self.assertIn("현재 해금됨", out)
        self.assertIn("복붙 파일:", out, "해금된 unlock에 brief_path가 있으면 복붙 파일이 표기되어야 함")


if __name__ == "__main__":
    unittest.main()
