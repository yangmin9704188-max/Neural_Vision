#!/usr/bin/env python3
"""
Validate fitting_facts_summary.json v1 against labs/specs/fitting_facts_summary.schema.json.
Schema validation + warnings_summary sample_messages length (<=5) and type check.
Exit 0 = OK, 1 = FAIL. Requires: jsonschema (pip install jsonschema).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("error: jsonschema required. pip install jsonschema", file=sys.stderr)
    sys.exit(1)


def _schema_path(repo_root: Path) -> Path:
    return repo_root / "labs" / "specs" / "fitting_facts_summary.schema.json"


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text), None
    except FileNotFoundError:
        return None, f"file not found: {path}"
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def _validate_warnings_summary(data: dict) -> list[str]:
    """Check warnings_summary: each value has count>=0, sample_messages length<=5, all strings, truncated bool."""
    errs: list[str] = []
    ws = data.get("warnings_summary")
    if ws is None or not isinstance(ws, dict):
        return errs
    for code, entry in ws.items():
        if not isinstance(entry, dict):
            errs.append(f"warnings_summary.{code}: value must be object with count, sample_messages, truncated")
            continue
        count = entry.get("count")
        if count is not None and (not isinstance(count, int) or count < 0):
            errs.append(f"warnings_summary.{code}.count: must be integer >= 0")
        msgs = entry.get("sample_messages")
        if msgs is not None:
            if not isinstance(msgs, list):
                errs.append(f"warnings_summary.{code}.sample_messages: must be array")
            else:
                if len(msgs) > 5:
                    errs.append(f"warnings_summary.{code}.sample_messages: at most 5 items (got {len(msgs)})")
                for i, m in enumerate(msgs):
                    if not isinstance(m, str):
                        errs.append(f"warnings_summary.{code}.sample_messages[{i}]: must be string")
        if "truncated" in entry and not isinstance(entry.get("truncated"), bool):
            errs.append(f"warnings_summary.{code}.truncated: must be boolean")
    return errs


def validate_facts(facts_path: Path, repo_root: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    data, load_err = _load_json(facts_path)
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
                validator_cls = jsonschema.Draft7Validator
                format_checker = getattr(validator_cls, "FORMAT_CHECKER", None)
                if format_checker is not None:
                    validator_cls(schema_data, format_checker=format_checker).validate(data)
                else:
                    jsonschema.validate(instance=data, schema=schema_data)
            except jsonschema.ValidationError as e:
                errors.append(f"schema violation: {e.message}")

    errors.extend(_validate_warnings_summary(data))
    return len(errors) == 0, errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate fitting_facts_summary.json v1.")
    ap.add_argument("--facts", type=Path, required=True, help="Path to fitting_facts_summary.json")
    ap.add_argument("--repo-root", type=Path, default=None, help="Repo root (default: cwd)")
    args = ap.parse_args()

    repo_root = (args.repo_root or Path.cwd()).resolve()
    facts_path = args.facts.resolve()
    if not facts_path.is_file():
        print("error: facts file not found:", facts_path, file=sys.stderr)
        return 1

    ok, errors = validate_facts(facts_path, repo_root)
    if ok:
        return 0
    print("VALIDATION FAILED", file=sys.stderr)
    print("Summary: schema or warnings_summary (count/sample_messages<=5/truncated) violation.", file=sys.stderr)
    for e in errors:
        print(" -", e, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
