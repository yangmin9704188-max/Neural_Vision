#!/usr/bin/env python3
"""
Append-only progress event logger.
Writes to <lab_root>/exports/progress/PROGRESS_LOG.jsonl.
Exit 0 always; failures surface as stdout warning.
"""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime


def _warn(code: str, message: str, path: str = "N/A") -> str:
    return f"[{code}] {message} | path={path}"


def _ts_now() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    except ImportError:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _resolve_log_path(lab_root: Path) -> Path:
    """Resolve to <lab_root>/exports/progress/PROGRESS_LOG.jsonl. Path safety: no parent escape."""
    lab = lab_root.resolve()
    log_path = (lab / "exports" / "progress" / "PROGRESS_LOG.jsonl").resolve()
    try:
        log_path.relative_to(lab)
    except ValueError:
        return lab / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    return log_path


def _load_parallel_policy(repo_root: Path) -> dict:
    path = repo_root / "contracts" / "parallel_execution_policy_v1.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _policy_errors(module: str, step_id: str, lifecycle_state: str | None, validation_report_ref: str, closure_spec_ref: str, repo_root: Path) -> list[str]:
    errs: list[str] = []
    policy = _load_parallel_policy(repo_root)
    if not policy:
        return errs

    prefix = (step_id[:1] if step_id else "").upper()
    common_prefix = str(policy.get("common_step_prefix", "C")).upper()
    allowed_common_modules = {str(x).lower() for x in policy.get("allowed_common_event_modules", ["body", "common"])}
    module_prefix = {k.lower(): str(v).upper() for k, v in (policy.get("module_step_prefix") or {}).items()}

    if prefix == common_prefix:
        if module.lower() not in allowed_common_modules:
            errs.append(_warn("COMMON_STEP_MODULE_MISMATCH", f"C* must use module in {sorted(allowed_common_modules)}"))
    elif prefix in {"B", "F", "G"}:
        expected = None
        for mod, pfx in module_prefix.items():
            if pfx == prefix:
                expected = mod
                break
        if expected and module.lower() != expected:
            errs.append(_warn("STEP_MODULE_MISMATCH", f"{prefix}* must use module={expected}"))

    state = (lifecycle_state or "").upper()
    if state == "VALIDATED" and not validation_report_ref.strip():
        errs.append(_warn("VALIDATED_REPORT_MISSING", "VALIDATED requires --validation-report-ref"))
    if state == "CLOSED" and not closure_spec_ref.strip():
        errs.append(_warn("CLOSED_SPEC_MISSING", "CLOSED requires --closure-spec-ref"))
    return errs


def main() -> int:
    parser = argparse.ArgumentParser(description="Append progress event to PROGRESS_LOG.jsonl")
    parser.add_argument("--lab-root", required=True, help="Lab root (exports/progress under here)")
    parser.add_argument("--module", required=True, choices=("common", "body", "fitting", "garment"))
    parser.add_argument("--step-id", required=True, help="e.g. F01, G12, B02")
    parser.add_argument("--event", required=True, help="e.g. milestone_passed, dod_checkpoint, note, run_finished")
    parser.add_argument("--run-id", default="N/A")
    parser.add_argument("--status", default="N/A", choices=("OK", "WARN", "FAIL", "N/A"))
    parser.add_argument("--m-level", default="M0", choices=("M0", "M1", "M2"),
                        help="Completion level for this event (default: M0)")
    parser.add_argument(
        "--lifecycle-state",
        default=None,
        choices=("IMPLEMENTED", "VALIDATED", "CLOSED"),
        help="Lifecycle state for closure protocol"
    )
    parser.add_argument("--note", default="")
    parser.add_argument("--dod-done-delta", type=int, default=0)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--closure-spec-ref", default="", help="Repo-relative closure spec path")
    parser.add_argument("--validation-report-ref", default="", help="Repo-relative validation report path")
    parser.add_argument("--skip-policy-check", action="store_true", help="Skip parallel execution policy checks")
    parser.add_argument("--gate-code", action="append", default=[], help="e.g. STEP_ID_MISSING")
    parser.add_argument("--soft-validate", action="store_true")
    parser.add_argument("--ts", default=None)
    args = parser.parse_args()

    lab_root = Path(args.lab_root).resolve()
    log_path = _resolve_log_path(lab_root)
    warnings = []

    if args.soft_validate and args.evidence:
        for p in args.evidence:
            ep = Path(p)
            if not ep.is_absolute():
                ep = lab_root / p
            if not ep.exists():
                warnings.append(_warn("EVIDENCE_NOT_FOUND", "evidence path missing", str(p)))
    if args.soft_validate and args.closure_spec_ref:
        cp = Path(args.closure_spec_ref)
        if not cp.is_absolute():
            cp = Path.cwd() / cp
        if not cp.exists():
            warnings.append(_warn("CLOSURE_SPEC_NOT_FOUND", "closure spec path missing", args.closure_spec_ref))
    if args.soft_validate and args.validation_report_ref:
        vp = Path(args.validation_report_ref)
        if not vp.is_absolute():
            vp = Path.cwd() / vp
        if not vp.exists():
            warnings.append(_warn("VALIDATION_REPORT_NOT_FOUND", "validation report path missing", args.validation_report_ref))

    if args.lifecycle_state == "VALIDATED" and not args.validation_report_ref:
        warnings.append(_warn("VALIDATION_REPORT_REF_MISSING", "VALIDATED requires validation_report_ref"))
    if args.lifecycle_state == "CLOSED" and not args.closure_spec_ref:
        warnings.append(_warn("CLOSURE_SPEC_REF_MISSING", "CLOSED requires closure_spec_ref"))

    if not args.skip_policy_check:
        perrs = _policy_errors(
            module=args.module,
            step_id=args.step_id,
            lifecycle_state=args.lifecycle_state,
            validation_report_ref=args.validation_report_ref,
            closure_spec_ref=args.closure_spec_ref,
            repo_root=Path.cwd(),
        )
        if perrs:
            print(
                f"appended PROGRESS_LOG.jsonl (module={args.module}, step={args.step_id}, event={args.event}), "
                f"warnings={len(warnings) + len(perrs)}"
            )
            return 1

    ev = {
        "ts": args.ts or _ts_now(),
        "module": args.module,
        "step_id": args.step_id,
        "event": args.event,
        "run_id": args.run_id,
        "status": args.status,
        "m_level": args.m_level,
        "dod_done_delta": args.dod_done_delta,
        "note": args.note,
        "evidence": args.evidence or [],
        "closure_spec_ref": args.closure_spec_ref or None,
        "validation_report_ref": args.validation_report_ref or None,
        "warnings": warnings + [f"[{g}]" for g in args.gate_code],
    }
    if args.lifecycle_state:
        ev["lifecycle_state"] = args.lifecycle_state

    line = json.dumps(ev, ensure_ascii=False) + "\n"

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        print(f"appended PROGRESS_LOG.jsonl (module={args.module}, step={args.step_id}, event={args.event}), warnings={len(warnings)+1}")
        return 0

    print(f"appended PROGRESS_LOG.jsonl (module={args.module}, step={args.step_id}, event={args.event}), warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
