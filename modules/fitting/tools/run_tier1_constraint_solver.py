#!/usr/bin/env python3
"""
Tier-1 Constraint Solver. Generates fit_signal.json.
- Loads body/garment inputs (measurements, npz, obj) from run-dir.
- Computes proxy quality scores (clipping, penetration, constraint_violation) from AABB/verts.
- When verts unavailable: degraded + neutral scores. Facts-only. No quality thresholds.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Seoul")
except ImportError:
    TZ = None

# Proxy params (recorded in solver.notes)
ALPHA = 0.7
BETA = 0.3


def _ts_now() -> str:
    if TZ:
        from datetime import datetime
        return datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _is_relative(s: str) -> bool:
    if not s or not isinstance(s, str):
        return False
    s = s.strip().replace("\\", "/")
    if s.startswith("/"):
        return False
    if re.match(r"^[A-Za-z]:", s):
        return False
    if s.startswith("file://"):
        return False
    return True


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _load_verts_from_npz(path: Path) -> Any | None:
    """Load vertex array from npz. Tries common keys: vertices, verts, V, positions, points."""
    if not HAS_NUMPY or not path.is_file():
        return None
    try:
        with np.load(path, allow_pickle=True) as data:
            for key in ("vertices", "verts", "V", "positions", "points", "positions"):
                if key in data.files:
                    arr = np.asarray(data[key], dtype=float)
                    if arr.ndim == 2 and arr.shape[1] >= 3:
                        return arr[:, :3]
    except Exception:
        pass
    return None


def _load_verts_from_obj(path: Path) -> Any | None:
    """Parse OBJ file for vertex lines (v x y z)."""
    if not path.is_file():
        return None
    verts: list[list[float]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("v ") and not line.startswith("vt ") and not line.startswith("vn "):
                parts = line.split()
                if len(parts) >= 4:
                    verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
        if verts and HAS_NUMPY:
            return np.array(verts)
        if verts:
            return verts  # fallback without numpy: use list (less efficient)
    except Exception:
        pass
    return None


def _load_body_subset(run_dir: Path) -> dict[str, float] | None:
    """Load body measurements (m). Keys: BUST/WAIST/HIP (circumferences)."""
    candidates = [
        run_dir / "body_measurements_subset.json",
    ]
    body_geom = run_dir / "body_geometry_manifest.json"
    if body_geom.is_file():
        try:
            data = json.loads(body_geom.read_text(encoding="utf-8"))
            p = (data.get("artifacts") or {}).get("measurements_path")
            if p and isinstance(p, str) and _is_relative(p):
                candidates.insert(0, run_dir / p.replace("\\", "/"))
        except Exception:
            pass
    key_aliases = {
        "BUST_CIRC_M": "bust",
        "bust": "bust",
        "BUST": "bust",
        "WAIST_CIRC_M": "waist",
        "waist": "waist",
        "WAIST": "waist",
        "HIP_CIRC_M": "hip",
        "hip": "hip",
        "HIP": "hip",
    }
    for p in candidates:
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            vals = data.get("values") or data.get("measurements_summary") or data
            if not isinstance(vals, dict):
                continue
            out: dict[str, float] = {}
            for k, v in vals.items():
                std = key_aliases.get(k, k.lower())
                if std in ("bust", "waist", "hip") and isinstance(v, (int, float)):
                    out[std] = float(v)
            if len(out) >= 3:
                return out
        except Exception:
            pass
    return None


def _find_body_subset_path(run_dir: Path) -> str:
    cand = run_dir / "body_measurements_subset.json"
    if cand.is_file():
        return "body_measurements_subset.json"
    body_geom = run_dir / "body_geometry_manifest.json"
    if body_geom.is_file():
        try:
            data = json.loads(body_geom.read_text(encoding="utf-8"))
            p = (data.get("artifacts") or {}).get("measurements_path")
            if p and isinstance(p, str) and _is_relative(p):
                return p
        except Exception:
            pass
    return "body_measurements_subset.json"


def _find_garment_path(run_dir: Path) -> str:
    for name in ("garment_geometry_manifest.json", "geometry_manifest.json"):
        cand = run_dir / name
        if not cand.is_file():
            continue
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
            if data.get("module") in ("garment", "fitting", None):
                return name
        except Exception:
            pass
    return "garment_geometry_manifest.json"


def _load_garment_verts(run_dir: Path, garment_ref: str) -> tuple[Any | None, list[str]]:
    """Load garment verts. Prefer npz_path, fallback mesh_path. Returns (verts, missing_reasons)."""
    manifest_path = run_dir / garment_ref.replace("\\", "/")
    if not manifest_path.is_file():
        return None, [f"garment manifest not found: {garment_ref}"]
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifacts = data.get("artifacts") or {}
    except Exception:
        return None, [f"garment manifest unreadable: {garment_ref}"]

    # Prefer npz
    npz_path = artifacts.get("npz_path")
    if npz_path and isinstance(npz_path, str) and _is_relative(npz_path):
        full = (run_dir / npz_path.replace("\\", "/")).resolve()
        verts = _load_verts_from_npz(full)
        if verts is not None:
            if HAS_NUMPY and hasattr(verts, "size") and verts.size == 0:
                return None, [f"npz empty or no vertices: {npz_path}"]
            if HAS_NUMPY:
                n = verts.shape[0] if verts.ndim else 0
            else:
                n = len(verts) if verts else 0
            if n >= 1:
                return verts, []
        return None, [f"npz has no verts or unreadable: {npz_path}"]

    # Fallback: mesh
    mesh_path = artifacts.get("mesh_path")
    if mesh_path and isinstance(mesh_path, str) and _is_relative(mesh_path):
        full = (run_dir / mesh_path.replace("\\", "/")).resolve()
        verts = _load_verts_from_obj(full)
        if verts is not None:
            n = len(verts) if hasattr(verts, "__len__") else (verts.shape[0] if HAS_NUMPY and hasattr(verts, "shape") else 0)
            if n >= 1:
                if not HAS_NUMPY and isinstance(verts, list):
                    verts = np.array(verts) if HAS_NUMPY else verts  # keep list if no numpy
                return verts, []
        return None, [f"mesh unreadable or no verts: {mesh_path}"]

    return None, ["garment artifacts: no npz_path or mesh_path"]


def _load_body_verts(run_dir: Path, body_subset_path: str) -> Any | None:
    """Load body verts from body geometry manifest npz/mesh."""
    body_geom = run_dir / "body_geometry_manifest.json"
    if not body_geom.is_file():
        return None
    try:
        data = json.loads(body_geom.read_text(encoding="utf-8"))
        artifacts = data.get("artifacts") or {}
    except Exception:
        return None
    for key, path_key in [("npz_path", _load_verts_from_npz), ("mesh_path", _load_verts_from_obj)]:
        p = artifacts.get(key)
        if p and isinstance(p, str) and _is_relative(p):
            full = (run_dir / p.replace("\\", "/")).resolve()
            verts = path_key(full)
            if verts is not None:
                n = verts.shape[0] if (HAS_NUMPY and hasattr(verts, "shape")) else len(verts)
                if n >= 1:
                    return verts
    return None


def _aabb_from_verts(verts: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """(min_xyz, max_xyz)"""
    if HAS_NUMPY and hasattr(verts, "min") and hasattr(verts, "max"):
        mn = verts.min(axis=0)
        mx = verts.max(axis=0)
        return (float(mn[0]), float(mn[1]), float(mn[2])), (float(mx[0]), float(mx[1]), float(mx[2]))
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _aabb_from_measurements(bust: float, waist: float, hip: float) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Approximate body AABB from circumferences (m). Assume ellipsoid-like: depth~0.4*c/pi, width~0.5*c/pi, height from bust->hip."""
    import math
    pi = math.pi
    # Circumference to approximate width/depth: c = pi*(w+d) roughly, use w=d for circle cross-section
    # Half-axis from circumference: r = c/(2*pi)
    w_bust = bust / (2 * pi) if bust > 0 else 0.2
    w_waist = waist / (2 * pi) if waist > 0 else 0.15
    w_hip = hip / (2 * pi) if hip > 0 else 0.2
    width = max(w_bust, w_waist, w_hip) * 2
    depth = width * 0.8
    # Height: bust~0.3m from waist, hip~0.2m below waist (arbitrary torso)
    height = 0.6
    cx, cy, cz = 0.0, 0.0, 0.0
    hx, hy, hz = width / 2, depth / 2, height / 2
    return (cx - hx, cy - hy, cz - hz), (cx + hx, cy + hy, cz + hz)


def _aabb_volume(mn: tuple[float, float, float], mx: tuple[float, float, float]) -> float:
    v = (mx[0] - mn[0]) * (mx[1] - mn[1]) * (mx[2] - mn[2])
    return max(0.0, v)


def _aabb_diagonal(mn: tuple[float, float, float], mx: tuple[float, float, float]) -> float:
    import math
    d = math.sqrt((mx[0] - mn[0])**2 + (mx[1] - mn[1])**2 + (mx[2] - mn[2])**2)
    return d if d > 1e-12 else 1e-12


def _aabb_intersection_volume(
    a1: tuple[tuple[float, float, float], tuple[float, float, float]],
    a2: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> float:
    mn1, mx1 = a1
    mn2, mx2 = a2
    inter_mn = (max(mn1[0], mn2[0]), max(mn1[1], mn2[1]), max(mn1[2], mn2[2]))
    inter_mx = (min(mx1[0], mx2[0]), min(mx1[1], mx2[1]), min(mx1[2], mx2[2]))
    if inter_mn[0] >= inter_mx[0] or inter_mn[1] >= inter_mx[1] or inter_mn[2] >= inter_mx[2]:
        return 0.0
    return _aabb_volume(inter_mn, inter_mx)


def _points_inside_aabb(verts: Any, mn: tuple[float, float, float], mx: tuple[float, float, float]) -> Any:
    """Boolean mask of verts inside AABB [mn, mx]."""
    if HAS_NUMPY and hasattr(verts, "__getitem__"):
        arr = np.asarray(verts)
        in_x = (arr[:, 0] >= mn[0]) & (arr[:, 0] <= mx[0])
        in_y = (arr[:, 1] >= mn[1]) & (arr[:, 1] <= mx[1])
        in_z = (arr[:, 2] >= mn[2]) & (arr[:, 2] <= mx[2])
        return in_x & in_y & in_z
    return [mn[0] <= v[0] <= mx[0] and mn[1] <= v[1] <= mx[1] and mn[2] <= v[2] <= mx[2] for v in verts]


def _mean_internal_depth(verts: Any, mask: Any, mn: tuple[float, float, float], mx: tuple[float, float, float], diag: float) -> float:
    """Mean over inside verts of min distance to AABB faces, normalized by diagonal."""
    if HAS_NUMPY and hasattr(verts, "__getitem__"):
        inside = np.asarray(verts)[np.asarray(mask)]
    else:
        inside = [v for v, m in zip(verts, mask) if m]
    n = len(inside) if hasattr(inside, "__len__") else (int(inside.shape[0]) if HAS_NUMPY and hasattr(inside, "shape") else 0)
    if n == 0:
        return 0.0
    dists = []
    for i in range(n):
        if HAS_NUMPY and hasattr(inside, "shape") and len(inside.shape) == 2:
            v = (float(inside[i, 0]), float(inside[i, 1]), float(inside[i, 2]))
        else:
            vi = inside[i]
            v = (float(vi[0]), float(vi[1]), float(vi[2])) if len(vi) >= 3 else (0.0, 0.0, 0.0)
        d_to_faces = [
            v[0] - mn[0], mx[0] - v[0],
            v[1] - mn[1], mx[1] - v[1],
            v[2] - mn[2], mx[2] - v[2],
        ]
        dists.append(min(d_to_faces))
    avg = sum(dists) / len(dists)
    return avg / diag


def _compute_proxy_scores(
    body_aabb: tuple[tuple[float, float, float], tuple[float, float, float]],
    garment_verts: Any,
    body_from_measurements: bool,
    warnings: list[dict],
) -> tuple[float, float, float]:
    """Returns (clipping_score, penetration_score, constraint_violation_score)."""
    mn_b, mx_b = body_aabb
    garment_aabb = _aabb_from_verts(garment_verts)
    mn_g, mx_g = garment_aabb

    if body_from_measurements:
        warnings.append({
            "code": "PROXY_BODY_AABB_FROM_MEASUREMENTS",
            "severity": "info",
            "message": "Body AABB approximated from BUST/WAIST/HIP measurements",
        })

    vol_b = _aabb_volume(mn_b, mx_b)
    vol_g = _aabb_volume(mn_g, mx_g)
    vol_inter = _aabb_intersection_volume(body_aabb, garment_aabb)
    denom = min(vol_b, vol_g)
    v = vol_inter / denom if denom > 1e-12 else 0.0
    clipping_score = _clamp01(1.0 - v)

    diag = _aabb_diagonal(mn_b, mx_b)
    mask = _points_inside_aabb(garment_verts, mn_b, mx_b)
    if HAS_NUMPY:
        n_total = garment_verts.shape[0] if hasattr(garment_verts, "shape") else len(garment_verts)
        n_inside = int(np.count_nonzero(mask) if hasattr(mask, "__iter__") else sum(1 for m in mask if m))
    else:
        n_total = len(garment_verts)
        n_inside = sum(1 for m in mask if m)
    r_in = n_inside / n_total if n_total > 0 else 0.0
    d = _mean_internal_depth(garment_verts, mask, mn_b, mx_b, diag)
    raw_pen = ALPHA * r_in + BETA * d
    penetration_score = _clamp01(1.0 - raw_pen)

    violation = _clamp01(0.5 * (1 - penetration_score) + 0.5 * (1 - clipping_score))
    constraint_violation_score = _clamp01(1.0 - violation)

    return clipping_score, penetration_score, constraint_violation_score


def _get_output_path(run_dir: Path) -> Path:
    manifest = run_dir / "fitting_manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            out = (data.get("outputs") or {}).get("fit_signal_path")
            if out and isinstance(out, str) and _is_relative(out):
                return (run_dir / out.replace("\\", "/")).resolve()
        except Exception:
            pass
    return run_dir / "fit_signal.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Tier-1 Constraint Solver.")
    ap.add_argument("--run-dir", type=Path, required=True, dest="run_dir", help="Run directory")
    ap.add_argument("--repo-root", type=Path, default=None, help="Repo root (default: cwd)")
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    if not run_dir.is_dir():
        print("error: run-dir not found:", run_dir, file=sys.stderr)
        return 1

    t0 = time.perf_counter()

    early_exit = "hard_gate" in str(run_dir).lower()
    body_path = _find_body_subset_path(run_dir)
    garment_path = _find_garment_path(run_dir)

    input_refs: dict = {
        "body_subset_path": body_path,
        "garment_ref": garment_path,
    }
    body_resolved = (run_dir / body_path.replace("\\", "/")).resolve()
    garment_resolved = (run_dir / garment_path.replace("\\", "/")).resolve()
    input_refs["resolved_paths"] = {
        "body_subset_path_resolved": str(body_resolved),
        "garment_ref_resolved": str(garment_resolved),
    }

    warnings: list[dict] = []
    degraded = False
    clipping = 0.5
    penetration = 0.5
    constraint_viol = 0.5
    solver_notes = ""

    if early_exit:
        warnings.append({
            "code": "EARLY_EXIT_NO_SOLVE",
            "severity": "info",
            "message": "Hard gate: early exit (no solve attempted). Scores neutral.",
        })
        solver_notes = f"proxy_skip(early_exit); alpha={ALPHA} beta={BETA}"
    else:
        garment_verts, missing = _load_garment_verts(run_dir, garment_path)
        if garment_verts is None:
            degraded = True
            warnings.append({
                "code": "INPUT_MISSING_FOR_PROXY",
                "severity": "warning",
                "message": f"Cannot load garment verts for proxy. Missing: {'; '.join(missing)}",
            })
            solver_notes = "proxy_degraded(no_garment_verts)"
        else:
            body_verts = _load_body_verts(run_dir, body_path)
            body_subset = _load_body_subset(run_dir)
            body_aabb = None
            body_from_meas = False
            if body_verts is not None:
                body_aabb = _aabb_from_verts(body_verts)
            elif body_subset and "bust" in body_subset and "waist" in body_subset and "hip" in body_subset:
                body_aabb = _aabb_from_measurements(
                    body_subset["bust"], body_subset["waist"], body_subset["hip"]
                )
                body_from_meas = True

            if body_aabb is not None:
                clipping, penetration, constraint_viol = _compute_proxy_scores(
                    body_aabb, garment_verts, body_from_meas, warnings
                )
                solver_notes = f"proxy_alpha={ALPHA} beta={BETA}"
            else:
                degraded = True
                warnings.append({
                    "code": "INPUT_MISSING_FOR_PROXY",
                    "severity": "warning",
                    "message": "Cannot build body AABB: no body verts, no BUST/WAIST/HIP measurements",
                })
                solver_notes = "proxy_degraded(no_body_ref)"

    if "degraded" in str(run_dir).lower() and not early_exit:
        degraded = True
        if not any(w.get("code") == "PARTIAL_CONVERGENCE" for w in warnings):
            warnings.append({"code": "PARTIAL_CONVERGENCE", "severity": "warning", "message": "iter_max reached"})

    t1 = time.perf_counter()
    wall_ms = max(1, int((t1 - t0) * 1000))

    WALL_MS_SOFT_LIMIT = 1500
    budget_exceeded = wall_ms > WALL_MS_SOFT_LIMIT

    solver_obj: dict = {
        "solver_id": "tier1_constraint_solver_stub",
        "solver_version": "0.1",
    }
    if solver_notes:
        solver_obj["notes"] = solver_notes

    payload = {
        "schema_version": "fit_signal.v0",
        "created_at": _ts_now(),
        "input_refs": input_refs,
        "solver": solver_obj,
        "timing": {"wall_ms": wall_ms, "notes": "proxy" if not early_exit else "stub"},
        "quality_scores": {
            "clipping_score": clipping,
            "penetration_score": penetration,
            "constraint_violation_score": constraint_viol,
        },
        "flags": {"early_exit": early_exit, "degraded": degraded},
    }
    if budget_exceeded:
        payload["budget"] = {"wall_ms_soft_limit": WALL_MS_SOFT_LIMIT, "wall_ms_soft_exceeded": True}
        warnings.append({
            "code": "BUDGET_WALL_MS_EXCEEDED_SOFT",
            "severity": "warning",
            "message": f"wall_ms={wall_ms} exceeds soft limit {WALL_MS_SOFT_LIMIT}ms",
        })
    if warnings:
        payload["warnings"] = warnings

    out_path = _get_output_path(run_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
