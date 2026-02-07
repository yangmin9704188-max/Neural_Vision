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

# Path classification for observed_paths (priority order: lower = higher priority)
PATH_PRIORITY = {"RUN_EVIDENCE": 0, "MANIFEST": 1, "OTHER": 2, "SAMPLE": 3}
OPS_STATUS = REPO_ROOT / "ops" / "STATUS.md"
LAB_ROOTS_PATH = REPO_ROOT / "ops" / "lab_roots.local.json"

# Warning format: [CODE] message | path=<path or N/A>
def _warn(code: str, message: str, path: str = "N/A") -> str:
    """Format warning: [CODE] message | path=<path>"""
    return f"[{code}] {message} | path={path}"


def _sort_warnings(warnings: list[str]) -> list[str]:
    """Sort by CODE then path for stable diff."""
    def key(w: str) -> tuple:
        m = re.match(r"\[([^\]]+)\].*\| path=(.*)", w)
        if m:
            return (m.group(1), m.group(2))
        return (w, "")

    return sorted(warnings, key=key)


def _normalize_line(line: str) -> str:
    """CRLF/LF -> LF, tab -> 2 spaces, strip trailing."""
    s = line.replace("\r\n", "\n").replace("\r", "\n").expandtabs(2)
    return s.rstrip()


def _normalize_lines(lines: list[str]) -> list[str]:
    return [_normalize_line(ln) for ln in lines]


MARKERS = {
    "BLOCKERS": ("<!-- GENERATED:BEGIN:BLOCKERS -->", "<!-- GENERATED:END:BLOCKERS -->"),
    "BODY": ("<!-- GENERATED:BEGIN:BODY -->", "<!-- GENERATED:END:BODY -->"),
    "FITTING": ("<!-- GENERATED:BEGIN:FITTING -->", "<!-- GENERATED:END:FITTING -->"),
    "GARMENT": ("<!-- GENERATED:BEGIN:GARMENT -->", "<!-- GENERATED:END:GARMENT -->"),
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
    curated: dict, geo: dict, warnings: list[str], *, body_progress: list[dict] | None = None
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


def _aggregate_blockers_top_n(lab_roots: list[tuple[Path, str]], n: int = 5) -> list[tuple[str, int]]:
    """Aggregate gate codes from labs, return top n by count."""
    from collections import Counter
    all_codes = []
    for lab_root, module in lab_roots:
        if lab_root and lab_root.exists():
            events = _read_lab_progress_events(lab_root, module, max_events=50)
            all_codes.extend(_extract_gate_codes_from_events(events))
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
            with open(LAB_ROOTS_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            val = (cfg.get(env_key) or "").strip()
            if val:
                lab_root = str((REPO_ROOT / val).resolve())
        except Exception:
            pass
    return lab_root


def _read_lab_brief(module: str) -> tuple[dict, list[str]]:
    """Read brief from FITTING_LAB_ROOT or GARMENT_LAB_ROOT (ENV or lab_roots.local.json). Returns brief_path, mtime, head_12, observed_paths."""
    out = {"brief_path": "N/A", "brief_mtime": "N/A", "brief_head": [], "observed_paths": [], "path_hygiene": [], "progress_hygiene": []}
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
    if not brief_path.exists():
        warnings.append(_warn("BRIEF_NOT_FOUND", "brief not found", str(brief_path)))
        return out, warnings

    observed_paths, path_hygiene = _extract_observed_paths(root, module, max_items=3)
    out["observed_paths"] = observed_paths
    out["path_hygiene"] = path_hygiene
    out["progress_hygiene"] = _compute_progress_hygiene(root, module)
    try:
        out["brief_path"] = str(brief_path)
        mtime = brief_path.stat().st_mtime
        try:
            from zoneinfo import ZoneInfo
            dt = datetime.fromtimestamp(mtime, tz=ZoneInfo("Asia/Seoul"))
        except ImportError:
            dt = datetime.fromtimestamp(mtime)
        out["brief_mtime"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        raw = brief_path.read_text(encoding="utf-8", errors="replace")
        lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        out["brief_head"] = _normalize_lines(lines[:12])
    except Exception as e:
        warnings.append(_warn("BRIEF_READ_FAIL", str(e), str(brief_path)))

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


def _render_module_brief(module: str, brief: dict, warnings: list[str]) -> str:
    soft = list(brief.get("path_hygiene") or [])
    soft.extend(brief.get("progress_hygiene") or [])
    brief_warn_codes = _parse_brief_head_warnings(brief.get("brief_head") or [])
    soft.extend(brief_warn_codes)
    soft_warns = [_warn(c, "observed", "N/A") for c in soft]
    all_w = warnings + soft_warns
    nw = len(all_w)
    health = "OK (warnings=0)" if nw == 0 else f"WARN (warnings={nw})"
    lines = [f"- health: {health}"]
    if nw > 0:
        top3 = _sort_warnings(all_w)[:3]
        lines.append(f"- health_summary: {'; '.join(top3)}")
    lines.append(f"- brief_path: {brief['brief_path']}")
    lines.append(f"- brief_mtime: {brief['brief_mtime']}")
    paths = brief.get("observed_paths") or []
    if paths:
        lines.append("- observed_paths:")
        for p in paths[:3]:
            lines.append(f"  - {p}")
    else:
        lines.append("- observed_paths: N/A (no evidence paths observed in progress events yet)")
    if brief["brief_head"]:
        lines.append("- brief_head:")
        for ln in brief["brief_head"]:
            lines.append(f"  {ln}")
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
    for module, (mb, me) in MARKERS.items():
        if module == "BLOCKERS":
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
    return out


def _check_dependency_ledger(
    ledger: dict,
    observed_paths: set[str],
) -> dict[str, list[str]]:
    """
    Check dependency ledger against observed paths. enforcement_u1=warn only (no FAIL).
    Returns {module_upper: [gate_code, ...]} for modules with missing deps.
    """
    result = {"BODY": [], "FITTING": [], "GARMENT": []}
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
        consumer = (row.get("consumer_module") or "").lower()
        producer = (row.get("producer_module") or "").lower()
        if consumer == "fitting":
            result["FITTING"].append(gate)
        elif consumer == "garment":
            result["GARMENT"].append(gate)
        elif consumer == "ops" and producer == "body":
            result["BODY"].append(gate)
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


def main() -> int:
    all_warnings = []

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

    dep_warnings = {"BODY": [], "FITTING": [], "GARMENT": []}
    ledger = _load_dependency_ledger()
    if ledger:
        observed = _collect_global_observed_paths(lab_roots)
        dep_warnings = _check_dependency_ledger(ledger, observed)
    for gate in dep_warnings.get("BODY", []):
        w1.append(_warn(gate, "dependency", "N/A"))
    for gate in dep_warnings.get("FITTING", []):
        w3.append(_warn(gate, "dependency", "N/A"))
    for gate in dep_warnings.get("GARMENT", []):
        w4.append(_warn(gate, "dependency", "N/A"))

    body_progress = _latest_body_progress(max_items=3)
    body_content = _render_body(curated, geo, w1 + w2, body_progress=body_progress)
    fitting_content = _render_module_brief("FITTING", fitting_brief, w3)
    garment_content = _render_module_brief("GARMENT", garment_brief, w4)

    try:
        text = OPS_STATUS.read_text(encoding="utf-8")
    except Exception as e:
        print(f"updated ops/STATUS.md (BODY/FITTING/GARMENT), warnings={len(all_warnings)+1}")
        return 0

    text = _ensure_markers(text)

    content_map = {"BLOCKERS": blockers_content, "BODY": body_content, "FITTING": fitting_content, "GARMENT": garment_content}
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
        print(f"updated ops/STATUS.md (BODY/FITTING/GARMENT), warnings={len(all_warnings)+1}")
        return 0

    print(f"updated ops/STATUS.md (BODY/FITTING/GARMENT), warnings={len(all_warnings)}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
