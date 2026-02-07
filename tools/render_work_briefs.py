#!/usr/bin/env python3
"""
Render WORK_BRIEF.md from PROGRESS_LOG.jsonl per lab.
Inputs: lab roots (ENV + lab_roots.local.json), PLAN_v0.yaml, PROGRESS_LOG.jsonl.
Outputs: <lab_root>/exports/brief/{BODY,FITTING,GARMENT}_WORK_BRIEF.md
Exit 0 always; failures surface as warnings in brief.
"""
import json
import os
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "docs" / "ops" / "dashboard_legacy" / "PLAN_v0.yaml"
LAB_ROOTS_PATH = REPO_ROOT / "ops" / "lab_roots.local.json"

MODULES = ("body", "fitting", "garment")
BRIEF_HEADER_KEYS = (
    "module", "updated_at", "run_id", "phase", "status",
    "summary", "artifacts", "warnings", "next", "owner"
)


def _get_lab_roots() -> dict[str, Path]:
    """Lab roots: ENV > lab_roots.local.json. Body = repo root."""
    roots = {"body": REPO_ROOT}
    from_env = {
        "fitting": os.environ.get("FITTING_LAB_ROOT", "").strip(),
        "garment": os.environ.get("GARMENT_LAB_ROOT", "").strip(),
    }
    for k, v in from_env.items():
        if v:
            roots[k] = Path(v).resolve()
        else:
            roots[k] = None

    if roots.get("fitting") is None or roots.get("garment") is None:
        if LAB_ROOTS_PATH.exists():
            try:
                with open(LAB_ROOTS_PATH, encoding="utf-8") as f:
                    cfg = json.load(f)
                for k in ("fitting", "garment"):
                    if roots.get(k) is None and cfg.get(f"{k.upper()}_LAB_ROOT"):
                        roots[k] = (REPO_ROOT / cfg[f"{k.upper()}_LAB_ROOT"]).resolve()
            except Exception:
                pass

    return roots


def _load_plan() -> dict:
    """Load PLAN_v0.yaml (read-only)."""
    if not PLAN_PATH.exists():
        return {}
    try:
        import yaml
        with open(PLAN_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return {}
    except Exception:
        return {}


def _plan_dod_total(plan: dict, module: str, step_id: str) -> int | None:
    """Get dod.total for step from PLAN."""
    mods = plan.get("modules", {})
    steps = mods.get(module, {}).get("steps", [])
    for s in steps:
        if s.get("id") == step_id:
            dod = s.get("dod", {})
            return dod.get("total")
    return None


def _parse_progress_log(log_path: Path) -> tuple[list[dict], list[str]]:
    """Parse PROGRESS_LOG.jsonl. Returns events, warnings."""
    events = []
    warnings = []
    if not log_path.exists():
        return events, warnings
    try:
        for i, line in enumerate(log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                events.append(ev)
            except json.JSONDecodeError as e:
                warnings.append(f"parse_fail:L{i}:{e}")
    except Exception as e:
        warnings.append(f"read_fail:{e}")
    return events, warnings


def _aggregate_by_module(events: list[dict], plan: dict) -> dict[str, dict]:
    """Per module: dod_done, last_event_ts, last_step_id, last_note, warnings."""
    by_mod: dict[str, dict] = {m: {"dod_done": 0, "last_ts": None, "last_step": None, "last_note": None, "by_step": {}, "warnings": []} for m in MODULES}

    for ev in events:
        mod = ev.get("module", "").lower()
        if mod not in by_mod:
            continue
        step_id = ev.get("step_id")
        delta = ev.get("dod_done_delta", 0)
        total = ev.get("dod_total")
        ts = ev.get("ts")
        note = ev.get("note", "")

        if step_id:
            cur = by_mod[mod]["by_step"].setdefault(step_id, {"done": 0, "total": total or 0, "ts": ts, "note": note})
            cur["done"] += delta
            if total is not None:
                cur["total"] = total
            if ts:
                cur["ts"] = ts
            cur["note"] = note or cur.get("note")
            by_mod[mod]["dod_done"] += delta
            if ts:
                by_mod[mod]["last_ts"] = ts
            by_mod[mod]["last_step"] = step_id
            by_mod[mod]["last_note"] = note or by_mod[mod]["last_note"]

            exp_total = _plan_dod_total(plan, mod, step_id)
            if exp_total is not None and cur["done"] > exp_total:
                by_mod[mod]["warnings"].append(f"dod_over:{step_id}:done={cur['done']}>total={exp_total}")
        if step_id == "UNSPECIFIED":
            by_mod[mod]["warnings"].append("STEP_ID_MISSING")

    return by_mod


def _render_brief(module: str, lab_root: Path, agg: dict, all_warnings: list[str]) -> str:
    """Render WORK_BRIEF.md content with fixed header."""
    try:
        from zoneinfo import ZoneInfo
        ts = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S +0900")
    except ImportError:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S +0900")

    last_step = agg.get("last_step") or "N/A"
    dod_done = agg.get("dod_done", 0)
    last_note = (agg.get("last_note") or "")[:120]
    warns = agg.get("warnings", []) + all_warnings
    status = "WARN" if warns else "OK"
    summary = f"last_step={last_step} dod_done={dod_done}"
    if last_note:
        summary = f"{summary} | {last_note[:80]}"
    summary = summary[:120]
    warnings_str = ",".join(warns[:5]) if warns else "0"
    next_line = f"Continue step {last_step}" if last_step != "N/A" else "Configure lab roots and PROGRESS_LOG"

    lines = [
        "# " + module.upper() + " Work Brief",
        "",
        "<!-- generated-only: do not edit by hand. Rendered from PROGRESS_LOG.jsonl -->",
        "",
        f"module: {module}",
        f"updated_at: {ts}",
        "run_id: N/A",
        "phase: N/A",
        f"status: {status}",
        f"summary: {summary}",
        "artifacts: N/A",
        f"warnings: {warnings_str}",
        f"next: {next_line[:120]}",
        "owner: N/A",
        "---",
        "",
        "## Generated from PROGRESS_LOG.jsonl",
        "",
        f"- last_step_id: {last_step}",
        f"- dod_done_cumulative: {dod_done}",
        f"- last_event_ts: {agg.get('last_ts') or 'N/A'}",
    ]
    if warns:
        lines.append("- warnings:")
        for w in warns[:5]:
            lines.append(f"  - {w}")
    return "\n".join(lines)


def _write_brief(lab_root: Path, module: str, content: str) -> list[str]:
    """Write brief to lab_root/exports/brief/<MODULE>_WORK_BRIEF.md. Returns warnings."""
    warnings = []
    brief_dir = lab_root / "exports" / "brief"
    brief_path = brief_dir / f"{module.upper()}_WORK_BRIEF.md"
    try:
        brief_dir.mkdir(parents=True, exist_ok=True)
        brief_path.write_text(content, encoding="utf-8")
    except Exception as e:
        warnings.append(f"write_fail:{e}")
    return warnings


def main() -> int:
    roots = _get_lab_roots()
    plan = _load_plan()
    total_warnings = []

    for module in MODULES:
        lab_root = roots.get(module)
        if lab_root is None or not lab_root.exists():
            if module != "body":
                total_warnings.append(f"lab_root_missing:{module}")
            continue

        log_path = lab_root / "exports" / "progress" / "PROGRESS_LOG.jsonl"
        events, parse_warns = _parse_progress_log(log_path)
        total_warnings.extend(parse_warns)

        agg_map = _aggregate_by_module(events, plan)
        agg = agg_map.get(module, {"dod_done": 0, "last_step": None, "last_ts": None, "last_note": None, "warnings": []})

        content = _render_brief(module, lab_root, agg, parse_warns)
        write_warns = _write_brief(lab_root, module, content)
        total_warnings.extend(write_warns)

    n = len(total_warnings)
    print(f"rendered work briefs (body/fitting/garment), warnings={n}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
