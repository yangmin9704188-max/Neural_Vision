"""Tests for LLM context pack generation (common + per-module)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


class TestLLMContextRender(unittest.TestCase):
    """LLM context file generation."""

    def test_four_files_created(self):
        """4 LLM_CONTEXT_*.md files are created in exports/brief/."""
        from tools.ops.render_hub_state import (
            _load_master_plan,
            _compute_artifacts_observed,
            _compute_unlocks,
            _search_roots,
            _render_llm_context_files,
            BRIEF_DIR,
        )
        plan, _ = _load_master_plan()
        if not plan:
            self.skipTest("master_plan not found")
        roots = _search_roots()
        observed = _compute_artifacts_observed(plan, roots)
        unlocks = _compute_unlocks(plan, observed)
        warnings = []
        _render_llm_context_files(plan, observed, unlocks, warnings)
        for name in ("LLM_CONTEXT_COMMON.md", "LLM_CONTEXT_BODY.md", "LLM_CONTEXT_FITTING.md", "LLM_CONTEXT_GARMENT.md"):
            path = BRIEF_DIR / name
            self.assertTrue(path.exists(), f"{name} should exist")

    def test_now_action_section_from_plan_items(self):
        """지금 할 일 is populated from plan_items (module match, done==false)."""
        from tools.ops.render_hub_state import (
            _load_master_plan,
            _plan_items_not_done,
            _compute_artifacts_observed,
            _compute_unlocks,
            _search_roots,
            _render_llm_context_module,
            _blocker_warnings,
        )
        plan, _ = _load_master_plan()
        if not plan:
            self.skipTest("master_plan not found")
        roots = _search_roots()
        observed = _compute_artifacts_observed(plan, roots)
        unlocks = _compute_unlocks(plan, observed)
        not_done = _plan_items_not_done(plan, observed)
        blockers = _blocker_warnings(plan, observed, unlocks)
        content = _render_llm_context_module(
            "body", plan, observed, unlocks, not_done, [], blockers
        )
        self.assertIn("## 👉 지금 할 일", content)
        self.assertIn("plan_id=", content)

    def test_main_exits_zero(self):
        """main() always returns 0 (warn-only, no FAIL)."""
        from tools.ops.render_hub_state import main
        result = main()
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
