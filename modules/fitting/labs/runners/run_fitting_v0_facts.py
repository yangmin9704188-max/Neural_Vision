#!/usr/bin/env python3
"""
Fitting runner v0 - Facts-only stub (Round4)
Always exits with code 0. Records all issues in warnings.
Supports dual measurement input formats.
"""
import argparse
import hashlib
import json
import math
import pathlib
import subprocess
import sys
from typing import Any, Dict, List, Optional


def add_warning(warnings_dict: Dict[str, Dict[str, Any]], code: str, message: str, max_samples: int = 5) -> None:
    """Helper to accumulate warnings in dict[CODE] -> {count, sample_messages, truncated} format."""
    if code not in warnings_dict:
        warnings_dict[code] = {"count": 0, "sample_messages": [], "truncated": False}
    warnings_dict[code]["count"] += 1
    if len(warnings_dict[code]["sample_messages"]) < max_samples:
        warnings_dict[code]["sample_messages"].append(message)
    else:
        warnings_dict[code]["truncated"] = True


def safe_load_json(path: str, reasons: Dict[str, int], warnings_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Load JSON file, return {} on failure and track reason."""
    try:
        p = pathlib.Path(path)
        if not p.exists():
            reasons['missing_input'] = reasons.get('missing_input', 0) + 1
            add_warning(warnings_dict, 'MISSING_INPUT', f"{path}")
            return {}
        with open(p, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        reasons['parse_fail'] = reasons.get('parse_fail', 0) + 1
        add_warning(warnings_dict, 'PARSE_FAIL', f"{path}: {type(e).__name__}")
        return {}


def extract_measurements(data: Dict[str, Any], reasons: Dict[str, int], warnings_dict: Dict[str, Dict[str, Any]], source_label: str = "unknown") -> tuple[Dict[str, Any], str]:
    """
    Extract measurements from dual format:
    A) {"bust":..., "waist":..., "hip":...}
    B) {"units":"m", "measurements":{"bust":...,"waist":...,"hip":...}}
    
    Returns: (measurements_dict, format_used)
    """
    if not data:
        return {}, "none"
    
    # Check format B first
    if 'measurements' in data and isinstance(data['measurements'], dict):
        # Validate units if present
        units = data.get('units')
        if units is not None and units != 'm':
            reasons['units_mismatch'] = reasons.get('units_mismatch', 0) + 1
            add_warning(warnings_dict, 'UNITS_MISMATCH', f"{source_label}: units='{units}' (expected 'm')")
        return data['measurements'], "B"
    
    # Assume format A
    return data, "A"


def extract_representative_body(facts_data: Dict[str, Any], reasons: Dict[str, int], warnings_dict: Dict[str, Dict[str, Any]]) -> tuple[Dict[str, Any], str, Dict[str, str]]:
    """Extract representative body measurements from facts_summary.json with keyspace detection."""
    body_measurements = {}
    key_mapping = {
        'BUST_CIRC_M': 'bust',
        'WAIST_CIRC_M': 'waist',
        'HIP_CIRC_M': 'hip'
    }
    key_mapping_used = {}
    
    # Check for torso keys and warn (do not substitute)
    for torso_key in ['BUST_CIRC_TORSO_M', 'WAIST_CIRC_TORSO_M', 'HIP_CIRC_TORSO_M']:
        if torso_key in facts_data:
            add_warning(warnings_dict, 'BODY_TORSO_KEY_IGNORED', f"{torso_key} found but ignored")
    
    # Aggregate body warnings if present
    if 'warnings' in facts_data and isinstance(facts_data['warnings'], dict):
        total_body_warnings = sum(len(v) if isinstance(v, list) else v if isinstance(v, int) else 0 
                                  for v in facts_data['warnings'].values())
        if total_body_warnings > 0:
            add_warning(warnings_dict, 'BODY_WARNINGS_PRESENT', f"count={total_body_warnings}")
    
    # Keyspace detection priority
    keyspace_candidates = [
        ('summary', facts_data.get('summary', {})),
        ('top_level', facts_data),
        ('value_stats_by_key', facts_data.get('value_stats_by_key', {})),
        ('stats_by_key', facts_data.get('stats_by_key', {})),
        ('per_key', facts_data.get('per_key', {})),
        ('by_key', facts_data.get('by_key', {}))
    ]
    
    detected_keyspace = None
    keyspace_data = None
    
    for keyspace_name, candidate_data in keyspace_candidates:
        if isinstance(candidate_data, dict):
            # Check if any of our keys exist in this keyspace
            for fact_key in key_mapping.keys():
                if fact_key in candidate_data:
                    detected_keyspace = keyspace_name
                    keyspace_data = candidate_data
                    break
            if detected_keyspace:
                break
    
    # Record detected keyspace
    if detected_keyspace:
        add_warning(warnings_dict, 'BODY_FACTS_KEYSPACE_PATH', detected_keyspace)
    else:
        detected_keyspace = "none"
        keyspace_data = {}
    
    # Extract measurements
    for fact_key, meas_key in key_mapping.items():
        if fact_key in keyspace_data:
            entry = keyspace_data[fact_key]
            if isinstance(entry, dict):
                # Flexible value extraction priority
                median_val = None
                value_stats = entry.get('value_stats', {})
                if isinstance(value_stats, dict):
                    median_val = value_stats.get('median') or value_stats.get('p50')
                if median_val is None:
                    median_val = entry.get('median') or entry.get('p50')
                
                if median_val is not None:
                    body_measurements[meas_key] = median_val
                    key_mapping_used[meas_key] = fact_key
                else:
                    reasons['missing_field'] = reasons.get('missing_field', 0) + 1
                    add_warning(warnings_dict, 'MISSING_FIELD', f"{fact_key}.median/p50")
            else:
                reasons['missing_field'] = reasons.get('missing_field', 0) + 1
                add_warning(warnings_dict, 'MISSING_FIELD', f"{fact_key} not dict")
        else:
            reasons['missing_field'] = reasons.get('missing_field', 0) + 1
            add_warning(warnings_dict, 'MISSING_FIELD', f"{fact_key}")
    
    return body_measurements, detected_keyspace, key_mapping_used


def safe_divide(numerator: Optional[float], denominator: Optional[float], reasons: Dict[str, int], warnings_dict: Dict[str, Dict[str, Any]], key: str) -> float:
    """Safely divide, return NaN on error and track reason."""
    try:
        if denominator is None or denominator == 0:
            reasons['zero_division'] = reasons.get('zero_division', 0) + 1
            add_warning(warnings_dict, 'ZERO_DIVISION', f"{key}: denom={denominator}")
            return float('nan')
        if numerator is None:
            reasons['missing_key'] = reasons.get('missing_key', 0) + 1
            add_warning(warnings_dict, 'MISSING_KEY', f"{key}: numer=None")
            return float('nan')
        return float(numerator) / float(denominator)
    except Exception as e:
        reasons['parse_fail'] = reasons.get('parse_fail', 0) + 1
        add_warning(warnings_dict, 'PARSE_FAIL', f"{key}: {type(e).__name__}")
        return float('nan')


def nan_to_null(value: Any) -> Any:
    """Convert NaN/inf/-inf to None for JSON serialization."""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
    return value


def serialize_safe(obj: Any) -> Any:
    """Recursively convert NaN/inf to null in nested structures."""
    if isinstance(obj, dict):
        return {k: serialize_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_safe(item) for item in obj]
    else:
        return nan_to_null(obj)


def _append_progress(step_id: str, dod_done_delta: int = 0, dod_total: int | None = None, note: str = "", status: str = "OK") -> None:
    """Append progress event via tools/progress_append.py (best-effort, no raise)."""
    try:
        repo = pathlib.Path(__file__).resolve().parents[2]  # labs/runners -> fitting_lab
        script = repo / "tools" / "progress_append.py"
        if not script.exists():
            return
        cmd = [sys.executable, str(script), "--step", step_id, "--done", str(dod_done_delta), "--note", note, "--event", "run_finished", "--status", status]
        if dod_total is not None:
            cmd.extend(["--total", str(dod_total)])
        subprocess.run(cmd, cwd=str(repo), capture_output=True, timeout=5)
    except Exception:
        pass


def compute_code_fingerprint() -> str:
    """Compute a simple fingerprint of this script."""
    try:
        script_path = pathlib.Path(__file__)
        if script_path.exists():
            content = script_path.read_bytes()
            return hashlib.sha256(content).hexdigest()[:16]
    except Exception:
        pass
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description='Run fitting v0 facts-only (Round4)')
    parser.add_argument('--manifest', required=True, help='Path to fitting manifest JSON')
    parser.add_argument('--out_dir', required=True, help='Output directory (overrides manifest)')
    args = parser.parse_args()

    reasons: Dict[str, int] = {'missing_input': 0, 'parse_fail': 0, 'zero_division': 0, 'missing_key': 0, 'missing_field': 0}
    global_warnings: Dict[str, Dict[str, Any]] = {}
    
    # Load manifest
    manifest = safe_load_json(args.manifest, reasons, global_warnings)
    if not manifest:
        add_warning(global_warnings, 'PARSE_FAIL', "Manifest is empty")

    # Validate schema_version
    schema_ver = manifest.get('schema_version')
    if schema_ver != 'fitting_manifest.v0':
        add_warning(global_warnings, 'SCHEMA_MISMATCH', f"expected 'fitting_manifest.v0', got '{schema_ver}'")

    # Validate inputs
    inputs = manifest.get('inputs', {})
    units = inputs.get('units')
    if units and units != 'm':
        add_warning(global_warnings, 'UNITS_MISMATCH', f"manifest units='{units}' (expected 'm')")

    # Extract sources
    body_source = inputs.get('body_source', {})
    garment_source = inputs.get('garment_source', {})

    # Load measurements
    body_data_raw = {}
    garment_data_raw = {}
    has_body = False
    has_garment = False
    body_source_type = "none"
    detected_keyspace = "none"
    key_mapping_used = {}

    # Check for facts_summary_path first
    facts_path = body_source.get('facts_summary_path')
    if facts_path:
        facts_data = safe_load_json(facts_path, reasons, global_warnings)
        if facts_data:
            body_measurements, detected_keyspace, key_mapping_used = extract_representative_body(facts_data, reasons, global_warnings)
            has_body = bool(body_measurements)
            body_source_type = "facts_summary"
            body_format = "facts_summary"
        else:
            body_measurements = {}
            body_format = "none"
    else:
        # Original body_measurements_path logic
        body_path = body_source.get('body_measurements_path')
        if body_path:
            body_data_raw = safe_load_json(body_path, reasons, global_warnings)
            has_body = bool(body_data_raw)
            body_source_type = "measurements"
        # Extract measurements (dual format support)
        body_measurements, body_format = extract_measurements(body_data_raw, reasons, global_warnings, "body")

    garment_path = garment_source.get('garment_measurements_path')
    if garment_path:
        garment_data_raw = safe_load_json(garment_path, reasons, global_warnings)
        has_garment = bool(garment_data_raw)

    # Extract garment measurements
    garment_measurements, garment_format = extract_measurements(garment_data_raw, reasons, global_warnings, "garment")
    
    # Diagnostic: log source type and keys
    loaded_body_keys = list(body_measurements.keys()) if body_measurements else []
    loaded_garment_keys = list(garment_measurements.keys()) if garment_measurements else []
    if body_source_type == "facts_summary":
        std_keys = [key_mapping_used.get(k, k) for k in loaded_body_keys]
        print(f"[Diagnostic] Body source=facts_summary, keyspace={detected_keyspace}, extracted_keys_std={std_keys}, extracted_keys_simple={loaded_body_keys}")
    else:
        print(f"[Diagnostic] Body source={body_source_type}, extracted_keys={loaded_body_keys}")

    # Calculate ease ratios
    ease_warnings: Dict[str, Dict[str, Any]] = {}
    ease_ratios = {}
    keys_of_interest = ['bust', 'waist', 'hip']
    used_keys = []

    for key in keys_of_interest:
        garment_val = garment_measurements.get(key)
        body_val = body_measurements.get(key)

        # Validate that values are numeric, not None/NaN
        garment_valid = garment_val is not None and (isinstance(garment_val, (int, float)) and not math.isnan(garment_val))
        body_valid = body_val is not None and (isinstance(body_val, (int, float)) and not math.isnan(body_val))

        if not garment_valid:
            reasons['missing_key'] = reasons.get('missing_key', 0) + 1
            add_warning(ease_warnings, 'MISSING_KEY', f"garment.{key}={garment_val}")
        if not body_valid:
            reasons['missing_key'] = reasons.get('missing_key', 0) + 1
            add_warning(ease_warnings, 'MISSING_KEY', f"body.{key}={body_val}")

        if garment_valid and body_valid:
            ratio = safe_divide(garment_val, body_val, reasons, ease_warnings, key)
            used_keys.append(key)
        else:
            ratio = float('nan')

        ease_ratios[f'{key}_ease_ratio'] = ratio

    # Count NaN
    nan_count = sum(1 for v in ease_ratios.values() if isinstance(v, float) and math.isnan(v))
    total_count = len(ease_ratios)
    nan_rate_val = nan_count / total_count if total_count > 0 else 0.0

    # Prepare outputs
    out_path = pathlib.Path(args.out_dir)
    try:
        out_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        add_warning(global_warnings, 'IO_ERROR', f"mkdir {args.out_dir}: {type(e).__name__}")

    # Compute provenance
    code_fingerprint = compute_code_fingerprint()
    provenance = {
        "manifest_path": str(pathlib.Path(args.manifest).resolve()),
        "code_fingerprint": code_fingerprint
    }

    # fitting_summary.json
    fitting_summary = {
        "schema_version": "fitting_summary.v0",
        "metrics": {
            "bust_ease_ratio": ease_ratios.get('bust_ease_ratio', float('nan')),
            "waist_ease_ratio": ease_ratios.get('waist_ease_ratio', float('nan')),
            "hip_ease_ratio": ease_ratios.get('hip_ease_ratio', float('nan'))
        },
        "warnings": ease_warnings,
        "provenance": provenance
    }

    # facts_summary.json
    facts_summary = {
        "schema_version": "facts_summary.v0",
        "coverage": {
            "has_body_measurements": has_body,
            "has_garment_measurements": has_garment,
            "used_keys": used_keys
        },
        "nan_count": {
            "total": total_count,
            "nan": nan_count
        },
        "nan_rate": nan_rate_val,
        "reasons": reasons,
        "warnings": {**global_warnings, **ease_warnings},
        "provenance": provenance
    }
    
    # Add key_mapping_used if facts_summary source was used
    if key_mapping_used:
        facts_summary["key_mapping_used"] = key_mapping_used

    # Serialize with NaN->null conversion
    fitting_summary_safe = serialize_safe(fitting_summary)
    facts_summary_safe = serialize_safe(facts_summary)

    # Write outputs
    try:
        with open(out_path / 'fitting_summary.json', 'w', encoding='utf-8') as f:
            json.dump(fitting_summary_safe, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to write fitting_summary.json: {e}", file=sys.stderr)

    try:
        with open(out_path / 'facts_summary.json', 'w', encoding='utf-8') as f:
            json.dump(facts_summary_safe, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to write facts_summary.json: {e}", file=sys.stderr)

    print(f"Output written to: {out_path}")
    print(f"NaN rate: {nan_rate_val:.2%} ({nan_count}/{total_count})")
    print(f"Total warnings: {sum(len(v) for v in {**global_warnings, **ease_warnings}.values())}")

    # Progress append (F02: fitting runner)
    _append_progress(
        step_id="F02",
        dod_done_delta=1 if nan_count == 0 else 0,
        dod_total=2,
        note=f"run_fitting_v0_facts nan_rate={nan_rate_val:.1%}",
        status="WARN" if nan_count > 0 else "OK",
    )
    sys.exit(0)


if __name__ == '__main__':
    main()
