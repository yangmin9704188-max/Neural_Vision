#!/usr/bin/env python3
"""next_step.py — Recommend next actions based on plan + progress (Round 03).

Facts-only logic:
  - Scans progress logs for completed step_ids (status=="OK")
  - Calculates DONE/READY/BLOCKED based on depends_on
  - Outputs top N recommended next steps + blockers

Exit codes: 0 = success, 1 = fatal error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Constants ────────────────────────────────────────────────────────

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

VALID_MODULES = {"body", "garment", "fitting", "common", "all"}


# ── Repo root detection ──────────────────────────────────────────────

def find_repo_root(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find repository root by walking up until .git/ or project_map.md."""
    if start_dir is None:
        start_dir = Path.cwd()
    current = start_dir.resolve()
    while True:
        if (current / ".git").is_dir():
            return current
        if (current / "project_map.md").is_file():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


# ── Progress log scanning ────────────────────────────────────────────

def scan_progress_logs(repo_root: Path) -> Tuple[Set[str], List[str]]:
    """Scan PROGRESS_LOG.jsonl files, return (done_step_ids, warnings)."""
    done_ids: Set[str] = set()
    warnings: List[str] = []

    candidates = [
        repo_root / "exports" / "progress" / "PROGRESS_LOG.jsonl",
        repo_root / "modules" / "body" / "exports" / "progress" / "PROGRESS_LOG.jsonl",
        repo_root / "modules" / "garment" / "exports" / "progress" / "PROGRESS_LOG.jsonl",
        repo_root / "modules" / "fitting" / "exports" / "progress" / "PROGRESS_LOG.jsonl",
    ]

    for log_path in candidates:
        if not log_path.is_file():
            continue

        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        sid = obj.get("step_id")
                        status = obj.get("status")
                        if isinstance(sid, str) and status == "OK":
                            done_ids.add(sid)
                    except json.JSONDecodeError:
                        warnings.append(f"WARN: parse error in {log_path.name} line {line_num}")
        except OSError as exc:
            warnings.append(f"WARN: failed to read {log_path}: {exc}")

    return done_ids, warnings


# ── Plan computation ─────────────────────────────────────────────────

def compute_state(plan_data: Dict[str, Any], done_ids: Set[str]) -> Dict[str, Any]:
    """Compute done/ready/blocked sets + per-step state."""
    steps = plan_data.get("steps", [])
    if not isinstance(steps, list):
        return {"steps": [], "done": set(), "ready": set(), "blocked": set()}

    all_ids = {s["step_id"] for s in steps if isinstance(s.get("step_id"), str)}
    done_set = done_ids & all_ids
    ready_set: Set[str] = set()
    blocked_set: Set[str] = set()

    step_map: Dict[str, Dict[str, Any]] = {}
    for step in steps:
        sid = step.get("step_id")
        if not isinstance(sid, str):
            continue
        step_map[sid] = step

    for sid, step in step_map.items():
        if sid in done_set:
            continue

        deps = step.get("depends_on", [])
        if not isinstance(deps, list):
            deps = []

        unmet_deps = [d for d in deps if d not in done_set]
        if unmet_deps:
            blocked_set.add(sid)
        else:
            ready_set.add(sid)

    return {
        "steps": steps,
        "step_map": step_map,
        "done": done_set,
        "ready": ready_set,
        "blocked": blocked_set,
    }


def recommend_next(state: Dict[str, Any], module_filter: str, top: int) -> List[Dict[str, Any]]:
    """Return top N ready steps, optionally filtered by module."""
    ready_ids = state["ready"]
    step_map = state["step_map"]

    candidates = []
    for sid in ready_ids:
        step = step_map.get(sid, {})
        mod = step.get("module", "")
        if module_filter != "all" and mod != module_filter:
            continue

        phase = step.get("phase", "")
        title = step.get("title", "")
        unlock = step.get("unlock", {})
        req_u1 = unlock.get("requires_u1", False)
        req_u2 = unlock.get("requires_u2", False)
        commands = step.get("commands", [])

        reason = f"All dependencies met"
        req_evidence = []
        if req_u1:
            req_evidence.append("U1 validators must pass")
        if req_u2:
            req_evidence.append("U2 smokes must pass")

        suggested = commands[0] if commands else "N/A"

        candidates.append({
            "step_id": sid,
            "module": mod,
            "phase": phase,
            "title": title,
            "reason_ready": reason,
            "required_evidence": req_evidence,
            "suggested_command": suggested,
        })

    # Sort by phase then step_id for determinism
    candidates.sort(key=lambda x: (x["phase"], x["step_id"]))
    return candidates[:top]


def list_blockers(state: Dict[str, Any], module_filter: str, top: int) -> List[Dict[str, Any]]:
    """Return top N blocked steps with their blocking deps."""
    blocked_ids = state["blocked"]
    step_map = state["step_map"]
    done_ids = state["done"]

    candidates = []
    for sid in blocked_ids:
        step = step_map.get(sid, {})
        mod = step.get("module", "")
        if module_filter != "all" and mod != module_filter:
            continue

        deps = step.get("depends_on", [])
        unmet = [d for d in deps if d not in done_ids]

        candidates.append({
            "step_id": sid,
            "module": mod,
            "phase": step.get("phase", ""),
            "title": step.get("title", ""),
            "blockers": unmet,
        })

    # Sort by phase then step_id
    candidates.sort(key=lambda x: (x["phase"], x["step_id"]))
    return candidates[:top]


# ── Output ───────────────────────────────────────────────────────────

def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def print_human(state: Dict[str, Any], next_steps: List[Dict[str, Any]],
                blockers: List[Dict[str, Any]], plan_path: Path,
                progress_warnings: List[str], repo_root: Path,
                scanned_logs: List[str]) -> None:
    _safe_print("NEXT_STEP SUMMARY: OK")
    _safe_print()

    _safe_print(f"-- Repo Root: {repo_root} --")
    _safe_print()

    _safe_print("-- Inputs --")
    _safe_print(f"  Plan: {plan_path.name}")
    _safe_print(f"  Progress logs scanned: {len(scanned_logs)}")
    for log_hint in scanned_logs:
        _safe_print(f"    - {log_hint}")
    _safe_print()

    _safe_print("-- Progress Snapshot --")
    _safe_print(f"  done_steps: {len(state['done'])}")
    _safe_print(f"  blocked_steps: {len(state['blocked'])}")
    _safe_print(f"  ready_steps: {len(state['ready'])}")
    _safe_print()

    if progress_warnings:
        _safe_print("-- Warnings --")
        for w in progress_warnings:
            _safe_print(f"  {w}")
        _safe_print()

    _safe_print("-- Recommended Next Steps --")
    if not next_steps:
        _safe_print("  (none ready)")
    else:
        for rec in next_steps:
            _safe_print(f"  [{rec['step_id']}] {rec['module']} | {rec['title']}")
            _safe_print(f"    Phase: {rec['phase']}")
            _safe_print(f"    Ready: {rec['reason_ready']}")
            if rec["required_evidence"]:
                _safe_print(f"    Required: {'; '.join(rec['required_evidence'])}")
            _safe_print(f"    Suggested: {rec['suggested_command']}")
            _safe_print()

    _safe_print("-- Blockers --")
    if not blockers:
        _safe_print("  (none)")
    else:
        for blk in blockers:
            _safe_print(f"  [{blk['step_id']}] {blk['module']} | {blk['title']}")
            _safe_print(f"    Blocked by: {', '.join(blk['blockers'])}")
        _safe_print()


def print_json(state: Dict[str, Any], next_steps: List[Dict[str, Any]],
               blockers: List[Dict[str, Any]], plan_path: Path,
               progress_warnings: List[str], repo_root: Path,
               scanned_logs: List[str]) -> None:
    out = {
        "summary": "OK",
        "repo_root": str(repo_root),
        "plan_path": str(plan_path),
        "scanned_logs": scanned_logs,
        "progress": {
            "done_steps": list(state["done"]),
            "blocked_steps": list(state["blocked"]),
            "ready_steps": list(state["ready"]),
        },
        "warnings": progress_warnings,
        "recommended_next": next_steps,
        "blockers": blockers,
    }
    _safe_print(json.dumps(out, indent=2, ensure_ascii=False))


# ── Main ─────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Recommend next actions based on plan + progress (Round 03)")
    parser.add_argument("--plan", type=str, default="contracts/master_plan_v1.json",
                        help="Path to plan JSON (default: contracts/master_plan_v1.json)")
    parser.add_argument("--module", type=str, default="all",
                        choices=list(VALID_MODULES),
                        help="Filter by module (default: all)")
    parser.add_argument("--top", type=int, default=5,
                        help="Number of top items to show (default: 5)")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Output structured JSON")
    parser.add_argument("--repo-root", type=str, default=None,
                        help="Repo root (default: auto-detect)")
    args = parser.parse_args(argv)

    # Repo root
    if args.repo_root:
        repo_root = Path(args.repo_root)
    else:
        repo_root = find_repo_root()
    if not repo_root:
        _safe_print("ERROR: Could not find repo root. Use --repo-root or run from repo.")
        return 1

    # Plan path
    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = repo_root / plan_path

    if not plan_path.is_file():
        _safe_print(f"ERROR: Plan not found: {plan_path}")
        return 1

    try:
        with open(plan_path, encoding="utf-8") as f:
            plan_data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        _safe_print(f"ERROR: Failed to load plan: {exc}")
        return 1

    # Scan progress
    done_ids, progress_warnings = scan_progress_logs(repo_root)

    # Compute state
    state = compute_state(plan_data, done_ids)

    # Recommendations
    next_steps = recommend_next(state, args.module, args.top)
    blockers = list_blockers(state, args.module, args.top)

    # Scanned logs hint
    scanned_logs = [
        "exports/progress/PROGRESS_LOG.jsonl",
        "modules/body/exports/progress/PROGRESS_LOG.jsonl",
        "modules/garment/exports/progress/PROGRESS_LOG.jsonl",
        "modules/fitting/exports/progress/PROGRESS_LOG.jsonl",
    ]

    if args.json_output:
        print_json(state, next_steps, blockers, plan_path, progress_warnings,
                   repo_root, scanned_logs)
    else:
        print_human(state, next_steps, blockers, plan_path, progress_warnings,
                    repo_root, scanned_logs)

    return 0


if __name__ == "__main__":
    sys.exit(main())
