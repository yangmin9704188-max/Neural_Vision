#!/usr/bin/env python3
"""
Step3: SMPL-X beta optimization v0 — fit target measurements (BUST/WAIST/HIP) for prototypes.
Deterministic, atomic writes, facts-only. Pluggable mesh_provider (dummy when SMPL-X unavailable).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

U1_KEYS = ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]
QUALITY_THRESHOLD = 70
QUALITY_WEIGHTS = {"BUST_CIRC_M": 1.0, "WAIST_CIRC_M": 1.0, "HIP_CIRC_M": 1.0}
DOMINANT_MAP = {"BUST_CIRC_M": "TORSO_UPPER", "WAIST_CIRC_M": "TORSO_MID", "HIP_CIRC_M": "TORSO_LOWER"}


def quality_bucket(score: float, threshold: float = QUALITY_THRESHOLD) -> str:
    """Facts-only bucket: OK if score >= threshold else LOW. Exposed for tests."""
    return "OK" if score >= threshold else "LOW"


class MeshProvider(Protocol):
    def generate_mesh(self, beta: list[float], pose_id: str = "PZ1") -> tuple[Any, Any]:
        """Return (verts, faces). verts (N,3) in meters."""
        ...


def _measure_verts(verts: Any, keys: list[str]) -> dict[str, float | None]:
    import numpy as np
    from modules.body.src.measurements.vtm.core_measurements_v0 import measure_circumference_v0_with_metadata
    out = {}
    v = np.asarray(verts, dtype=np.float32)
    if v.ndim == 3:
        v = v[0]
    for k in keys:
        if k not in U1_KEYS:
            continue
        res = measure_circumference_v0_with_metadata(v, k)
        val = getattr(res, "value_m", None)
        if val is not None and (math.isnan(val) or math.isinf(val)):
            val = None
        out[k] = val
    return out


def quality_score_from_residuals_m(residuals_m: dict[str, float], keys: list[str] | None = None) -> float:
    """score = 100 - clamp( weighted sum |residual_cm|, 0, 100 ). Exposed for tests."""
    keys = keys or list(residuals_m.keys())
    pen = 0.0
    for k in keys:
        r = residuals_m.get(k)
        if r is not None:
            pen += QUALITY_WEIGHTS.get(k, 1.0) * abs(r) * 100  # m -> cm
    return max(0.0, min(100.0, 100.0 - pen))


def _quality_score(residuals_m: dict[str, float], keys: list[str]) -> float:
    return quality_score_from_residuals_m(residuals_m, keys)


def _dominant_and_ranked(residuals_m: dict[str, float], keys: list[str]) -> tuple[str, list[str]]:
    abs_res = [(k, abs(residuals_m.get(k) or 0)) for k in keys]
    abs_res.sort(key=lambda x: -x[1])
    ranked = [x[0] for x in abs_res]
    dominant_key = ranked[0] if ranked else keys[0]
    pattern = DOMINANT_MAP.get(dominant_key, "TORSO_MID")
    return pattern, ranked


def _residuals_cm(residuals_m: dict[str, float]) -> dict[str, float]:
    return {k: (v * 100.0 if v is not None else 0.0) for k, v in residuals_m.items()}


class DummyMeshProvider:
    """Deterministic dummy: scale base mesh by (1 + beta[0]). No SMPL-X required."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._base_verts = None

    def _load_base(self) -> Any:
        import numpy as np
        if self._base_verts is not None:
            return self._base_verts
        fixture = _REPO / "tests" / "fixtures" / "vtm_mesh" / "smoke_verts.npz"
        if fixture.exists():
            data = np.load(fixture)
            v = np.asarray(data["verts"], dtype=np.float32)
            if v.ndim == 3:
                v = v[0]
            self._base_verts = v
            return v
        # Fallback: minimal ring
        np.random.seed(self._seed)
        verts = []
        for yi in range(11):
            y = yi / 10.0
            for xi in range(8):
                t = xi * 2 * np.pi / 8
                verts.append([0.3 * np.cos(t), y, 0.3 * np.sin(t)])
        self._base_verts = np.array(verts, dtype=np.float32)
        return self._base_verts

    def generate_mesh(self, beta: list[float], pose_id: str = "PZ1") -> tuple[Any, Any]:
        import numpy as np
        base = self._load_base()
        s = 1.0 + (beta[0] if beta else 0.0)
        verts = base * s
        return verts, None


def _optimize_deterministic(
    target_m: dict[str, float],
    mesh_provider: MeshProvider,
    keys: list[str],
    seed: int,
    max_iter: int,
    pose_id: str,
) -> tuple[list[float], dict[str, float], dict[str, float | None], list[str]]:
    import numpy as np
    from scipy.optimize import minimize

    def objective(x: np.ndarray) -> float:
        beta = x.tolist()
        try:
            verts, _ = mesh_provider.generate_mesh(beta, pose_id=pose_id)
            pred = _measure_verts(verts, keys)
        except Exception:
            return 1e10
        loss = 0.0
        for k in keys:
            t = target_m.get(k)
            p = pred.get(k)
            if t is not None and p is not None:
                loss += (p - t) ** 2
            elif t is not None:
                loss += t ** 2
        return loss

    np.random.seed(seed)
    x0 = np.array([0.0], dtype=np.float64)
    res = minimize(objective, x0, method="Nelder-Mead", options={"maxfev": max_iter, "xatol": 1e-6, "fatol": 1e-8})
    beta_final = res.x.tolist()
    verts, _ = mesh_provider.generate_mesh(beta_final, pose_id=pose_id)
    pred = _measure_verts(verts, keys)
    residuals_m = {}
    for k in keys:
        t = target_m.get(k)
        p = pred.get(k)
        if t is not None:
            residuals_m[k] = (p if p is not None else 0.0) - t
        else:
            residuals_m[k] = 0.0
    warnings = []
    if not res.success:
        warnings.append(f"OPTIMIZER_NOT_CONVERGED:{res.message}")
    return beta_final, residuals_m, pred, warnings


def _fit_one(
    p_id: str,
    target_m: dict[str, float],
    mesh_provider: MeshProvider,
    keys: list[str],
    seed: int,
    max_iter: int,
    pose_id: str,
    out_path: Path,
    diagnostics_dir: Path,
) -> dict[str, Any]:
    from tools.utils.atomic_io import atomic_save_json
    stub = {
        "schema_version": "beta_fit_v0",
        "prototype_id": p_id,
        "success": False,
        "error_type": None,
        "error_message": None,
        "beta": None,
        "residuals_m": None,
        "residuals_cm": None,
        "quality_score": None,
        "quality_bucket": "LOW",
        "dominant_residual_key": None,
        "residual_ranked_keys": None,
        "warnings": ["FIT_FAILED"],
    }
    try:
        beta, residuals_m, predicted, warnings = _optimize_deterministic(
            target_m, mesh_provider, keys, seed, max_iter, pose_id
        )
        residuals_cm = _residuals_cm(residuals_m)
        score = _quality_score(residuals_m, keys)
        bucket = quality_bucket(score)
        dom_pattern, ranked = _dominant_and_ranked(residuals_m, keys)
        if score < QUALITY_THRESHOLD:
            warnings.append("QUALITY_BELOW_THRESHOLD_70")
        payload = {
            "schema_version": "beta_fit_v0",
            "prototype_id": p_id,
            "success": True,
            "beta": beta,
            "residuals_m": {k: round(v, 6) for k, v in residuals_m.items()},
            "residuals_cm": {k: round(v, 4) for k, v in residuals_cm.items()},
            "quality_score": round(score, 2),
            "quality_bucket": bucket,
            "dominant_residual_key": dom_pattern,
            "residual_ranked_keys": ranked,
            "predicted_m": {k: (round(v, 6) if v is not None else None) for k, v in (predicted or {}).items()},
            "warnings": warnings,
        }
        atomic_save_json(out_path, payload)
        return payload
    except Exception as e:
        import traceback
        stub["error_type"] = type(e).__name__
        stub["error_message"] = str(e)[:500]
        try:
            atomic_save_json(out_path, stub)
        except Exception:
            pass
        diag_path = diagnostics_dir / f"fit_error_{p_id}.json"
        try:
            atomic_save_json(diag_path, {
                "error_type": type(e).__name__,
                "error_message": str(e)[:500],
                "traceback": traceback.format_exc(),
                "prototype_id": p_id,
            })
        except Exception:
            pass
        return stub


def main() -> int:
    import numpy as np
    parser = argparse.ArgumentParser(description="Step3: beta fit v0 — fit BUST/WAIST/HIP targets per prototype")
    parser.add_argument("--centroids_json", type=Path, default=None, help="Path to centroids_v0.json (or use --k 10 dev)")
    parser.add_argument("--out_dir", type=Path, required=True, help="Output dir (e.g. exports/runs/.../beta_fit_v0)")
    parser.add_argument("--k", type=int, default=10, help="Number of prototypes (default 10 for dev)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max_iter", type=int, default=200)
    parser.add_argument("--pose_id", type=str, default="PZ1")
    parser.add_argument("--keys", type=str, default=",".join(U1_KEYS), help="Comma-separated keys")
    parser.add_argument("--mesh_provider", type=str, default="dummy", choices=("dummy",), help="dummy when SMPL-X unavailable")
    parser.add_argument("--resume", action="store_true", help="Skip prototype if fit_result.json already exists")
    parser.add_argument("--time_budget_sec", type=int, default=0, help="Stop gracefully after N seconds (0=no limit)")
    parser.add_argument("--batch_size", type=int, default=1, help="Batch size for future parallelization (default 1)")
    parser.add_argument("--log-progress", action="store_true", help="Append progress event to repo exports/progress (ops)")
    args = parser.parse_args()

    keys = [x.strip() for x in args.keys.split(",") if x.strip()] or list(U1_KEYS)
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    prototypes_dir = out_dir / "prototypes"
    prototypes_dir.mkdir(parents=True, exist_ok=True)
    diag_dir = out_dir / "artifacts" / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)

    # Load targets: from centroids_json or dev set
    if args.centroids_json and args.centroids_json.exists():
        data = json.loads(args.centroids_json.read_text(encoding="utf-8"))
        vectors = data.get("centroid_vectors", [])
        feature_keys = data.get("feature_keys", U1_KEYS)
        # Map feature_keys to keys
        targets_list = []
        for vec in vectors[: args.k]:
            targets_list.append(dict(zip(feature_keys, vec)))
    else:
        # Dev set: use first k centroid-like targets from a small deterministic list
        import numpy as np
        np.random.seed(args.seed)
        targets_list = []
        for i in range(args.k):
            targets_list.append({
                "BUST_CIRC_M": 0.85 + i * 0.02,
                "WAIST_CIRC_M": 0.72 + i * 0.015,
                "HIP_CIRC_M": 0.92 + i * 0.02,
            })

    if args.mesh_provider == "dummy":
        mesh_provider = DummyMeshProvider(seed=args.seed)
    else:
        print("ERROR: Only dummy mesh_provider implemented (SMPL-X not wired)", file=sys.stderr)
        return 1

    t0 = time.perf_counter()
    results = []
    failures = []
    skipped_resume = []
    for i, target_m in enumerate(targets_list):
        if args.time_budget_sec and (time.perf_counter() - t0) >= args.time_budget_sec:
            break
        p_id = f"p{i:04d}"
        fit_path = prototypes_dir / p_id / "fit_result.json"
        fit_path.parent.mkdir(parents=True, exist_ok=True)
        if getattr(args, "resume", False) and fit_path.exists():
            try:
                r = json.loads(fit_path.read_text(encoding="utf-8"))
                results.append(r)
                skipped_resume.append({"prototype_id": p_id, "reason": "resume_skip"})
                if not r.get("success"):
                    failures.append({"p_id": p_id, "error_type": r.get("error_type")})
            except Exception:
                r = _fit_one(p_id, target_m, mesh_provider, keys, args.seed, args.max_iter, args.pose_id, fit_path, diag_dir)
                results.append(r)
                if not r.get("success"):
                    failures.append({"p_id": p_id, "error_type": r.get("error_type")})
        else:
            r = _fit_one(p_id, target_m, mesh_provider, keys, args.seed, args.max_iter, args.pose_id, fit_path, diag_dir)
            results.append(r)
            if not r.get("success"):
                failures.append({"p_id": p_id, "error_type": r.get("error_type")})

    if skipped_resume:
        skip_path = out_dir / "SKIPPED_RESUME.jsonl"
        with open(skip_path, "w", encoding="utf-8") as f:
            for rec in skipped_resume:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Summary
    successful = [x for x in results if x.get("success")]
    residuals_cm_all = {k: [] for k in keys}
    quality_scores = []
    bucket_counts = {"OK": 0, "LOW": 0}
    dominant_counts = {"TORSO_UPPER": 0, "TORSO_MID": 0, "TORSO_LOWER": 0}
    for r in successful:
        for k in keys:
            res_cm = r.get("residuals_cm") or {}
            if k in res_cm:
                residuals_cm_all[k].append(res_cm[k])
        q = r.get("quality_score")
        if q is not None:
            quality_scores.append(q)
        bucket_counts[r.get("quality_bucket", "LOW")] = bucket_counts.get(r.get("quality_bucket", "LOW"), 0) + 1
        dom = r.get("dominant_residual_key")
        if dom:
            dominant_counts[dom] = dominant_counts.get(dom, 0) + 1

    def p50(x): return float(np.percentile(x, 50)) if x else 0.0
    def p90(x): return float(np.percentile(x, 90)) if x else 0.0

    def p95(x): return float(np.percentile(x, 95)) if x else 0.0
    residual_cm_stats = {}
    for k in keys:
        arr = residuals_cm_all.get(k, [])
        residual_cm_stats[k] = {"p50": p50(arr), "p90": p90(arr), "p95": p95(arr), "max": float(np.max(arr)) if arr else 0.0}
    quality_score_stats = {"p50": p50(quality_scores), "p90": p90(quality_scores), "min": float(np.min(quality_scores)) if quality_scores else 0.0}
    frac_above = (bucket_counts.get("OK", 0) / len(results)) if results else 0.0
    summary = {
        "schema_version": "beta_fit_v0",
        "k": len(results),
        "seed": args.seed,
        "max_iter": args.max_iter,
        "method": "Nelder-Mead",
        "keyset": keys,
        "residual_cm_stats": residual_cm_stats,
        "quality_score_stats": quality_score_stats,
        "bucket_counts": bucket_counts,
        "dominant_pattern_counts": dominant_counts,
        "failures": {"count": len(failures), "top_error_types": list(set(f.get("error_type") for f in failures if f.get("error_type")))},
        "proposed_unlock_signal": {
            "threshold_score": QUALITY_THRESHOLD,
            "fraction_above_threshold": round(frac_above, 4),
            "note": "facts-only; gating not enforced",
        },
    }
    from tools.utils.atomic_io import atomic_save_json
    summary_path = out_dir / "summary.json"
    atomic_save_json(summary_path, summary)

    # KPI.md
    worst = sorted(successful, key=lambda x: x.get("quality_score") or 0)[:10]
    kpi_lines = [
        "# KPI",
        "",
        "## Step3 beta_fit_v0",
        f"- k: {len(results)}",
        f"- failures: {len(failures)}",
        f"- quality_score p50/p90/min: {quality_score_stats['p50']:.2f} / {quality_score_stats['p90']:.2f} / {quality_score_stats['min']:.2f}",
        f"- bucket OK/LOW: {bucket_counts.get('OK', 0)} / {bucket_counts.get('LOW', 0)}",
        "- residual_cm_stats:",
    ]
    for k in keys:
        s = residual_cm_stats.get(k, {})
        kpi_lines.append(f"  - {k}: p50={s.get('p50', 0):.4f} p90={s.get('p90', 0):.4f} max={s.get('max', 0):.4f}")
    kpi_lines.append("")
    kpi_lines.append("## Top-10 worst prototypes (by quality_score)")
    for r in worst:
        kpi_lines.append(f"- {r.get('prototype_id')} score={r.get('quality_score')} dominant={r.get('dominant_residual_key')}")
    kpi_lines.append("")
    kpi_path = out_dir / "KPI.md"
    kpi_tmp = out_dir / "KPI.md.tmp"
    kpi_tmp.write_text("\n".join(kpi_lines), encoding="utf-8")
    kpi_tmp.replace(kpi_path)

    # KPI_DIFF.md
    kpi_diff_path = out_dir / "KPI_DIFF.md"
    kpi_diff_path.write_text("# KPI_DIFF\n\nNO_BASELINE\n", encoding="utf-8")

    # residual_report.json (atomic)
    top_worst_k = 20
    top_best_k = 20
    worst_list = sorted(successful, key=lambda x: x.get("quality_score") or 0)[:top_worst_k]
    best_list = sorted(successful, key=lambda x: -(x.get("quality_score") or 0))[:top_best_k]
    sign_pattern_hist = {}
    for r in successful:
        res_cm = r.get("residuals_cm") or {}
        signs = []
        for k in keys:
            v = res_cm.get(k, 0)
            if v > 0:
                signs.append("+")
            elif v < 0:
                signs.append("-")
            else:
                signs.append("0")
        key = ",".join(signs)
        sign_pattern_hist[key] = sign_pattern_hist.get(key, 0) + 1
    residual_report = {
        "schema_version": "beta_fit_residual_report_v0",
        "top_worst": [{"prototype_id": r.get("prototype_id"), "quality_score": r.get("quality_score"), "residuals_cm": r.get("residuals_cm"), "dominant_residual_key": r.get("dominant_residual_key"), "warnings": r.get("warnings", [])} for r in worst_list],
        "top_best": [{"prototype_id": r.get("prototype_id"), "quality_score": r.get("quality_score"), "residuals_cm": r.get("residuals_cm"), "dominant_residual_key": r.get("dominant_residual_key")} for r in best_list],
        "residual_distribution": {k: residual_cm_stats.get(k, {}) for k in keys},
        "quality_score_distribution": quality_score_stats,
        "pattern_counts": dominant_counts,
        "sign_pattern_histogram": sign_pattern_hist,
        "failure_summary": {"count": len(failures), "top_error_types": list(set(f.get("error_type") for f in failures if f.get("error_type")))},
    }
    atomic_save_json(out_dir / "residual_report.json", residual_report)

    # RESIDUAL_REPORT.md (human-readable, facts-only)
    md_lines = [
        "# RESIDUAL REPORT",
        "",
        "## Top-20 worst (by quality_score)",
        "| prototype_id | quality_score | residuals_cm | dominant_residual_key |",
        "|--------------|---------------|--------------|------------------------|",
    ]
    for r in worst_list:
        rc = r.get("residuals_cm") or {}
        md_lines.append(f"| {r.get('prototype_id')} | {r.get('quality_score')} | {rc} | {r.get('dominant_residual_key')} |")
    md_lines.append("")
    md_lines.append("## Top-20 best")
    md_lines.append("| prototype_id | quality_score | dominant_residual_key |")
    for r in best_list:
        md_lines.append(f"| {r.get('prototype_id')} | {r.get('quality_score')} | {r.get('dominant_residual_key')} |")
    md_lines.append("")
    md_lines.append("## Residual distribution (cm)")
    for k in keys:
        s = residual_cm_stats.get(k, {})
        md_lines.append(f"- {k}: p50={s.get('p50', 0):.4f} p90={s.get('p90', 0):.4f} p95={s.get('p95', 0):.4f} max={s.get('max', 0):.4f}")
    md_lines.append("")
    md_lines.append("## Pattern counts (dominant_residual_key)")
    for k, v in dominant_counts.items():
        md_lines.append(f"- {k}: {v}")
    md_lines.append("")
    md_lines.append("## Sign pattern histogram (BUST,WAIST,HIP)")
    for k, v in sorted(sign_pattern_hist.items(), key=lambda x: -x[1]):
        md_lines.append(f"- {k}: {v}")
    md_lines.append("")
    md_lines.append("## Failure summary")
    md_lines.append(f"- count: {len(failures)}")
    md_lines.append(f"- top_error_types: {residual_report['failure_summary']['top_error_types']}")
    md_lines.append("")
    report_md_path = out_dir / "RESIDUAL_REPORT.md"
    report_md_tmp = out_dir / "RESIDUAL_REPORT.md.tmp"
    report_md_tmp.write_text("\n".join(md_lines), encoding="utf-8")
    report_md_tmp.replace(report_md_path)

    elapsed = round(time.perf_counter() - t0, 3)
    sha = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    print(f"[DONE] out_dir: {out_dir}")
    print(f"[DONE] summary.json sha256={sha}")
    print(f"[DONE] quality_score p50={quality_score_stats['p50']:.2f} p90={quality_score_stats['p90']:.2f}")
    print(f"[DONE] failures: {len(failures)} elapsed={elapsed}s")

    if getattr(args, "log_progress", False):
        try:
            rel_out = out_dir.relative_to(_REPO)
        except ValueError:
            rel_out = out_dir
        try:
            import subprocess
            subprocess.run(
                [
                    sys.executable,
                    str(_REPO / "tools" / "ops" / "append_progress_event.py"),
                    "--lab-root", str(_REPO),
                    "--module", "body",
                    "--step-id", "B03",
                    "--event", "note",
                    "--note", f"Step3 beta_fit_v0 k={len(results)}: summary sha256={sha[:16]}..., quality p50={quality_score_stats['p50']:.2f} p90={quality_score_stats['p90']:.2f} min={quality_score_stats['min']:.2f}, failures={len(failures)}",
                    "--evidence", str(rel_out),
                ],
                cwd=str(_REPO),
                check=False,
            )
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
