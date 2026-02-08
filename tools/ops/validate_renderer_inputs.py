#!/usr/bin/env python3
"""
Validate renderer inputs against contracts (warn-only, exit 0 always).
Inputs: ops/lab_roots.local.json, PROGRESS_LOG.jsonl per lab, brief files, master_plan.
Outputs: stdout summary of warnings; optionally ops/hub_state_v1.json diagnostics section.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAB_ROOTS_PATH = REPO_ROOT / "ops" / "lab_roots.local.json"
SCHEMA_PATH = REPO_ROOT / "contracts" / "progress_event_v1.schema.json"
MASTER_PLAN_PATH = REPO_ROOT / "contracts" / "master_plan_v1.json"
HUB_STATE_PATH = REPO_ROOT / "ops" / "hub_state_v1.json"

MODULES = ("body", "fitting", "garment")
BRIEF_NAMES = ("BODY_WORK_BRIEF.md", "FITTING_WORK_BRIEF.md", "GARMENT_WORK_BRIEF.md")
MAX_LINES = 100


def _warn(code: str, message: str, path: str = "N/A") -> str:
    return f"[{code}] {message} | path={path}"


def _get_lab_roots() -> dict[str, Path | None]:
    """Lab roots: ENV > lab_roots.local.json. Body = repo root."""
    roots: dict[str, Path | None] = {"body": REPO_ROOT}
    from_env = {
        "fitting": os.environ.get("FITTING_LAB_ROOT", "").strip(),
        "garment": os.environ.get("GARMENT_LAB_ROOT", "").strip(),
    }
    for k, v in from_env.items():
        if v:
            roots[k] = Path(v).resolve()
        else:
            roots[k] = None

    if roots.get("fitting") is None or roots.get("garment") is None:
        if LAB_ROOTS_PATH.exists():
            try:
                with open(LAB_ROOTS_PATH, encoding="utf-8") as f:
                    cfg = json.load(f)
                for k in ("fitting", "garment"):
                    if roots.get(k) is None and cfg.get(f"{k.upper()}_LAB_ROOT"):
                        val = cfg[f"{k.upper()}_LAB_ROOT"]
                        roots[k] = (REPO_ROOT / val).resolve() if not Path(val).is_absolute() else Path(val).resolve()
            except Exception:
                pass
    return roots


def _load_schema() -> dict | None:
    if not SCHEMA_PATH.exists():
        return None
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _validate_event_manual(ev: dict, line_no: int) -> list[str]:
    """Manual minimal validation when jsonschema unavailable."""
    warns = []
    if not isinstance(ev, dict):
        warns.append(_warn("EVENT_NOT_OBJECT", f"line {line_no}: not a JSON object", "N/A"))
        return warns
    if "ts" not in ev:
        warns.append(_warn("TS_MISSING", f"line {line_no}: ts required", "N/A"))
    elif not isinstance(ev.get("ts"), str):
        warns.append(_warn("TS_INVALID", f"line {line_no}: ts must be string", "N/A"))
    if "module" not in ev:
        warns.append(_warn("MODULE_MISSING", f"line {line_no}: module required", "N/A"))
    elif ev.get("module", "").lower() not in ("body", "fitting", "garment"):
        warns.append(_warn("MODULE_INVALID", f"line {line_no}: module must be body|fitting|garment", "N/A"))
    if "step_id" not in ev:
        warns.append(_warn("STEP_ID_MISSING", f"line {line_no}: step_id required", "N/A"))
    if "event_type" not in ev and "event" not in ev:
        warns.append(_warn("EVENT_TYPE_MISSING", f"line {line_no}: event_type or event required", "N/A"))
    return warns


def _validate_progress_log(log_path: Path) -> list[str]:
    warns = []
    if not log_path.exists():
        warns.append(_warn("PROGRESS_LOG_NOT_FOUND", "PROGRESS_LOG.jsonl not found", str(log_path)))
        return warns
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except Exception as e:
        warns.append(_warn("PROGRESS_LOG_READ_FAIL", str(e), str(log_path)))
        return warns
    lines = [ln.strip() for ln in lines if ln.strip()][-MAX_LINES:]
    schema = _load_schema()
    for i, line in enumerate(lines):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError as e:
            warns.append(_warn("PROGRESS_LOG_PARSE_FAIL", f"line {i+1}: {e}", str(log_path)))
            continue
        if schema:
            try:
                import jsonschema
                jsonschema.validate(ev, schema)
            except ImportError:
                warns.extend(_validate_event_manual(ev, i + 1))
            except jsonschema.ValidationError as e:
                warns.append(_warn("SCHEMA_VIOLATION", f"line {i+1}: {e.message}", str(log_path)))
        else:
            warns.extend(_validate_event_manual(ev, i + 1))
    return warns


def _validate_brief_files(roots: dict[str, Path | None]) -> list[str]:
    warns = []
    for mod in MODULES:
        root = roots.get(mod)
        if root is None or not root.exists():
            if mod != "body":
                warns.append(_warn("LAB_ROOT_MISSING", f"{mod} lab root not configured", "N/A"))
            continue
        brief_name = f"{mod.upper()}_WORK_BRIEF.md"
        brief_path = root / "exports" / "brief" / brief_name
        if not brief_path.exists():
            expects = f"exports/brief/{brief_name}"
            warns.append(_warn("BRIEF_NOT_FOUND", f"expected {expects}", str(brief_path)))
        elif brief_name not in BRIEF_NAMES:
            warns.append(_warn("BRIEF_NAME_MISMATCH", f"expected one of {BRIEF_NAMES}", brief_name))
    return warns


def _validate_master_plan() -> list[str]:
    warns = []
    if not MASTER_PLAN_PATH.exists():
        warns.append(_warn("MASTER_PLAN_NOT_FOUND", "contracts/master_plan_v1.json not found", str(MASTER_PLAN_PATH)))
        return warns
    try:
        with open(MASTER_PLAN_PATH, encoding="utf-8") as f:
            plan = json.load(f)
    except json.JSONDecodeError as e:
        warns.append(_warn("MASTER_PLAN_INVALID", str(e), str(MASTER_PLAN_PATH)))
        return warns
    if plan.get("schema_version") != "master_plan.v1":
        warns.append(_warn("MASTER_PLAN_SCHEMA", "expected schema_version master_plan.v1", "N/A"))
    return warns


def _update_hub_state_diagnostics(warnings: list[str]) -> None:
    """Add diagnostics section to hub_state_v1.json if it exists (minimal schema change)."""
    if not HUB_STATE_PATH.exists():
        return
    try:
        with open(HUB_STATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return
    data["diagnostics"] = {
        "validator": "validate_renderer_inputs",
        "warning_count": len(warnings),
        "warnings": warnings[:20],
    }
    try:
        with open(HUB_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def main() -> int:
    warnings: list[str] = []
    roots = _get_lab_roots()

    warnings.extend(_validate_master_plan())
    warnings.extend(_validate_brief_files(roots))

    for mod in MODULES:
        root = roots.get(mod)
        if root is None or not root.exists():
            continue
        log_path = root / "exports" / "progress" / "PROGRESS_LOG.jsonl"
        warnings.extend(_validate_progress_log(log_path))

    if not LAB_ROOTS_PATH.exists():
        warnings.append(_warn("LAB_ROOTS_MISSING", "ops/lab_roots.local.json not found (fitting/garment optional)", str(LAB_ROOTS_PATH)))

    # Optional: write diagnostics to hub_state
    add_diagnostics = "--hub-state" in sys.argv or "-H" in sys.argv
    if add_diagnostics and warnings:
        _update_hub_state_diagnostics(warnings)

    n = len(warnings)
    if n == 0:
        print("validate_renderer_inputs: OK (no warnings)")
    else:
        print(f"validate_renderer_inputs: {n} warning(s)")
        for w in warnings[:15]:
            print(f"  {w}")
        if n > 15:
            print(f"  ... and {n - 15} more")

    return 0


if __name__ == "__main__":
    sys.exit(main())
