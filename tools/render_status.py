#!/usr/bin/env python3
"""
Render ops/STATUS.md BODY generated section from latest curated and geo runs.
Read-only: data/derived, exports/runs. Overwrites only GENERATED:BEGIN:BODY..END:BODY.
Exit 0 always; failures surface as Warnings in output.
"""
from pathlib import Path
from datetime import datetime
import json
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_STATUS = REPO_ROOT / "ops" / "STATUS.md"
MARKER_BEGIN = "<!-- GENERATED:BEGIN:BODY -->"
MARKER_END = "<!-- GENERATED:END:BODY -->"


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
        out["warnings"].append(f"RUN_LOG parse failed: {e}")
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
        warnings.append("data/derived/curated_v0 not found")
        return out, warnings

    parquets = list(base.rglob("curated_v0.parquet"))
    if not parquets:
        warnings.append("no curated_v0.parquet found")
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
                warnings.append(f"parquet read fallback failed: {e}")
        except Exception as e:
            warnings.append(f"parquet metadata read failed: {e}")

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
        warnings.append("exports/runs not found")
        return out, warnings

    files = list(base.rglob("facts_summary.json"))
    if not files:
        warnings.append("no facts_summary.json found")
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
        warnings.append(f"facts_summary parse failed: {e}")

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
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


def _ensure_markers(text: str) -> str:
    """If BODY markers missing, insert under first ## Dashboard (generated-only) in Body section."""
    if MARKER_BEGIN in text and MARKER_END in text:
        return text

    pattern = r"(## Body[\s\S]*?### Dashboard \(generated-only\)\s*\n)"
    match = re.search(pattern, text)
    if match:
        insert = match.group(0) + f"{MARKER_BEGIN}\n- N/A\n{MARKER_END}\n"
        text = text[: match.start()] + insert + text[match.end() :]
    else:
        text = text.rstrip() + f"\n\n{MARKER_BEGIN}\n- N/A\n{MARKER_END}\n"
    return text


def main() -> int:
    curated, w1 = _latest_curated()
    geo, w2 = _latest_geo()
    warnings = w1 + w2

    content = _render_body(curated, geo, warnings)
    block = f"{MARKER_BEGIN}\n{content}\n{MARKER_END}"

    try:
        text = OPS_STATUS.read_text(encoding="utf-8")
    except Exception as e:
        print(f"updated ops/STATUS.md (BODY) — read failed: {e}, warnings={len(warnings)+1}")
        return 0

    text = _ensure_markers(text)

    if MARKER_BEGIN in text and MARKER_END in text:
        text = re.sub(
            rf"{re.escape(MARKER_BEGIN)}[\s\S]*?{re.escape(MARKER_END)}",
            block,
            text,
            count=1,
        )
    else:
        text = text.rstrip() + "\n\n" + block + "\n"

    try:
        OPS_STATUS.write_text(text, encoding="utf-8")
    except Exception as e:
        print(f"updated ops/STATUS.md (BODY) — write failed: {e}, warnings={len(warnings)+1}")
        return 0

    print(f"updated ops/STATUS.md (BODY), warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
