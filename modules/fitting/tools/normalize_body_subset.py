#!/usr/bin/env python3
"""
Normalize body subset input keys to canonical standard keys.
Contract: contracts/body_subset_mapping_v1.md
Schema: labs/specs/body_subset.schema.json
Keymap: labs/specs/body_subset_keymap.v1.json
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None


def _normalize_key_for_lookup(key: str) -> str:
    """Case-insensitive, separator normalization: space/dash/underscore -> underscore."""
    s = str(key).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or key


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text), None
    except FileNotFoundError:
        return None, f"file not found: {path}"
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def _is_invalid(v: object) -> bool:
    if v is None:
        return True
    if isinstance(v, (int, float)):
        return math.isnan(v) or math.isinf(v)
    return False


def _prepare_for_schema(data: dict) -> dict:
    """Accept measurements/measurements_summary as legacy alias for values. Output schema-compliant dict."""
    vals = data.get("values") or data.get("measurements") or data.get("measurements_summary") or {}
    if not isinstance(vals, dict):
        vals = {}
    return {
        "schema_version": data.get("schema_version") or "body_subset.v1",
        "unit": data.get("unit") or data.get("units") or "m",
        "pose_id": data.get("pose_id") or "PZ1",
        "values": vals,
    }


def _build_lookup(keymap: dict) -> dict[str, str]:
    """Build normalized_key -> canonical map. Alias order = priority."""
    lookup: dict[str, str] = {}
    aliases = keymap.get("aliases") or {}
    for canonical, alias_list in aliases.items():
        for alias in alias_list:
            norm = _normalize_key_for_lookup(alias)
            if norm not in lookup:
                lookup[norm] = canonical
    return lookup


def _resolve_value(src_val: object) -> object:
    """NaN/Infinity -> null."""
    if _is_invalid(src_val):
        return None
    return src_val


def normalize(
    data: dict,
    keymap: dict,
    *,
    schema_validate: bool = True,
    schema_path: Path | None = None,
) -> tuple[dict, list[str]]:
    """
    Normalize body subset to canonical_values.
    Returns (output_dict, errors). errors non-empty => schema violation.
    """
    errors: list[str] = []
    prepared = _prepare_for_schema(data)

    if schema_validate and schema_path and schema_path.is_file() and jsonschema:
        schema_data, sch_err = _load_json(schema_path)
        if sch_err:
            errors.append(f"schema load error: {sch_err}")
        else:
            try:
                jsonschema.validate(instance=prepared, schema=schema_data)
            except jsonschema.ValidationError as e:
                errors.append(f"schema violation: {e.message}")
                return _empty_output(prepared), errors

    lookup = _build_lookup(keymap)
    canonical_keys = keymap.get("canonical_keys") or ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]
    values = prepared.get("values") or {}

    canonical_values: dict[str, int | float | None] = {k: None for k in canonical_keys}
    mapping: list[dict] = []
    unmapped_keys: list[str] = []
    used_canonical: dict[str, str] = {}

    # Deterministic iteration: process source keys in sorted order
    for src_key in sorted(values.keys()):
        norm = _normalize_key_for_lookup(src_key)
        val = _resolve_value(values[src_key])
        canonical = lookup.get(norm)
        if canonical:
            # Tie-break: first source key for this canonical wins
            if canonical not in used_canonical:
                used_canonical[canonical] = src_key
                canonical_values[canonical] = val if isinstance(val, (int, float)) else None
                mapping.append({"src": src_key, "dst": canonical, "status": "mapped"})
            else:
                mapping.append({"src": src_key, "dst": canonical, "status": "tie_broken"})
        else:
            unmapped_keys.append(src_key)
            mapping.append({"src": src_key, "dst": None, "status": "unmapped"})

    output = {
        "schema_version": "body_subset_normalized.v1",
        "unit": prepared.get("unit", "m"),
        "pose_id": prepared.get("pose_id", "PZ1"),
        "canonical_values": canonical_values,
        "mapping": mapping,
        "unmapped_keys": unmapped_keys,
    }
    return output, errors


def _empty_output(prepared: dict) -> dict:
    return {
        "schema_version": "body_subset_normalized.v1",
        "unit": prepared.get("unit", "m"),
        "pose_id": prepared.get("pose_id", "PZ1"),
        "canonical_values": {},
        "mapping": [],
        "unmapped_keys": [],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Normalize body subset keys to canonical.")
    ap.add_argument("--in", dest="in_path", type=Path, required=True, help="Input body subset JSON")
    ap.add_argument("--out", type=Path, required=True, help="Output normalized JSON path")
    ap.add_argument(
        "--keymap",
        type=Path,
        default=None,
        help="Keymap JSON (default: labs/specs/body_subset_keymap.v1.json)",
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    keymap_path = args.keymap or (repo_root / "labs" / "specs" / "body_subset_keymap.v1.json")
    schema_path = repo_root / "labs" / "specs" / "body_subset.schema.json"

    data, load_err = _load_json(args.in_path)
    if load_err:
        print("error:", load_err, file=sys.stderr)
        return 1

    keymap, km_err = _load_json(keymap_path)
    if km_err or not keymap:
        print("error: keymap load failed:", km_err or "empty", file=sys.stderr)
        return 1

    output, errors = normalize(data or {}, keymap, schema_validate=True, schema_path=schema_path)

    if errors:
        print("VALIDATION FAILED", file=sys.stderr)
        for e in errors:
            print(" -", e, file=sys.stderr)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False, allow_nan=False)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, allow_nan=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
