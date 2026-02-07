#!/usr/bin/env python3
"""
Generate B2 unlock signal from a beta_fit_v0 run_dir.
Facts-only; no hard gating. Emits unlock_signal.json + KPI_UNLOCK.md.
Deterministic: same summary.json + thresholds -> byte-identical output.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TOOL_VERSION = "1.0"
SCHEMA_VERSION = "unlock_signal.b2.v0"


def _sanitize_number(v: float | None) -> float | None:
    if v is None:
        return None
    if math.isfinite(v):
        return v
    return None


def _sanitize_metrics(summary: dict) -> tuple[dict, list[str]]:
    """Extract metrics from summary; replace NaN/Inf with null; return (metrics, warnings)."""
    warnings: list[str] = []
    quality = summary.get("quality_score_stats") or {}
    residual_stats = summary.get("residual_cm_stats") or {}
    bucket = summary.get("bucket_counts") or {}
    dominant = summary.get("dominant_pattern_counts") or {}
    failures = summary.get("failures") or {}
    failures_count = int(failures.get("count", 0)) if isinstance(failures.get("count"), (int, float)) else 0

    quality_out = {}
    for k in ("p50", "p90", "min"):
        v = quality.get(k)
        if v is not None and not math.isfinite(v):
            warnings.append(f"quality_score_stats.{k} non-finite, replaced with null")
            v = None
        quality_out[k] = _sanitize_number(v) if v is not None else None

    residual_out = {}
    for key, stats in residual_stats.items():
        if not isinstance(stats, dict):
            continue
        residual_out[key] = {}
        for q in ("p50", "p90", "max"):
            v = stats.get(q)
            if v is not None and not math.isfinite(v):
                warnings.append(f"residual_cm_stats.{key}.{q} non-finite, replaced with null")
                v = None
            residual_out[key][q] = _sanitize_number(v) if v is not None else None

    return {
        "quality_score": quality_out,
        "residual_cm": residual_out,
        "failures_count": failures_count,
        "bucket_counts": dict(bucket),
        "dominant_pattern_counts": dict(dominant),
    }, warnings


def _evaluate_candidate(
    metrics: dict,
    threshold_score: float,
    threshold_residual_p90_cm: float,
    max_failures: int,
    threshold_fraction_above_score: float | None,
    summary: dict,
) -> tuple[bool, list[str], list[str]]:
    """Return (unlock_candidate, reasons, extra_warnings)."""
    reasons: list[str] = []
    extra_warnings: list[str] = []

    # failures_count <= max_failures
    fc = metrics["failures_count"]
    if fc <= max_failures:
        reasons.append(f"failures_count={fc} (<= max_failures={max_failures})")
    else:
        reasons.append(f"failures_count={fc} (> max_failures={max_failures})")

    # |residual_p90_cm[key]| <= threshold_residual_p90_cm
    for key, stats in metrics["residual_cm"].items():
        p90 = stats.get("p90")
        if p90 is None:
            extra_warnings.append(f"residual_cm.{key}.p90 missing")
            continue
        abs_p90 = abs(p90)
        if abs_p90 <= threshold_residual_p90_cm:
            reasons.append(f"residual_p90_cm[{key}]={p90:.4f} (|{abs_p90:.4f}| <= {threshold_residual_p90_cm})")
        else:
            reasons.append(f"residual_p90_cm[{key}]={p90:.4f} (|{abs_p90:.4f}| > {threshold_residual_p90_cm})")

    # quality_score_p90 >= threshold_score
    q90 = metrics["quality_score"].get("p90")
    if q90 is not None:
        if q90 >= threshold_score:
            reasons.append(f"quality_p90={q90:.2f} (>= {threshold_score})")
        else:
            reasons.append(f"quality_p90={q90:.2f} (< {threshold_score})")
    else:
        extra_warnings.append("quality_score.p90 missing")

    # optional: fraction_above_score_threshold
    if threshold_fraction_above_score is not None:
        prop = summary.get("proposed_unlock_signal") or {}
        frac = prop.get("fraction_above_threshold")
        if frac is not None and math.isfinite(frac):
            if frac >= threshold_fraction_above_score:
                reasons.append(f"fraction_above_score_threshold={frac:.4f} (>= {threshold_fraction_above_score})")
            else:
                reasons.append(f"fraction_above_score_threshold={frac:.4f} (< {threshold_fraction_above_score})")
        else:
            extra_warnings.append("fraction_above_threshold missing in summary")

    # unlock_candidate: all "positive" rules must hold
    candidate = fc <= max_failures
    if q90 is not None and q90 < threshold_score:
        candidate = False
    for key, stats in metrics["residual_cm"].items():
        p90 = stats.get("p90")
        if p90 is not None and abs(p90) > threshold_residual_p90_cm:
            candidate = False
            break
    if threshold_fraction_above_score is not None:
        prop = summary.get("proposed_unlock_signal") or {}
        frac = prop.get("fraction_above_threshold")
        if frac is not None and math.isfinite(frac) and frac < threshold_fraction_above_score:
            candidate = False

    return candidate, reasons, extra_warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate B2 unlock signal from beta_fit_v0 run_dir")
    parser.add_argument("--run_dir", required=True, help="beta_fit_v0 run directory (must contain summary.json)")
    parser.add_argument("--out_dir", required=True, help="Output directory (unlock_signal.json, KPI_UNLOCK.md)")
    parser.add_argument("--threshold_score", type=float, default=70.0, help="Minimum quality_score p90 (default 70)")
    parser.add_argument("--threshold_residual_p90_cm", type=float, default=1.0, help="Max |residual p90| per key in cm (default 1.0)")
    parser.add_argument("--max_failures", type=int, default=0, help="Max allowed failures_count (default 0)")
    parser.add_argument("--threshold_fraction_above_score", type=float, default=None, help="Optional min fraction above threshold_score")
    parser.add_argument("--log-progress", action="store_true", help="Append progress event and run ops render_status")
    parser.add_argument("--created_at", default=None, help="Override created_at (ISO UTC); for determinism tests")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        print(f"[ERROR] summary.json not found: {summary_path}", file=sys.stderr)
        return 1

    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)
    beta_fit_schema = summary.get("schema_version") or "beta_fit_v0"

    metrics, warn_list = _sanitize_metrics(summary)
    candidate, reasons, extra = _evaluate_candidate(
        metrics,
        args.threshold_score,
        args.threshold_residual_p90_cm,
        args.max_failures,
        args.threshold_fraction_above_score,
        summary,
    )
    warn_list.extend(extra)

    rules = {
        "threshold_score": args.threshold_score,
        "threshold_residual_p90_cm": args.threshold_residual_p90_cm,
        "max_failures": args.max_failures,
    }
    if args.threshold_fraction_above_score is not None:
        rules["threshold_fraction_above_score"] = args.threshold_fraction_above_score

    try:
        run_dir_norm = str(run_dir)
    except Exception:
        run_dir_norm = args.run_dir

    created_at = args.created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_dir": run_dir_norm,
        "created_at": created_at,
        "source": {"beta_fit_schema_version": beta_fit_schema, "tool_version": TOOL_VERSION},
        "metrics": metrics,
        "rules": rules,
        "unlock_candidate": candidate,
        "reasons": reasons,
        "warnings": warn_list,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "unlock_signal.json"
    tmp_json = out_dir / f"unlock_signal.json.tmp.{os.getpid()}"
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp_json, json_path)

    # KPI_UNLOCK.md
    md_lines = [
        "# B2 Unlock Signal (facts-only)",
        "",
        f"- schema_version: {SCHEMA_VERSION}",
        f"- run_dir: {run_dir_norm}",
        f"- created_at: {created_at}",
        f"- unlock_candidate: {candidate}",
        "",
        "## Rules used",
    ]
    for k, v in rules.items():
        md_lines.append(f"- {k}: {v}")
    md_lines.append("")
    md_lines.append("## Metrics")
    md_lines.append("- quality_score: p50, p90, min")
    for k, v in metrics["quality_score"].items():
        md_lines.append(f"  - {k}: {v if v is None else f'{v:.2f}'}")
    md_lines.append("- residual_cm (p50, p90, max) per key:")
    for key, stats in metrics["residual_cm"].items():
        s = {k: (f"{v:.4f}" if v is not None else "null") for k, v in stats.items()}
        md_lines.append(f"  - {key}: {s}")
    md_lines.append(f"- failures_count: {metrics['failures_count']}")
    md_lines.append(f"- bucket_counts: {metrics['bucket_counts']}")
    md_lines.append("")
    md_lines.append("## Reasons")
    for r in reasons:
        md_lines.append(f"- {r}")
    if warn_list:
        md_lines.append("")
        md_lines.append("## Warnings")
        for w in warn_list:
            md_lines.append(f"- {w}")
    md_path = out_dir / "KPI_UNLOCK.md"
    tmp_md = out_dir / f"KPI_UNLOCK.md.tmp.{os.getpid()}"
    tmp_md.write_text("\n".join(md_lines), encoding="utf-8")
    os.replace(tmp_md, md_path)

    print(f"[DONE] unlock_candidate={candidate} -> {json_path}")

    if args.log_progress:
        try:
            rel_out = out_dir.relative_to(_REPO)
        except ValueError:
            rel_out = out_dir
        q90 = metrics["quality_score"].get("p90")
        q90_str = f"{q90:.2f}" if q90 is not None else "N/A"
        res_p90 = metrics["residual_cm"]
        res_str = ",".join(f"{k}:{res_p90[k].get('p90')}" for k in sorted(res_p90.keys()))
        note = (
            f"B2 unlock signal: candidate={str(candidate).lower()}, quality_p90={q90_str}, "
            f"residual_p90_cm={{{res_str}}}, failures={metrics['failures_count']}, run_dir={rel_out}"
        )
        import subprocess
        subprocess.run(
            [
                sys.executable,
                str(_REPO / "tools" / "ops" / "append_progress_event.py"),
                "--lab-root", str(_REPO),
                "--module", "body",
                "--step-id", "B04",
                "--event", "note",
                "--note", note,
                "--evidence", str(rel_out),
            ],
            cwd=str(_REPO),
            check=False,
        )
        subprocess.run(
            [sys.executable, str(_REPO / "tools" / "render_status.py")],
            cwd=str(_REPO),
            check=False,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
