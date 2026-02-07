#!/usr/bin/env python3
"""
Phase0 Step2: Generate 384 representative centroids from curated_v0 dataset.
Determinism: stable ordering by id_col, fixed seed, atomic writes.
Outputs: centroids_v0.json, assignments_v0.parquet, diagnostics/centroids_run.json, KPI.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

U1_KEYS = ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]
# Outlier gate (Body_Module_Plan_v1): drop rows outside range
HEIGHT_M_MIN, HEIGHT_M_MAX = 1.0, 2.2
WEIGHT_KG_MIN, WEIGHT_KG_MAX = 20.0, 250.0


def _sanitize_json_value(obj: object) -> object:
    """Replace NaN/Inf with None for JSON."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_json_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json_value(x) for x in obj]
    if isinstance(obj, float) and (not math.isfinite(obj) or math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _deterministic_kmeans_fallback(
    X: list[list[float]], k: int, subject_ids: list[str], seed: int, max_iter: int = 300
) -> tuple[list[list[float]], list[int]]:
    """Deterministic k-means: first k rows as init, Lloyd with fixed max_iter."""
    n = len(X)
    if n == 0 or k <= 0:
        return [], []
    if k >= n:
        return [list(x) for x in X], list(range(n))
    centroids = [list(X[i]) for i in range(k)]
    assignments = [0] * n
    dim = len(X[0])
    for _ in range(max_iter):
        for i in range(n):
            best_j = 0
            best_d = sum((X[i][d] - centroids[0][d]) ** 2 for d in range(dim))
            for j in range(1, k):
                d = sum((X[i][d] - centroids[j][d]) ** 2 for d in range(dim))
                if d < best_d:
                    best_d = d
                    best_j = j
            assignments[i] = best_j
        new_centroids = [[0.0] * dim for _ in range(k)]
        counts = [0] * k
        for i in range(n):
            j = assignments[i]
            counts[j] += 1
            for d in range(dim):
                new_centroids[j][d] += X[i][d]
        for j in range(k):
            if counts[j] > 0:
                for d in range(dim):
                    new_centroids[j][d] /= counts[j]
        if new_centroids == centroids:
            break
        centroids = new_centroids
    return centroids, assignments


def main() -> int:
    parser = argparse.ArgumentParser(description="Step2: deterministic 384 centroid generation from curated parquet")
    parser.add_argument("--curated_parquet", type=Path, required=True, help="Path to curated parquet")
    parser.add_argument(
        "--out_dir",
        type=Path,
        default=None,
        help="Output directory (default: exports/runs/_tools/centroids/<run_id>/)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    parser.add_argument("--k", type=int, default=384, help="Number of centroids (default 384)")
    parser.add_argument("--id_col", type=str, default="subject_id", help="Subject ID column (default subject_id)")
    parser.add_argument(
        "--feature_keys",
        type=str,
        default=",".join(U1_KEYS),
        help="Comma-separated feature keys (default: BUST_CIRC_M,WAIST_CIRC_M,HIP_CIRC_M)",
    )
    parser.add_argument(
        "--impute",
        type=str,
        default="drop_row",
        choices=("drop_row", "median"),
        help="Missingness strategy (default drop_row)",
    )
    parser.add_argument("--report_top_residuals", type=int, default=10, help="Top N residual subjects in diagnostics (default 10)")
    parser.add_argument("--log-progress", action="store_true", help="After success, append progress event to repo exports/progress (ops)")
    args = parser.parse_args()

    feature_keys = [k.strip() for k in args.feature_keys.split(",") if k.strip()]
    if not feature_keys:
        feature_keys = list(U1_KEYS)
    for k in U1_KEYS:
        if k not in feature_keys:
            feature_keys.insert(0, k) if k == U1_KEYS[0] else None  # keep order: require U1 baseline
    # Ensure U1 baseline present
    missing = [k for k in U1_KEYS if k not in feature_keys]
    if missing:
        print(f"ERROR: Required feature keys missing: {missing}. Available columns will be checked after load.", file=sys.stderr)

    if args.out_dir is not None:
        out_dir = args.out_dir.resolve()
    else:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = (_REPO / "exports" / "runs" / "_tools" / "centroids" / run_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    try:
        import pandas as pd
    except ImportError:
        print("ERROR: pandas required", file=sys.stderr)
        return 1

    try:
        df = pd.read_parquet(args.curated_parquet)
    except Exception as e:
        print(f"ERROR: Failed to load parquet: {e}", file=sys.stderr)
        return 1

    id_col = args.id_col
    if id_col not in df.columns:
        if "subject_id" in df.columns:
            id_col = "subject_id"
        elif "HUMAN_ID" in df.columns:
            id_col = "HUMAN_ID"
            print(f"[INFO] id_col 'subject_id' not found; using HUMAN_ID", file=sys.stderr)
        else:
            print(f"ERROR: id_col '{args.id_col}' not in columns; try --id_col HUMAN_ID or check columns: {list(df.columns)[:10]}...", file=sys.stderr)
            return 1
    if id_col != args.id_col:
        pass  # already switched above

    # Restrict feature_keys to columns that exist
    feature_keys = [c for c in feature_keys if c in df.columns]
    missing_u1 = [k for k in U1_KEYS if k not in feature_keys]
    if missing_u1:
        print(f"ERROR: Required U1 keys missing in parquet: {missing_u1}", file=sys.stderr)
        return 1

    # Stable ordering by id_col
    df = df.sort_values(id_col, kind="mergesort").reset_index(drop=True)
    subject_ids = df[id_col].astype(str).tolist()
    n_subjects_total = len(df)

    # Outlier filter (GIGO): HEIGHT_M, WEIGHT_KG
    if "HEIGHT_M" in df.columns:
        v = pd.to_numeric(df["HEIGHT_M"], errors="coerce")
        df = df.loc[(v >= HEIGHT_M_MIN) & (v <= HEIGHT_M_MAX) & v.notna()].reset_index(drop=True)
    if "WEIGHT_KG" in df.columns:
        v = pd.to_numeric(df["WEIGHT_KG"], errors="coerce")
        df = df.loc[(v >= WEIGHT_KG_MIN) & (v <= WEIGHT_KG_MAX) & v.notna()].reset_index(drop=True)
    n_dropped_outlier = n_subjects_total - len(df)
    subject_ids = df[id_col].astype(str).tolist()

    # Missingness: drop_row or median impute
    X_raw = df[feature_keys].to_numpy()
    valid_mask = []
    for i in range(len(X_raw)):
        row = X_raw[i]
        ok = True
        for v in row:
            if v != v or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                ok = False
                break
        valid_mask.append(ok)

    if args.impute == "median":
        medians = [float(df[col].median()) for col in feature_keys]
        X_fill = np.array(X_raw, dtype=float)
        for j in range(len(feature_keys)):
            bad = np.isnan(X_fill[:, j]) | ~np.isfinite(X_fill[:, j])
            if bad.any():
                X_fill[bad, j] = medians[j]
        n_dropped_missing = 0
        X_list = X_fill.tolist()
        subject_ids_clean = subject_ids
    else:
        n_dropped_missing = sum(1 for x in valid_mask if not x)
        X_list = [X_raw[i].tolist() for i in range(len(X_raw)) if valid_mask[i]]
        subject_ids_clean = [subject_ids[i] for i in range(len(subject_ids)) if valid_mask[i]]

    n_subjects_used = len(X_list)
    if n_subjects_used == 0:
        print("ERROR: No subjects remaining after outlier and missingness filters", file=sys.stderr)
        return 1

    k_actual = min(args.k, n_subjects_used)
    if k_actual < args.k:
        print(f"WARN: n_subjects_used={n_subjects_used} < k={args.k}; using k={k_actual}", file=sys.stderr)

    # Standardization (Z-score) on used subjects only
    X = np.array(X_list, dtype=float)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    X_scaled = (X - mean) / std

    # Clustering on scaled data
    try:
        from sklearn.cluster import KMeans
        km = KMeans(n_clusters=k_actual, random_state=args.seed, n_init=10, max_iter=300)
        km.fit(X_scaled)
        labels = km.labels_.tolist()
        method = "sklearn_kmeans"
        # Centroids in scaled space -> inverse transform to original scale
        centroid_vectors_scaled = km.cluster_centers_
        centroid_vectors = (centroid_vectors_scaled * std + mean).tolist()
    except ImportError:
        X_scaled_list = X_scaled.tolist()
        centroid_vectors_scaled, labels = _deterministic_kmeans_fallback(
            X_scaled_list, k_actual, subject_ids_clean, args.seed, max_iter=300
        )
        method = "deterministic_lloyd"
        centroid_vectors = []
        for c in centroid_vectors_scaled:
            orig = [c[d] * std[d] + mean[d] for d in range(len(c))]
            centroid_vectors.append(orig)

    # Distances (in original scale) from each point to its centroid
    distances = []
    for i in range(len(X_list)):
        c = centroid_vectors[labels[i]]
        d = math.sqrt(sum((X_list[i][j] - c[j]) ** 2 for j in range(len(feature_keys))))
        distances.append(d)

    # Assignment summary
    assignment_summary = [0] * k_actual
    for a in labels:
        assignment_summary[a] += 1

    # Top residuals (largest distance)
    idx_by_dist = sorted(range(len(distances)), key=lambda i: -distances[i])
    top_residuals = []
    for idx in idx_by_dist[: args.report_top_residuals]:
        sid = subject_ids_clean[idx]
        d = distances[idx]
        z_scores = ((np.array(X_list[idx]) - mean) / std).tolist() if len(mean) else []
        top_residuals.append({
            "id": sid,
            "distance": round(d, 6),
            "centroid_id": labels[idx],
            "z_scores": [round(z, 4) for z in z_scores],
        })

    dist_arr = np.array(distances)
    dist_min = float(np.min(dist_arr))
    dist_median = float(np.median(dist_arr))
    dist_p90 = float(np.percentile(dist_arr, 90))
    dist_max = float(np.max(dist_arr))

    cnt_arr = np.array(assignment_summary)
    cnt_min = int(np.min(cnt_arr))
    cnt_median = float(np.median(cnt_arr))
    cnt_max = int(np.max(cnt_arr))

    # Build outputs
    centroids_payload = {
        "schema_version": "centroids_v0",
        "k": k_actual,
        "seed": args.seed,
        "method": method,
        "feature_keys": feature_keys,
        "n_subjects": n_subjects_used,
        "centroid_vectors": _sanitize_json_value(centroid_vectors),
        "assignment_summary": assignment_summary,
        "warnings": [],
    }
    if n_dropped_missing > 0:
        centroids_payload["warnings"].append(f"DROPPED_MISSING:{n_dropped_missing}")
    if n_dropped_outlier > 0:
        centroids_payload["warnings"].append(f"DROPPED_OUTLIER:{n_dropped_outlier}")

    scaling_params = {"mean": [float(x) for x in mean], "std": [float(x) for x in std]}
    diag = {
        "schema_version": "centroids_run_v0",
        "timings_sec": round(time.perf_counter() - t0, 3),
        "n_subjects_total": n_subjects_total,
        "n_subjects_used": n_subjects_used,
        "n_dropped_missing": n_dropped_missing,
        "n_dropped_outlier": n_dropped_outlier,
        "k": k_actual,
        "method": method,
        "feature_keys": feature_keys,
        "scaling_params": scaling_params,
        "distance_stats": {"min": dist_min, "median": dist_median, "p90": dist_p90, "max": dist_max},
        "centroid_size": {"min": cnt_min, "median": cnt_median, "max": cnt_max},
        "top_residuals": top_residuals,
        "warnings": centroids_payload["warnings"],
    }

    # Assignments table: id, centroid_id, distance
    assignments_df = pd.DataFrame({
        id_col: subject_ids_clean,
        "centroid_id": labels,
        "distance": distances,
    })

    # KPI.md (facts-only)
    kpi_lines = [
        "# KPI",
        "",
        "## Step2 centroids v0",
        f"- n_subjects_total: {n_subjects_total}",
        f"- n_subjects_used: {n_subjects_used}",
        f"- n_dropped_missing: {n_dropped_missing}",
        f"- n_dropped_outlier: {n_dropped_outlier}",
        f"- feature_keys: {feature_keys}",
        f"- seed: {args.seed}",
        f"- k: {k_actual}",
        f"- method: {method}",
        f"- distance min/median/p90/max: {dist_min:.6f} / {dist_median:.6f} / {dist_p90:.6f} / {dist_max:.6f}",
        f"- centroid size min/median/max: {cnt_min} / {cnt_median} / {cnt_max}",
        "",
    ]
    kpi_md = "\n".join(kpi_lines)

    # Atomic writes
    from tools.utils.atomic_io import atomic_save_json
    atomic_save_json(out_dir / "centroids_v0.json", centroids_payload)
    diag_dir = out_dir / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)
    atomic_save_json(diag_dir / "centroids_run.json", _sanitize_json_value(diag))

    assignments_path = out_dir / "assignments_v0.parquet"
    tmp_assign = out_dir / "assignments_v0.parquet.tmp"
    assignments_df.to_parquet(tmp_assign, index=False)
    os.replace(tmp_assign, assignments_path)

    kpi_path = out_dir / "KPI.md"
    kpi_tmp = out_dir / "KPI.md.tmp"
    kpi_tmp.write_text(kpi_md, encoding="utf-8")
    kpi_tmp.replace(kpi_path)

    centroids_path = out_dir / "centroids_v0.json"
    sha = hashlib.sha256(centroids_path.read_bytes()).hexdigest()
    print(f"[DONE] out_dir: {out_dir}")
    print(f"[DONE] centroids_v0.json (k={k_actual}, method={method}) sha256={sha}")
    print(f"[DONE] assignments_v0.parquet")
    print(f"[DONE] diagnostics/centroids_run.json")
    print(f"[DONE] KPI.md")

    if getattr(args, "log_progress", False):
        try:
            rel_out = out_dir.relative_to(_REPO)
        except ValueError:
            rel_out = out_dir
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(_REPO / "tools" / "ops" / "append_progress_event.py"),
                    "--lab-root", str(_REPO),
                    "--module", "body",
                    "--step-id", "B02",
                    "--event", "note",
                    "--note", f"Phase0 Step2: 384 centroids generated v0 (deterministic, atomic). out_dir={rel_out} sha256={sha}",
                    "--evidence", str(rel_out),
                ],
                cwd=str(_REPO),
                check=False,
            )
        except Exception:
            pass  # ops logging best-effort
    return 0


if __name__ == "__main__":
    sys.exit(main())
