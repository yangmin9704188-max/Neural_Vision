#!/usr/bin/env python3
"""
Run-end ops hook: B2 unlock readiness (if beta_fit run found) → append progress → render_work_briefs → render_status.
Called from postprocess_round or run completion. Exit 0 by default. Facts-only; never gate.
With --restore-generated (Round 09): restores ops/STATUS.md and removes temp files after render.
With --strict-clean (Round 10): FAIL if working tree dirty at start or end.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# B2 unlock: default thresholds (must match generate_unlock_signal_b2_v0.py defaults when used)
B2_THRESHOLD_SCORE = 70.0
B2_THRESHOLD_RESIDUAL_P90_CM = 1.0
B2_MAX_FAILURES = 0


def _get_lab_roots() -> dict[str, Path | None]:
    """ENV > lab_roots.local.json. Returns fitting, garment roots or None."""
    roots = {"fitting": None, "garment": None}
    for k, env_key in (("fitting", "FITTING_LAB_ROOT"), ("garment", "GARMENT_LAB_ROOT")):
        v = os.environ.get(env_key, "").strip()
        if v:
            roots[k] = Path(v).resolve()
        else:
            roots[k] = None

    if roots["fitting"] is None or roots["garment"] is None:
        cfg_path = REPO_ROOT / "ops" / "lab_roots.local.json"
        if cfg_path.exists():
            try:
                with open(cfg_path, encoding="utf-8") as f:
                    cfg = json.load(f)
                for k, key in (("fitting", "FITTING_LAB_ROOT"), ("garment", "GARMENT_LAB_ROOT")):
                    if roots[k] is None and cfg.get(key):
                        roots[k] = (REPO_ROOT / cfg[key]).resolve()
            except Exception:
                pass
    return roots


def _b2_unlock_rules_match(unlock_path: Path) -> bool:
    """True if unlock_signal.json exists and rules match current CLI thresholds."""
    if not unlock_path.exists():
        return False
    try:
        with open(unlock_path, encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("rules") or {}
        return (
            rules.get("threshold_score") == B2_THRESHOLD_SCORE
            and rules.get("threshold_residual_p90_cm") == B2_THRESHOLD_RESIDUAL_P90_CM
            and rules.get("max_failures") == B2_MAX_FAILURES
        )
    except Exception:
        return False


def _run_b2_unlock_readiness() -> None:
    """Discover latest beta_fit_v0 run; generate unlock_signal + optionally append progress. Never raises."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        from tools.ops.find_latest_beta_fit_run import find_latest_beta_fit_run
    except ImportError:
        print("[B2 unlock] skip: find_latest_beta_fit_run not importable")
        return

    run_dir = find_latest_beta_fit_run(REPO_ROOT)
    if run_dir is None:
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "ops" / "append_progress_event.py"),
                    "--lab-root", str(REPO_ROOT),
                    "--module", "body",
                    "--step-id", "B04",
                    "--event", "note",
                    "--note", "B2 unlock signal skipped: no beta_fit_v0 summary.json found",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                check=False,
            )
        except Exception:
            pass
        print("[B2 unlock] skip: no beta_fit_v0 run_dir found")
        return

    unlock_path = run_dir / "unlock_signal.json"
    rules_match = _b2_unlock_rules_match(unlock_path)
    log_progress = not rules_match

    cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "generate_unlock_signal_b2_v0.py"),
        "--run_dir", str(run_dir),
        "--out_dir", str(run_dir),
        "--threshold_score", "70",
        "--threshold_residual_p90_cm", "1.0",
        "--max_failures", "0",
    ]
    if log_progress:
        cmd.append("--log-progress")

    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if r.returncode != 0:
        print(f"[B2 unlock] generator exit {r.returncode}: {run_dir}")
        return
    print(f"[B2 unlock] run_dir={run_dir} log_progress={log_progress} rules_match={rules_match}")


def _git_status_porcelain(repo_root: Path):
    """Run git status --porcelain.  Returns (stdout, error_msg)."""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )
        if r.returncode == 0:
            return r.stdout, None
        return None, f"git status exit {r.returncode}"
    except Exception as exc:
        return None, str(exc)


def _is_clean(porcelain_output: str) -> bool:
    return porcelain_output.strip() == ""


def _dirty_files_summary(porcelain_output: str, max_lines: int = 20) -> str:
    lines = [l for l in porcelain_output.strip().splitlines() if l.strip()]
    shown = lines[:max_lines]
    text = "\n".join(f"    {l}" for l in shown)
    if len(lines) > max_lines:
        text += f"\n    ... ({len(lines) - max_lines} more)"
    return text


def _cleanup_generated(repo_root: Path) -> None:
    """Restore generated files and remove temp files. WARN on failure, never FAIL. (Round 09)"""
    targets_restore = ["ops/STATUS.md"]
    targets_remove = [".tmp_pr_body.txt"]

    for rel_path in targets_restore:
        full = repo_root / rel_path
        if not full.is_file():
            print(f"[CLEANUP] {rel_path}: missing (skipped)")
            continue
        try:
            r = subprocess.run(
                ["git", "restore", rel_path],
                cwd=str(repo_root), capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                print(f"[CLEANUP] {rel_path}: restored")
            else:
                print(f"[CLEANUP] {rel_path}: warn (git restore exit {r.returncode})")
        except Exception as exc:
            print(f"[CLEANUP] {rel_path}: warn ({exc})")

    for rel_path in targets_remove:
        full = repo_root / rel_path
        if not full.is_file():
            print(f"[CLEANUP] {rel_path}: absent")
            continue
        try:
            full.unlink()
            print(f"[CLEANUP] {rel_path}: removed")
        except OSError as exc:
            print(f"[CLEANUP] {rel_path}: warn ({exc})")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run-end ops hook (R09 restore / R10 strict-clean)")
    parser.add_argument("--restore-generated", action="store_true",
                        help="Restore ops/STATUS.md and remove temp files after render")
    parser.add_argument("--strict-clean", action="store_true",
                        help="FAIL if working tree dirty at start or end (Round 10)")
    parser.add_argument("--allow-pre-dirty", action="store_true",
                        help="With --strict-clean: downgrade pre-dirty to WARN (Round 10)")
    parser.add_argument("--require-step-id", action="store_true",
                        help="(legacy) Require step IDs via env")
    parser.add_argument("--fitting-step-id", type=str, default=None,
                        help="(legacy) Fitting step ID override")
    parser.add_argument("--garment-step-id", type=str, default=None,
                        help="(legacy) Garment step ID override")
    args, _unknown = parser.parse_known_args()

    strict = args.strict_clean
    pre_status = "clean"

    # ── Pre-check (Round 10) ─────────────────────────────────────────
    if strict:
        out, err = _git_status_porcelain(REPO_ROOT)
        if err is not None:
            print(f"[STRICT_CLEAN] pre-check ERROR: {err}")
            return 1
        if not _is_clean(out):
            pre_status = "dirty"
            if args.allow_pre_dirty:
                print("[STRICT_CLEAN] pre=dirty (WARN, --allow-pre-dirty)")
                print(_dirty_files_summary(out))
            else:
                print("[STRICT_CLEAN] pre=dirty policy=FAIL")
                print(_dirty_files_summary(out))
                return 1
        else:
            pre_status = "clean"

    warnings = 0
    roots = _get_lab_roots()

    # Step IDs: CLI override > ENV
    fitting_step_raw = (args.fitting_step_id
                        or os.environ.get("FITTING_STEP_ID", "")).strip()
    garment_step_raw = (args.garment_step_id
                        or os.environ.get("GARMENT_STEP_ID", "")).strip()
    fitting_step = fitting_step_raw if fitting_step_raw else "UNSPECIFIED"
    garment_step = garment_step_raw if garment_step_raw else "UNSPECIFIED"

    for module, lab_root, step_id, step_missing in (
        ("fitting", roots["fitting"], fitting_step, not fitting_step_raw),
        ("garment", roots["garment"], garment_step, not garment_step_raw),
    ):
        if lab_root is None or not lab_root.exists():
            continue
        note = "[WARN] STEP_ID_MISSING run end hook" if step_missing else "run end hook"
        cmd = [
            sys.executable,
            str(REPO_ROOT / "tools" / "ops" / "append_progress_event.py"),
            "--lab-root", str(lab_root),
            "--module", module,
            "--step-id", step_id,
            "--event", "run_finished",
            "--status", "WARN" if step_missing else "OK",
            "--note", note,
            "--dod-done-delta", "0",
        ]
        if step_missing:
            cmd.extend(["--gate-code", "STEP_ID_MISSING"])
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
        if r.returncode != 0:
            warnings += 1

    try:
        _run_b2_unlock_readiness()
    except Exception as e:
        print(f"[B2 unlock] warning: {e}")
        warnings += 1

    for script in ("render_work_briefs.py", "render_status.py"):
        cmd = [sys.executable, str(REPO_ROOT / "tools" / script)]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
        if r.returncode != 0:
            warnings += 1

    print(f"ops hook done, warnings={warnings}")

    # Post-render cleanup (Round 09)
    if args.restore_generated:
        _cleanup_generated(REPO_ROOT)

    # ── Post-check (Round 10) ────────────────────────────────────────
    if strict:
        out, err = _git_status_porcelain(REPO_ROOT)
        if err is not None:
            print(f"[STRICT_CLEAN] post-check ERROR: {err}")
            return 1
        post_clean = _is_clean(out)
        post_status = "clean" if post_clean else "dirty"
        policy = "FAIL" if not post_clean else ("WARN" if pre_status == "dirty" else "PASS")
        print(f"[STRICT_CLEAN] pre={pre_status} post={post_status} policy={policy}")
        if not post_clean:
            print(_dirty_files_summary(out))
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
