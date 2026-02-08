#!/usr/bin/env python3
"""
Render hub state, events, LLM briefs, and DASHBOARD from master_plan.
Inputs: contracts/master_plan_v1.json, ops/lab_roots.local.json (optional),
  ops/run_registry.jsonl (optional), lab exports/progress/PROGRESS_LOG.jsonl,
  exports/runs/** (main + each lab root).
Outputs: ops/hub_state_v1.json, ops/hub_events_v1.jsonl (append-only newly_unlocked),
  exports/brief/LLM_SYNC_*.txt, ops/DASHBOARD.md.
Unlock logic from master_plan only (and/or/not + artifact_observed). Warn-only; no FAIL.
"""
from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]
MASTER_PLAN_PATH = REPO_ROOT / "contracts" / "master_plan_v1.json"
LAB_ROOTS_PATH = REPO_ROOT / "ops" / "lab_roots.local.json"
RUN_REGISTRY_PATH = REPO_ROOT / "ops" / "run_registry.jsonl"
HUB_STATE_PATH = REPO_ROOT / "ops" / "hub_state_v1.json"
HUB_EVENTS_PATH = REPO_ROOT / "ops" / "hub_events_v1.jsonl"
DASHBOARD_PATH = REPO_ROOT / "ops" / "DASHBOARD.md"
NOTION_SYNC_STATUS_PATH = REPO_ROOT / "ops" / "notion_sync_status.json"
BRIEF_DIR = REPO_ROOT / "exports" / "brief"
STATUS_PATH = REPO_ROOT / "ops" / "STATUS.md"

MODULES = ("body", "fitting", "garment")


def _warn(code: str, message: str) -> str:
    return f"[{code}] {message}"


def _load_master_plan() -> tuple[dict, list[str]]:
    """Load master_plan_v1.json. Returns (plan, warnings)."""
    warnings = []
    if not MASTER_PLAN_PATH.exists():
        warnings.append(_warn("SKIPPED", "master_plan not found"))
        return {}, warnings
    try:
        with open(MASTER_PLAN_PATH, encoding="utf-8") as f:
            plan = json.load(f)
    except json.JSONDecodeError as e:
        warnings.append(_warn("SKIPPED", f"master_plan invalid JSON: {e}"))
        return {}, warnings
    except Exception as e:
        warnings.append(_warn("SKIPPED", f"master_plan read failed: {e}"))
        return {}, warnings
    return plan, warnings


def _get_lab_roots() -> list[tuple[Path, str]]:
    """Lab roots: ENV then lab_roots.local.json. Returns [(Path, module), ...]."""
    roots = []
    for module in ("fitting", "garment"):
        env_key = f"{module.upper()}_LAB_ROOT"
        lab_root = os.environ.get(env_key, "").strip()
        if not lab_root and LAB_ROOTS_PATH.exists():
            try:
                with open(LAB_ROOTS_PATH, encoding="utf-8") as f:
                    cfg = json.load(f)
                lab_root = (cfg.get(env_key) or "").strip()
            except Exception:
                pass
        if lab_root:
            p = (REPO_ROOT / lab_root).resolve()
            if p.exists():
                roots.append((p, module))
    return roots


def _search_roots() -> list[Path]:
    """Search roots: REPO_ROOT + each lab root."""
    roots = [REPO_ROOT]
    for lab_root, _ in _get_lab_roots():
        roots.append(lab_root)
    return roots


def _artifact_observed(plan: dict, artifact_id: str, search_roots: list[Path]) -> bool:
    """True if any path under any search root matches artifact path_glob_any."""
    artifacts = (plan.get("artifacts") or {})
    art = artifacts.get(artifact_id)
    if not art:
        return False
    patterns = art.get("path_glob_any") or []
    if not patterns:
        return False
    for root in search_roots:
        runs_dir = root / "exports" / "runs"
        if not runs_dir.exists():
            continue
        try:
            for p in runs_dir.rglob("*"):
                if not p.is_file():
                    continue
                try:
                    rel = p.relative_to(root).as_posix()
                except ValueError:
                    continue
                for pat in patterns:
                    if fnmatch.fnmatch(rel, pat):
                        return True
        except OSError:
            continue
    return False


def _eval_logic(plan: dict, logic: dict, observed: set[str]) -> bool:
    """Evaluate logic (and/or/not + artifact_observed) against observed artifact_ids."""
    if not logic:
        return False
    t = logic.get("type")
    if t == "artifact_observed":
        aid = logic.get("artifact_id")
        return bool(aid and aid in observed)
    if t == "and":
        items = logic.get("items") or []
        return all(_eval_logic(plan, it, observed) for it in items)
    if t == "or":
        items = logic.get("items") or []
        return any(_eval_logic(plan, it, observed) for it in items)
    if t == "not":
        return not _eval_logic(plan, logic.get("item") or {}, observed)
    return False


def _compute_artifacts_observed(plan: dict, search_roots: list[Path]) -> dict[str, bool]:
    """Compute artifact_id -> observed for all artifacts in plan."""
    artifacts = plan.get("artifacts") or {}
    out = {}
    for aid in artifacts:
        out[aid] = _artifact_observed(plan, aid, search_roots)
    return out


def _compute_unlocks(plan: dict, observed_artifacts: dict[str, bool]) -> dict[str, bool]:
    """Compute unlock_id -> true/false from plan.unlocks logic."""
    unlocks = plan.get("unlocks") or []
    out = {}
    for u in unlocks:
        uid = u.get("unlock_id")
        if not uid:
            continue
        logic = u.get("logic") or {}
        out[uid] = _eval_logic(plan, logic, set(k for k, v in observed_artifacts.items() if v))
    return out


def _load_previous_hub_state() -> dict:
    """Load previous hub_state_v1.json if exists."""
    if not HUB_STATE_PATH.exists():
        return {}
    try:
        with open(HUB_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _newly_unlocked(current: dict[str, bool], previous: dict) -> list[str]:
    """Unlock IDs that are true now and were not true in previous state."""
    prev_unlocks = previous.get("unlocks") or {}
    return [uid for uid, v in current.items() if v and not prev_unlocks.get(uid)]


def _write_hub_state(plan: dict, artifacts_observed: dict[str, bool], unlocks: dict[str, bool],
                    newly: list[str], warnings: list[str]) -> None:
    """Write ops/hub_state_v1.json."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Asia/Seoul")
    except ImportError:
        tz = timezone.utc
    ts = datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S%z")
    payload = {
        "schema_version": "hub_state.v1",
        "updated_at": ts,
        "artifacts_observed": artifacts_observed,
        "unlocks": unlocks,
        "newly_unlocked": newly,
    }
    try:
        HUB_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(HUB_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        warnings.append(_warn("SKIPPED", f"hub_state write failed: {e}"))


def _append_hub_events(plan: dict, newly_unlocked: list[str], warnings: list[str]) -> None:
    """Append one line per newly_unlocked to ops/hub_events_v1.jsonl."""
    if not newly_unlocked:
        return
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Asia/Seoul")
    except ImportError:
        tz = timezone.utc
    ts = datetime.now(tz).isoformat()
    unlocks_by_id = {u["unlock_id"]: u for u in (plan.get("unlocks") or []) if u.get("unlock_id")}
    try:
        HUB_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(HUB_EVENTS_PATH, "a", encoding="utf-8") as f:
            for uid in newly_unlocked:
                u = unlocks_by_id.get(uid) or {}
                on_u = u.get("on_unlocked") or {}
                module = (on_u.get("target_agent") or "").replace("_llm", "").upper() or "N/A"
                brief_path = on_u.get("brief_path") or "N/A"
                ev = {
                    "ts": ts,
                    "event_type": "UNLOCKED",
                    "unlock_id": uid,
                    "module": module,
                    "target_agent": on_u.get("target_agent") or "N/A",
                    "brief_path": brief_path,
                }
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception as e:
        warnings.append(_warn("SKIPPED", f"hub_events append failed: {e}"))


def _write_briefs(plan: dict, unlocks_now_true: list[str], warnings: list[str]) -> None:
    """Write exports/brief/LLM_SYNC_*.txt from on_unlocked.template_ko for unlocked IDs."""
    unlocks_by_id = {u["unlock_id"]: u for u in (plan.get("unlocks") or []) if u.get("unlock_id")}
    try:
        BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        warnings.append(_warn("SKIPPED", f"brief dir failed: {e}"))
        return
    for uid in unlocks_now_true:
        u = unlocks_by_id.get(uid)
        if not u:
            continue
        on_u = u.get("on_unlocked") or {}
        template_ko = on_u.get("template_ko")
        brief_path_rel = on_u.get("brief_path")
        if not template_ko or not brief_path_rel:
            continue
        # brief_path is like "exports/brief/LLM_SYNC_FITTING_U1_READY.txt"
        full_path = REPO_ROOT / brief_path_rel
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text("\n".join(template_ko), encoding="utf-8")
        except Exception as e:
            warnings.append(_warn("SKIPPED", f"brief write {brief_path_rel}: {e}"))


def _plan_items_not_done(plan: dict, observed_artifacts: dict[str, bool]) -> list[dict]:
    """Plan items whose done_when is not satisfied."""
    items = plan.get("plan_items") or []
    out = []
    for it in items:
        done_when = it.get("done_when") or {}
        satisfied = _eval_logic(plan, done_when, set(k for k, v in observed_artifacts.items() if v))
        if not satisfied:
            out.append(it)
    return out


def _blocker_warnings(plan: dict, artifacts_observed: dict[str, bool], unlocks: dict[str, bool]) -> list[str]:
    """Minimal blocker lines: missing artifacts for unlocks not yet met."""
    lines = []
    artifacts = plan.get("artifacts") or {}
    for u in plan.get("unlocks") or []:
        uid = u.get("unlock_id")
        if unlocks.get(uid):
            continue
        logic = u.get("logic") or {}
        # Collect artifact_ids required by this unlock
        req = set()

        def collect_ids(lg):
            if not lg:
                return
            if lg.get("type") == "artifact_observed":
                aid = lg.get("artifact_id")
                if aid and not artifacts_observed.get(aid):
                    req.add(aid)
            for it in lg.get("items") or []:
                collect_ids(it)
            collect_ids(lg.get("item"))

        collect_ids(logic)
        if req:
            labels = [artifacts.get(aid, {}).get("label", aid) for aid in req]
            lines.append(f"[{uid}] 대기: {', '.join(labels)} 미관측")
    return lines


def _collect_satisfied_artifact_ids_from_logic(logic: dict, observed_set: set[str], max_items: int = 2) -> list[str]:
    """Collect artifact_ids from logic that are in observed_set (for unlock 근거)."""
    out = []

    def collect(lg):
        if not lg or len(out) >= max_items:
            return
        if lg.get("type") == "artifact_observed":
            aid = lg.get("artifact_id")
            if aid and aid in observed_set:
                out.append(aid)
        for it in lg.get("items") or []:
            collect(it)
        collect(lg.get("item"))

    collect(logic)
    return out[:max_items]


def _module_status_summary(plan: dict, artifacts_observed: dict[str, bool], blockers: list[str]) -> dict[str, str]:
    """Per-module status: OK or WARN (simplified)."""
    by_mod = {m: "OK" for m in MODULES}
    for b in blockers:
        if "FITTING" in b or "U1" in b:
            by_mod["fitting"] = "WARN"
        if "GARMENT" in b or "garment" in b.lower():
            by_mod["garment"] = "WARN"
    # If body artifact missing and needed for U1, body can be WARN
    if not artifacts_observed.get("body_subset_m0") and any("body" in b.lower() for b in blockers):
        by_mod["body"] = "WARN"
    return by_mod


def _render_notion_sync_section() -> list[str]:
    """Render Notion Sync status block for DASHBOARD top. Returns list of markdown lines."""
    if not NOTION_SYNC_STATUS_PATH.exists():
        return ["## 🔁 Notion Sync 상태", "", "Notion sync status: (no status file)", ""]
    try:
        with open(NOTION_SYNC_STATUS_PATH, encoding="utf-8") as f:
            st = json.load(f)
    except Exception:
        return ["## 🔁 Notion Sync 상태", "", "Notion sync status: (no status file)", ""]
    updated_at = st.get("updated_at", "?")
    mode = st.get("mode", "?")
    reason = st.get("reason", "?")
    processed = st.get("processed", 0)
    updated = st.get("updated", 0)
    error_count = st.get("error_count", 0)
    return [
        "## 🔁 Notion Sync 상태",
        "",
        f"`{updated_at}` | mode={mode} | reason={reason} | processed={processed} updated={updated} error_count={error_count}",
        "",
    ]


def _render_dashboard(plan: dict, artifacts_observed: dict[str, bool], unlocks: dict[str, bool],
                      newly_unlocked: list[str], warnings: list[str]) -> str:
    """Render ops/DASHBOARD.md (Korean, card-style top sections)."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Asia/Seoul")
        ts = datetime.now(tz).strftime("%Y-%m-%d %H:%M (+0900)")
    except ImportError:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M (+0900)")
    title = (plan.get("dashboard") or {}).get("title") or "Neural Vision Dashboard"
    limits = (plan.get("dashboard") or {}).get("limits") or {}
    n_new = limits.get("newly_unlocked", 10)
    n_blockers = limits.get("blockers", 10)

    lines = [
        f"# {title}",
        f"업데이트: {ts}",
        "",
        "---",
        "",
    ]
    lines.extend(_render_notion_sync_section())
    lines.extend([
        "---",
        "",
        "## ✅ 새로 언락됨 (지난 갱신 이후)",
    ])
    unlocks_list = plan.get("unlocks") or []
    by_uid = {u["unlock_id"]: u for u in unlocks_list if u.get("unlock_id")}
    observed_set = set(k for k, v in artifacts_observed.items() if v)
    artifacts = plan.get("artifacts") or {}
    newly_display = [uid for uid in newly_unlocked if uid in by_uid][:n_new]
    if not newly_display:
        lines.append("- (없음)")
    else:
        for uid in newly_display:
            u = by_uid[uid]
            on_u = u.get("on_unlocked") or {}
            brief_path = on_u.get("brief_path") if on_u else None
            target = (on_u.get("target_agent") or "").strip() or "N/A"
            lines.append(f"- {u.get('title', uid)}")
            lines.append(f"  - 대상: {target}")
            if brief_path:
                lines.append(f"  - 복붙 파일: {brief_path}")
            else:
                lines.append("  - 복붙 파일: (브리핑 없음)")
            logic = u.get("logic") or {}
            satisfied_ids = _collect_satisfied_artifact_ids_from_logic(logic, observed_set, 2)
            if satisfied_ids:
                labels = [artifacts.get(aid, {}).get("label", aid) for aid in satisfied_ids]
                lines.append(f"  - 근거: {', '.join(labels)} 관측")
            else:
                lines.append("  - 근거: (master_plan logic)")
    n_locked = limits.get("locked", 10)
    lines.extend(["", "---", "", "## ✅ 현재 해금됨(이미 언락)"])
    current_unlocked = [uid for uid in by_uid if unlocks.get(uid)]
    if not current_unlocked:
        lines.append("- (없음)")
    else:
        for uid in current_unlocked:
            u = by_uid[uid]
            on_u = u.get("on_unlocked") or {}
            brief_path = on_u.get("brief_path") if on_u else None
            target = (on_u.get("target_agent") or "").strip() or "N/A"
            lines.append(f"- {u.get('title', uid)}")
            lines.append(f"  - 대상: {target}")
            if brief_path:
                lines.append(f"  - 복붙 파일: {brief_path}")
            else:
                lines.append("  - 복붙 파일: (브리핑 없음)")
            logic = u.get("logic") or {}
            satisfied_ids = _collect_satisfied_artifact_ids_from_logic(logic, observed_set, 2)
            if satisfied_ids:
                labels = [artifacts.get(aid, {}).get("label", aid) for aid in satisfied_ids]
                lines.append(f"  - 근거: {', '.join(labels)} 관측")
            else:
                lines.append("  - 근거: (master_plan logic)")
    lines.extend(["", "---", "", "## 🔒 아직 잠김"])
    locked = [uid for uid in by_uid if not unlocks.get(uid)][:n_locked]
    if not locked:
        lines.append("- (없음)")
    else:
        for uid in locked:
            u = by_uid[uid]
            lines.append(f"- {u.get('title', uid)}")
    lines.extend(["", "---", "", "## 🚧 현재 막힌 것 / 경고 Top"])
    blockers = _blocker_warnings(plan, artifacts_observed, unlocks)[:n_blockers]
    if not blockers:
        lines.append("- (없음)")
    else:
        for b in blockers:
            lines.append(f"- {b}")
    lines.extend(["", "---", "", "## 👉 지금 할 일 (민영이가 판단할 필요 없음)"])
    not_done = _plan_items_not_done(plan, artifacts_observed)
    by_module = {}
    if not not_done:
        lines.append("- (없음)")
    for it in not_done:
        mod = (it.get("module") or "other").lower()
        by_module.setdefault(mod, []).append(it)
    max_per_mod = limits.get("next_actions_per_module") or 3
    for mod in MODULES:
        items = by_module.get(mod, [])
        if not items:
            continue
        # Sort: priority ascending (missing = 999), then plan_id
        def sort_key(it):
            p = it.get("priority")
            if p is None:
                p = 999
            return (p, it.get("plan_id") or "")
        items = sorted(items, key=sort_key)[:max_per_mod]
        lines.append(f"### {mod.capitalize()}")
        for i, it in enumerate(items, 1):
            display_text = it.get("action_ko") or it.get("title") or it.get("plan_id") or "?"
            plan_id = it.get("plan_id") or "?"
            module_val = (it.get("module") or "?").lower()
            lines.append(f"- ({i}) {display_text}  (plan_id={plan_id}, module={module_val})")
    lines.extend(["", "---", "", "## 모듈 상태 요약"])
    mod_status = _module_status_summary(plan, artifacts_observed, blockers)
    for mod in MODULES:
        st = mod_status.get(mod, "OK")
        lines.append(f"- {mod.upper()}: {st}")
    return "\n".join(lines)


def _extract_observed_paths_for_module(lab_root: Path, module: str, max_items: int = 3) -> list[str]:
    """Extract evidence paths from PROGRESS_LOG for module. Returns display paths."""
    log_path = lab_root / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    if not log_path.exists():
        return []
    mod_lower = module.lower()
    events = []
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    if ev.get("module", "").lower() == mod_lower:
                        events.append(ev)
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    seen = set()
    out = []
    for ev in events[-30:]:
        if len(out) >= max_items:
            break
        for key in ("evidence", "artifacts_touched", "evidence_paths"):
            if len(out) >= max_items:
                break
            for item in (ev.get(key) or []):
                if isinstance(item, str):
                    raw = item.split(":")[0].strip() if ":" in item else item
                    raw = raw.replace("\\", "/").strip()
                    if raw and raw not in seen:
                        seen.add(raw)
                        p = raw
                        if p.startswith("/") or (len(p) > 1 and p[1] == ":"):
                            p = Path(raw).name + " (absolute)"
                        out.append(p)
                        if len(out) >= max_items:
                            break
    return out[:max_items]


def _get_module_roots() -> list[tuple[Path, str]]:
    """(lab_root, module) including body."""
    roots = [(REPO_ROOT, "body")]
    roots.extend(_get_lab_roots())
    return roots


def _parse_status_observed_paths() -> dict[str, list[str]]:
    """Parse STATUS.md for observed_paths per module. Returns {module: [paths]}."""
    out: dict[str, list[str]] = {"body": [], "fitting": [], "garment": []}
    if not STATUS_PATH.exists():
        return out
    try:
        text = STATUS_PATH.read_text(encoding="utf-8")
    except Exception:
        return out
    import re
    for mod in ("BODY", "FITTING", "GARMENT"):
        block = re.search(
            rf"<!-- GENERATED:BEGIN:{mod} -->([\s\S]*?)<!-- GENERATED:END:{mod} -->",
            text,
        )
        if not block:
            continue
        content = block.group(1)
        in_paths = False
        for line in content.splitlines():
            stripped = line.strip()
            if "observed_paths:" in stripped:
                in_paths = True
                continue
            if in_paths and stripped.startswith("- "):
                path = stripped[2:].strip()
                if path and "/" in path and not path.endswith(":"):
                    out[mod.lower()].append(path)
            elif in_paths and stripped and not stripped.startswith("- ") and not stripped.startswith("#"):
                in_paths = False
    return out


def _render_llm_context_common(
    plan: dict,
    unlocks: dict[str, bool],
    blockers: list[str],
    warnings: list[str],
) -> str:
    """Render LLM_CONTEXT_COMMON.md (80~120 lines)."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Asia/Seoul")
        ts = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S +0900")
    except ImportError:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S +0900")

    unlocks_list = plan.get("unlocks") or []
    by_uid = {u["unlock_id"]: u for u in unlocks_list if u.get("unlock_id")}
    current_unlocked = [uid for uid in by_uid if unlocks.get(uid)]
    locked = [uid for uid in by_uid if not unlocks.get(uid)][:10]

    notion_lines = []
    if NOTION_SYNC_STATUS_PATH.exists():
        try:
            with open(NOTION_SYNC_STATUS_PATH, encoding="utf-8") as f:
                st = json.load(f)
            notion_lines = [
                "",
                "## Notion Sync",
                f"- updated_at: {st.get('updated_at', '?')}",
                f"- mode: {st.get('mode', '?')}",
            ]
        except Exception:
            notion_lines = ["", "## Notion Sync", "- (없음)"]
    else:
        notion_lines = ["", "## Notion Sync", "- (없음)"]

    blocker_top5 = blockers[:5] if blockers else ["(없음)"]

    return "\n".join([
        "# LLM Context (Common)",
        f"업데이트: {ts}",
        "",
        "<!-- generated-only: do not edit -->",
        "",
        "## 운영 헌법",
        "- SSoT: contracts/* + ops/*",
        "- labs: append-only PROGRESS_LOG + exports/runs",
        "- 메인: 판정/표면화만 담당(코드 직접 개발 X)",
        "- warn-only, FAIL 금지",
        "- roundwrap 통로 단일화(ROUND_START/ROUND_END)",
        "",
        "## 렌더러 입력 규율",
        "- PROGRESS_LOG: ts, module, step_id, event(event_type/event) 최소",
        "- STEP_ID_MISSING: UNSPECIFIED - BACKFILLED net",
        "- ROUND_END: event_type=round_end",
        "- run_minset: facts_summary.json, RUN_README.md, geometry_manifest.json 포함 원칙",
        "",
        "## 현재 전역 상태",
        "",
        "### ✅ 현재 해금됨",
        *([f"- {uid}" for uid in current_unlocked] if current_unlocked else ["- (없음)"]),
        "",
        "### 🔒 아직 잠김 (최대 10)",
        *([f"- {uid}" for uid in locked] if locked else ["- (없음)"]),
        "",
        "### 🚧 경고/블로커 Top 5",
        *[f"- {b}" for b in blocker_top5],
        *notion_lines,
        "",
        "## 금지사항",
        "- generated 파일 직접 수정 금지",
        "- append-only 로그 rewrite 금지",
        "- 계약/판정 규칙은 contract/master_plan 먼저",
        "- lab 코드는 메인이 수정/통합하지 않음(산출물로만 연결)",
    ])


def _render_llm_context_module(
    module: str,
    plan: dict,
    artifacts_observed: dict[str, bool],
    unlocks: dict[str, bool],
    not_done: list[dict],
    observed_paths: list[str],
    blockers: list[str],
) -> str:
    """Render LLM_CONTEXT_{MODULE}.md (60 lines target)."""
    mod_upper = module.upper()
    blockers_for_mod = [b for b in blockers if mod_upper in b or module in b.lower()][:5]
    status = "WARN" if blockers_for_mod else "OK"
    warn_codes = list(dict.fromkeys(b.split("]")[0].replace("[", "") for b in blockers_for_mod if "[" in b))[:5]

    unlocks_list = plan.get("unlocks") or []
    by_uid = {u["unlock_id"]: u for u in unlocks_list if u.get("unlock_id")}
    def _mod_relevant(uid: str) -> bool:
        u = by_uid.get(uid) or {}
        agent = (u.get("on_unlocked") or {}).get("target_agent", "").lower().replace("_llm", "")
        return module in agent or module in uid.lower()

    mod_unlocks_true = [uid for uid in by_uid if unlocks.get(uid) and _mod_relevant(uid)]
    mod_unlocks_false = [uid for uid in by_uid if not unlocks.get(uid) and _mod_relevant(uid)][:5]

    items = [it for it in not_done if (it.get("module") or "").lower() == module]
    items = sorted(items, key=lambda x: (x.get("priority") or 999, x.get("plan_id") or ""))[:3]

    evidence = observed_paths[:3] if observed_paths else ["(없음)"]

    return "\n".join([
        f"# LLM Context ({mod_upper})",
        "",
        "<!-- generated-only: do not edit -->",
        "",
        "## 모듈 상태",
        f"- status: {status}",
        f"- warnings: {', '.join(warn_codes) if warn_codes else '0'}",
        "",
        "## 이 모듈 관련 unlock",
        "- 현재 true: " + ", ".join(mod_unlocks_true) if mod_unlocks_true else "- 현재 true: (없음)",
        "- 아직 false: " + ", ".join(mod_unlocks_false) if mod_unlocks_false else "- 아직 false: (없음)",
        "",
        "## 👉 지금 할 일 Top 3",
        *([f"- ({i}) {it.get('action_ko') or it.get('title', '?')}  (plan_id={it.get('plan_id', '?')})" for i, it in enumerate(items, 1)] if items else ["- (없음)"]),
        "",
        "## 최근 관측 증거 Top 3",
        *[f"- {p}" for p in evidence],
        "",
        "## 세션 종료 체크리스트",
        "- ROUND_END 기록됨?",
        "- step_id 포함?",
        "- run_dir 루트 minset 존재?",
    ])


def _render_llm_context_files(
    plan: dict,
    artifacts_observed: dict[str, bool],
    unlocks: dict[str, bool],
    warnings: list[str],
) -> None:
    """Write 4 LLM_CONTEXT_*.md files to exports/brief/."""
    try:
        BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        warnings.append(_warn("SKIPPED", f"LLM context brief dir failed: {e}"))
        return
    blockers = _blocker_warnings(plan, artifacts_observed, unlocks)
    not_done = _plan_items_not_done(plan, artifacts_observed)
    status_paths = _parse_status_observed_paths()
    roots = _get_module_roots()

    common_content = _render_llm_context_common(plan, unlocks, blockers, warnings)
    try:
        (BRIEF_DIR / "LLM_CONTEXT_COMMON.md").write_text(common_content, encoding="utf-8")
    except Exception as e:
        warnings.append(_warn("SKIPPED", f"LLM_CONTEXT_COMMON write failed: {e}"))

    for lab_root, module in roots:
        paths = status_paths.get(module, [])
        if not paths:
            paths = _extract_observed_paths_for_module(lab_root, module, 3)
        content = _render_llm_context_module(
            module, plan, artifacts_observed, unlocks, not_done, paths, blockers,
        )
        try:
            (BRIEF_DIR / f"LLM_CONTEXT_{module.upper()}.md").write_text(content, encoding="utf-8")
        except Exception as e:
            warnings.append(_warn("SKIPPED", f"LLM_CONTEXT_{module.upper()} write failed: {e}"))


def main() -> int:
    warnings = []
    plan, w1 = _load_master_plan()
    warnings.extend(w1)
    if not plan:
        print("render_hub_state: SKIPPED (no master_plan); warnings=", len(warnings))
        return 0

    search_roots = _search_roots()
    artifacts_observed = _compute_artifacts_observed(plan, search_roots)
    unlocks = _compute_unlocks(plan, artifacts_observed)
    previous = _load_previous_hub_state()
    newly_unlocked = _newly_unlocked(unlocks, previous)

    _write_hub_state(plan, artifacts_observed, unlocks, newly_unlocked, warnings)
    _append_hub_events(plan, newly_unlocked, warnings)
    _write_briefs(plan, [uid for uid, v in unlocks.items() if v], warnings)

    dashboard_content = _render_dashboard(plan, artifacts_observed, unlocks, newly_unlocked, warnings)
    try:
        DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
        DASHBOARD_PATH.write_text(dashboard_content, encoding="utf-8")
    except Exception as e:
        warnings.append(_warn("SKIPPED", f"DASHBOARD write failed: {e}"))

    _render_llm_context_files(plan, artifacts_observed, unlocks, warnings)

    print(f"render_hub_state: hub_state, events, briefs, DASHBOARD, LLM context updated; warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
