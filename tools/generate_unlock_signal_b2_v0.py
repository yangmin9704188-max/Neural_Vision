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


def _parse_float_list(s: str, default: list[float]) -> list[float]:
    """Parse comma-separated floats; return default on empty/invalid. No NaN/Inf."""
    s = (s or "").strip()
    if not s:
        return default
    out = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            v = float(part)
            if math.isfinite(v):
                out.append(v)
        except ValueError:
            continue
    return out if out else default


def _parse_int_list(s: str, default: list[int]) -> list[int]:
    """Parse comma-separated ints; return default on empty/invalid."""
    s = (s or "").strip()
    if not s:
        return default
    out = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out if out else default


def _compute_recommendations(
    metrics: dict,
    summary: dict,
    residual_candidates: list[float],
    score_candidates: list[int],
    max_failures: int,
    generated_at: str,
) -> dict:
    """Compute advisory recommendations from metrics only. Deterministic. No effect on unlock_candidate."""
    based_on = ["residual_cm.p90_per_key", "quality_score.p90", "quality_score.min", "failures_count"]
    rec_warnings: list[str] = []

    # Per residual candidate: all_keys_meet_p90
    residual_results: list[dict] = []
    for thr in residual_candidates:
        all_meet = True
        per_key: dict[str, bool] = {}
        for key, stats in metrics["residual_cm"].items():
            p90 = stats.get("p90")
            if p90 is None:
                per_key[key] = False
                all_meet = False
            else:
                ok = abs(p90) <= thr
                per_key[key] = ok
                if not ok:
                    all_meet = False
        residual_results.append({
            "threshold_residual_p90_cm": thr,
            "meets_p90_per_key": per_key,
            "all_keys_meet_p90": all_meet,
        })

    # Per score candidate: quality_meets_p90, quality_meets_min
    q90 = metrics["quality_score"].get("p90")
    qmin = metrics["quality_score"].get("min")
    score_results: list[dict] = []
    for thr in score_candidates:
        score_results.append({
            "threshold_score": thr,
            "quality_meets_p90": q90 is not None and q90 >= thr,
            "quality_meets_min": qmin is not None and qmin >= thr,
        })

    # Cartesian product: combined_rows
    combined_rows: list[dict] = []
    for r in residual_results:
        for s in score_results:
            would_be = (
                metrics["failures_count"] <= max_failures
                and r["all_keys_meet_p90"]
                and s["quality_meets_p90"]
            )
            combined_rows.append({
                "residual_thr_p90_cm": r["threshold_residual_p90_cm"],
                "score_thr_p90": s["threshold_score"],
                "all_keys_meet_p90": r["all_keys_meet_p90"],
                "quality_meets_p90": s["quality_meets_p90"],
                "would_be_candidate_by_p90": would_be,
                "notes": [] if would_be else ["residual_or_quality_threshold_not_met"],
            })

    # Implied fraction: only when summary has proposed_unlock_signal.fraction_above_threshold at a matching score
    prop = summary.get("proposed_unlock_signal") or {}
    frac_value = prop.get("fraction_above_threshold")
    if frac_value is not None and math.isfinite(frac_value):
        implied_ok_fraction = round(frac_value, 4)
        summary_score = prop.get("threshold_score")
        if summary_score is not None and int(summary_score) in score_candidates:
            implied_rates = {
                "implied_ok_fraction": implied_ok_fraction,
                "at_threshold_score": int(summary_score),
                "notes": [],
            }
        else:
            implied_rates = {
                "implied_ok_fraction": implied_ok_fraction,
                "at_threshold_score": int(summary_score) if summary_score is not None else None,
                "notes": ["fraction_from_summary_single_threshold_only"],
            }
    else:
        implied_rates = {
            "implied_ok_fraction": None,
            "at_threshold_score": None,
            "notes": ["FRACTION_NOT_AVAILABLE"],
        }
        rec_warnings.append("FRACTION_NOT_AVAILABLE")

    return {
        "generated_at": generated_at,
        "based_on_metrics": based_on,
        "suggested_thresholds": {
            "threshold_residual_p90_cm_candidates": residual_candidates,
            "threshold_score_candidates": score_candidates,
        },
        "residual_candidate_results": residual_results,
        "score_candidate_results": score_results,
        "combined_rows": combined_rows,
        "implied_rates": implied_rates,
        "warnings": rec_warnings,
    }


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
    parser.add_argument("--recommend_thresholds", action="store_true", help="Add advisory threshold recommendations to output")
    parser.add_argument("--residual_threshold_candidates", default="0.8,1.0,1.2", help="Comma-separated residual p90 cm candidates (default 0.8,1.0,1.2)")
    parser.add_argument("--score_threshold_candidates", default="65,70,75", help="Comma-separated score candidates (default 65,70,75)")
    parser.add_argument("--emit_recommendations_only", action="store_true", help="When set, do not append progress event (recommendations output only)")
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

    if getattr(args, "recommend_thresholds", False):
        residual_cands = _parse_float_list(
            getattr(args, "residual_threshold_candidates", "0.8,1.0,1.2"),
            [0.8, 1.0, 1.2],
        )
        score_cands = _parse_int_list(
            getattr(args, "score_threshold_candidates", "65,70,75"),
            [65, 70, 75],
        )
        payload["recommendations"] = _compute_recommendations(
            metrics,
            summary,
            residual_cands,
            score_cands,
            args.max_failures,
            created_at,
        )

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

    if getattr(args, "recommend_thresholds", False) and "recommendations" in payload:
        rec = payload["recommendations"]
        md_lines.append("")
        md_lines.append("## Recommended thresholds (advisory)")
        md_lines.append("| residual_thr_p90_cm | score_thr_p90 | all_keys_meet_p90 | quality_meets_p90 | would_be_candidate_by_p90 | notes |")
        md_lines.append("|--------------------|--------------|-------------------|-------------------|---------------------------|-------|")
        for row in rec.get("combined_rows", []):
            res_thr = row.get("residual_thr_p90_cm")
            score_thr = row.get("score_thr_p90")
            all_meet = row.get("all_keys_meet_p90", False)
            q_meet = row.get("quality_meets_p90", False)
            would_be = row.get("would_be_candidate_by_p90", False)
            notes_str = "; ".join(row.get("notes", [])) or "-"
            md_lines.append(f"| {res_thr} | {score_thr} | {all_meet} | {q_meet} | {would_be} | {notes_str} |")
        impl = rec.get("implied_rates", {})
        frac = impl.get("implied_ok_fraction")
        at_thr = impl.get("at_threshold_score")
        if frac is not None or impl.get("notes"):
            md_lines.append("")
            md_lines.append(f"- implied_ok_fraction: {frac}")
            md_lines.append(f"- at_threshold_score: {at_thr}")
            for n in impl.get("notes", []):
                md_lines.append(f"- {n}")

    md_path = out_dir / "KPI_UNLOCK.md"
    tmp_md = out_dir / f"KPI_UNLOCK.md.tmp.{os.getpid()}"
    tmp_md.write_text("\n".join(md_lines), encoding="utf-8")
    os.replace(tmp_md, md_path)

    print(f"[DONE] unlock_candidate={candidate} -> {json_path}")

    if args.log_progress and not getattr(args, "emit_recommendations_only", False):
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
