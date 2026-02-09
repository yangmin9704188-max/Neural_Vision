#!/usr/bin/env python3
"""Recommend next actions based on plan + progress (level-aware)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

VALID_MODULES = {"body", "garment", "fitting", "common", "all"}
LEVELS = {"M0": 0, "M1": 1, "M2": 2}
LIFECYCLE_LEVELS = {"NONE": 0, "IMPLEMENTED": 1, "VALIDATED": 2, "CLOSED": 3}
LIFECYCLE_LABELS = {v: k for k, v in LIFECYCLE_LEVELS.items()}
M1_SIGNAL_TO_STEP = {
    "body": "B10_M1_PUBLISH",
    "garment": "G10_M1_PUBLISH",
    "fitting": "F10_M1_E2E",
}


def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


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


def _norm_level(value: Any) -> str:
    if isinstance(value, str) and value in LEVELS:
        return value
    return "M0"


def _level_ge(lhs: str, rhs: str) -> bool:
    return LEVELS.get(lhs, 0) >= LEVELS.get(rhs, 0)


def _level_max(a: str, b: str) -> str:
    return a if LEVELS.get(a, 0) >= LEVELS.get(b, 0) else b


def _scan_one_log(
    log_path: Path,
    done_levels: Dict[str, str],
    lifecycle_levels: Dict[str, int],
    warnings: List[str],
) -> None:
    if not log_path.is_file():
        return
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    warnings.append(f"WARN: parse error in {log_path.name} line {line_num}")
                    continue
                sid = obj.get("step_id")
                status = str(obj.get("status") or "").upper()
                if not isinstance(sid, str):
                    continue

                if status == "OK":
                    lvl = _norm_level(obj.get("m_level", "M0"))
                    if sid in done_levels:
                        done_levels[sid] = _level_max(done_levels[sid], lvl)
                    else:
                        done_levels[sid] = lvl

                # lifecycle capture (closure protocol)
                cur_lf = lifecycle_levels.get(sid, LIFECYCLE_LEVELS["NONE"])
                explicit = str(obj.get("lifecycle_state") or "").upper()
                if explicit in LIFECYCLE_LEVELS:
                    cur_lf = max(cur_lf, LIFECYCLE_LEVELS[explicit])
                if status in {"OK", "PASS"}:
                    cur_lf = max(cur_lf, LIFECYCLE_LEVELS["IMPLEMENTED"])

                report_ref = obj.get("validation_report_ref")
                if isinstance(report_ref, str) and report_ref.strip():
                    cur_lf = max(cur_lf, LIFECYCLE_LEVELS["VALIDATED"])
                closure_ref = obj.get("closure_spec_ref")
                if isinstance(closure_ref, str) and closure_ref.strip():
                    cur_lf = max(cur_lf, LIFECYCLE_LEVELS["CLOSED"])

                for key in ("evidence", "evidence_paths", "artifacts_touched"):
                    vals = obj.get(key)
                    if not isinstance(vals, list):
                        continue
                    for item in vals:
                        if not isinstance(item, str):
                            continue
                        norm = item.replace("\\", "/")
                        if norm.startswith("reports/validation/"):
                            cur_lf = max(cur_lf, LIFECYCLE_LEVELS["VALIDATED"])
                        if norm.startswith("contracts/closure_specs/"):
                            cur_lf = max(cur_lf, LIFECYCLE_LEVELS["CLOSED"])
                lifecycle_levels[sid] = cur_lf
    except OSError as exc:
        warnings.append(f"WARN: failed to read {log_path}: {exc}")


def scan_progress_logs(repo_root: Path) -> Tuple[Dict[str, str], Dict[str, int], List[str]]:
    """Scan PROGRESS_LOG.jsonl files, return (done_levels_map, lifecycle_levels, warnings)."""
    done_levels: Dict[str, str] = {}
    lifecycle_levels: Dict[str, int] = {}
    warnings: List[str] = []
    candidates = [
        repo_root / "exports" / "progress" / "PROGRESS_LOG.jsonl",
        repo_root / "modules" / "body" / "exports" / "progress" / "PROGRESS_LOG.jsonl",
        repo_root / "modules" / "garment" / "exports" / "progress" / "PROGRESS_LOG.jsonl",
        repo_root / "modules" / "fitting" / "exports" / "progress" / "PROGRESS_LOG.jsonl",
    ]
    for log_path in candidates:
        _scan_one_log(log_path, done_levels, lifecycle_levels, warnings)
    return done_levels, lifecycle_levels, warnings


def _scan_m1_signals(repo_root: Path, done_levels: Dict[str, str], warnings: List[str]) -> None:
    """Augment done levels from ops/signals/m1/*/LATEST.json when run dir exists."""
    for module, step_id in M1_SIGNAL_TO_STEP.items():
        sig_path = repo_root / "ops" / "signals" / "m1" / module / "LATEST.json"
        if not sig_path.is_file():
            continue
        try:
            with open(sig_path, encoding="utf-8-sig") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            warnings.append(f"WARN: failed to parse {sig_path}: {exc}")
            continue
        if not isinstance(payload, dict):
            warnings.append(f"WARN: invalid payload in {sig_path}")
            continue
        run_dir_rel = payload.get("run_dir_rel")
        if not isinstance(run_dir_rel, str) or not run_dir_rel.strip():
            warnings.append(f"WARN: missing run_dir_rel in {sig_path}")
            continue
        run_dir = (repo_root / run_dir_rel).resolve()
        if not run_dir.is_dir():
            warnings.append(f"WARN: signal run_dir missing for {sig_path}: {run_dir_rel}")
            continue
        observed = payload.get("m_level")
        lvl = observed if isinstance(observed, str) and observed in LEVELS else "M1"
        if step_id in done_levels:
            done_levels[step_id] = _level_max(done_levels[step_id], lvl)
        else:
            done_levels[step_id] = lvl


def _step_required_level(step: Dict[str, Any]) -> str:
    return _norm_level(step.get("m_level", "M0"))


def _dependency_requirements(step: Dict[str, Any]) -> Dict[str, str]:
    """Dependency min-level map from depends_on + consumes (default M0)."""
    dep_reqs: Dict[str, str] = {}
    deps = step.get("depends_on", [])
    if isinstance(deps, list):
        for dep in deps:
            if isinstance(dep, str):
                dep_reqs[dep] = "M0"

    consumes = step.get("consumes")
    if isinstance(consumes, list):
        for item in consumes:
            if not isinstance(item, dict):
                continue
            dep = item.get("from_step")
            if not isinstance(dep, str) or not dep:
                continue
            dep_reqs[dep] = _norm_level(item.get("min_level", "M0"))
    return dep_reqs


def _required_lifecycle_level(step: Dict[str, Any], plan_data: Dict[str, Any]) -> int:
    """
    Determine required lifecycle level for step completion.
    If closure contract is enabled, default requirement is CLOSED.
    """
    completion = plan_data.get("step_completion_contract")
    if not isinstance(completion, dict):
        return LIFECYCLE_LEVELS["NONE"]
    if completion.get("closure_required") is not True:
        return LIFECYCLE_LEVELS["NONE"]

    closure = step.get("closure")
    if not isinstance(closure, dict):
        return LIFECYCLE_LEVELS["CLOSED"]
    states = closure.get("lifecycle_states_required")
    if not isinstance(states, list) or not states:
        return LIFECYCLE_LEVELS["CLOSED"]
    levels = [LIFECYCLE_LEVELS.get(str(s).upper(), 0) for s in states]
    return max(levels) if levels else LIFECYCLE_LEVELS["CLOSED"]


def compute_state(
    plan_data: Dict[str, Any],
    done_levels: Dict[str, str],
    lifecycle_levels: Dict[str, int],
) -> Dict[str, Any]:
    """Compute done/ready/blocked sets + per-step state."""
    steps = plan_data.get("steps", [])
    if not isinstance(steps, list):
        return {
            "steps": [],
            "done": set(),
            "ready": set(),
            "blocked": set(),
            "step_map": {},
            "done_levels": {},
            "lifecycle_levels": {},
            "blocker_details": {},
        }

    step_map: Dict[str, Dict[str, Any]] = {}
    for step in steps:
        sid = step.get("step_id")
        if isinstance(sid, str):
            step_map[sid] = step

    all_ids = set(step_map.keys())
    done_set: Set[str] = set()
    for sid in all_ids:
        observed = done_levels.get(sid)
        if observed is None:
            continue
        required = _step_required_level(step_map[sid])
        required_lifecycle = _required_lifecycle_level(step_map[sid], plan_data)
        observed_lifecycle = lifecycle_levels.get(sid, LIFECYCLE_LEVELS["NONE"])
        if _level_ge(observed, required) and observed_lifecycle >= required_lifecycle:
            done_set.add(sid)

    ready_set: Set[str] = set()
    blocked_set: Set[str] = set()
    blocker_details: Dict[str, List[Dict[str, str]]] = {}

    for sid, step in step_map.items():
        if sid in done_set:
            continue
        dep_reqs = _dependency_requirements(step)
        unmet: List[Dict[str, str]] = []
        for dep, req_level in dep_reqs.items():
            current_level = done_levels.get(dep, "NONE")
            dep_required_lifecycle = _required_lifecycle_level(step_map.get(dep, {}), plan_data)
            dep_current_lifecycle = lifecycle_levels.get(dep, LIFECYCLE_LEVELS["NONE"])
            dep_ok = dep in done_set and current_level != "NONE" and _level_ge(current_level, req_level)
            if not dep_ok:
                unmet.append({
                    "from_step": dep,
                    "required_min_level": req_level,
                    "current_level": current_level,
                    "required_lifecycle": LIFECYCLE_LABELS.get(dep_required_lifecycle, "NONE"),
                    "current_lifecycle": LIFECYCLE_LABELS.get(dep_current_lifecycle, "NONE"),
                })
        if unmet:
            blocked_set.add(sid)
            blocker_details[sid] = unmet
        else:
            ready_set.add(sid)

    filtered_levels = {sid: lvl for sid, lvl in done_levels.items() if sid in all_ids}
    return {
        "steps": steps,
        "step_map": step_map,
        "done": done_set,
        "ready": ready_set,
        "blocked": blocked_set,
        "done_levels": filtered_levels,
        "lifecycle_levels": lifecycle_levels,
        "blocker_details": blocker_details,
    }


def recommend_next(state: Dict[str, Any], module_filter: str, top: int) -> List[Dict[str, Any]]:
    ready_ids = state["ready"]
    step_map = state["step_map"]
    candidates: List[Dict[str, Any]] = []
    for sid in ready_ids:
        step = step_map.get(sid, {})
        mod = step.get("module", "")
        if module_filter != "all" and mod != module_filter:
            continue

        unlock = step.get("unlock", {})
        req_u1 = unlock.get("requires_u1", False)
        req_u2 = unlock.get("requires_u2", False)
        req_evidence = []
        if req_u1:
            req_evidence.append("U1 validators must pass")
        if req_u2:
            req_evidence.append("U2 smokes must pass")
        closure = step.get("closure")
        if isinstance(closure, dict):
            vpath = closure.get("validation_report_path")
            cpath = closure.get("closure_spec_path")
            if isinstance(vpath, str) and vpath:
                req_evidence.append(f"Validation report required: {vpath}")
            if isinstance(cpath, str) and cpath:
                req_evidence.append(f"Closure spec required: {cpath}")

        commands = step.get("commands", [])
        candidates.append({
            "step_id": sid,
            "module": mod,
            "phase": step.get("phase", ""),
            "title": step.get("title", ""),
            "reason_ready": "All dependencies met",
            "required_evidence": req_evidence,
            "suggested_command": commands[0] if commands else "N/A",
        })
    candidates.sort(key=lambda x: (x["phase"], x["step_id"]))
    return candidates[:top]


def list_blockers(state: Dict[str, Any], module_filter: str, top: int) -> List[Dict[str, Any]]:
    blocked_ids = state["blocked"]
    step_map = state["step_map"]
    detail_map = state["blocker_details"]
    candidates: List[Dict[str, Any]] = []
    for sid in blocked_ids:
        step = step_map.get(sid, {})
        mod = step.get("module", "")
        if module_filter != "all" and mod != module_filter:
            continue
        details = detail_map.get(sid, [])
        candidates.append({
            "step_id": sid,
            "module": mod,
            "phase": step.get("phase", ""),
            "title": step.get("title", ""),
            "blockers": [d["from_step"] for d in details],
            "blocker_levels": details,
        })
    candidates.sort(key=lambda x: (x["phase"], x["step_id"]))
    return candidates[:top]


def print_human(state: Dict[str, Any], next_steps: List[Dict[str, Any]],
                blockers: List[Dict[str, Any]], plan_path: Path,
                warnings: List[str], repo_root: Path,
                scanned_logs: List[str]) -> None:
    _safe_print("NEXT_STEP SUMMARY: OK")
    _safe_print()
    _safe_print(f"-- Repo Root: {repo_root} --")
    _safe_print()
    _safe_print("-- Inputs --")
    _safe_print(f"  Plan: {plan_path.name}")
    _safe_print(f"  Progress logs scanned: {len(scanned_logs)}")
    for hint in scanned_logs:
        _safe_print(f"    - {hint}")
    _safe_print()
    _safe_print("-- Progress Snapshot --")
    _safe_print(f"  done_steps: {len(state['done'])}")
    _safe_print(f"  blocked_steps: {len(state['blocked'])}")
    _safe_print(f"  ready_steps: {len(state['ready'])}")
    _safe_print()

    if warnings:
        _safe_print("-- Warnings --")
        for w in warnings:
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
            if blk.get("blocker_levels"):
                for detail in blk["blocker_levels"]:
                    _safe_print(
                        "    Blocked by: "
                        f"{detail['from_step']} (need>={detail['required_min_level']}, current={detail['current_level']}; "
                        f"need_lifecycle>={detail.get('required_lifecycle','NONE')}, "
                        f"current_lifecycle={detail.get('current_lifecycle','NONE')})"
                    )
            else:
                _safe_print(f"    Blocked by: {', '.join(blk['blockers'])}")
        _safe_print()


def print_json(state: Dict[str, Any], next_steps: List[Dict[str, Any]],
               blockers: List[Dict[str, Any]], plan_path: Path,
               warnings: List[str], repo_root: Path,
               scanned_logs: List[str]) -> None:
    out = {
        "summary": "OK",
        "repo_root": str(repo_root),
        "plan_path": str(plan_path),
        "scanned_logs": scanned_logs,
        "progress": {
            "done_steps": sorted(state["done"]),
            "blocked_steps": sorted(state["blocked"]),
            "ready_steps": sorted(state["ready"]),
        },
        "done_levels": state["done_levels"],
        "lifecycle_levels": state.get("lifecycle_levels", {}),
        "warnings": warnings,
        "recommended_next": next_steps,
        "blockers": blockers,
    }
    _safe_print(json.dumps(out, indent=2, ensure_ascii=False))


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

    repo_root = Path(args.repo_root) if args.repo_root else find_repo_root()
    if not repo_root:
        _safe_print("ERROR: Could not find repo root. Use --repo-root or run from repo.")
        return 1

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

    done_levels, lifecycle_levels, progress_warnings = scan_progress_logs(repo_root)
    _scan_m1_signals(repo_root, done_levels, progress_warnings)
    state = compute_state(plan_data, done_levels, lifecycle_levels)
    next_steps = recommend_next(state, args.module, args.top)
    blockers = list_blockers(state, args.module, args.top)

    scanned_logs = [
        "exports/progress/PROGRESS_LOG.jsonl",
        "modules/body/exports/progress/PROGRESS_LOG.jsonl",
        "modules/garment/exports/progress/PROGRESS_LOG.jsonl",
        "modules/fitting/exports/progress/PROGRESS_LOG.jsonl",
    ]

    if args.json_output:
        print_json(state, next_steps, blockers, plan_path, progress_warnings, repo_root, scanned_logs)
    else:
        print_human(state, next_steps, blockers, plan_path, progress_warnings, repo_root, scanned_logs)
    return 0


if __name__ == "__main__":
    sys.exit(main())

