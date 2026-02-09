#!/usr/bin/env python3
"""
Render ops/STATUS.md BODY/FITTING/GARMENT generated sections.
BODY: curated + geo runs. FITTING/GARMENT: external lab briefs (read-only).
Exit 0 always; failures surface as Warnings.
Atomic write, stable warnings, text normalization.
"""
import json
import os
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone

REPO_ROOT = Path(__file__).resolve().parents[1]
MASTER_PLAN_PATH = REPO_ROOT / "contracts" / "master_plan_v1.json"
STATUS_SOURCE_POLICY_PATH = REPO_ROOT / "contracts" / "status_source_policy_v1.json"
STATUS_REFRESH_SLA_PATH = REPO_ROOT / "contracts" / "status_refresh_sla_v1.json"

# Path classification for observed_paths (priority order: lower = higher priority)
PATH_PRIORITY = {"RUN_EVIDENCE": 0, "MANIFEST": 1, "OTHER": 2, "SAMPLE": 3}
OPS_STATUS = REPO_ROOT / "ops" / "STATUS.md"
LAB_ROOTS_PATH = REPO_ROOT / "ops" / "lab_roots.local.json"
NON_BLOCKER_GATE_CODES = {"GARMENT_ASSET_MISSING"}

# Warning format: [CODE] message | path=<path or N/A> OR expected=<hint_path>
def _warn(code: str, message: str, path: str = "N/A") -> str:
    """Format warning: [CODE] message | path=<path>"""
    return f"[{code}] {message} | path={path}"


def _warn_dep(code: str, message: str, hint_path: str | None = None) -> str:
    """Format dependency warning: use expected=hint_path when hint_path given, else path=N/A."""
    if hint_path and hint_path.strip():
        return f"[{code}] {message} | expected={hint_path.strip()}"
    return f"[{code}] {message} | path=N/A"


def _warn_m1(dep_id: str, hint_path: str, detail: str) -> str:
    """Format M1 check failure: [M1_CHECK_FAILED] dependency | id=...; expected=...; detail=..."""
    return f"[M1_CHECK_FAILED] dependency | id={dep_id}; expected={hint_path}; detail={detail}"


def _sort_warnings(warnings: list[str]) -> list[str]:
    """Sort by CODE then path/expected/id for stable diff."""
    def key(w: str) -> tuple:
        m = re.match(r"\[([^\]]+)\].*\| (?:path|expected|id)=([^;]*)(?:;|$)", w)
        if m:
            return (m.group(1), (m.group(2) or "").strip())
        m2 = re.match(r"\[([^\]]+)\].*", w)
        if m2:
            return (m2.group(1), w)
        return (w, "")

    return sorted(warnings, key=key)


def _normalize_line(line: str) -> str:
    """CRLF/LF -> LF, tab -> 2 spaces, strip trailing."""
    s = line.replace("\r\n", "\n").replace("\r", "\n").expandtabs(2)
    return s.rstrip()


def _normalize_lines(lines: list[str]) -> list[str]:
    return [_normalize_line(ln) for ln in lines]


def _load_status_source_policy() -> dict:
    """Load status source policy contract. Returns defaults on failure."""
    default = {
        "policy_version": "status_source_policy.v1",
        "status_selection_rule": {
            "type": "latest_updated_at",
            "fallback_order": ["work_brief_progress_log", "smoke_status_summary"],
        },
        "dashboard_noise_policy": {
            "hide_raw_paths": True,
            "show_path_class_counts": True,
        },
    }
    if not STATUS_SOURCE_POLICY_PATH.exists():
        return default
    try:
        with open(STATUS_SOURCE_POLICY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            default.update(data)
    except Exception:
        pass
    return default


def _load_status_refresh_sla() -> dict:
    default = {
        "sla_version": "status_refresh_sla.v1",
        "module_status_sla": {
            "body": {"max_status_age_minutes": 240},
            "fitting": {"max_status_age_minutes": 240},
            "garment": {"max_status_age_minutes": 240},
        },
        "enforcement": {"stale_status": "warn"},
    }
    if not STATUS_REFRESH_SLA_PATH.exists():
        return default
    try:
        with open(STATUS_REFRESH_SLA_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            default.update(data)
    except Exception:
        pass
    return default


def _parse_any_ts(ts_value: str | None) -> datetime | None:
    """Parse timestamp variants used in briefs/summaries/signals into aware datetime."""
    if not isinstance(ts_value, str) or not ts_value.strip():
        return None
    s = ts_value.strip()
    # ISO forms, including trailing Z
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    # Brief style: 2026-02-10 00:26:08 or with +0900
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone(timedelta(hours=9)))
            return dt
        except Exception:
            continue
    return None


def _to_utc_iso(dt: datetime | None) -> str:
    if not dt:
        return "N/A"
    try:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return "N/A"


MARKERS = {
    "BLOCKERS": ("<!-- GENERATED:BEGIN:BLOCKERS -->", "<!-- GENERATED:END:BLOCKERS -->"),
    "M1_SIGNALS": ("<!-- GENERATED:BEGIN:M1_SIGNALS -->", "<!-- GENERATED:END:M1_SIGNALS -->"),
    "BODY": ("<!-- GENERATED:BEGIN:BODY -->", "<!-- GENERATED:END:BODY -->"),
    "FITTING": ("<!-- GENERATED:BEGIN:FITTING -->", "<!-- GENERATED:END:FITTING -->"),
    "GARMENT": ("<!-- GENERATED:BEGIN:GARMENT -->", "<!-- GENERATED:END:GARMENT -->"),
}


def _load_master_plan() -> dict:
    if not MASTER_PLAN_PATH.exists():
        return {}
    try:
        with open(MASTER_PLAN_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _module_steps_and_closure(master_plan: dict, module: str) -> tuple[set[str], dict[str, dict]]:
    step_ids: set[str] = set()
    closure_map: dict[str, dict] = {}
    for step in master_plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        if (step.get("module") or "").lower() != module.lower():
            continue
        sid = step.get("step_id")
        if not isinstance(sid, str) or not sid:
            continue
        step_ids.add(sid)
        closure = step.get("closure")
        if isinstance(closure, dict):
            closure_map[sid] = closure
    return step_ids, closure_map


def _extract_event_paths(ev: dict) -> set[str]:
    out: set[str] = set()
    for key in ("evidence", "evidence_paths", "artifacts_touched"):
        val = ev.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    out.add(item.strip().replace("\\", "/"))
    for key in ("closure_spec_ref", "validation_report_ref"):
        val = ev.get(key)
        if isinstance(val, str) and val.strip():
            out.add(val.strip().replace("\\", "/"))
    return out


def _compute_lifecycle_snapshot(events: list[dict], step_ids: set[str], closure_map: dict[str, dict]) -> dict:
    """Compute lifecycle counters from progress events + closure paths."""
    order = {"NONE": 0, "IMPLEMENTED": 1, "VALIDATED": 2, "CLOSED": 3}
    state_by_step = {sid: 0 for sid in step_ids}

    for ev in events:
        sid = ev.get("step_id")
        if sid not in step_ids:
            continue
        state = state_by_step.get(sid, 0)
        status = str(ev.get("status") or "").upper()
        lifecycle_state = str(ev.get("lifecycle_state") or "").upper()
        paths = _extract_event_paths(ev)
        if status in {"OK", "PASS"}:
            state = max(state, order["IMPLEMENTED"])
        if lifecycle_state in order:
            state = max(state, order[lifecycle_state])

        closure = closure_map.get(sid) or {}
        report_path = str(closure.get("validation_report_path") or "").replace("\\", "/")
        spec_path = str(closure.get("closure_spec_path") or "").replace("\\", "/")
        has_report = any(p.startswith("reports/validation/") for p in paths)
        has_spec = any(p.startswith("contracts/closure_specs/") for p in paths)
        if report_path and report_path in paths:
            has_report = True
        if spec_path and spec_path in paths:
            has_spec = True
        if has_report:
            state = max(state, order["VALIDATED"])
        if has_spec:
            state = max(state, order["CLOSED"])
        state_by_step[sid] = state

    total = len(step_ids)
    implemented = sum(1 for v in state_by_step.values() if v >= order["IMPLEMENTED"])
    validated = sum(1 for v in state_by_step.values() if v >= order["VALIDATED"])
    closed = sum(1 for v in state_by_step.values() if v >= order["CLOSED"])
    pending = max(0, total - implemented)
    next_validate = sorted([sid for sid, v in state_by_step.items() if v == order["IMPLEMENTED"]])[:5]
    next_close = sorted([sid for sid, v in state_by_step.items() if v == order["VALIDATED"]])[:5]
    return {
        "total": total,
        "implemented": implemented,
        "validated": validated,
        "closed": closed,
        "pending": pending,
        "next_validate": next_validate,
        "next_close": next_close,
    }


def _empty_lifecycle(total: int = 0) -> dict:
    return {
        "total": total,
        "implemented": 0,
        "validated": 0,
        "closed": 0,
        "pending": total,
        "next_validate": [],
        "next_close": [],
    }


def _parse_run_log(run_log_path: Path) -> dict:
    """Parse RUN_LOG.txt for rows/cols/warnings. Returns dict with rows, cols, warnings."""
    out = {"rows": None, "cols": None, "warnings": []}
    try:
        text = run_log_path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"Rows?:\s*(\d+)", text, re.I)
        if m:
            out["rows"] = int(m.group(1))
        m = re.search(r"Columns?:\s*(\d+)", text, re.I)
        if m:
            out["cols"] = int(m.group(1))
    except Exception as e:
        out["warnings"].append(_warn("RUN_LOG_PARSE_FAIL", str(e), str(run_log_path)))
    return out


def _latest_curated() -> tuple[dict, list[str]]:
    out = {
        "run_dir": "N/A",
        "run_id": "N/A",
        "rows": None,
        "cols": None,
        "parquet_path": "N/A",
        "parquet_size": None,
        "run_log_path": "N/A",
    }
    warnings = []
    base = REPO_ROOT / "data" / "derived" / "curated_v0"
    if not base.exists():
        warnings.append(_warn("CURATED_NOT_FOUND", "data/derived/curated_v0 not found", "N/A"))
        return out, warnings

    parquets = list(base.rglob("curated_v0.parquet"))
    if not parquets:
        warnings.append(_warn("CURATED_PARQUET_NOT_FOUND", "no curated_v0.parquet found", str(base)))
        return out, warnings

    latest_parquet = max(parquets, key=lambda p: p.stat().st_mtime)
    latest_dir = latest_parquet.parent
    run_id = latest_dir.relative_to(base).as_posix()
    out["run_id"] = run_id
    out["run_dir"] = f"data/derived/curated_v0/{run_id}"
    out["parquet_path"] = str(latest_parquet.relative_to(REPO_ROOT).as_posix())

    run_log = latest_dir / "RUN_LOG.txt"
    if run_log.exists():
        out["run_log_path"] = run_log.relative_to(REPO_ROOT).as_posix()
        parsed = _parse_run_log(run_log)
        if parsed["rows"] is not None:
            out["rows"] = parsed["rows"]
        if parsed["cols"] is not None:
            out["cols"] = parsed["cols"]
        warnings.extend(parsed["warnings"])

    if out["rows"] is None or out["cols"] is None:
        try:
            import pyarrow.parquet as pq
            meta = pq.read_metadata(latest_parquet)
            if out["rows"] is None:
                out["rows"] = meta.num_rows
            if out["cols"] is None:
                out["cols"] = meta.num_columns
        except ImportError:
            try:
                import pandas as pd
                df = pd.read_parquet(latest_parquet, columns=[])
                if out["rows"] is None:
                    out["rows"] = len(df)
                if out["cols"] is None:
                    out["cols"] = len(df.columns)
            except Exception as e:
                warnings.append(_warn("CURATED_PARQUET_META_FAIL", str(e), str(latest_parquet)))
        except Exception as e:
            warnings.append(_warn("CURATED_PARQUET_META_FAIL", str(e), str(latest_parquet)))

    if latest_parquet.exists():
        out["parquet_size"] = latest_parquet.stat().st_size

    return out, warnings


def _latest_geo() -> tuple[dict, list[str]]:
    out = {
        "path": "N/A",
        "schema_version": None,
        "total": None,
        "processed": None,
        "skipped": None,
        "manifest_duplicate_case_id_count": None,
        "record_missing_count": None,
        "processed_sink_count": None,
    }
    warnings = []
    base = REPO_ROOT / "exports" / "runs"
    if not base.exists():
        warnings.append(_warn("GEO_FACTS_NOT_FOUND", "exports/runs not found", str(base)))
        return out, warnings

    files = list(base.rglob("facts_summary.json"))
    if not files:
        warnings.append(_warn("GEO_FACTS_NOT_FOUND", "no facts_summary.json found", str(base)))
        return out, warnings

    latest = max(files, key=lambda p: p.stat().st_mtime)
    out["path"] = str(latest.relative_to(REPO_ROOT).as_posix())

    try:
        with open(latest, encoding="utf-8") as f:
            data = json.load(f)
        out["schema_version"] = data.get("schema_version")
        out["total"] = data.get("total_cases")
        out["processed"] = data.get("processed_cases")
        out["skipped"] = data.get("skipped_cases")
        out["manifest_duplicate_case_id_count"] = data.get("manifest_duplicate_case_id_count")
        out["record_missing_count"] = data.get("record_missing_count")
        out["processed_sink_count"] = data.get("processed_sink_count")
    except Exception as e:
        warnings.append(_warn("GEO_FACTS_PARSE_FAIL", str(e), str(latest)))

    return out, warnings


def _latest_body_progress(max_items: int = 3) -> list[dict]:
    """Read PROGRESS_LOG.jsonl, filter module=body, return last max_items events (facts-only)."""
    log_path = REPO_ROOT / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    if not log_path.exists():
        return []
    events = []
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    if ev.get("module") == "body":
                        events.append(ev)
                except json.JSONDecodeError:
                    continue
        return events[-max_items:] if events else []
    except Exception:
        return []


def _render_body(
    curated: dict,
    geo: dict,
    warnings: list[str],
    *,
    body_progress: list[dict] | None = None,
    lifecycle: dict | None = None,
) -> str:
    try:
        from zoneinfo import ZoneInfo
        ts = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    except ImportError:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [f"*Updated: {ts}*", ""]
    nw = len(warnings)
    health = "OK (warnings=0)" if nw == 0 else f"WARN (warnings={nw})"
    lines.append(f"- health: {health}")
    if nw > 0:
        top3 = _sort_warnings(warnings)[:3]
        lines.append(f"- health_summary: {'; '.join(top3)}")
    if lifecycle:
        lines.append(f"- lifecycle_total_steps: {lifecycle.get('total', 0)}")
        lines.append(f"- lifecycle_implemented: {lifecycle.get('implemented', 0)}")
        lines.append(f"- lifecycle_validated: {lifecycle.get('validated', 0)}")
        lines.append(f"- lifecycle_closed: {lifecycle.get('closed', 0)}")
        lines.append(f"- lifecycle_pending: {lifecycle.get('pending', 0)}")
        if lifecycle.get("next_validate"):
            lines.append(f"- next_validate: {', '.join(lifecycle['next_validate'])}")
        if lifecycle.get("next_close"):
            lines.append(f"- next_close: {', '.join(lifecycle['next_close'])}")
    lines.append("")

    lines.append("### Curated ingest")
    lines.append(f"- run_dir: {curated['run_dir']}")
    if curated["rows"] is not None and curated["cols"] is not None:
        lines.append(f"- curated_v0.parquet: {curated['rows']} rows, {curated['cols']} cols")
        if curated["parquet_size"]:
            lines.append(f"  - path: {curated['parquet_path']} ({curated['parquet_size']:,} bytes)")
        else:
            lines.append(f"  - path: {curated['parquet_path']}")
    else:
        lines.append(f"- curated_v0.parquet: N/A (path: {curated['parquet_path']})")
    lines.append(f"- RUN_LOG: {curated['run_log_path']}")
    lines.append("")

    lines.append("### Geo runner facts")
    lines.append(f"- facts_summary: {geo['path']}")
    if geo["total"] is not None or geo["processed"] is not None or geo["skipped"] is not None:
        parts = []
        if geo["total"] is not None:
            parts.append(f"total={geo['total']}")
        if geo["processed"] is not None:
            parts.append(f"processed={geo['processed']}")
        if geo["skipped"] is not None:
            parts.append(f"skipped={geo['skipped']}")
        lines.append(f"  - {' '.join(parts)}")
        opts = []
        if geo.get("manifest_duplicate_case_id_count") is not None:
            opts.append(f"duplicates={geo['manifest_duplicate_case_id_count']}")
        if geo.get("record_missing_count") is not None:
            opts.append(f"missing={geo['record_missing_count']}")
        if geo.get("processed_sink_count") is not None:
            opts.append(f"sink={geo['processed_sink_count']}")
        if opts:
            lines.append(f"  - {', '.join(opts)}")
    else:
        lines.append("  - N/A")
    lines.append("")

    if body_progress:
        lines.append("### Latest progress")
        for ev in body_progress:
            note = ev.get("note", "")
            step_id = ev.get("step_id", "N/A")
            ts = ev.get("ts", "N/A")
            if note:
                lines.append(f"- [{step_id}] {ts}: {note}")
        lines.append("")

    if warnings:
        lines.append("### Warnings")
        for w in _sort_warnings(warnings):
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


def _read_lab_progress_events(lab_root: Path, module: str, max_events: int = 50) -> list[dict]:
    """Read last max_events from lab PROGRESS_LOG for module."""
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
    return events[-max_events:]


def _compute_progress_hygiene(lab_root: Path, module: str) -> list[str]:
    """Compute STALE_PROGRESS, STEP_STUCK, EVENT_THIN from last 10 events."""
    events = _read_lab_progress_events(lab_root, module, max_events=10)
    codes = []
    if not events:
        return codes
    # STALE_PROGRESS: last event ts older than 24h
    try:
        last_ts = events[-1].get("ts")
        if last_ts:
            try:
                dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            except Exception:
                dt = None
            if dt:
                now = datetime.now(timezone.utc)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if (now - dt) > timedelta(hours=24):
                    codes.append("STALE_PROGRESS")
    except Exception:
        pass
    # STEP_STUCK: all 10 have same step_id
    if len(events) >= 5:
        step_ids = [ev.get("step_id", "") for ev in events]
        if len(set(step_ids)) == 1 and step_ids[0]:
            codes.append("STEP_STUCK")
    # EVENT_THIN: 7+ of 10 have note len < 12
    if len(events) >= 7:
        thin = sum(1 for ev in events if len((ev.get("note") or "")) < 12)
        if thin >= 7:
            codes.append("EVENT_THIN")
    return codes


def _extract_gate_codes_from_events(events: list[dict]) -> list[str]:
    """Extract gate codes from gate_code, gate_codes, or [CODE] in warnings."""
    codes = []
    for ev in events:
        for key in ("gate_code", "gate_codes"):
            val = ev.get(key)
            if isinstance(val, str) and val:
                codes.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item:
                        codes.append(item)
        for w in ev.get("warnings") or []:
            if isinstance(w, str) and w.startswith("[") and "]" in w:
                m = re.match(r"\[([^\]]+)\]", w)
                if m:
                    codes.append(m.group(1))
    return codes


def _extract_round_end_fail_gate_codes(lab_root: Path, module: str, max_events: int = 200) -> list[str]:
    """
    Extract gate codes from FAIL round_end events in module progress log.
    Used to surface fail-fast producer signals (e.g. RUN_MANIFEST_ROOT_MISSING) in STATUS.
    """
    events = _read_lab_progress_events(lab_root, module, max_events=max_events)
    out: list[str] = []
    for ev in events:
        status = str(ev.get("status") or "").upper()
        if status != "FAIL":
            continue
        et = str(ev.get("event_type") or ev.get("event") or "").lower()
        if et != "round_end":
            continue
        for code in _extract_gate_codes_from_events([ev]):
            if code:
                out.append(code)
    # Stable dedupe while preserving first occurrence.
    return list(dict.fromkeys(out))


def _aggregate_blockers_top_n(lab_roots: list[tuple[Path, str]], n: int = 5) -> list[tuple[str, int]]:
    """Aggregate gate codes from labs, return top n by count.
    STEP_ID_BACKFILLED resolves STEP_ID_MISSING 1:1 per module (net count only)."""
    from collections import Counter
    all_codes = []
    step_missing_by_mod: dict[str, int] = {}
    step_backfilled_by_mod: dict[str, int] = {}

    for lab_root, module in lab_roots:
        if not lab_root or not lab_root.exists():
            continue
        mod_key = module.lower()
        events = _read_lab_progress_events(lab_root, module, max_events=50)
        codes = _extract_gate_codes_from_events(events)
        step_missing_by_mod[mod_key] = step_missing_by_mod.get(mod_key, 0) + codes.count("STEP_ID_MISSING")
        for ev in events:
            gc = ev.get("gate_codes") or ev.get("gate_code")
            if isinstance(gc, str):
                gc = [gc] if gc else []
            wrn = ev.get("warnings") or []
            has_backfill = (isinstance(gc, list) and "STEP_ID_BACKFILLED" in gc) or any(
                "STEP_ID_BACKFILLED" in str(w) for w in wrn
            )
            if has_backfill:
                step_backfilled_by_mod[mod_key] = step_backfilled_by_mod.get(mod_key, 0) + 1
        for c in codes:
            if c != "STEP_ID_MISSING" and c not in NON_BLOCKER_GATE_CODES:
                all_codes.append(c)

    net_step_missing = sum(max(0, step_missing_by_mod.get(m, 0) - step_backfilled_by_mod.get(m, 0)) for m in step_missing_by_mod)
    for _ in range(net_step_missing):
        all_codes.append("STEP_ID_MISSING")

    cnt = Counter(all_codes)
    return cnt.most_common(n)


def _classify_path(path: str) -> str:
    """Classify path: RUN_EVIDENCE, SAMPLE, MANIFEST, OTHER."""
    p = path.replace("\\", "/")
    if "exports/runs" in p or "exports\\runs" in path:
        return "RUN_EVIDENCE"
    if "/samples/" in p or "\\samples\\" in path or "/labs/samples/" in p:
        return "SAMPLE"
    if "manifest" in Path(path).name.lower():
        return "MANIFEST"
    return "OTHER"


def _format_path_for_display(raw: str) -> str:
    """Display path; use basename + suffix if absolute."""
    path = raw.replace("\\", "/")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return f"{Path(path).name} (absolute path suppressed)"
    return path


def _extract_observed_paths(lab_root: Path, module: str, max_items: int = 3) -> tuple[list[str], list[str]]:
    """
    Extract up to max_items evidence path candidates from PROGRESS_LOG (last 30 events).
    Returns (display_paths_sorted_by_priority, hygiene_warnings e.g. EVIDENCE_ONLY_SAMPLES).
    """
    log_path = lab_root / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    if not log_path.exists():
        return [], []
    mod_lower = module.lower()
    classified: list[tuple[str, str, str]] = []  # (raw, display, category)
    seen_raw = set()
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
        return [], []
    for ev in events[-30:]:
        for key in ("evidence", "artifacts_touched", "evidence_paths"):
            val = ev.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        raw = item.split(":")[0].strip() if ":" in item else item
                        raw = raw.replace("\\", "/")
                        if not raw or raw in seen_raw:
                            continue
                        seen_raw.add(raw)
                        cat = _classify_path(raw)
                        display = _format_path_for_display(raw)
                        classified.append((raw, display, cat))
    # Sort by priority, then dedupe by display, take max_items
    classified.sort(key=lambda x: (PATH_PRIORITY.get(x[2], 99), x[0]))
    result = []
    seen_display = set()
    for _, display, cat in classified:
        if display not in seen_display and len(result) < max_items:
            seen_display.add(display)
            result.append(display)
    # EVIDENCE_ONLY_SAMPLES: SAMPLE only or SAMPLE >= 2/3
    hygiene = []
    if classified:
        cats = [c for _, _, c in classified]
        sample_count = sum(1 for c in cats if c == "SAMPLE")
        if sample_count == len(cats) or (len(cats) >= 3 and sample_count >= (2 * len(cats) + 2) // 3):
            hygiene.append("EVIDENCE_ONLY_SAMPLES")
    return result, hygiene


def _extract_raw_observed_paths(lab_root: Path, module: str, max_events: int = 30) -> list[str]:
    """Extract raw path strings from PROGRESS_LOG for dependency matching."""
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
    for ev in events[-max_events:]:
        for key in ("evidence", "artifacts_touched", "evidence_paths", "observed_paths"):
            for item in (ev.get(key) or []):
                if isinstance(item, str):
                    raw = item.split(":")[0].strip() if ":" in item else item
                    raw = raw.replace("\\", "/").strip()
                    if raw and raw not in seen:
                        seen.add(raw)
                        out.append(raw)
    return out


def _get_lab_root(module: str) -> str:
    """Lab root: (1) ENV, (2) lab_roots.local.json, (3) empty. Returns resolved path or ''."""
    env_key = "FITTING_LAB_ROOT" if module == "FITTING" else "GARMENT_LAB_ROOT"
    lab_root = os.environ.get(env_key, "").strip()
    if not lab_root and LAB_ROOTS_PATH.exists():
        try:
            with open(LAB_ROOTS_PATH, encoding="utf-8-sig") as f:
                cfg = json.load(f)
            val = (cfg.get(env_key) or "").strip()
            if val:
                lab_root = str((REPO_ROOT / val).resolve())
        except Exception:
            pass
    return lab_root


def _read_smoke_status_summary(root: Path) -> dict:
    """Read optional SMOKE_STATUS_SUMMARY.json under lab brief folder."""
    out = {
        "path": "N/A",
        "updated_at": "N/A",
        "overall": "N/A",
        "updated_at_utc": "N/A",
        "smoke2_out_dir": "N/A",
        "smoke2_proxy_asset_present": "N/A",
        "fitting_facts_summary_path": "N/A",
        "garment_input_path_used": "N/A",
        "early_exit": "N/A",
        "early_exit_reason": "N/A",
        "warning_codes": [],
        "hard_gate_artifact_only_ok": False,
        "warning_classification": "N/A",
        "_dt": None,
    }
    path = root / "exports" / "brief" / "SMOKE_STATUS_SUMMARY.json"
    if not path.exists():
        return out
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return out
        out["path"] = str(path)
        out["updated_at"] = str(data.get("updated_at") or "N/A")
        out["overall"] = str(data.get("overall") or "N/A")
        dt = _parse_any_ts(out["updated_at"])
        out["_dt"] = dt
        out["updated_at_utc"] = _to_utc_iso(dt)

        smoke2 = data.get("smoke2") if isinstance(data.get("smoke2"), dict) else {}
        evidence = smoke2.get("evidence") if isinstance(smoke2.get("evidence"), dict) else {}
        smoke2_out_dir = _first_non_empty_str(smoke2.get("out_dir"), evidence.get("out_dir"))
        if smoke2_out_dir:
            out["smoke2_out_dir"] = smoke2_out_dir
        smoke2_out_dir_resolved = _resolve_smoke_out_dir(smoke2_out_dir, root)
        proxy_asset_present = False
        if smoke2_out_dir_resolved is not None:
            proxy_asset_present = _run_dir_has_proxy_assets(smoke2_out_dir_resolved)
            out["smoke2_proxy_asset_present"] = proxy_asset_present

        facts_path_value = _first_non_empty_str(
            evidence.get("fitting_facts_summary"),
            evidence.get("fitting_facts_summary_path"),
            smoke2.get("fitting_facts_summary"),
            smoke2.get("fitting_facts_summary_path"),
        )
        if facts_path_value:
            out["fitting_facts_summary_path"] = facts_path_value

        input_used = _first_non_empty_str(
            smoke2.get("garment_input_path_used"),
            evidence.get("garment_input_path_used"),
        )
        early_exit = _first_bool(smoke2.get("early_exit"), evidence.get("early_exit"))
        early_exit_reason = _first_non_empty_str(
            smoke2.get("early_exit_reason"),
            evidence.get("early_exit_reason"),
        )
        warning_codes = []
        for key in ("warnings", "warning_codes", "warnings_summary"):
            warning_codes.extend(_normalize_warning_codes(smoke2.get(key)))
            warning_codes.extend(_normalize_warning_codes(evidence.get(key)))

        if facts_path_value:
            facts_path = _resolve_summary_path(facts_path_value, root)
            if facts_path:
                try:
                    with open(facts_path, encoding="utf-8") as f:
                        facts = json.load(f)
                    if isinstance(facts, dict):
                        input_used = input_used or _first_non_empty_str(facts.get("garment_input_path_used"))
                        if early_exit is None:
                            early_exit = _first_bool(facts.get("early_exit"))
                        early_exit_reason = early_exit_reason or _first_non_empty_str(facts.get("early_exit_reason"))
                        warning_codes.extend(_normalize_warning_codes(facts.get("warnings")))
                        warning_codes.extend(_normalize_warning_codes(facts.get("warnings_summary")))
                except Exception:
                    pass

        uniq_codes = []
        seen_codes = set()
        for code in warning_codes:
            if code not in seen_codes:
                seen_codes.add(code)
                uniq_codes.append(code)

        out["garment_input_path_used"] = input_used or "N/A"
        out["early_exit"] = early_exit if early_exit is not None else "N/A"
        out["early_exit_reason"] = early_exit_reason or "N/A"
        out["warning_codes"] = uniq_codes
        input_used_lower = (input_used or "").lower()
        has_asset_missing = "GARMENT_ASSET_MISSING" in seen_codes
        if input_used_lower == "unknown":
            if proxy_asset_present:
                out["hard_gate_artifact_only_ok"] = False
                out["warning_classification"] = "GARMENT_INPUT_PATH_UNKNOWN_INVALID_WITH_PROXY"
            elif early_exit is True and has_asset_missing:
                out["hard_gate_artifact_only_ok"] = True
                out["warning_classification"] = "GARMENT_ASSET_MISSING:non_blocker"
            elif has_asset_missing:
                out["hard_gate_artifact_only_ok"] = False
                out["warning_classification"] = "GARMENT_ASSET_MISSING:non_blocker"
            else:
                out["hard_gate_artifact_only_ok"] = False
                out["warning_classification"] = "GARMENT_INPUT_PATH_UNKNOWN_REVIEW"
        elif has_asset_missing:
            out["warning_classification"] = "GARMENT_ASSET_MISSING:non_blocker"
    except Exception:
        return out
    return out


def _read_m1_signal(module: str) -> dict:
    """Read ops/signals/m1/<module>/LATEST.json signal (readiness-only source)."""
    out = {
        "path": "N/A",
        "created_at_utc": "N/A",
        "run_id": "N/A",
        "run_dir_rel": "N/A",
        "_dt": None,
    }
    m = module.lower()
    path = REPO_ROOT / "ops" / "signals" / "m1" / m / "LATEST.json"
    if not path.exists():
        return out
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return out
        out["path"] = str(path)
        out["created_at_utc"] = str(data.get("created_at_utc") or "N/A")
        out["run_id"] = str(data.get("run_id") or "N/A")
        out["run_dir_rel"] = str(data.get("run_dir_rel") or "N/A")
        out["_dt"] = _parse_any_ts(out["created_at_utc"])
    except Exception:
        return out
    return out


def _parse_brief_head_status(brief_head: list[str]) -> str:
    """Extract status token from brief head ('status: XXX')."""
    for ln in brief_head or []:
        s = ln.strip()
        if s.lower().startswith("status:"):
            return s.split(":", 1)[-1].strip() or "N/A"
    return "N/A"


def _summarize_observed_paths(raw_paths: list[str]) -> dict:
    """Summarize observed paths by class to avoid noisy dashboard output."""
    counts = {"RUN_EVIDENCE": 0, "MANIFEST": 0, "SAMPLE": 0, "OTHER": 0}
    for p in raw_paths:
        cat = _classify_path(p)
        counts[cat] = counts.get(cat, 0) + 1
    total = sum(counts.values())
    return {"total": total, "counts": counts}


def _select_status_source(brief: dict, smoke: dict, policy: dict) -> dict:
    """
    Select authoritative status source for module dashboard.
    Rule: latest_updated_at among configured status sources.
    """
    cands = []
    configured = []
    for row in policy.get("status_sources") or []:
        if isinstance(row, dict):
            sid = str(row.get("id") or "").strip()
            if sid:
                configured.append(sid)
    allowed = set(configured) if configured else {"work_brief_progress_log", "smoke_status_summary"}

    brief_dt = brief.get("_brief_dt")
    if brief_dt and "work_brief_progress_log" in allowed:
        cands.append({
            "id": "work_brief_progress_log",
            "dt": brief_dt,
            "value": brief.get("brief_status") or "N/A",
        })
    smoke_dt = smoke.get("_dt")
    if smoke_dt and "smoke_status_summary" in allowed:
        cands.append({
            "id": "smoke_status_summary",
            "dt": smoke_dt,
            "value": smoke.get("overall") or "N/A",
        })

    if not cands:
        return {"id": "N/A", "updated_at_utc": "N/A", "value": "N/A"}

    fallback = ((policy.get("status_selection_rule") or {}).get("fallback_order") or configured)
    fallback_rank = {sid: i for i, sid in enumerate(fallback)}
    latest_dt = max(c["dt"] for c in cands)
    latest = [c for c in cands if c["dt"] == latest_dt]
    latest.sort(key=lambda c: fallback_rank.get(c["id"], 999))
    selected = latest[0]
    return {
        "id": selected["id"],
        "updated_at_utc": _to_utc_iso(selected["dt"]),
        "value": selected["value"],
    }


def _first_non_empty_str(*values) -> str | None:
    for v in values:
        if isinstance(v, str):
            s = v.strip()
            if s:
                return s
    return None


def _first_bool(*values) -> bool | None:
    for v in values:
        if isinstance(v, bool):
            return v
    return None


def _normalize_warning_codes(value) -> list[str]:
    codes: list[str] = []
    if isinstance(value, str):
        code = value.strip()
        if code:
            codes.append(code)
        return codes
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                code = item.strip()
                if code:
                    codes.append(code)
            elif isinstance(item, dict):
                code = _first_non_empty_str(item.get("code"), item.get("gate_code"), item.get("id"))
                if code:
                    codes.append(code)
    return codes


def _resolve_summary_path(path_value: str, root: Path) -> Path | None:
    p = Path(path_value)
    cands = []
    if p.is_absolute():
        cands.append(p)
    else:
        cands.extend([root / p, root / "runs" / p, root / "exports" / "runs" / p])
    for cand in cands:
        if cand.is_file():
            return cand
    return None


def _resolve_smoke_out_dir(path_value: str | None, root: Path) -> Path | None:
    if not isinstance(path_value, str):
        return None
    raw = path_value.strip()
    if not raw:
        return None
    p = Path(raw)
    cands = []
    if p.is_absolute():
        cands.append(p)
    else:
        cands.extend([root / p, root / "runs" / p, root / "exports" / "runs" / p])
    for cand in cands:
        if cand.exists() and cand.is_dir():
            return cand
    return None


def _run_dir_has_proxy_assets(run_dir: Path) -> bool:
    direct = (
        run_dir / "garment_proxy.npz",
        run_dir / "garment_proxy_mesh.glb",
    )
    if any(p.is_file() for p in direct):
        return True
    # Legacy/nested output layout guard.
    nested = (
        "garment_proxy.npz",
        "garment_proxy_mesh.glb",
    )
    for name in nested:
        if any(run_dir.rglob(name)):
            return True
    return False


def _status_signal_recency(status_selected: dict, signal: dict) -> str:
    """Compare status-source timestamp vs signal timestamp (signal is readiness-only)."""
    status_dt = _parse_any_ts(status_selected.get("updated_at_utc"))
    signal_dt = _parse_any_ts(signal.get("created_at_utc"))
    if not status_dt or not signal_dt:
        return "N/A"
    if status_dt > signal_dt:
        return "status_newer"
    if signal_dt > status_dt:
        return "signal_newer_readiness_only"
    return "same_timestamp"


def _format_status_signal_policy(policy: dict) -> str:
    cfg = policy.get("status_vs_signal_policy") or {}
    status_only = cfg.get("status_selection_sources_only")
    if not isinstance(status_only, list) or not status_only:
        status_only = ["work_brief_progress_log", "smoke_status_summary"]
    signal_role = str(cfg.get("signal_role") or "readiness_only")
    signal_id = str(cfg.get("signal_source") or "m1_latest_signal")
    joins = ",".join(str(x) for x in status_only)
    return f"status_sources_only({joins}); signal={signal_role}({signal_id})"


def _read_lab_brief(module: str) -> tuple[dict, list[str]]:
    """Read brief from FITTING_LAB_ROOT or GARMENT_LAB_ROOT (ENV or lab_roots.local.json). Returns brief_path, mtime, head_12, observed_paths."""
    policy = _load_status_source_policy()
    sla = _load_status_refresh_sla()
    out = {
        "brief_path": "N/A",
        "brief_mtime": "N/A",
        "brief_mtime_utc": "N/A",
        "_brief_dt": None,
        "brief_head": [],
        "brief_status": "N/A",
        "path_hygiene": [],
        "progress_hygiene": [],
        "evidence_snapshot": {"total": 0, "counts": {"RUN_EVIDENCE": 0, "MANIFEST": 0, "SAMPLE": 0, "OTHER": 0}},
        "smoke_summary": {"path": "N/A", "updated_at": "N/A", "updated_at_utc": "N/A", "overall": "N/A", "_dt": None},
        "signal": {"path": "N/A", "created_at_utc": "N/A", "run_id": "N/A", "run_dir_rel": "N/A", "_dt": None},
        "status_selected": {"id": "N/A", "updated_at_utc": "N/A", "value": "N/A"},
        "status_policy_version": str(policy.get("policy_version") or "N/A"),
        "status_signal_policy": _format_status_signal_policy(policy),
        "status_vs_signal_recency": "N/A",
        "status_sla_version": str(sla.get("sla_version") or "N/A"),
        "status_sla_max_age_min": None,
        "status_source_age_min": None,
        "status_sla_state": "N/A",
    }
    warnings = []
    env_key = "FITTING_LAB_ROOT" if module == "FITTING" else "GARMENT_LAB_ROOT"
    lab_root = _get_lab_root(module)
    if not lab_root:
        warnings.append(_warn("LAB_ROOT_MISSING", f"{env_key} not set", "N/A"))
        return out, warnings

    root = Path(lab_root).resolve()
    if not root.exists():
        warnings.append(_warn("LAB_ROOT_NOT_FOUND", f"{env_key} path not found", str(root)))
        return out, warnings

    brief_name = f"{module}_WORK_BRIEF.md"
    brief_path = root / "exports" / "brief" / brief_name
    raw_paths = _extract_raw_observed_paths(root, module, max_events=30)
    out["evidence_snapshot"] = _summarize_observed_paths(raw_paths)
    _observed_paths, path_hygiene = _extract_observed_paths(root, module, max_items=3)
    out["path_hygiene"] = path_hygiene
    out["progress_hygiene"] = _compute_progress_hygiene(root, module)
    out["smoke_summary"] = _read_smoke_status_summary(root)
    out["signal"] = _read_m1_signal(module.lower())
    if not brief_path.exists():
        warnings.append(_warn("BRIEF_NOT_FOUND", "brief not found", str(brief_path)))
        out["status_selected"] = _select_status_source(out, out.get("smoke_summary") or {}, policy)
        out["status_vs_signal_recency"] = _status_signal_recency(out["status_selected"], out["signal"])
        if out["status_selected"]["id"] == "N/A":
            warnings.append(_warn("STATUS_SOURCE_MISSING", "no status source available", str(root / "exports" / "brief")))
        return out, warnings
    try:
        out["brief_path"] = str(brief_path)
        mtime = brief_path.stat().st_mtime
        try:
            from zoneinfo import ZoneInfo
            dt = datetime.fromtimestamp(mtime, tz=ZoneInfo("Asia/Seoul"))
        except ImportError:
            dt = datetime.fromtimestamp(mtime)
        out["_brief_dt"] = dt
        out["brief_mtime_utc"] = _to_utc_iso(dt)
        out["brief_mtime"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        raw = brief_path.read_text(encoding="utf-8", errors="replace")
        lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        out["brief_head"] = _normalize_lines(lines[:12])
        out["brief_status"] = _parse_brief_head_status(out["brief_head"])
    except Exception as e:
        warnings.append(_warn("BRIEF_READ_FAIL", str(e), str(brief_path)))

    out["status_selected"] = _select_status_source(out, out.get("smoke_summary") or {}, policy)
    out["status_vs_signal_recency"] = _status_signal_recency(out["status_selected"], out["signal"])
    if out["status_selected"]["id"] == "smoke_status_summary":
        warnings.append(_warn("STATUS_SOURCE_SWITCHED", "newer smoke summary selected over work brief", out["smoke_summary"]["path"]))
    if out["status_selected"]["id"] == "N/A":
        warnings.append(_warn("STATUS_SOURCE_MISSING", "no status source available", str(root / "exports" / "brief")))

    # SLA freshness evaluation
    mod = module.lower()
    mod_sla = ((sla.get("module_status_sla") or {}).get(mod) or {})
    max_age = mod_sla.get("max_status_age_minutes")
    now = datetime.now(timezone.utc)
    selected_dt = _parse_any_ts(out["status_selected"].get("updated_at_utc"))
    out["status_sla_max_age_min"] = max_age if isinstance(max_age, int) else None
    if selected_dt:
        age_min = int((now - selected_dt.astimezone(timezone.utc)).total_seconds() // 60)
        out["status_source_age_min"] = max(0, age_min)
        if isinstance(max_age, int):
            if age_min <= max_age:
                out["status_sla_state"] = "OK"
            else:
                out["status_sla_state"] = "STALE"
                warnings.append(_warn("STATUS_STALE", f"status source older than SLA ({age_min}m>{max_age}m)", str(root)))
        else:
            out["status_sla_state"] = "N/A"
    else:
        out["status_sla_state"] = "N/A"

    return out, warnings


def _parse_brief_head_warnings(brief_head: list[str]) -> list[str]:
    """Extract warning codes from brief_head 'warnings: X' line for health aggregation."""
    for ln in brief_head or []:
        s = ln.strip()
        if s.lower().startswith("warnings:"):
            val = s.split(":", 1)[-1].strip()
            if not val or val == "0":
                return []
            return [c.strip() for c in val.split(",") if c.strip()]
    return []


def _render_module_brief(module: str, brief: dict, warnings: list[str], lifecycle: dict | None = None) -> str:
    soft = list(brief.get("path_hygiene") or [])
    soft.extend(brief.get("progress_hygiene") or [])
    brief_warn_codes = _parse_brief_head_warnings(brief.get("brief_head") or [])
    soft.extend(brief_warn_codes)
    selected = brief.get("status_selected") or {}
    selected_id = selected.get("id", "N/A")
    smoke = brief.get("smoke_summary") or {}
    smoke_ok = bool(smoke.get("hard_gate_artifact_only_ok"))
    if selected_id == "smoke_status_summary" and str(smoke.get("overall", "")).upper() not in {"PASS", "OK"} and not smoke_ok:
        soft.append("SMOKE_OVERALL_NOT_PASS")
    if module == "GARMENT":
        smoke_class = str(smoke.get("warning_classification", "N/A"))
        if smoke_class == "GARMENT_ASSET_MISSING:non_blocker":
            soft.append("GARMENT_ASSET_MISSING_CLASS_WARN")
        elif smoke_class == "GARMENT_INPUT_PATH_UNKNOWN_INVALID_WITH_PROXY":
            soft.append("GARMENT_INPUT_PATH_UNKNOWN_INVALID")
        elif smoke_class != "N/A":
            soft.append("GARMENT_SMOKE2_CLASSIFIED")
    soft_warns = [_warn(c, "observed", "N/A") for c in soft]
    all_w = warnings + soft_warns
    nw = len(all_w)
    health = "OK (warnings=0)" if nw == 0 else f"WARN (warnings={nw})"
    lines = [f"- health: {health}"]
    if nw > 0:
        top3 = _sort_warnings(all_w)[:3]
        lines.append(f"- health_summary: {'; '.join(top3)}")
    if lifecycle:
        lines.append(f"- lifecycle_total_steps: {lifecycle.get('total', 0)}")
        lines.append(f"- lifecycle_implemented: {lifecycle.get('implemented', 0)}")
        lines.append(f"- lifecycle_validated: {lifecycle.get('validated', 0)}")
        lines.append(f"- lifecycle_closed: {lifecycle.get('closed', 0)}")
        lines.append(f"- lifecycle_pending: {lifecycle.get('pending', 0)}")
        if lifecycle.get("next_validate"):
            lines.append(f"- next_validate: {', '.join(lifecycle['next_validate'])}")
        if lifecycle.get("next_close"):
            lines.append(f"- next_close: {', '.join(lifecycle['next_close'])}")
    lines.append(f"- status_policy_version: {brief.get('status_policy_version', 'N/A')}")
    lines.append(f"- status_source_selected: {selected.get('id', 'N/A')}")
    lines.append(f"- status_source_updated_at_utc: {selected.get('updated_at_utc', 'N/A')}")
    lines.append(f"- status_source_value: {selected.get('value', 'N/A')}")
    lines.append(f"- status_signal_policy: {brief.get('status_signal_policy', 'N/A')}")
    lines.append(f"- status_vs_signal_recency: {brief.get('status_vs_signal_recency', 'N/A')}")
    lines.append(f"- status_sla_version: {brief.get('status_sla_version', 'N/A')}")
    lines.append(f"- status_sla_max_age_min: {brief.get('status_sla_max_age_min', 'N/A')}")
    lines.append(f"- status_source_age_min: {brief.get('status_source_age_min', 'N/A')}")
    lines.append(f"- status_sla_state: {brief.get('status_sla_state', 'N/A')}")
    signal = brief.get("signal") or {}
    lines.append("- signal_source: m1_latest_signal")
    lines.append(f"- signal_created_at_utc: {signal.get('created_at_utc', 'N/A')}")
    lines.append(f"- signal_run_id: {signal.get('run_id', 'N/A')}")
    lines.append(f"- signal_run_dir_rel: {signal.get('run_dir_rel', 'N/A')}")
    ev = brief.get("evidence_snapshot") or {}
    evc = ev.get("counts") or {}
    lines.append(
        "- evidence_snapshot: "
        f"total={ev.get('total', 0)}; "
        f"run_evidence={evc.get('RUN_EVIDENCE', 0)}, "
        f"manifest={evc.get('MANIFEST', 0)}, "
        f"sample={evc.get('SAMPLE', 0)}, "
        f"other={evc.get('OTHER', 0)}"
    )
    lines.append(f"- brief_path: {brief['brief_path']}")
    lines.append(f"- brief_mtime_local: {brief['brief_mtime']}")
    lines.append(f"- brief_mtime_utc: {brief.get('brief_mtime_utc', 'N/A')}")
    smoke_path = smoke.get("path", "N/A")
    primary_evidence = smoke.get("fitting_facts_summary_path", "N/A")
    if not isinstance(primary_evidence, str) or not primary_evidence.strip() or primary_evidence == "N/A":
        primary_evidence = smoke_path
    lines.append(f"- run_level_evidence_primary: {primary_evidence}")
    lines.append(f"- fitting_facts_summary_path: {smoke.get('fitting_facts_summary_path', 'N/A')}")
    lines.append(f"- smoke2_garment_input_path_used: {smoke.get('garment_input_path_used', 'N/A')}")
    lines.append(f"- smoke2_early_exit: {smoke.get('early_exit', 'N/A')}")
    lines.append(f"- smoke2_early_exit_reason: {smoke.get('early_exit_reason', 'N/A')}")
    lines.append(f"- smoke2_hard_gate_artifact_only_ok: {str(bool(smoke.get('hard_gate_artifact_only_ok'))).lower()}")
    lines.append(f"- smoke2_warning_classification: {smoke.get('warning_classification', 'N/A')}")
    lines.append(f"- smoke2_out_dir: {smoke.get('smoke2_out_dir', 'N/A')}")
    lines.append(f"- smoke2_proxy_asset_present: {smoke.get('smoke2_proxy_asset_present', 'N/A')}")
    lines.append(f"- smoke_summary_path: {smoke_path}")
    lines.append(f"- smoke_summary_updated_at_utc: {smoke.get('updated_at_utc', 'N/A')}")
    lines.append(f"- smoke_summary_overall: {smoke.get('overall', 'N/A')}")
    if all_w:
        lines.append("- warnings:")
        for w in _sort_warnings(all_w):
            lines.append(f"  - {w}")
    return "\n".join(lines)


def _ensure_markers(text: str) -> str:
    """If any markers missing, insert placeholder."""
    if "<!-- GENERATED:BEGIN:BLOCKERS -->" not in text:
        # Insert BLOCKERS block after Manual section, before ---
        pattern = r"(## Manual \(ops auto-refresh checks\)[\s\S]*?open `ops/lab_roots\.local\.json`)\s*(\n---)"
        match = re.search(pattern, text)
        if match:
            insert = f"\n\n## BLOCKERS (generated)\n<!-- GENERATED:BEGIN:BLOCKERS -->\n- BLOCKERS: none observed\n<!-- GENERATED:END:BLOCKERS -->"
            text = text[: match.end(1)] + insert + text[match.start(2) :]
    if "<!-- GENERATED:BEGIN:M1_SIGNALS -->" not in text:
        pattern = r"(<!-- GENERATED:END:BLOCKERS -->)\s*(\n---)"
        match = re.search(pattern, text)
        if match:
            insert = (
                "\n\n## M1 Signals (generated)\n"
                "<!-- GENERATED:BEGIN:M1_SIGNALS -->\n"
                "- body: missing\n"
                "- garment: missing\n"
                "- fitting: missing\n"
                "<!-- GENERATED:END:M1_SIGNALS -->"
            )
            text = text[: match.end(1)] + insert + text[match.start(2) :]
    for module, (mb, me) in MARKERS.items():
        if module in {"BLOCKERS", "M1_SIGNALS"}:
            continue
        if mb not in text or me not in text:
            section = module.lower().capitalize()
            pattern = rf"(## {section}[\s\S]*?### Dashboard \(generated-only\)\s*\n)"
            match = re.search(pattern, text)
            if match:
                placeholder = f"- N/A (placeholder)\n" if module != "BODY" else "- N/A\n"
                insert = match.group(0) + f"{mb}\n{placeholder}{me}\n"
                text = text[: match.start()] + insert + text[match.end() :]
    return text


def _load_dependency_ledger() -> dict | None:
    """Load contracts/dependency_ledger_v1.json. Returns None on error."""
    path = REPO_ROOT / "contracts" / "dependency_ledger_v1.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _path_matches_glob(path: str, pattern: str) -> bool:
    """Check if path matches glob pattern (supports **). Uses fnmatch; ** = any path segments."""
    import fnmatch

    pnorm = path.replace("\\", "/")
    pnorm_pat = pattern.replace("\\", "/")
    if "**" not in pnorm_pat:
        return fnmatch.fnmatch(pnorm, pnorm_pat)
    parts = pnorm_pat.split("**", 1)
    prefix, suffix = parts[0].rstrip("/"), (parts[1].lstrip("/") if len(parts) > 1 else "")
    if not prefix and not suffix:
        return True
    if prefix and not pnorm.startswith(prefix):
        return False
    if suffix and not pnorm.endswith(suffix):
        return False
    if prefix and suffix and len(pnorm) < len(prefix) + len(suffix):
        return False
    return True


def _collect_global_observed_paths(lab_roots: list[tuple[Path, str]]) -> set[str]:
    """Collect all raw observed paths from progress logs and run_registry."""
    out = set()
    for lab_root, module in lab_roots:
        for p in _extract_raw_observed_paths(lab_root, module, max_events=50):
            out.add(p.replace("\\", "/"))
    body_progress_path = REPO_ROOT / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    if body_progress_path.exists():
        for p in _extract_raw_observed_paths(REPO_ROOT, "body", max_events=50):
            out.add(p.replace("\\", "/"))
    registry_path = REPO_ROOT / "ops" / "run_registry.jsonl"
    if registry_path.exists():
        try:
            with open(registry_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        for ep in rec.get("evidence_paths") or []:
                            if isinstance(ep, str):
                                out.add(ep.replace("\\", "/"))
                        mp = rec.get("manifest_path")
                        if isinstance(mp, str):
                            out.add(mp.replace("\\", "/"))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
    runs_root = REPO_ROOT / "exports" / "runs"
    # REPO exports/runs 스캔 (메인 레포 내부)
    if runs_root.exists():
        for name in ("body_measurements_subset.json", "garment_proxy_meta.json"):
            for p in runs_root.rglob(name):
                try:
                    rel = p.relative_to(REPO_ROOT).as_posix()
                    out.add(rel)
                except ValueError:
                    pass

    # LAB exports/runs 스캔 (외부 lab 폴더)
    for lab_root, _ in lab_roots:
        if lab_root and lab_root.exists():
            runs_in_lab = lab_root / "exports" / "runs"
            if runs_in_lab.exists():
                for name in ("body_measurements_subset.json", "garment_proxy_meta.json"):
                    for p in runs_in_lab.rglob(name):
                        try:
                            rel = p.relative_to(lab_root).as_posix()
                            out.add(rel)
                        except ValueError:
                            pass

    return out


def _resolve_path_to_file(rel_path: str, roots: list[Path]) -> Path | None:
    """Resolve relative path against roots; return first existing file path."""
    norm = rel_path.replace("\\", "/").strip()
    for root in roots:
        cand = root / norm
        if cand.is_file():
            return cand
    return None


def _evaluate_m1_checks(checks: dict, data: dict) -> list[str]:
    """
    Evaluate m1_checks against loaded JSON data. Returns list of failure detail strings.
    Checks: require_fields, require_any_fields, schema_version_exact, require_keys_any, unit_exact, no_nan.
    require_any_fields: list of field groups; each group must have at least one field present.
    """
    details = []
    if not isinstance(data, dict):
        return ["not a dict"]

    for field in checks.get("require_fields") or []:
        if field not in data:
            details.append(f"missing_field:{field}")

    for group in checks.get("require_any_fields") or []:
        if not isinstance(group, (list, tuple)):
            continue
        if not any(f in data for f in group):
            details.append(f"require_any_fields:{group}")

    exact = checks.get("schema_version_exact")
    if exact:
        got = data.get("schema_version")
        if got != exact:
            details.append(f"schema_version:{got!r}!={exact!r}")

    keys_any = checks.get("require_keys_any")
    if keys_any:
        targets = [data]
        if checks.get("require_keys_any_in"):
            sub = data.get(checks["require_keys_any_in"])
            if isinstance(sub, dict):
                targets.append(sub)
        found = False
        for t in targets:
            if isinstance(t, dict) and any(k in t for k in keys_any):
                found = True
                break
        if not found:
            details.append(f"require_keys_any:{keys_any}")

    unit_exact = checks.get("unit_exact")
    if unit_exact is not None:
        unit_val = data.get("unit") or data.get("unit_of_measure") or data.get("units")
        if unit_val != unit_exact:
            details.append(f"unit:{unit_val!r}!={unit_exact!r}")

    if checks.get("no_nan"):
        def has_nan(obj, depth=0):
            if depth > 10:
                return False
            if obj is None:
                return False
            if isinstance(obj, dict):
                return any(has_nan(v, depth + 1) for v in obj.values())
            if isinstance(obj, list):
                return any(has_nan(v, depth + 1) for v in obj)
            if isinstance(obj, float):
                return obj != obj  # NaN check
            return False
        if has_nan(data):
            details.append("has_nan")

    return details


def _check_m1_ledger(
    ledger: dict,
    observed_paths: set[str],
    lab_roots: list[tuple[Path, str]],
) -> dict[str, list[str]]:
    """
    Evaluate m1_checks on observed files. Warn-only. Returns {module: [warn_str, ...]}.
    Only runs when observed target file exists.
    """
    result: dict[str, list[str]] = {"BODY": [], "FITTING": [], "GARMENT": []}
    roots = [r for r, _ in lab_roots] + [REPO_ROOT]
    rows = ledger.get("rows") or []

    for row in rows:
        m1 = row.get("m1_checks") or {}
        if not m1:
            continue
        required = row.get("required_paths_any") or []
        if not required:
            continue
        consumer = (row.get("consumer_module") or "").lower()
        producer = (row.get("producer_module") or "").lower()
        dep_id = (row.get("id") or "").strip()
        hint = (row.get("hint_path") or "").strip() or "N/A"

        mod_upper = "FITTING" if consumer == "fitting" else ("GARMENT" if consumer == "garment" else ("BODY" if producer == "body" else None))
        if not mod_upper:
            continue

        matched_path = None
        for pattern in required:
            for op in observed_paths:
                if _path_matches_glob(op, pattern):
                    matched_path = op
                    break
            if matched_path:
                break
        if not matched_path:
            continue

        fpath = _resolve_path_to_file(matched_path, roots)
        if not fpath or not fpath.exists():
            continue

        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            result[mod_upper].append(_warn_m1(dep_id, hint, f"load_fail:{str(e)[:40]}"))
            continue

        failures = _evaluate_m1_checks(m1, data)
        if failures:
            detail = ";".join(failures[:3])
            if len(failures) > 3:
                detail += f"...+{len(failures)-3}"
            result[mod_upper].append(_warn_m1(dep_id, hint, detail))

    return result


def _check_dependency_ledger(
    ledger: dict,
    observed_paths: set[str],
) -> dict[str, list[tuple[str, str | None]]]:
    """
    Check dependency ledger against observed paths. enforcement_u1=warn only (no FAIL).
    Returns {module_upper: [(gate_code, hint_path), ...]} for modules with missing deps.
    """
    result: dict[str, list[tuple[str, str | None]]] = {"BODY": [], "FITTING": [], "GARMENT": []}
    rows = ledger.get("rows") or []
    for row in rows:
        if (row.get("enforcement_u1") or "").lower() != "warn":
            continue
        required = row.get("required_paths_any") or []
        if not required:
            continue
        matched = False
        for pattern in required:
            for op in observed_paths:
                if _path_matches_glob(op, pattern):
                    matched = True
                    break
            if matched:
                break
        if matched:
            continue
        gate = (row.get("gate_code") or "").strip()
        if not gate:
            continue
        hint = (row.get("hint_path") or "").strip() or None
        consumer = (row.get("consumer_module") or "").lower()
        producer = (row.get("producer_module") or "").lower()
        if consumer == "fitting":
            result["FITTING"].append((gate, hint))
        elif consumer == "garment":
            result["GARMENT"].append((gate, hint))
        elif consumer == "ops" and producer == "body":
            result["BODY"].append((gate, hint))
    return result


RUN_MINSET_FILES = (
    "geometry_manifest.json",
    "facts_summary.json",
)
RUN_MINSET_GLOBS = ("*facts_summary*.json",)
RUN_MINSET_README = "RUN_README.md"
RUN_MINSET_MIN_COUNT = 2


def _check_run_minset(lab_roots: list[tuple[Path, str]], max_records: int = 50) -> dict[str, list[str]]:
    """
    Check run_registry records for minset (>=2 of geometry_manifest, facts_summary, RUN_README).
    Returns {module_upper: [expected_str, ...]} for runs that fail. Warn-only.
    """
    result: dict[str, list[str]] = {"BODY": [], "FITTING": [], "GARMENT": []}
    root_result: dict[str, list[str]] = {"BODY": [], "FITTING": [], "GARMENT": []}
    registry_path = REPO_ROOT / "ops" / "run_registry.jsonl"
    if not registry_path.exists():
        return result, root_result

    lab_map = {m: r for r, m in lab_roots}
    lab_map["body"] = REPO_ROOT

    records = []
    try:
        with open(registry_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return result, root_result

    seen_run_keys = set()
    for rec in records[-max_records:]:
        module = (rec.get("module") or "").strip().lower()
        lane = (rec.get("lane") or "").strip()
        run_id = (rec.get("run_id") or "").strip()
        if not module or not lane or not run_id:
            continue
        mod_upper = module.upper() if module in ("fitting", "garment") else "BODY"
        root = lab_map.get(module)
        if not root:
            continue
        run_key = (module, lane, run_id)
        if run_key in seen_run_keys:
            continue
        seen_run_keys.add(run_key)

        run_dir = root / "exports" / "runs" / lane / run_id
        if not run_dir.exists():
            expected = f"exports/runs/{lane}/{run_id}/{{facts_summary.json,RUN_README.md}}"
            result[mod_upper].append(expected)
            continue

        count = 0
        missing = []
        has_geo = bool(list(run_dir.rglob("geometry_manifest.json")))
        has_facts = bool(list(run_dir.rglob("facts_summary.json")) or list(run_dir.rglob("*facts_summary*.json")))
        has_readme = bool(list(run_dir.rglob("RUN_README.md")) or list(run_dir.rglob("README.txt")))
        if has_geo:
            count += 1
        else:
            missing.append("geometry_manifest.json")
        if has_facts:
            count += 1
        else:
            missing.append("facts_summary.json")
        if has_readme:
            count += 1
        else:
            missing.append("RUN_README.md")

        if count < RUN_MINSET_MIN_COUNT and missing:
            expected = f"exports/runs/{lane}/{run_id}/{{{','.join(missing)}}}"
            result[mod_upper].append(expected)

        has_root_geo = (run_dir / "geometry_manifest.json").is_file()
        if not has_root_geo and has_geo:
            root_expected = f"exports/runs/{lane}/{run_id}/geometry_manifest.json"
            root_result[mod_upper].append(root_expected)

    return result, root_result


def _check_round_end_missing(lab_roots: list[tuple[Path, str]], hours: int = 24) -> dict[str, list[str]]:
    """
    Count-based: if ROUND_START > ROUND_END in last 24h, add ROUND_END_MISSING. Warn-only.
    Returns {module_upper: ["expected=...", ...]}.
    """
    result: dict[str, list[str]] = {"BODY": [], "FITTING": [], "GARMENT": []}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    for lab_root, module in lab_roots:
        mod_upper = module.upper() if module in ("fitting", "garment") else "BODY"
        log_path = lab_root / "exports" / "progress" / "PROGRESS_LOG.jsonl"
        if not log_path.exists():
            continue
        start_count = 0
        end_count = 0
        try:
            with open(log_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                        if ev.get("module", "").lower() != module.lower():
                            continue
                        ts = ev.get("ts", "")
                        if ts:
                            try:
                                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                if dt < cutoff:
                                    continue
                            except Exception:
                                pass
                        et = str(ev.get("event_type") or ev.get("event") or "").lower()
                        if et == "round_start":
                            start_count += 1
                        elif et == "round_end":
                            end_count += 1
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue
        if start_count > end_count:
            result[mod_upper].append("expected=roundwrap end required")

    body_log = REPO_ROOT / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    if body_log.exists():
        start_count = 0
        end_count = 0
        try:
            with open(body_log, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                        if ev.get("module", "").lower() != "body":
                            continue
                        ts = ev.get("ts", "")
                        if ts:
                            try:
                                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                if dt < cutoff:
                                    continue
                            except Exception:
                                pass
                        et = str(ev.get("event_type") or ev.get("event") or "").lower()
                        if et == "round_start":
                            start_count += 1
                        elif et == "round_end":
                            end_count += 1
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        if start_count > end_count:
            result["BODY"].append("expected=roundwrap end required")

    return result


def _render_blockers(lab_roots: list[tuple[Path, str]]) -> str:
    """Render BLOCKERS Top 5 content."""
    top = _aggregate_blockers_top_n(lab_roots, n=5)
    if not top:
        return "- BLOCKERS: none observed"
    lines = ["- BLOCKERS Top 5:"]
    for code, count in top:
        lines.append(f"  - {code}: {count}")
    return "\n".join(lines)


def _render_m1_signals() -> str:
    """Render M1 signal readiness from ops/signals/m1/*/LATEST.json."""
    lines: list[str] = []
    for module in ("body", "garment", "fitting"):
        path = REPO_ROOT / "ops" / "signals" / "m1" / module / "LATEST.json"
        if not path.exists():
            lines.append(f"- {module}: missing")
            continue
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            lines.append(f"- {module}: invalid_json")
            continue
        if not isinstance(payload, dict):
            lines.append(f"- {module}: invalid_payload")
            continue
        run_id = payload.get("run_id") or "N/A"
        run_dir_rel = payload.get("run_dir_rel") or "N/A"
        created_at_utc = payload.get("created_at_utc") or "N/A"
        lines.append(
            f"- {module}: run_id={run_id}; run_dir_rel={run_dir_rel}; created_at_utc={created_at_utc}"
        )
    return "\n".join(lines)


def main() -> int:
    all_warnings = []
    master_plan = _load_master_plan()
    body_steps, body_closure = _module_steps_and_closure(master_plan, "body")
    fitting_steps, fitting_closure = _module_steps_and_closure(master_plan, "fitting")
    garment_steps, garment_closure = _module_steps_and_closure(master_plan, "garment")

    curated, w1 = _latest_curated()
    geo, w2 = _latest_geo()
    all_warnings.extend(w1)
    all_warnings.extend(w2)

    fitting_brief, w3 = _read_lab_brief("FITTING")
    garment_brief, w4 = _read_lab_brief("GARMENT")
    all_warnings.extend(w3)
    all_warnings.extend(w4)

    fit_r = _get_lab_root("FITTING")
    gar_r = _get_lab_root("GARMENT")
    lab_roots = []
    if fit_r:
        p = Path(fit_r).resolve()
        if p.exists():
            lab_roots.append((p, "fitting"))
    if gar_r:
        p = Path(gar_r).resolve()
        if p.exists():
            lab_roots.append((p, "garment"))
    blockers_content = _render_blockers(lab_roots)
    m1_signals_content = _render_m1_signals()

    body_events = _read_lab_progress_events(REPO_ROOT, "body", max_events=5000)
    body_lifecycle = _compute_lifecycle_snapshot(body_events, body_steps, body_closure) if body_steps else _empty_lifecycle(0)

    fitting_lifecycle = _empty_lifecycle(len(fitting_steps))
    if fit_r:
        p = Path(fit_r).resolve()
        if p.exists():
            fitting_events = _read_lab_progress_events(p, "fitting", max_events=5000)
            fitting_lifecycle = _compute_lifecycle_snapshot(fitting_events, fitting_steps, fitting_closure)
            for gate in _extract_round_end_fail_gate_codes(p, "fitting", max_events=200):
                w3.append(_warn_dep(gate, "round_end_fail", "exports/progress/PROGRESS_LOG.jsonl"))

    garment_lifecycle = _empty_lifecycle(len(garment_steps))
    if gar_r:
        p = Path(gar_r).resolve()
        if p.exists():
            garment_events = _read_lab_progress_events(p, "garment", max_events=5000)
            garment_lifecycle = _compute_lifecycle_snapshot(garment_events, garment_steps, garment_closure)
            for gate in _extract_round_end_fail_gate_codes(p, "garment", max_events=200):
                w4.append(_warn_dep(gate, "round_end_fail", "exports/progress/PROGRESS_LOG.jsonl"))

    dep_warnings = {"BODY": [], "FITTING": [], "GARMENT": []}
    ledger = _load_dependency_ledger()
    if ledger:
        observed = _collect_global_observed_paths(lab_roots)
        dep_warnings = _check_dependency_ledger(ledger, observed)
    for gate, hint in dep_warnings.get("BODY", []):
        w1.append(_warn_dep(gate, "dependency", hint))
    for gate, hint in dep_warnings.get("FITTING", []):
        w3.append(_warn_dep(gate, "dependency", hint))
    for gate, hint in dep_warnings.get("GARMENT", []):
        w4.append(_warn_dep(gate, "dependency", hint))

    if ledger:
        m1_warnings = _check_m1_ledger(ledger, observed, lab_roots)
        for warn in m1_warnings.get("BODY", []):
            w1.append(warn)
        for warn in m1_warnings.get("FITTING", []):
            w3.append(warn)
        for warn in m1_warnings.get("GARMENT", []):
            w4.append(warn)

    minset_warnings, root_warns = _check_run_minset(lab_roots)
    for expected in minset_warnings.get("BODY", []):
        w1.append(_warn_dep("RUN_MINSET_MISSING", "observed", expected))
    for expected in minset_warnings.get("FITTING", []):
        w3.append(_warn_dep("RUN_MINSET_MISSING", "observed", expected))
    for expected in minset_warnings.get("GARMENT", []):
        w4.append(_warn_dep("RUN_MINSET_MISSING", "observed", expected))

    for expected in root_warns.get("BODY", []):
        w1.append(_warn_dep("RUN_MANIFEST_ROOT_MISSING", "observed", expected))
    for expected in root_warns.get("FITTING", []):
        w3.append(_warn_dep("RUN_MANIFEST_ROOT_MISSING", "observed", expected))
    for expected in root_warns.get("GARMENT", []):
        w4.append(_warn_dep("RUN_MANIFEST_ROOT_MISSING", "observed", expected))

    round_end_warnings = _check_round_end_missing(lab_roots)
    for expected in round_end_warnings.get("BODY", []):
        w1.append(_warn_dep("ROUND_END_MISSING", "hygiene", expected))
    for expected in round_end_warnings.get("FITTING", []):
        w3.append(_warn_dep("ROUND_END_MISSING", "hygiene", expected))
    for expected in round_end_warnings.get("GARMENT", []):
        w4.append(_warn_dep("ROUND_END_MISSING", "hygiene", expected))

    body_progress = _latest_body_progress(max_items=3)
    body_content = _render_body(
        curated, geo, w1 + w2, body_progress=body_progress, lifecycle=body_lifecycle
    )
    fitting_content = _render_module_brief("FITTING", fitting_brief, w3, lifecycle=fitting_lifecycle)
    garment_content = _render_module_brief("GARMENT", garment_brief, w4, lifecycle=garment_lifecycle)

    try:
        text = OPS_STATUS.read_text(encoding="utf-8")
    except Exception as e:
        print(f"updated ops/STATUS.md (BODY/FITTING/GARMENT/M1), warnings={len(all_warnings)+1}")
        return 0

    text = _ensure_markers(text)

    content_map = {
        "BLOCKERS": blockers_content,
        "M1_SIGNALS": m1_signals_content,
        "BODY": body_content,
        "FITTING": fitting_content,
        "GARMENT": garment_content,
    }
    for module, (mb, me) in MARKERS.items():
        content = content_map.get(module)
        if content is None:
            continue
        block = f"{mb}\n{content}\n{me}"
        if mb in text and me in text:
            def replacer(m, b=block):
                return b
            text = re.sub(rf"{re.escape(mb)}[\s\S]*?{re.escape(me)}", replacer, text, count=1)

    try:
        tmp_path = OPS_STATUS.parent / f"STATUS.md.tmp.{os.getpid()}"
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, OPS_STATUS)
    except Exception as e:
        print(f"updated ops/STATUS.md (BODY/FITTING/GARMENT/M1), warnings={len(all_warnings)+1}")
        return 0

    print(f"updated ops/STATUS.md (BODY/FITTING/GARMENT/M1), warnings={len(all_warnings)}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
