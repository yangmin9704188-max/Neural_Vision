#!/usr/bin/env python3
"""Audit Body/Fitting/Garment geometry_manifest.json conformance against canonical schema."""
from __future__ import annotations

import json
import re
import sys
from argparse import ArgumentParser
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:
    jsonschema = None

CANONICAL_REQUIRED = [
    "schema_version",
    "module_name",
    "contract_version",
    "created_at",
    "inputs_fingerprint",
    "version_keys",
    "artifacts",
]
CANONICAL_KNOWN_KEYS = CANONICAL_REQUIRED + ["warnings", "warnings_path", "provenance_path"]
VERSION_KEYS_REQUIRED = ["snapshot_version", "semantic_version", "geometry_impl_version", "dataset_version"]
RELATIVE_PATH_PATTERN = re.compile(r"^(?!\/)(?!^[A-Za-z]:)(?!.*\.\.).+$")


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load JSON file; return None on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return None


def _normalize_for_compare(obj: Any) -> Any:
    """Recursively sort keys for deterministic comparison."""
    if isinstance(obj, dict):
        return {k: _normalize_for_compare(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_normalize_for_compare(v) for v in obj]
    return obj


def _check_relative_path(s: str) -> bool:
    """Return True if path is relative (no leading /, no drive, no ..)."""
    if not isinstance(s, str) or not s.strip():
        return False
    return bool(RELATIVE_PATH_PATTERN.match(s))


def audit_one(
    run_dir: Path,
    schema: dict[str, Any],
    module_label: str,
) -> dict[str, Any]:
    """
    Audit a single run_dir's geometry_manifest.json.
    Returns facts-only dict: valid, schema_version, missing_required_fields, extra_fields_not_in_schema,
    path_violations, artifact_paths_missing_on_disk, jsonschema_errors, top_issue_types.
    """
    manifest_path = run_dir / "geometry_manifest.json"
    out: dict[str, Any] = {
        "valid": False,
        "module": module_label,
        "run_dir": str(run_dir),
        "manifest_exists": manifest_path.exists(),
        "schema_version": None,
        "missing_required_fields": [],
        "extra_fields_not_in_schema": [],
        "path_violations": [],
        "artifact_paths_missing_on_disk": [],
        "jsonschema_errors": [],
        "top_issue_types": [],
    }

    if not manifest_path.exists():
        out["missing_required_fields"] = list(CANONICAL_REQUIRED)
        out["top_issue_types"] = [("manifest_missing", 1)]
        return out

    data = _load_json(manifest_path)
    if data is None:
        out["top_issue_types"] = [("load_error", 1)]
        return out

    out["schema_version"] = data.get("schema_version")

    # Missing required fields
    for k in CANONICAL_REQUIRED:
        if k not in data:
            out["missing_required_fields"].append(k)
        elif k == "version_keys" and isinstance(data[k], dict):
            for vk in VERSION_KEYS_REQUIRED:
                if vk not in data[k]:
                    out["missing_required_fields"].append(f"version_keys.{vk}")

    # Extra fields (informational; schema allows additionalProperties)
    for k in data:
        if k not in CANONICAL_KNOWN_KEYS:
            out["extra_fields_not_in_schema"].append(k)

    # Path violations: artifacts, warnings_path, provenance_path
    for rel in data.get("artifacts") or []:
        if isinstance(rel, str) and not _check_relative_path(rel):
            out["path_violations"].append(("artifacts", rel))
    for key in ("warnings_path", "provenance_path"):
        val = data.get(key)
        if isinstance(val, str) and val and not _check_relative_path(val):
            out["path_violations"].append((key, val))

    # Artifact paths missing on disk (WARN only)
    for rel in data.get("artifacts") or []:
        if isinstance(rel, str):
            full = (run_dir / rel).resolve()
            run_resolved = run_dir.resolve()
            if not full.exists():
                out["artifact_paths_missing_on_disk"].append(rel)
            elif not str(full).startswith(str(run_resolved)):
                out["path_violations"].append(("artifacts_escape", rel))

    # jsonschema validation
    if jsonschema:
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            out["jsonschema_errors"].append(str(e))
            if not out["missing_required_fields"]:
                out["missing_required_fields"] = ["schema_validation_failed"]
    else:
        # Minimal manual checks
        if out["missing_required_fields"] or out["path_violations"]:
            pass  # Already captured
        elif data.get("schema_version") != "geometry_manifest.v1":
            out["jsonschema_errors"].append(f"schema_version must be geometry_manifest.v1, got {data.get('schema_version')}")
        elif data.get("module_name") not in ("body", "fitting", "garment"):
            out["jsonschema_errors"].append(f"module_name must be body|fitting|garment, got {data.get('module_name')}")

    # Determine valid
    out["valid"] = (
        not out["missing_required_fields"]
        and not out["path_violations"]
        and not out["jsonschema_errors"]
    )

    # Top issue types
    counts: Counter[str] = Counter()
    if out["missing_required_fields"]:
        counts["missing_required"] = len(out["missing_required_fields"])
    if out["path_violations"]:
        counts["path_violations"] = len(out["path_violations"])
    if out["jsonschema_errors"]:
        counts["jsonschema_errors"] = len(out["jsonschema_errors"])
    if out["artifact_paths_missing_on_disk"]:
        counts["artifact_missing_on_disk"] = len(out["artifact_paths_missing_on_disk"])
    out["top_issue_types"] = counts.most_common(5)

    return out


def find_module_schemas(repo_root: Path) -> list[Path]:
    """Find module-local geometry_manifest schema files."""
    found: list[Path] = []
    for p in repo_root.rglob("*geometry_manifest*schema*.json"):
        if "contracts" in p.parts:
            continue  # Skip canonical
        found.append(p)
    return found


def check_schema_drift(canonical: dict[str, Any], local_path: Path) -> tuple[bool, str | None]:
    """
    Compare local schema to canonical (normalized). Return (equal, diff_msg).
    """
    local = _load_json(local_path)
    if local is None:
        return False, "Could not load local schema"
    a = json.dumps(_normalize_for_compare(canonical), sort_keys=True)
    b = json.dumps(_normalize_for_compare(local), sort_keys=True)
    if a == b:
        return True, None
    return False, "Schema differs from canonical (normalized JSON)"


def print_report(
    results: list[dict[str, Any]],
    drift_warnings: list[str],
) -> None:
    """Print concise facts-only report."""
    print("=== geometry_manifest conformance audit ===\n")

    for r in results:
        label = r["module"]
        status = "VALID" if r["valid"] else "INVALID"
        sv = r.get("schema_version") or "(none)"
        print(f"[{label}] {status}  schema_version={sv}")
        if not r["manifest_exists"]:
            print(f"  manifest: not found at {r['run_dir']}/geometry_manifest.json")
        else:
            issues = r.get("top_issue_types", [])
            if issues:
                print(f"  issues: {dict(issues)}")
            if r.get("missing_required_fields"):
                print(f"  missing_required_fields: {r['missing_required_fields'][:5]}")
            if r.get("path_violations"):
                print(f"  path_violations: {r['path_violations'][:3]}")
            if r.get("artifact_paths_missing_on_disk"):
                print(f"  artifact_paths_missing_on_disk (WARN): {r['artifact_paths_missing_on_disk'][:5]}")
        print()

    if drift_warnings:
        print("--- schema drift (WARN) ---")
        for w in drift_warnings:
            print(f"  {w}")
        print()

    # Combined: common mismatches across modules
    invalid_results = [r for r in results if not r["valid"]]
    if invalid_results:
        all_missing: Counter[str] = Counter()
        for r in invalid_results:
            for m in r.get("missing_required_fields", []):
                all_missing[m] += 1
        if all_missing:
            print("--- common mismatches (invalid modules) ---")
            for k, c in all_missing.most_common(5):
                print(f"  {k}: {c} modules")


def main() -> int:
    parser = ArgumentParser(
        description="Audit Body/Fitting/Garment geometry_manifest.json conformance against canonical schema"
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=None,
        help="Canonical schema path (default: contracts/geometry_manifest_v1.schema.json)",
    )
    parser.add_argument("--run_dir_body", type=Path, default=None, help="Body run directory")
    parser.add_argument("--run_dir_fitting", type=Path, default=None, help="Fitting run directory")
    parser.add_argument("--run_dir_garment", type=Path, default=None, help="Garment run directory")
    parser.add_argument(
        "--strict_drift",
        action="store_true",
        help="Exit 1 if schema drift detected (default: WARN only)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    schema_path = args.schema or repo_root / "contracts" / "geometry_manifest_v1.schema.json"
    if not schema_path.exists():
        print(f"ERROR: Schema not found: {schema_path}", file=sys.stderr)
        return 2

    schema = _load_json(schema_path)
    if schema is None:
        print("ERROR: Could not load schema", file=sys.stderr)
        return 2

    run_dirs = [
        ("body", args.run_dir_body),
        ("fitting", args.run_dir_fitting),
        ("garment", args.run_dir_garment),
    ]
    results: list[dict[str, Any]] = []
    for label, run_dir in run_dirs:
        if run_dir is None:
            continue
        r = audit_one(run_dir, schema, label)
        results.append(r)

    if not results:
        print("No run directories provided (--run_dir_body, --run_dir_fitting, --run_dir_garment)", file=sys.stderr)
        return 0

    # Optional: schema drift check
    drift_warnings: list[str] = []
    for local_path in find_module_schemas(repo_root):
        equal, diff_msg = check_schema_drift(schema, local_path)
        if not equal and diff_msg:
            drift_warnings.append(f"{local_path}: {diff_msg}")

    print_report(results, drift_warnings)

    # Exit: 0 if all valid, 1 if any invalid
    any_invalid = any(not r["valid"] for r in results)
    if any_invalid:
        return 1
    if args.strict_drift and drift_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
