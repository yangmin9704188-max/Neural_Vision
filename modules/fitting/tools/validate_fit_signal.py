#!/usr/bin/env python3
"""
Validate fit_signal.json v0 against labs/specs/fit_signal.schema.json.
Schema validation + created_at date-time check (when possible).
Exit 0 = OK, 1 = FAIL.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("error: jsonschema required. pip install jsonschema", file=sys.stderr)
    sys.exit(1)


def _schema_path(repo_root: Path) -> Path:
    return repo_root / "labs" / "specs" / "fit_signal.schema.json"


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text), None
    except FileNotFoundError:
        return None, "file not found"
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


# ISO 8601 date-time pattern (flexible)
_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)


def _validate_created_at(data: dict) -> list[str]:
    """Check created_at is a reasonable date-time string."""
    errs: list[str] = []
    v = data.get("created_at")
    if not isinstance(v, str) or not v.strip():
        errs.append("created_at: must be non-empty string")
        return errs
    if not _DATETIME_PATTERN.match(v.strip()):
        errs.append("created_at: expected ISO 8601 date-time (e.g. 2026-02-08T12:00:00+09:00)")
    return errs


def validate_fit_signal(path: Path, repo_root: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    data, load_err = _load_json(path)
    if load_err:
        return False, [load_err]
    assert data is not None

    schema_path = _schema_path(repo_root)
    if not schema_path.is_file():
        errors.append(f"schema not found: {schema_path}")
    else:
        schema_data, sch_err = _load_json(schema_path)
        if sch_err:
            errors.append(f"schema load error: {sch_err}")
        else:
            try:
                jsonschema.validate(instance=data, schema=schema_data)
            except jsonschema.ValidationError as e:
                errors.append(f"schema violation: {getattr(e, 'message', str(e))}")

    errors.extend(_validate_created_at(data))
    return len(errors) == 0, errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate fit_signal.json v0.")
    ap.add_argument("--fit-signal", type=Path, required=True, dest="fit_signal", help="Path to fit_signal.json")
    ap.add_argument("--repo-root", type=Path, default=None, help="Repo root (default: cwd)")
    args = ap.parse_args()

    repo_root = (args.repo_root or Path.cwd()).resolve()
    path = args.fit_signal.resolve()
    if not path.is_file():
        print("error: fit_signal file not found:", path, file=sys.stderr)
        return 1

    ok, errors = validate_fit_signal(path, repo_root)
    if ok:
        return 0
    print("VALIDATION FAILED", file=sys.stderr)
    print("Summary: schema or created_at violation.", file=sys.stderr)
    for e in errors:
        print(" -", e, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
