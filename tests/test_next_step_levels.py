"""Level-aware next_step tests (R11)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NEXT_STEP = REPO / "tools" / "agent" / "next_step.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_log(root: Path, lines: list[dict]) -> None:
    log_path = root / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n"
    log_path.write_text(serialized, encoding="utf-8")


def _run_next_step(root: Path) -> dict:
    plan_path = root / "contracts" / "master_plan_v1.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(NEXT_STEP),
            "--repo-root",
            str(root),
            "--plan",
            str(plan_path),
            "--module",
            "all",
            "--top",
            "20",
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError(f"next_step failed: {proc.stderr}\n{proc.stdout}")
    return json.loads(proc.stdout)


def _plan(steps: list[dict]) -> dict:
    return {
        "plan_version": "master_plan.v1",
        "generated_at": "2026-02-09T00:00:00Z",
        "description": "test plan",
        "rounds": [
            {"round_id": "R10", "title": "r10", "description": "d"},
            {"round_id": "R11", "title": "r11", "description": "d"},
            {"round_id": "R12", "title": "r12", "description": "d"},
        ],
        "steps": steps,
    }


def _step(step_id: str, module: str, m_level: str = "M0",
          depends_on: list[str] | None = None, consumes: list[dict] | None = None) -> dict:
    return {
        "step_id": step_id,
        "module": module,
        "phase": "P0",
        "title": f"{step_id}",
        "depends_on": depends_on or [],
        "round_id": "R11",
        "m_level": m_level,
        "consumes": consumes if consumes is not None else [],
        "unlock": {"requires_u1": False, "requires_u2": False},
        "touched_paths": [],
        "commands": [],
        "dod": [],
        "evidence": {},
    }


class TestNextStepLevels(unittest.TestCase):
    def test_event_without_m_level_counts_as_m0(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(
                root / "contracts" / "master_plan_v1.json",
                _plan([_step("S1", "common", m_level="M0")]),
            )
            _write_log(
                root,
                [
                    {
                        "ts": "2026-02-09T00:00:00Z",
                        "module": "common",
                        "step_id": "S1",
                        "status": "OK",
                    }
                ],
            )
            out = _run_next_step(root)
            self.assertIn("S1", out["progress"]["done_steps"])
            self.assertEqual(out["done_levels"]["S1"], "M0")

    def test_step_requiring_m1_blocked_with_only_m0_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = _plan([
                _step("A", "common", m_level="M1"),
                _step(
                    "B",
                    "common",
                    depends_on=["A"],
                    consumes=[{"from_step": "A", "min_level": "M1"}],
                ),
            ])
            _write_json(root / "contracts" / "master_plan_v1.json", plan)
            _write_log(
                root,
                [
                    {
                        "ts": "2026-02-09T00:00:00Z",
                        "module": "common",
                        "step_id": "A",
                        "status": "OK",
                    }
                ],
            )
            out = _run_next_step(root)
            self.assertNotIn("A", out["progress"]["done_steps"])
            self.assertIn("B", out["progress"]["blocked_steps"])
            blocker = next(x for x in out["blockers"] if x["step_id"] == "B")
            details = blocker["blocker_levels"]
            self.assertEqual(details[0]["from_step"], "A")
            self.assertEqual(details[0]["required_min_level"], "M1")
            self.assertEqual(details[0]["current_level"], "M0")

    def test_m1_ok_event_unblocks_dependents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = _plan([
                _step("A", "common", m_level="M1"),
                _step(
                    "B",
                    "common",
                    depends_on=["A"],
                    consumes=[{"from_step": "A", "min_level": "M1"}],
                ),
            ])
            _write_json(root / "contracts" / "master_plan_v1.json", plan)
            _write_log(
                root,
                [
                    {
                        "ts": "2026-02-09T00:00:00Z",
                        "module": "common",
                        "step_id": "A",
                        "status": "OK",
                    },
                    {
                        "ts": "2026-02-09T00:01:00Z",
                        "module": "common",
                        "step_id": "A",
                        "status": "OK",
                        "m_level": "M1",
                    },
                ],
            )
            out = _run_next_step(root)
            self.assertIn("A", out["progress"]["done_steps"])
            self.assertIn("B", out["progress"]["ready_steps"])
            self.assertEqual(out["done_levels"]["A"], "M1")


if __name__ == "__main__":
    unittest.main()

