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
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_STATUS = REPO_ROOT / "ops" / "STATUS.md"

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


def _render_body(curated: dict, geo: dict, warnings: list[str]) -> str:
    try:
        from zoneinfo import ZoneInfo
        ts = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    except ImportError:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [f"*Updated: {ts}*", ""]

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

    if warnings:
        lines.append("### Warnings")
        for w in _sort_warnings(warnings):
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


def _read_lab_brief(module: str) -> tuple[dict, list[str]]:
    """Read brief from FITTING_LAB_ROOT or GARMENT_LAB_ROOT env. Returns brief_path, mtime, head_12."""
    out = {"brief_path": "N/A", "brief_mtime": "N/A", "brief_head": []}
    warnings = []
    env_key = "FITTING_LAB_ROOT" if module == "FITTING" else "GARMENT_LAB_ROOT"
    lab_root = os.environ.get(env_key, "").strip()
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


def _render_module_brief(module: str, brief: dict, warnings: list[str]) -> str:
    lines = [f"- brief_path: {brief['brief_path']}", f"- brief_mtime: {brief['brief_mtime']}"]
    if brief["brief_head"]:
        lines.append("- brief_head:")
        for ln in brief["brief_head"]:
            lines.append(f"  {ln}")
    if warnings:
        lines.append("- warnings:")
        for w in _sort_warnings(warnings):
            lines.append(f"  - {w}")
    return "\n".join(lines)


def _ensure_markers(text: str) -> str:
    """If any markers missing, insert placeholder under ## Dashboard (generated-only) per section."""
    for module, (mb, me) in MARKERS.items():
        if mb not in text or me not in text:
            section = module.lower().capitalize()
            pattern = rf"(## {section}[\s\S]*?### Dashboard \(generated-only\)\s*\n)"
            match = re.search(pattern, text)
            if match:
                placeholder = f"- N/A (placeholder)\n" if module != "BODY" else "- N/A\n"
                insert = match.group(0) + f"{mb}\n{placeholder}{me}\n"
                text = text[: match.start()] + insert + text[match.end() :]
    return text


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

    body_content = _render_body(curated, geo, w1 + w2)
    fitting_content = _render_module_brief("FITTING", fitting_brief, w3)
    garment_content = _render_module_brief("GARMENT", garment_brief, w4)

    try:
        text = OPS_STATUS.read_text(encoding="utf-8")
    except Exception as e:
        print(f"updated ops/STATUS.md (BODY/FITTING/GARMENT), warnings={len(all_warnings)+1}")
        return 0

    text = _ensure_markers(text)

    for module, (mb, me) in MARKERS.items():
        if module == "BODY":
            content = body_content
        elif module == "FITTING":
            content = fitting_content
        else:
            content = garment_content
        block = f"{mb}\n{content}\n{me}"
        if mb in text and me in text:
            text = re.sub(rf"{re.escape(mb)}[\s\S]*?{re.escape(me)}", lambda m, b=block: b, text, count=1)

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
