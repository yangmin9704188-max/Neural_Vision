#!/usr/bin/env python3
"""
Step2 Phase0: Deterministic 384 centroid generation from curated parquet.
Outputs: centroids.json (atomic), diagnostics/centroids_run.json (atomic).
Determinism: stable subject ordering (subject_id), fixed seed, atomic writes.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

# Add repo root
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

U1_KEYS = ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]


def _sanitize_json_value(obj: object) -> object:
    """Replace NaN/Inf with None for JSON; recurse into dict/list."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_json_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json_value(x) for x in obj]
    if isinstance(obj, float) and (not math.isfinite(obj) or math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _deterministic_kmeans_fallback(X: list[list[float]], k: int, subject_ids: list[str], seed: int) -> tuple[list[list[float]], list[int]]:
    """
    Deterministic k-means: initial centroids = first k rows (after stable sort by subject_id).
    Lloyd iterations with tie-break by subject_id (stable sort). Fixed iterations.
    Returns (centroid_vectors, assignments) where assignments[i] = cluster index for row i.
    """
    n = len(X)
    if n == 0 or k <= 0:
        return [], []
    if k >= n:
        return [list(x) for x in X], list(range(n))
    # Initial centroids = first k rows (order already stable by subject_id)
    centroids = [list(X[i]) for i in range(k)]
    assignments = [0] * n
    max_iters = 50
    for _ in range(max_iters):
        # Assign each point to nearest centroid; tie-break by subject_id (index)
        for i in range(n):
            best_j = 0
            best_d = sum((X[i][d] - centroids[0][d]) ** 2 for d in range(len(X[i])))
            for j in range(1, k):
                d = sum((X[i][d] - centroids[j][d]) ** 2 for d in range(len(X[i])))
                if d < best_d:  # tie-break: smaller j (deterministic)
                    best_d = d
                    best_j = j
            assignments[i] = best_j
        # Recompute centroids
        new_centroids = [[0.0] * len(X[0]) for _ in range(k)]
        counts = [0] * k
        for i in range(n):
            j = assignments[i]
            counts[j] += 1
            for d in range(len(X[i])):
                new_centroids[j][d] += X[i][d]
        for j in range(k):
            if counts[j] > 0:
                for d in range(len(new_centroids[j])):
                    new_centroids[j][d] /= counts[j]
        if new_centroids == centroids:
            break
        centroids = new_centroids
    return centroids, assignments


def main() -> int:
    parser = argparse.ArgumentParser(description="Step2: deterministic 384 centroid generation from curated parquet")
    parser.add_argument("--curated_parquet", type=Path, required=True, help="Path to curated parquet")
    parser.add_argument("--out_dir", type=Path, required=True, help="Output directory (e.g. under exports/runs)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    parser.add_argument("--k", type=int, default=384, help="Number of centroids (default 384)")
    parser.add_argument("--id_col", type=str, default="subject_id", help="Subject ID column (default subject_id)")
    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    # 1) Load parquet
    try:
        import pandas as pd
        df = pd.read_parquet(args.curated_parquet)
    except Exception as e:
        print(f"ERROR: Failed to load parquet: {e}", file=sys.stderr)
        return 1

    if args.id_col not in df.columns:
        print(f"ERROR: id_col '{args.id_col}' not in columns: {list(df.columns)}", file=sys.stderr)
        return 1

    # 2) Feature keys: U1 baseline + optional if present
    feature_keys = [c for c in U1_KEYS if c in df.columns]
    optional = [c for c in df.columns if c != args.id_col and c not in U1_KEYS and df[c].dtype in ("float64", "float32")]
    for c in optional[:10]:  # cap extra keys for v0
        if c not in feature_keys:
            feature_keys.append(c)
    if not feature_keys:
        print("ERROR: No feature columns found (need at least one of BUST_CIRC_M, WAIST_CIRC_M, HIP_CIRC_M)", file=sys.stderr)
        return 1

    # 3) Deterministic ordering: sort by subject_id
    df = df.sort_values(args.id_col, kind="mergesort").reset_index(drop=True)
    subject_ids = df[args.id_col].astype(str).tolist()

    # 4) Build matrix; drop rows with any NaN/Inf in feature keys
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
    X = [X_raw[i].tolist() for i in range(len(X_raw)) if valid_mask[i]]
    subject_ids_clean = [subject_ids[i] for i in range(len(subject_ids)) if valid_mask[i]]
    n_dropped = len(X_raw) - len(X)
    n_subjects = len(X)

    if n_subjects < args.k:
        print(f"WARN: n_subjects={n_subjects} < k={args.k}; using k={n_subjects}", file=sys.stderr)
        k_actual = n_subjects
    else:
        k_actual = args.k

    # 5) Compute centroids deterministically
    try:
        from sklearn.cluster import KMeans
        km = KMeans(n_clusters=k_actual, random_state=args.seed, n_init=1, max_iter=300)
        km.fit(X)
        centroid_vectors = km.cluster_centers_.tolist()
        assignments = km.labels_.tolist()
        method = "sklearn_kmeans"
    except ImportError:
        centroid_vectors, assignments = _deterministic_kmeans_fallback(X, k_actual, subject_ids_clean, args.seed)
        method = "deterministic_lloyd"

    # Assignment summary: counts per centroid
    assignment_summary = [0] * len(centroid_vectors)
    for a in assignments:
        assignment_summary[a] += 1

    # 6) Build outputs (no NaN/Inf in JSON)
    centroids_payload = {
        "schema_version": "centroids_v0",
        "k": k_actual,
        "seed": args.seed,
        "method": method,
        "feature_keys": feature_keys,
        "n_subjects": n_subjects,
        "centroid_vectors": _sanitize_json_value(centroid_vectors),
        "assignment_summary": assignment_summary,
    }
    warnings_list: list[str] = []
    if n_dropped > 0:
        warnings_list.append(f"DROPPED_ROWS:{n_dropped}")
    centroids_payload["warnings"] = warnings_list

    diag = {
        "schema_version": "centroids_run_v0",
        "timings_sec": round(time.perf_counter() - t0, 3),
        "n_subjects": n_subjects,
        "n_dropped": n_dropped,
        "k": k_actual,
        "method": method,
        "feature_keys": feature_keys,
        "warnings": warnings_list,
    }

    # 7) Atomic writes
    from tools.utils.atomic_io import atomic_save_json
    centroids_path = out_dir / "centroids.json"
    atomic_save_json(centroids_path, centroids_payload)
    diag_dir = out_dir / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)
    atomic_save_json(diag_dir / "centroids_run.json", diag)

    print(f"[DONE] centroids: {centroids_path} (k={k_actual}, method={method})")
    print(f"[DONE] diagnostics: {diag_dir / 'centroids_run.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
