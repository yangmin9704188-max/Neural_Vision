#!/usr/bin/env python3
"""
Render ops/STATUS.md Generated section from latest curated and geo runs.
Read-only: data/derived, exports/runs. Overwrites only GENERATED:BEGIN..END block.
"""
from pathlib import Path
from datetime import datetime
import json

REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_STATUS = REPO_ROOT / "ops" / "STATUS.md"
MARKER_BEGIN = "<!-- GENERATED:BEGIN -->"
MARKER_END = "<!-- GENERATED:END -->"


def _latest_curated() -> dict:
    out = {"run_id": "N/A", "rows": None, "cols": None, "parquet_size": None, "run_log_path": None}
    base = REPO_ROOT / "data" / "derived" / "curated_v0"
    if not base.exists():
        return out
    parquets = list(base.rglob("curated_v0.parquet"))
    if not parquets:
        return out
    latest_parquet = max(parquets, key=lambda p: p.stat().st_mtime)
    latest = latest_parquet.parent
    out["run_id"] = latest.relative_to(base).as_posix()
    parquet = latest_parquet
    run_log = latest / "RUN_LOG.txt"
    if parquet.exists():
        try:
            import pyarrow.parquet as pq
            meta = pq.read_metadata(parquet)
            out["rows"] = meta.num_rows
            out["cols"] = meta.num_columns
            out["parquet_size"] = parquet.stat().st_size
        except Exception:
            pass
    if run_log.exists():
        out["run_log_path"] = run_log.relative_to(REPO_ROOT).as_posix()
    return out


def _latest_geo() -> dict:
    out = {"path": "N/A", "processed": None, "skipped": None, "total": None}
    base = REPO_ROOT / "exports" / "runs"
    if not base.exists():
        return out
    files = list(base.rglob("facts_summary.json"))
    if not files:
        return out
    latest = max(files, key=lambda p: p.stat().st_mtime)
    out["path"] = latest.relative_to(REPO_ROOT).as_posix()
    try:
        with open(latest, encoding="utf-8") as f:
            data = json.load(f)
        out["processed"] = data.get("processed_cases")
        out["skipped"] = data.get("skipped_cases")
        out["total"] = data.get("total_cases")
    except Exception:
        pass
    return out


def _render_content(curated: dict, geo: dict) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "## Generated",
        "",
        "### Last Curated Run",
        f"- RUN_ID: {curated['run_id']}",
    ]
    if curated["rows"] is not None:
        lines.append(f"- Rows: {curated['rows']}, Cols: {curated['cols']}")
    if curated["parquet_size"] is not None:
        lines.append(f"- Parquet size: {curated['parquet_size']:,} bytes")
    if curated["run_log_path"]:
        lines.append(f"- RUN_LOG: {curated['run_log_path']}")
    lines.extend(["", "### Last Geo Run", f"- Path: {geo['path']}"])
    if geo["processed"] is not None:
        lines.append(f"- Processed: {geo['processed']}, Skipped: {geo['skipped']}, Total: {geo['total']}")
    lines.extend(["", f"*Rendered: {ts}*", ""])
    return "\n".join(lines)


def main() -> int:
    curated = _latest_curated()
    geo = _latest_geo()
    content = _render_content(curated, geo)
    block = f"{MARKER_BEGIN}\n{content}{MARKER_END}"

    text = OPS_STATUS.read_text(encoding="utf-8")
    if MARKER_BEGIN not in text or MARKER_END not in text:
        text = text.rstrip() + "\n\n" + block + "\n"
    else:
        start = text.find(MARKER_BEGIN)
        end = text.find(MARKER_END) + len(MARKER_END)
        text = text[:start] + block + text[end:]

    OPS_STATUS.write_text(text, encoding="utf-8")
    print("Rendered ops/STATUS.md Generated section")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
