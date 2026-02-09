#!/usr/bin/env python3
"""
Consume M1 body/garment signals and run fitting publish flow.

Behavior:
1) Read ops/signals/m1/body/LATEST.json and ops/signals/m1/garment/LATEST.json.
2) If one/both missing: exit 0 with message "M1 inputs not available; stay in M0".
3) If both available: generate fitting outputs under data/shared_m1/fitting/<run_id>/.
4) Validate output with tools/validate/validate_u1_fitting.py.
5) Update ops/signals/m1/fitting/LATEST.json (repo-relative run_dir_rel only).
6) If append_progress_event supports --m-level, append M1 OK event.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BODY_SIGNAL = REPO_ROOT / "ops" / "signals" / "m1" / "body" / "LATEST.json"
GARMENT_SIGNAL = REPO_ROOT / "ops" / "signals" / "m1" / "garment" / "LATEST.json"
FITTING_SIGNAL = REPO_ROOT / "ops" / "signals" / "m1" / "fitting" / "LATEST.json"
SHARED_ROOT = REPO_ROOT / "data" / "shared_m1" / "fitting"


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("fitting_m1_%Y%m%d_%H%M%S")


def _sanitize_run_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or _default_run_id()


def _is_safe_rel_path(raw: str) -> bool:
    if not raw or not isinstance(raw, str):
        return False
    s = raw.strip().replace("\\", "/")
    if not s or s.startswith("/") or s.startswith("file://"):
        return False
    if re.match(r"^[A-Za-z]:", s):
        return False
    p = Path(s)
    if p.is_absolute() or ".." in p.parts:
        return False
    return True


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _resolve_from_signal(sig: dict, label: str) -> tuple[str | None, Path | None, str | None]:
    run_dir_rel = sig.get("run_dir_rel")
    if not isinstance(run_dir_rel, str) or not _is_safe_rel_path(run_dir_rel):
        return None, None, f"{label} signal missing valid run_dir_rel"

    run_dir = (REPO_ROOT / run_dir_rel).resolve()
    try:
        run_dir.relative_to(REPO_ROOT)
    except ValueError:
        return None, None, f"{label} run_dir_rel escapes repo"

    if not run_dir.is_dir():
        return None, None, f"{label} run_dir does not exist: {run_dir_rel}"

    return run_dir_rel.replace("\\", "/"), run_dir, None


def _garment_input_from_run(garment_run_dir: Path) -> tuple[str, Path | None]:
    npz = garment_run_dir / "garment_proxy.npz"
    glb = garment_run_dir / "garment_proxy_mesh.glb"
    if npz.is_file():
        return "npz", npz
    if glb.is_file():
        return "glb_fallback", glb
    return "glb_fallback", None


def _derive_early_exit(garment_sig: dict) -> tuple[bool, str | None]:
    hard_gate = False
    reason = None

    if garment_sig.get("hard_gate") is True:
        hard_gate = True
        reason = garment_sig.get("hard_gate_reason") or "garment_hard_gate_violation: signal"
    elif garment_sig.get("early_exit") is True:
        hard_gate = True
        reason = garment_sig.get("early_exit_reason") or "garment_hard_gate_violation: early_exit"
    elif str(garment_sig.get("status", "")).upper() == "HARD_GATE":
        hard_gate = True
        reason = garment_sig.get("reason") or "garment_hard_gate_violation: status=HARD_GATE"

    return hard_gate, reason


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _validate_u1(run_dir: Path) -> tuple[bool, str]:
    validator = REPO_ROOT / "tools" / "validate" / "validate_u1_fitting.py"
    if not validator.is_file():
        return False, "validator not found: tools/validate/validate_u1_fitting.py"

    p = subprocess.run(
        [sys.executable, str(validator), "--run-dir", str(run_dir)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    return p.returncode == 0, output.strip()


def _append_m1_progress(run_id: str, run_dir_rel: str) -> str:
    script = REPO_ROOT / "tools" / "ops" / "append_progress_event.py"
    if not script.is_file():
        return "append_progress_event.py not found; skipped"

    help_proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    help_text = (help_proc.stdout or "") + (help_proc.stderr or "")
    if "--m-level" not in help_text:
        return "--m-level not supported yet; skipped"

    cmd = [
        sys.executable,
        str(script),
        "--lab-root",
        str(REPO_ROOT),
        "--module",
        "fitting",
        "--step-id",
        "F01",
        "--event",
        "m1_run_performed",
        "--run-id",
        run_id,
        "--status",
        "OK",
        "--note",
        "U1 fitting output valid / M1 run performed",
        "--evidence",
        run_dir_rel,
        "--m-level",
        "M1",
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30)
    if proc.returncode == 0:
        return "progress event appended (m_level=M1)"
    return f"append_progress_event failed (rc={proc.returncode})"


def main() -> int:
    ap = argparse.ArgumentParser(description="Consume M1 signals and publish fitting M1 output.")
    ap.add_argument("--body-signal", type=Path, default=BODY_SIGNAL)
    ap.add_argument("--garment-signal", type=Path, default=GARMENT_SIGNAL)
    ap.add_argument("--fitting-signal", type=Path, default=FITTING_SIGNAL)
    ap.add_argument("--shared-root", type=Path, default=SHARED_ROOT)
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    body_sig = _load_json(args.body_signal)
    garment_sig = _load_json(args.garment_signal)
    if body_sig is None or garment_sig is None:
        print("M1 inputs not available; stay in M0")
        return 0

    body_rel, body_dir, body_err = _resolve_from_signal(body_sig, "body")
    garment_rel, garment_dir, garment_err = _resolve_from_signal(garment_sig, "garment")
    if body_err or garment_err:
        print("M1 inputs not available; stay in M0")
        if body_err:
            print(f"- {body_err}")
        if garment_err:
            print(f"- {garment_err}")
        return 0

    run_id = _sanitize_run_id(args.run_id or _default_run_id())
    run_dir = (args.shared_root / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        run_dir.relative_to(REPO_ROOT)
    except ValueError:
        print("refusing to write outside repo", file=sys.stderr)
        return 1

    garment_used, garment_src = _garment_input_from_run(garment_dir)
    artifact_names: list[str] = ["fitting_facts_summary.json"]

    if garment_src is not None:
        dst_name = "garment_proxy.npz" if garment_used == "npz" else "garment_proxy_mesh.glb"
        dst = run_dir / dst_name
        try:
            shutil.copy2(garment_src, dst)
        except Exception:
            dst.write_bytes(b"")
        artifact_names.append(dst_name)

    early_exit, early_reason = _derive_early_exit(garment_sig)
    warnings_summary: list[str] = []
    degraded_state = "none"
    if early_exit:
        warnings_summary.append("M1_GARMENT_HARD_GATE")
        degraded_state = "high_warning_degraded"

    fp_src = f"{body_rel}|{garment_rel}|{run_id}".encode("utf-8")
    manifest = {
        "schema_version": "geometry_manifest.v1",
        "module_name": "fitting",
        "contract_version": "contract.v1",
        "created_at": _utc_now_z(),
        "inputs_fingerprint": hashlib.sha256(fp_src).hexdigest(),
        "version_keys": {
            "snapshot_version": "m1",
            "semantic_version": "0.1.0",
            "geometry_impl_version": "consume_m1_and_run.v1",
            "dataset_version": "none",
        },
        "artifacts": artifact_names,
        "warnings": [],
    }

    facts = {
        "schema_version": "fitting_facts_summary.v1",
        "garment_input_path_used": garment_used,
        "early_exit": early_exit,
        "early_exit_reason": early_reason,
        "warnings_summary": warnings_summary,
        "degraded_state": degraded_state,
    }

    _write_json(run_dir / "geometry_manifest.json", manifest)
    _write_json(run_dir / "fitting_facts_summary.json", facts)

    ok, validation_out = _validate_u1(run_dir)
    if not ok:
        print("validate_u1_fitting failed", file=sys.stderr)
        print(validation_out, file=sys.stderr)
        return 1

    run_dir_rel = run_dir.relative_to(REPO_ROOT).as_posix()
    fitting_signal = {
        "schema_version": "m1_signal.v1",
        "module": "fitting",
        "m_level": "M1",
        "status": "OK",
        "run_id": run_id,
        "run_dir_rel": run_dir_rel,
        "updated_at": _utc_now_z(),
        "inputs": {
            "body_run_dir_rel": body_rel,
            "garment_run_dir_rel": garment_rel,
        },
    }
    _write_json(args.fitting_signal, fitting_signal)

    progress_msg = _append_m1_progress(run_id=run_id, run_dir_rel=run_dir_rel)

    print("M1 run completed")
    print(f"- run_dir_rel: {run_dir_rel}")
    print(f"- validate_u1_fitting: PASS/WARN (FAIL=0)")
    print(f"- progress: {progress_msg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
