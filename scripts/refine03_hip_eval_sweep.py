#!/usr/bin/env python3
"""
Refine03: Build HIP top-N eval set from Step4 residual_report / prototypes, run band sweep.
Outputs (local-only, under run_dir): artifacts/eval_sets/hip_topN_ids.json, hip_sweep_eval_report.json.
Facts-only, deterministic.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

N_DEFAULT = 40
CONFIG_IDS = ["A", "B", "C", "D", "E", "B_high"]


def _find_step4_run_dir() -> Path | None:
    """Locate Step4 full run (most prototypes). Prefer run_* with max k from summary."""
    runs_base = REPO / "exports" / "runs" / "facts" / "beta_fit_v0"
    if not runs_base.exists():
        return None
    best_dir = None
    best_k = 0
    for d in runs_base.iterdir():
        if not d.is_dir():
            continue
        summary = d / "summary.json"
        if not summary.exists():
            continue
        try:
            s = json.loads(summary.read_text(encoding="utf-8"))
            k = int(s.get("k", 0))
            if k >= N_DEFAULT and k > best_k:
                best_k = k
                best_dir = d
        except Exception:
            continue
    return best_dir


def _build_eval_set(run_dir: Path, n: int) -> list[str]:
    """Scan prototypes/*/fit_result.json; top N by abs(HIP residual cm); tie-break by prototype_id."""
    prototypes_dir = run_dir / "prototypes"
    if not prototypes_dir.exists():
        return []
    rows = []
    for pdir in prototypes_dir.iterdir():
        if not pdir.is_dir():
            continue
        fit_path = pdir / "fit_result.json"
        if not fit_path.exists():
            continue
        try:
            data = json.loads(fit_path.read_text(encoding="utf-8"))
            pid = data.get("prototype_id")
            rc = data.get("residuals_cm") or {}
            hip_cm = rc.get("HIP_CIRC_M")
            if pid is None or hip_cm is None:
                continue
            rows.append((abs(hip_cm), pid))
        except Exception:
            continue
    rows.sort(key=lambda x: (-x[0], x[1]))
    return [pid for _, pid in rows[:n]]


def _run_sweep(run_dir: Path, prototype_ids: list[str]) -> dict:
    """For each config, measure HIP on eval set (mesh from beta), compute residuals; return report."""
    import numpy as np
    from tools.fit_smplx_beta_v0 import DummyMeshProvider
    from modules.body.src.measurements.vtm.core_measurements_v0 import (
        set_hip_band_override,
        clear_hip_band_override,
        measure_circumference_v0_with_metadata,
    )

    def p50(x):
        return float(np.percentile(x, 50)) if x else None
    def p90(x):
        return float(np.percentile(x, 90)) if x else None
    def pmax(x):
        return float(max(x)) if x else None

    provider = DummyMeshProvider(seed=42)
    prototypes_dir = run_dir / "prototypes"
    report = {"schema_version": "hip_sweep_eval.v0", "eval_set_size": len(prototype_ids), "configs": {}}

    for config_id in CONFIG_IDS:
        set_hip_band_override(config_id)
        residuals_hip_cm = []
        residuals_waist_cm = []
        residuals_bust_cm = []
        quality_scores = []
        warnings_count = 0
        null_count = 0
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
            res = measure_circumference_v0_with_metadata(verts, "HIP_CIRC_M")
            measured_hip = getattr(res, "value_m", None)
            if measured_hip is not None and math.isfinite(measured_hip):
                residual_hip_m = measured_hip - target_hip_m
                residuals_hip_cm.append(residual_hip_m * 100.0)
            else:
                null_count += 1
            # WAIST/BUST residuals from fit_result (same for all configs; for sanity check)
            rc = data.get("residuals_cm") or {}
            residuals_waist_cm.append(rc.get("WAIST_CIRC_M", 0))
            residuals_bust_cm.append(rc.get("BUST_CIRC_M", 0))
            qual = data.get("quality_score")
            if qual is not None:
                quality_scores.append(qual)
            w = (res.metadata or {}).get("warnings", [])
            warnings_count += len(w)
        clear_hip_band_override()

        report["configs"][config_id] = {
            "HIP_p50_cm": p50(residuals_hip_cm),
            "HIP_p90_cm": p90(residuals_hip_cm),
            "HIP_max_cm": pmax([abs(r) for r in residuals_hip_cm]) if residuals_hip_cm else None,
            "WAIST_p90_cm": p90(residuals_waist_cm),
            "BUST_p90_cm": p90(residuals_bust_cm),
            "quality_p90": p90(quality_scores),
            "count": len(residuals_hip_cm),
            "null_count": null_count,
            "warnings_count": warnings_count,
        }

    return report


def main() -> int:
    run_dir = _find_step4_run_dir()
    if run_dir is None:
        print("refine03: no Step4 run_dir found (exports/runs/facts/beta_fit_v0 with k>=40)")
        return 0
    n = N_DEFAULT
    prototype_ids = _build_eval_set(run_dir, n)
    if len(prototype_ids) < 3:
        print(f"refine03: eval set has {len(prototype_ids)} prototypes, need >=3")
        return 0

    artifacts_dir = run_dir / "artifacts" / "eval_sets"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    eval_payload = {
        "schema_version": "eval_set.hip_topN.v0",
        "selection_rule": "topN_abs_hip_residual",
        "N": n,
        "prototype_ids": sorted(prototype_ids),
    }
    eval_path = artifacts_dir / "hip_topN_ids.json"
    tmp = artifacts_dir / "hip_topN_ids.json.tmp"
    tmp.write_text(json.dumps(eval_payload, indent=2), encoding="utf-8")
    tmp.replace(eval_path)
    print(f"refine03: wrote {eval_path.relative_to(REPO)}")

    report = _run_sweep(run_dir, prototype_ids)
    report_path = artifacts_dir / "hip_sweep_eval_report.json"
    tmp2 = artifacts_dir / "hip_sweep_eval_report.json.tmp"
    tmp2.write_text(json.dumps(report, indent=2), encoding="utf-8")
    tmp2.replace(report_path)
    print(f"refine03: wrote {report_path.relative_to(REPO)}")

    # Print summary
    configs = report.get("configs", {})
    hip_p90s = {cid: c.get("HIP_p90_cm") for cid, c in configs.items() if c.get("HIP_p90_cm") is not None}
    if hip_p90s:
        best = min(hip_p90s, key=lambda c: abs(hip_p90s[c]))
        print(f"refine03: best |HIP p90| config={best} HIP_p90_cm={hip_p90s.get(best)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
