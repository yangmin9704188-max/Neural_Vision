#!/usr/bin/env python3
"""
Validate Fitting Manifest v1 against labs/specs/fitting_manifest.schema.json.
Validates artifact paths (relative only), optional geometry manifests via contracts/geometry_manifest.schema.json,
and fingerprint/limits contract. With --strict-run: enforces required artifact existence.
Exit 0 = success, 1 = failure. Requires: jsonschema (pip install jsonschema).
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


def _repo_root() -> Path:
    return Path.cwd()


def _fitting_schema_path(repo_root: Path) -> Path:
    return repo_root / "labs" / "specs" / "fitting_manifest.schema.json"


def _geometry_schema_path(repo_root: Path) -> Path:
    return repo_root / "contracts" / "geometry_manifest.schema.json"


def _is_relative_path(s: str) -> bool:
    """Reject absolute and drive-letter paths. Allow relative only."""
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


def _collect_artifact_paths(data: dict) -> list[tuple[str, str]]:
    """Return list of (field_name, path_value) for all path fields that must be relative."""
    out: list[tuple[str, str]] = []
    im = data.get("input_manifests") or {}
    for k in ("body_manifest_path", "garment_manifest_path"):
        if k in im and im[k]:
            out.append((f"input_manifests.{k}", im[k]))
    o = data.get("outputs") or {}
    for k in ("geometry_manifest_path", "fitting_facts_summary_path", "fit_signal_path",
              "fitted_proxy_path", "condition_images_dir", "provenance_path"):
        if k in o and o[k]:
            out.append((f"outputs.{k}", o[k]))
    return out


def _validate_relative_paths(data: dict) -> list[str]:
    errs: list[str] = []
    for name, path in _collect_artifact_paths(data):
        if not _is_relative_path(path):
            errs.append(f"PATH_NOT_RELATIVE: {name} not a relative path: {path!r}")
    return errs


def _validate_fingerprint_input_based(data: dict) -> list[str]:
    """If inputs_fingerprint present, fingerprint_algo is required (input-based contract)."""
    errs: list[str] = []
    if data.get("inputs_fingerprint") and not data.get("fingerprint_algo"):
        errs.append("CHAIN_VALIDATION_FAILED: inputs_fingerprint present but fingerprint_algo missing")
    return errs


def _validate_limits(data: dict) -> list[str]:
    """Schema enforces const; double-check for clear error messages."""
    errs: list[str] = []
    limits = data.get("limits") or {}
    if "max_retry" in limits and limits["max_retry"] != 2:
        errs.append(f"CHAIN_VALIDATION_FAILED: limits.max_retry must be 2 (got {limits['max_retry']})")
    if "iter_max_per_attempt" in limits and limits.get("iter_max_per_attempt") != 100:
        errs.append(f"CHAIN_VALIDATION_FAILED: limits.iter_max_per_attempt must be 100 (got {limits.get('iter_max_per_attempt')})")
    return errs


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text), None
    except FileNotFoundError:
        return None, f"file not found: {path}"
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def _validate_geometry_manifest(path: Path, schema: dict, repo_root: Path) -> list[str]:
    errs: list[str] = []
    data, load_err = _load_json(path)
    if load_err:
        errs.append(f"CHAIN_VALIDATION_FAILED: geometry manifest {path}: {load_err}")
        return errs
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        errs.append(f"CHAIN_VALIDATION_FAILED: geometry manifest {path}: schema violation: {e.message}")
    return errs


def _strict_run_required_paths(data: dict) -> list[tuple[str, str]]:
    """Return (field_name, path) for paths that must exist in strict-run mode."""
    out: list[tuple[str, str]] = []
    im = data.get("input_manifests") or {}
    for k in ("body_manifest_path", "garment_manifest_path"):
        if k in im and im[k]:
            out.append((f"input_manifests.{k}", im[k]))
    o = data.get("outputs") or {}
    for k in ("geometry_manifest_path", "fitting_facts_summary_path"):
        if k in o and o[k]:
            out.append((f"outputs.{k}", o[k]))
    return out


# U1 minimal artifacts: body subset filename (freeze v1, single name only)
BODY_SUBSET_FILENAME = "body_measurements_subset.json"
CANONICAL_KEYS = ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]


def _collect_artifact_paths_from_geom(geom_data: dict) -> list[str]:
    """Collect all path strings from geometry manifest artifacts (run-root relative)."""
    paths: list[str] = []
    artifacts = geom_data.get("artifacts") or {}
    for k in ("mesh_path", "measurements_path", "npz_path"):
        v = artifacts.get(k)
        if v and isinstance(v, str):
            paths.append(v)
    for p in artifacts.get("aux_paths") or []:
        if p and isinstance(p, str):
            paths.append(p)
    return paths


def _has_canonical_key(vals: dict, canonical: str, keymap_aliases: dict[str, list[str]]) -> bool:
    """Check if vals has canonical key or any of its aliases (case-insensitive)."""
    if canonical in vals:
        return True
    aliases = keymap_aliases.get(canonical) or []
    val_keys_lower = {str(k).lower().replace(" ", "_").replace("-", "_") for k in vals}
    for a in aliases:
        norm = a.lower().replace(" ", "_").replace("-", "_")
        if norm in val_keys_lower:
            return True
    return False


def _validate_body_subset_content(path: Path, repo_root: Path) -> list[str]:
    """Validate body subset format: unit=m, pose_id=PZ1, 3 canonical keys. No quality judgment."""
    errs: list[str] = []
    data, load_err = _load_json(path)
    if load_err:
        errs.append(f"CHAIN_VALIDATION_FAILED: body subset {path}: {load_err}")
        return errs
    if not data:
        errs.append(f"CHAIN_VALIDATION_FAILED: body subset {path}: empty or invalid")
        return errs
    unit = data.get("unit") or data.get("units")
    if unit != "m":
        errs.append(f"CHAIN_VALIDATION_FAILED: body subset {path}: unit must be 'm' (got {unit!r})")
    pose_id = data.get("pose_id")
    if pose_id != "PZ1":
        errs.append(f"CHAIN_VALIDATION_FAILED: body subset {path}: pose_id must be 'PZ1' (got {pose_id!r})")
    vals = data.get("values") or data.get("measurements") or data.get("measurements_summary") or {}
    if not isinstance(vals, dict):
        vals = {}
    keymap_path = repo_root / "labs" / "specs" / "body_subset_keymap.v1.json"
    keymap, _ = _load_json(keymap_path)
    aliases = (keymap or {}).get("aliases") or {}
    missing = [k for k in CANONICAL_KEYS if not _has_canonical_key(vals, k, aliases)]
    if missing:
        errs.append(f"CHAIN_VALIDATION_FAILED: body subset {path}: missing canonical keys: {missing}")
    return errs


def _validate_u1_body_artifacts(body_geom_path: Path, run_root: Path, repo_root: Path) -> list[str]:
    """U1 gate: body must have subset file; if found, validate format. FAIL on missing or format violation."""
    errs: list[str] = []
    data, load_err = _load_json(body_geom_path)
    if load_err:
        errs.append(f"CHAIN_VALIDATION_FAILED: body manifest load: {load_err}")
        return errs
    paths = _collect_artifact_paths_from_geom(data or {})
    found_path: Path | None = None
    for p in paths:
        full = (run_root / p).resolve()
        if full.is_file() and full.name == BODY_SUBSET_FILENAME:
            found_path = full
            break
    if found_path is None:
        full = (run_root / BODY_SUBSET_FILENAME).resolve()
        if full.is_file():
            found_path = full
    if found_path is None:
        errs.append(f"BODY_SUBSET_MISSING: {BODY_SUBSET_FILENAME}")
        return errs
    errs.extend(_validate_body_subset_content(found_path, repo_root))
    return errs


def _validate_u1_garment_artifacts(garment_geom_path: Path, run_root: Path) -> list[str]:
    """
    U1 gate: garment must have npz_path (file exists) OR (mesh_path + measurements_path both exist).
    Artifacts field-based; run-root relative paths only. No basename check.
    """
    errs: list[str] = []
    data, load_err = _load_json(garment_geom_path)
    if load_err:
        errs.append(f"CHAIN_VALIDATION_FAILED: garment manifest load: {load_err}")
        return errs
    artifacts = (data or {}).get("artifacts") or {}
    npz_path = artifacts.get("npz_path")
    mesh_path = artifacts.get("mesh_path")
    measurements_path = artifacts.get("measurements_path")

    # Path policy: fitting strict-run requires run-root-relative only
    def check_rel(p: str | None) -> bool:
        return p and isinstance(p, str) and _is_relative_path(p)

    missing_items: list[str] = []

    # Option A: npz_path exists and file exists
    if check_rel(npz_path):
        full = (run_root / npz_path).resolve()
        if full.is_file():
            return errs
        missing_items.append(f"artifacts.npz_path file missing: {npz_path}")

    # Option B: mesh_path + measurements_path both exist and files exist
    if check_rel(mesh_path) and check_rel(measurements_path):
        m_full = (run_root / mesh_path).resolve()
        meas_full = (run_root / measurements_path).resolve()
        if m_full.is_file() and meas_full.is_file():
            return errs
        if not m_full.is_file():
            missing_items.append(f"artifacts.mesh_path file missing: {mesh_path}")
        if not meas_full.is_file():
            missing_items.append(f"artifacts.measurements_path file missing: {measurements_path}")
    else:
        if not check_rel(npz_path):
            missing_items.append("artifacts.npz_path missing or not relative")
        if not check_rel(mesh_path):
            missing_items.append("artifacts.mesh_path missing or not relative")
        if not check_rel(measurements_path):
            missing_items.append("artifacts.measurements_path missing or not relative")

    detail = "; ".join(missing_items) if missing_items else "need npz_path OR (mesh_path+measurements_path)"
    errs.append(f"GARMENT_ARTIFACTS_MISSING: {detail}")
    return errs


def _validate_strict_run(
    data: dict,
    run_root: Path,
    repo_root: Path,
    geometry_schema: dict | None,
) -> list[str]:
    """Strict-run: require artifact existence + validate geometry/facts + U1 minimal artifacts. No quality thresholds."""
    errs: list[str] = []
    required = _strict_run_required_paths(data)
    im = data.get("input_manifests") or {}
    body_rel = im.get("body_manifest_path")
    garment_rel = im.get("garment_manifest_path")

    for name, rel_path in required:
        full = (run_root / rel_path).resolve()
        if not full.is_file():
            errs.append(f"REQUIRED_FILE_MISSING: {name} -> {rel_path} (resolved: {full})")
            continue
        # File exists; run schema validation for geometry manifests and facts summary
        if "geometry_manifest" in name.lower() or "body_manifest" in name or "garment_manifest" in name:
            if geometry_schema:
                errs.extend(_validate_geometry_manifest(full, geometry_schema, repo_root))
        elif "fitting_facts_summary" in name.lower():
            try:
                if str(repo_root) not in sys.path:
                    sys.path.insert(0, str(repo_root))
                from tools.validate_fitting_facts_summary import validate_facts
                ok, fact_errs = validate_facts(full, repo_root)
                if not ok:
                    errs.extend([f"CHAIN_VALIDATION_FAILED: fitting_facts_summary ({rel_path}): {e}" for e in fact_errs])
            except ImportError as ie:
                errs.append(f"CHAIN_VALIDATION_FAILED: cannot import validate_fitting_facts_summary: {ie}")

    # U1 minimal artifacts gate (only if 4 required files passed so we have valid manifests)
    if body_rel and _is_relative_path(body_rel):
        body_full = (run_root / body_rel).resolve()
        if body_full.is_file():
            errs.extend(_validate_u1_body_artifacts(body_full, run_root, repo_root))
    if garment_rel and _is_relative_path(garment_rel):
        garment_full = (run_root / garment_rel).resolve()
        if garment_full.is_file():
            errs.extend(_validate_u1_garment_artifacts(garment_full, run_root))

    return errs


def validate_manifest(
    manifest_path: Path,
    repo_root: Path,
    geometry_schema: dict | None,
    *,
    strict_run: bool = False,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    data, load_err = _load_json(manifest_path)
    if load_err:
        return False, [f"CHAIN_VALIDATION_FAILED: {load_err}"]

    # Schema version: must be v1 for full validation
    if data.get("schema_version") != "fitting_manifest.v1":
        errors.append("SCHEMA_VERSION_MISMATCH: schema_version must be 'fitting_manifest.v1'")
    else:
        schema_path = _fitting_schema_path(repo_root)
        if not schema_path.is_file():
            errors.append(f"CHAIN_VALIDATION_FAILED: fitting schema not found: {schema_path}")
        else:
            schema_data, sch_err = _load_json(schema_path)
            if sch_err:
                errors.append(f"CHAIN_VALIDATION_FAILED: fitting schema load error: {sch_err}")
            else:
                try:
                    validator_cls = jsonschema.Draft7Validator
                    format_checker = getattr(validator_cls, "FORMAT_CHECKER", None)
                    if format_checker is not None:
                        validator_cls(schema_data, format_checker=format_checker).validate(data)
                    else:
                        jsonschema.validate(instance=data, schema=schema_data)
                except jsonschema.ValidationError as e:
                    errors.append(f"CHAIN_VALIDATION_FAILED: schema violation: {e.message}")

    # Always run path/limits/fingerprint checks when we have a manifest

    errors.extend(_validate_relative_paths(data))
    errors.extend(_validate_fingerprint_input_based(data))
    errors.extend(_validate_limits(data))

    run_root = manifest_path.parent
    if geometry_schema and not strict_run:
        im = data.get("input_manifests") or {}
        for key in ("body_manifest_path", "garment_manifest_path"):
            p = im.get(key)
            if p and _is_relative_path(p):
                full = (run_root / p).resolve()
                if full.is_file():
                    errors.extend(_validate_geometry_manifest(full, geometry_schema, repo_root))

    if strict_run and data.get("schema_version") == "fitting_manifest.v1":
        errors.extend(_validate_strict_run(data, run_root, repo_root, geometry_schema))

    return len(errors) == 0, errors


def _find_manifest_in_dir(run_dir: Path, repo_root: Path) -> tuple[Path | None, str | None]:
    """
    Discover fitting manifest in run-dir.
    Priority: fitting_manifest.json.
    Else: manifest*.json with schema_version fitting_manifest.v1.
    Returns (path, error_message). error is set when multiple v1 candidates.
    """
    priority = run_dir / "fitting_manifest.json"
    if priority.is_file():
        return priority, None

    candidates: list[Path] = []
    for p in sorted(run_dir.glob("manifest*.json")):
        data, _ = _load_json(p)
        if data and data.get("schema_version") == "fitting_manifest.v1":
            candidates.append(p)

    if len(candidates) == 0:
        return None, None
    if len(candidates) > 1:
        names = ", ".join(c.name for c in candidates)
        return None, f"multiple fitting_manifest.v1 candidates in run-dir: {names} (use fitting_manifest.json or single manifest)"
    return candidates[0], None


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate Fitting Manifest v1 (schema, relative paths, limits, fingerprint).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--manifest", type=Path, help="Path to fitting manifest JSON")
    g.add_argument("--run-dir", type=Path, help="Run directory; auto-discovers fitting manifest")
    ap.add_argument("--repo-root", type=Path, default=None, help="Repo root (default: cwd)")
    ap.add_argument("--strict-run", action="store_true", default=False, help="Enforce required artifact existence (FAIL if missing)")
    args = ap.parse_args()

    repo_root = (args.repo_root or _repo_root()).resolve()
    manifest_path: Path | None = None
    run_dir: Path | None = None

    if args.manifest is not None:
        manifest_path = args.manifest.resolve()
        if not manifest_path.is_file():
            print("error: manifest file not found:", manifest_path, file=sys.stderr)
            return 1
    else:
        run_dir = args.run_dir.resolve()
        if not run_dir.is_dir():
            print("error: run-dir not found or not a directory:", run_dir, file=sys.stderr)
            return 1
        path, err = _find_manifest_in_dir(run_dir, repo_root)
        if err:
            print("VALIDATION FAILED", file=sys.stderr)
            print("Summary: schema/path/limits or required-file violation.", file=sys.stderr)
            print(" -", f"CHAIN_VALIDATION_FAILED: {err}", file=sys.stderr)
            return 1
        if path is None:
            print("error: no fitting_manifest.json or manifest*.json (fitting_manifest.v1) in run-dir:", run_dir, file=sys.stderr)
            return 1
        manifest_path = path

    geom_schema_path = _geometry_schema_path(repo_root)
    geometry_schema: dict | None = None
    if geom_schema_path.is_file():
        gs, _ = _load_json(geom_schema_path)
        if gs is not None:
            geometry_schema = gs

    ok, errors = validate_manifest(manifest_path, repo_root, geometry_schema, strict_run=args.strict_run)
    if ok:
        return 0
    print("VALIDATION FAILED", file=sys.stderr)
    print("Summary: schema/path/limits or required-file violation.", file=sys.stderr)
    for e in errors:
        print(" -", e, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
