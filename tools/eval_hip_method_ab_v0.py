#!/usr/bin/env python3
"""
Refine04: A/B evaluation of HIP method (world_y_band vs pelvis_frame_band) on eval set.
Inputs: --run_dir (beta_fit_v0 run), --method_a, --method_b.
Outputs (local-only): run_dir/artifacts/eval_sets/hip_method_ab_report.json.
Facts-only, deterministic.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load_eval_set(run_dir: Path) -> tuple[list[str], int]:
    """Load hip_topN_ids.json; return (prototype_ids, N)."""
    path = run_dir / "artifacts" / "eval_sets" / "hip_topN_ids.json"
    if not path.exists():
        return [], 0
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = data.get("prototype_ids") or []
    n = data.get("N") or len(ids)
    return list(ids), n


def _run_method(
    run_dir: Path,
    prototype_ids: list[str],
    method: str,
) -> tuple[list[float], list[float], list[float], list[float], int, int]:
    """Run one method on eval set; return (hip_res_cm, waist_res_cm, bust_res_cm, quality, null_count, warnings_count)."""
    import numpy as np
    from tools.fit_smplx_beta_v0 import DummyMeshProvider
    from modules.body.src.measurements.vtm.core_measurements_v0 import (
        set_hip_method,
        clear_hip_method,
        measure_hip_group_with_shared_slice,
        HIP_METHOD_WORLD_Y_BAND,
        HIP_METHOD_PELVIS_FRAME_BAND,
    )

    set_hip_method(method)
    provider = DummyMeshProvider(seed=42)
    prototypes_dir = run_dir / "prototypes"
    hip_res_cm = []
    waist_res_cm = []
    bust_res_cm = []
    quality_scores = []
    null_count = 0
    warnings_count = 0

    for pid in prototype_ids:
        fit_path = prototypes_dir / pid / "fit_result.json"
        if not fit_path.exists():
            continue
        data = json.loads(fit_path.read_text(encoding="utf-8"))
        beta = data.get("beta") or [0.0]
        pred_m = data.get("predicted_m") or {}
        res_m = data.get("residuals_m") or {}
        target_hip_m = (pred_m.get("HIP_CIRC_M") or 0) - (res_m.get("HIP_CIRC_M") or 0)
        verts, _ = provider.generate_mesh(beta, pose_id="PZ1")
        verts = np.asarray(verts, dtype=np.float32)
        if verts.ndim == 3:
            verts = verts[0]
        results = measure_hip_group_with_shared_slice(verts, case_id=pid)
        hip_res = results.get("HIP_CIRC_M")
        measured_hip = getattr(hip_res, "value_m", None) if hip_res else None
        if measured_hip is not None and math.isfinite(measured_hip):
            residual_hip_m = measured_hip - target_hip_m
            hip_res_cm.append(residual_hip_m * 100.0)
        else:
            null_count += 1
        rc = data.get("residuals_cm") or {}
        waist_res_cm.append(rc.get("WAIST_CIRC_M", 0))
        bust_res_cm.append(rc.get("BUST_CIRC_M", 0))
        q = data.get("quality_score")
        if q is not None:
            quality_scores.append(q)
        if hip_res and getattr(hip_res, "metadata", None):
            w = (hip_res.metadata or {}).get("warnings", [])
            warnings_count += len(w)

    clear_hip_method()
    return hip_res_cm, waist_res_cm, bust_res_cm, quality_scores, null_count, warnings_count


def _percentile(x: list[float], p: float) -> float | None:
    if not x:
        return None
    import numpy as np
    return float(np.percentile(x, p))


def main() -> int:
    ap = argparse.ArgumentParser(description="Refine04: HIP method A/B eval on eval set")
    ap.add_argument("--run_dir", type=Path, required=True, help="beta_fit_v0 run dir")
    ap.add_argument("--method_a", default="world_y_band", help="Method A (default: world_y_band)")
    ap.add_argument("--method_b", default="pelvis_frame_band", help="Method B (default: pelvis_frame_band)")
    args = ap.parse_args()
    run_dir = args.run_dir.resolve()
    if not run_dir.is_dir():
        print(f"eval_hip_method_ab: run_dir not found: {run_dir}", file=sys.stderr)
        return 1

    prototype_ids, n = _load_eval_set(run_dir)
    if len(prototype_ids) < 3:
        print(f"eval_hip_method_ab: eval set has {len(prototype_ids)} ids, need >=3", file=sys.stderr)
        return 1

    import numpy as np

    # Method A
    hip_a, waist_a, bust_a, qual_a, null_a, warn_a = _run_method(run_dir, prototype_ids, args.method_a)
    # Method B
    hip_b, waist_b, bust_b, qual_b, null_b, warn_b = _run_method(run_dir, prototype_ids, args.method_b)
    # Determinism: run B again
    hip_b2, _, _, _, null_b2, _ = _run_method(run_dir, prototype_ids, args.method_b)
    determinism_ok = len(hip_b) == len(hip_b2) and all(
        math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9) for a, b in zip(hip_b, hip_b2)
    )

    def p50(x):
        return _percentile(x, 50)
    def p90(x):
        return _percentile(x, 90)
    def pmax_abs(x):
        return float(max(abs(v) for v in x)) if x else None

    report = {
        "schema_version": "hip_method_ab.v0",
        "eval_set": {"N": n, "prototype_ids": sorted(prototype_ids)},
        "method_a": args.method_a,
        "method_b": args.method_b,
        "method_a_results": {
            "HIP_p50_cm": p50(hip_a),
            "HIP_p90_cm": p90(hip_a),
            "HIP_max_abs_cm": pmax_abs(hip_a),
            "WAIST_p90_cm": p90(waist_a),
            "BUST_p90_cm": p90(bust_a),
            "quality_p90": p90(qual_a),
            "count": len(hip_a),
            "null_count": null_a,
            "warnings_count": warn_a,
        },
        "method_b_results": {
            "HIP_p50_cm": p50(hip_b),
            "HIP_p90_cm": p90(hip_b),
            "HIP_max_abs_cm": pmax_abs(hip_b),
            "WAIST_p90_cm": p90(waist_b),
            "BUST_p90_cm": p90(bust_b),
            "quality_p90": p90(qual_b),
            "count": len(hip_b),
            "null_count": null_b,
            "warnings_count": warn_b,
        },
        "delta_p90_cm": (p90(hip_b) - p90(hip_a)) if (hip_a and hip_b) else None,
        "delta_abs_p90_cm": (abs(p90(hip_b)) - abs(p90(hip_a))) if (hip_a and hip_b) else None,
        "waist_bust_unchanged": (
            math.isclose(p90(waist_a) or 0, p90(waist_b) or 0, rel_tol=1e-6, abs_tol=1e-6)
            and math.isclose(p90(bust_a) or 0, p90(bust_b) or 0, rel_tol=1e-6, abs_tol=1e-6)
        ),
        "determinism_check": {"method_b_twice_identical": determinism_ok},
    }

    out_dir = run_dir / "artifacts" / "eval_sets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "hip_method_ab_report.json"
    tmp = out_dir / "hip_method_ab_report.json.tmp"
    tmp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    tmp.replace(out_path)
    print(f"eval_hip_method_ab: wrote {out_path}")
    print(f"  A={args.method_a} HIP_p90={report['method_a_results']['HIP_p90_cm']} cm")
    print(f"  B={args.method_b} HIP_p90={report['method_b_results']['HIP_p90_cm']} cm")
    print(f"  delta_p90={report.get('delta_p90_cm')} cm, determinism_ok={determinism_ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
