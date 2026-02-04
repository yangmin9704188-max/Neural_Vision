#!/usr/bin/env python3
"""
Curated v0 Facts-Only Runner (Round 20).

Purpose: Load golden_real_data_v0.npz (measurements only), aggregate per-key stats
and warnings, emit facts_summary.json + md report. No geometric measurement.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Repo root (4 levels up: runners -> src -> body -> modules -> repo)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]

_CORE_KEYS_ORDER = ["HEIGHT_M", "BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M", "NECK_CIRC_M"]


def _abs(p: Path) -> Path:
    return p.resolve()


def get_git_sha() -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(_PROJECT_ROOT),
        )
        return r.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def load_npz(npz_path: Path) -> tuple[
    List[Dict[str, Any]],
    List[str],
    List[str],
    List[Dict[str, Any]],
    Optional[str],
    Optional[str],
]:
    """
    Load golden_real_data NPZ. Returns:
        measurements_list, case_ids, case_classes, case_metadata_list, source_path_abs, meta_unit
    """
    npz_path = _abs(npz_path)
    print(f"[NPZ LOAD] Loading NPZ from: {npz_path}")
    print(f"[NPZ LOAD] File exists: {npz_path.exists()}")
    if npz_path.exists():
        st = npz_path.stat()
        print(f"[NPZ LOAD] File size: {st.st_size / 1024:.1f} KB")
        print(f"[NPZ LOAD] File mtime: {st.st_mtime}")

    data = np.load(npz_path, allow_pickle=True)
    keys_loaded = list(data.files)
    print(f"[NPZ LOAD] Loaded NPZ keys: {keys_loaded}")

    measurements = data["measurements"]
    n = len(measurements)
    measurements_list = [measurements[i].item() if hasattr(measurements[i], "item") else measurements[i] for i in range(n)]

    case_id_arr = data.get("case_id", None)
    if case_id_arr is not None:
        case_ids = [str(case_id_arr[i]) for i in range(len(case_id_arr))]
    else:
        case_ids = [f"case_{i}" for i in range(n)]

    case_class_arr = data.get("case_class", None)
    if case_class_arr is not None:
        case_classes = [str(case_class_arr[i]) for i in range(len(case_class_arr))]
    else:
        case_classes = ["curated_real"] * n

    meta_arr = data.get("case_metadata", None)
    if meta_arr is not None:
        case_metadata_list = [meta_arr[i].item() if hasattr(meta_arr[i], "item") else meta_arr[i] for i in range(n)]
    else:
        case_metadata_list = [{}] * n

    source_path_abs = None
    if "source_path_abs" in data:
        sp = data["source_path_abs"]
        source_path_abs = str(sp) if np.isscalar(sp) else str(sp.flat[0])
    meta_unit = None
    if "meta_unit" in data:
        mu = data["meta_unit"]
        meta_unit = str(mu) if np.isscalar(mu) else str(mu.flat[0])

    return measurements_list, case_ids, case_classes, case_metadata_list, source_path_abs, meta_unit


def aggregate(
    measurements_list: List[Dict[str, Any]],
    case_ids: List[str],
    case_metadata_list: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Per-key count, nan_count, nan_rate, min, median, max; warnings_topN."""
    from collections import Counter

    keys_seen: set = set()
    for m in measurements_list:
        if isinstance(m, dict):
            keys_seen.update(m.keys())

    key_values: Dict[str, List[float]] = defaultdict(list)
    key_warnings: Dict[str, List[str]] = defaultdict(list)

    for i, m in enumerate(measurements_list):
        if not isinstance(m, dict):
            continue
        meta = case_metadata_list[i] if i < len(case_metadata_list) else {} or {}
        warns = meta.get("warnings") or []
        for k, v in m.items():
            keys_seen.add(k)
            if v is None or (isinstance(v, float) and not np.isfinite(v)):
                pass  # nan_count from key_values; warnings from case_metadata only
            else:
                try:
                    key_values[k].append(float(v))
                except (TypeError, ValueError):
                    pass
        for w in warns:
            if not isinstance(w, str):
                continue
            if ":" in w:
                pref, key_part = w.split(":", 1)
                key_part = key_part.strip()
                keys_seen.add(key_part)
                key_warnings[key_part].append(pref.strip())

    summary: Dict[str, Any] = {}
    n = len(measurements_list)
    for k in sorted(keys_seen):
        vals = key_values[k]
        n_valid = len(vals)
        n_nan = n - n_valid
        rate = (n_nan / n * 100) if n else 0.0
        c = Counter(key_warnings[k])
        top_w = [{"reason": r, "n": cnt} for r, cnt in c.most_common(5)]
        summary[k] = {
            "count": n_valid,
            "nan_count": n_nan,
            "nan_rate_pct": round(rate, 2),
            "min": float(np.min(vals)) if vals else None,
            "median": float(np.median(vals)) if vals else None,
            "max": float(np.max(vals)) if vals else None,
            "warnings_top5": top_w,
        }
    return summary


def generate_report(
    summary_json: Dict[str, Any],
    output_path: Path,
    npz_path_abs: str,
    source_path_abs: Optional[str],
) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = summary_json.get("n_samples", 0)
    summary = summary_json.get("summary", {})
    git_sha = summary_json.get("git_sha", "unknown")
    dataset_path = summary_json.get("dataset_path", "unknown")
    ts = summary_json.get("timestamp", "N/A")

    lines = [
        "# Curated v0 Facts-Only Summary (Round 20 – Real Data Golden)",
        "",
        "## 1. 실행 조건",
        "",
        f"- **샘플 수**: {n}",
        f"- **입력 NPZ**: `{dataset_path}`",
        f"- **NPZ 절대경로**: `{npz_path_abs}`",
        f"- **curated_v0 소스 절대경로**: `{source_path_abs or 'N/A'}`",
        f"- **Git SHA**: `{git_sha}`",
        f"- **실행 일시**: {ts}",
        "",
        "## 2. 핵심키 (HEIGHT / BUST / WAIST / HIP / NECK)",
        "",
        "| Key | Count | NaN | NaN % | Min | Median | Max |",
        "|-----|-------|-----|-------|-----|--------|-----|",
    ]

    for k in _CORE_KEYS_ORDER:
        if k not in summary:
            continue
        s = summary[k]
        mn = f"{s['min']:.4f}" if s["min"] is not None else "—"
        md = f"{s['median']:.4f}" if s["median"] is not None else "—"
        mx = f"{s['max']:.4f}" if s["max"] is not None else "—"
        lines.append(f"| {k} | {s['count']} | {s['nan_count']} | {s['nan_rate_pct']}% | {mn} | {md} | {mx} |")

    lines.extend([
        "",
        "## 3. Key별 요약 (전체)",
        "",
        "| Key | Count | NaN | NaN % | Min | Median | Max |",
        "|-----|-------|-----|-------|-----|--------|-----|",
    ])

    for k in sorted(summary.keys()):
        if k in _CORE_KEYS_ORDER:
            continue
        s = summary[k]
        mn = f"{s['min']:.4f}" if s["min"] is not None else "—"
        md = f"{s['median']:.4f}" if s["median"] is not None else "—"
        mx = f"{s['max']:.4f}" if s["max"] is not None else "—"
        lines.append(f"| {k} | {s['count']} | {s['nan_count']} | {s['nan_rate_pct']}% | {mn} | {md} | {mx} |")

    lines.extend([
        "",
        "## 4. Warnings Top-N (요약)",
        "",
    ])
    for k in _CORE_KEYS_ORDER + sorted(k for k in summary if k not in _CORE_KEYS_ORDER):
        s = summary.get(k, {})
        top = s.get("warnings_top5") or []
        if not top:
            continue
        lines.append(f"- **{k}**: " + ", ".join(f"{x['reason']}(n={x['n']})" for x in top))
    if not any(summary.get(k, {}).get("warnings_top5") for k in summary):
        lines.append("(none)")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Curated v0 facts runner (Round 20).")
    default_npz = _PROJECT_ROOT / "verification" / "datasets" / "golden" / "core_measurements_v0" / "golden_real_data_v0.npz"
    ap.add_argument("--npz", type=str, default=str(default_npz), help="Input NPZ path (golden_real_data_v0.npz)")
    ap.add_argument("--out_dir", type=str, default=None, help="Output dir (default: exports/runs/curated_v0/round20_<timestamp>)")
    args = ap.parse_args()

    npz_path = Path(args.npz)
    if not npz_path.is_absolute():
        npz_path = _PROJECT_ROOT / npz_path
    npz_path = _abs(npz_path)

    measurements_list, case_ids, case_classes, case_metadata_list, source_path_abs, meta_unit = load_npz(npz_path)
    n = len(measurements_list)
    print(f"  Loaded {n} cases")

    print(f"\n[PROOF] NPZ: {npz_path}")
    print(f"[PROOF] exists={npz_path.exists()}, size={npz_path.stat().st_size if npz_path.exists() else 0}, mtime={npz_path.stat().st_mtime if npz_path.exists() else 0}")
    if source_path_abs:
        print(f"[PROOF] curated_v0 source: {source_path_abs}")

    summary = aggregate(measurements_list, case_ids, case_metadata_list)

    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else _PROJECT_ROOT / "exports" / "runs" / "curated_v0" / f"round20_{ts}"
    out_dir = _abs(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_json = {
        "git_sha": get_git_sha(),
        "dataset_path": str(npz_path),
        "npz_path_abs": str(npz_path),
        "source_path_abs": source_path_abs,
        "n_samples": n,
        "case_ids": case_ids,
        "summary": summary,
        "timestamp": datetime.now().isoformat(),
    }

    summary_path = out_dir / "facts_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2, ensure_ascii=False)
    print(f"\nSaved summary: {summary_path}")

    report_path = out_dir / "curated_v0_facts_round1.md"
    generate_report(summary_json, report_path, str(npz_path), source_path_abs)
    print(f"Saved report: {report_path}")

    reports_dir = _PROJECT_ROOT / "reports" / "validation"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_final = reports_dir / "curated_v0_facts_round1.md"
    generate_report(summary_json, report_final, str(npz_path), source_path_abs)
    print(f"Saved report (validation): {report_final}")
    print(f"[PROOF] Report absolute path: {_abs(report_final)}")


if __name__ == "__main__":
    main()
