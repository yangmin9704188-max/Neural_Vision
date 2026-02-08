#!/usr/bin/env python
"""
tools/roundwrap.py - Round lifecycle wrapper for garment_lab (M0)

ROUND_START: Records start event, tracks active round
ROUND_END: Records end event, generates Run Minset:
  - geometry_manifest.json (root)
  - garment_proxy_meta.json (M0)
  - facts_summary.json
  - RUN_README.md

Step-id is MANDATORY for both start and end (single-channel enforcement).

Usage:
  py roundwrap.py start --step-id G11 --note "Starting round 11"
  py roundwrap.py end --step-id G11 --note "Completed round 11"
"""

import argparse
import json
import os
import re
import shutil
import sys
import glob
from pathlib import Path
from datetime import datetime

LOG_FILE = Path("exports/progress/PROGRESS_LOG.jsonl")
ACTIVE_ROUND_FILE = Path("exports/progress/.active_round.json")

EXPORTS_RUNS_PATTERNS = [
    "exports/runs/**/geometry_manifest.json",
    "exports/runs/**/garment_proxy_meta.json",
    "exports/runs/**/garment_manifest*.json",
    "exports/runs/**/manifest*.json",
    "exports/runs/**/*facts_summary*.json",
    "exports/runs/**/RUN_README.md",
]

FALLBACK_PATTERNS = [
    "runs/smoke/smoke2/**/geometry_manifest.json",
    "runs/smoke/smoke2/**/garment_proxy_meta.json",
]

FALLBACK_EVIDENCE = "exports/progress/PROGRESS_LOG.jsonl"

def collect_exports_runs_paths(max_paths=3):
    found = []
    for pattern in EXPORTS_RUNS_PATTERNS:
        matches = glob.glob(pattern, recursive=True)
        matches = sorted(matches, key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
        for m in matches:
            if m not in found:
                found.append(m)
            if len(found) >= max_paths:
                return found, True
    return found, len(found) > 0

def collect_fallback_paths(max_paths=3):
    found = []
    for pattern in FALLBACK_PATTERNS:
        matches = glob.glob(pattern, recursive=True)
        matches = sorted(matches, key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
        for m in matches:
            if m not in found:
                found.append(m)
            if len(found) >= max_paths:
                return found
    if not found:
        found.append(FALLBACK_EVIDENCE)
    return found

def normalize_path(path):
    return path.replace("\\", "/")

def extract_run_dir(observed_paths):
    """Extract run_dir from observed_paths. Pattern: exports/runs/<lane>/<run_id>/..."""
    pattern = r"^(exports/runs/([^/]+)/([^/]+))/"
    for p in observed_paths:
        norm_p = normalize_path(p)
        match = re.match(pattern, norm_p)
        if match:
            return match.group(1), match.group(2), match.group(3)
    return None, None, None

def validate_step_id(step_id):
    if not step_id:
        return False, "step-id is required"
    step_id = step_id.strip()
    if not step_id or step_id.upper() == "UNSPECIFIED":
        return False, "step-id cannot be empty or UNSPECIFIED"
    return True, step_id

def append_event(event_type, step_id, note, evidence=None, status="OK", gate_codes=None):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now().astimezone().isoformat(),
        "module": "garment",
        "step_id": step_id,
        "event": event_type,
        "run_id": "N/A",
        "status": status,
        "dod_done_delta": 0,
        "note": note,
        "evidence": evidence or [],
        "warnings": []
    }
    if gate_codes:
        entry["gate_codes"] = gate_codes
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry

def save_active_round(step_id, note):
    ACTIVE_ROUND_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"step_id": step_id, "note": note, "started_at": datetime.now().astimezone().isoformat()}
    with open(ACTIVE_ROUND_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data

def load_active_round():
    if ACTIVE_ROUND_FILE.exists():
        with open(ACTIVE_ROUND_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def clear_active_round():
    if ACTIVE_ROUND_FILE.exists():
        ACTIVE_ROUND_FILE.unlink()

def ensure_root_geometry_manifest(run_dir):
    """
    Ensure geometry_manifest.json exists at run_dir root.
    If not, find one in subdirectories and copy to root.
    Returns: (root_manifest_path, success, skip_reason)
    """
    run_path = Path(run_dir)
    root_manifest = run_path / "geometry_manifest.json"
    
    if root_manifest.exists():
        return str(root_manifest), True, None
    
    # Search for geometry_manifest.json in subdirectories
    sub_manifests = list(run_path.glob("**/geometry_manifest.json"))
    if sub_manifests:
        # Sort by modification time (newest first)
        sub_manifests = sorted(sub_manifests, key=lambda x: x.stat().st_mtime, reverse=True)
        source = sub_manifests[0]
        try:
            shutil.copy2(source, root_manifest)
            print(f"  Copied geometry_manifest.json to root from {source}")
            return str(root_manifest), True, None
        except Exception as e:
            return None, False, f"Failed to copy: {e}"
    
    return None, False, "No geometry_manifest.json found in run_dir or subdirectories"

def generate_facts_summary(run_dir, lane, run_id, step_id, observed_paths, gate_codes, manifest_relpath=None):
    """Generate facts_summary.json in run_dir with manifest_relpath."""
    missing_minset = []
    minset_ok = True
    
    run_path = Path(run_dir)
    if not (run_path / "geometry_manifest.json").exists():
        missing_minset.append("geometry_manifest.json")
        minset_ok = False
    
    facts = {
        "schema_version": "facts_summary.v1",
        "module": "garment",
        "lane": lane,
        "run_id": run_id,
        "round_id": f"round_{step_id}",
        "step_id": step_id,
        "created_at": datetime.now().astimezone().isoformat(),
        "observed_paths_count": len(observed_paths),
        "gate_codes_count": len(gate_codes) if gate_codes else 0,
        "gate_codes": gate_codes or [],
        "observed_paths": observed_paths,
        "minset_ok": minset_ok,
        "missing_minset": missing_minset
    }
    
    if manifest_relpath:
        facts["manifest_relpath"] = manifest_relpath
    
    facts_path = run_path / "facts_summary.json"
    facts_path.parent.mkdir(parents=True, exist_ok=True)
    with open(facts_path, "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2)
    
    return str(facts_path)

def generate_run_readme(run_dir, lane, run_id, step_id, note, files_created, skip_reasons=None):
    readme_path = Path(run_dir) / "RUN_README.md"
    content = f"""# Run: {run_id}

## Summary
- **Lane**: {lane}
- **Run ID**: {run_id}
- **Step ID**: {step_id}
- **Created**: {datetime.now().astimezone().isoformat()}

## Note
{note}

## Generated Files
"""
    for f in files_created:
        content += f"- `{f}`\n"
    
    if skip_reasons:
        content += "\n## Skipped Items\n"
        for reason in skip_reasons:
            content += f"- {reason}\n"
    
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)
    return str(readme_path)

def generate_garment_proxy_meta(run_dir, lane, run_id, step_id):
    """
    Generate garment_proxy_meta.json (M0 schema) at run_dir root.
    Returns: (proxy_meta_path, success, skip_reason)
    """
    run_path = Path(run_dir)
    proxy_meta_path = run_path / "garment_proxy_meta.json"
    
    # If already exists, return it
    if proxy_meta_path.exists():
        return str(proxy_meta_path), True, None
    
    # Generate M0 stub
    proxy_meta = {
        "schema_version": "garment_proxy_meta.v1",
        "garment_id": f"garment_{run_id}",
        "template_id": f"template_{lane}",
        "size_system": "UNSPECIFIED",
        "base_size": "UNSPECIFIED",
        "lane": lane,
        "run_id": run_id,
        "step_id": step_id,
        "created_at": datetime.now().astimezone().isoformat(),
        "note": "M0 stub: minimal schema for fitting dependency resolution"
    }
    
    try:
        proxy_meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(proxy_meta_path, "w", encoding="utf-8") as f:
            json.dump(proxy_meta, f, indent=2)
        return str(proxy_meta_path), True, None
    except Exception as e:
        return None, False, f"Failed to create garment_proxy_meta.json: {e}"

def cmd_start(args):
    valid, step_id = validate_step_id(args.step_id)
    if not valid:
        print(f"FATAL: {step_id}", file=sys.stderr)
        print("NO EVENT WILL BE APPENDED. Step-id is MANDATORY.", file=sys.stderr)
        sys.exit(2)
    
    active = load_active_round()
    if active:
        print(f"WARNING: Previous round {active['step_id']} was not ended. Overwriting.", file=sys.stderr)
    
    save_active_round(step_id, args.note)
    append_event(event_type="ROUND_START", step_id=step_id, note=args.note, evidence=[], status="OK")
    print(f"ROUND_START appended: step_id={step_id}")
    print(f"  Active round saved.")
    print(f"  -> {LOG_FILE}")
    return 0

def cmd_end(args):
    valid, step_id = validate_step_id(args.step_id)
    if not valid:
        print(f"FATAL: {step_id}", file=sys.stderr)
        print("NO EVENT WILL BE APPENDED. Step-id is MANDATORY.", file=sys.stderr)
        sys.exit(2)
    
    active = load_active_round()
    if not active:
        print("WARNING: No active round found. Proceeding anyway.", file=sys.stderr)
    elif active.get("step_id") != step_id:
        print(f"WARNING: step_id mismatch. Active: {active.get('step_id')}, Provided: {step_id}", file=sys.stderr)
    
    gate_codes = []
    skip_reasons = []
    files_created = []
    manifest_relpath = None
    
    # Collect observed_paths
    exports_paths, has_exports_runs = collect_exports_runs_paths(max_paths=5)
    
    if has_exports_runs:
        observed = [normalize_path(p) for p in exports_paths]
        print(f"  exports/runs paths found: {len(observed)}")
    else:
        fallback = collect_fallback_paths(max_paths=3)
        observed = [normalize_path(p) for p in fallback]
        gate_codes.append("RUN_PATH_MISSING")
        print(f"  WARNING: No exports/runs paths found. Using fallback.")
    
    if args.evidence:
        for p in args.evidence:
            norm_p = normalize_path(p)
            if norm_p not in observed:
                observed.append(norm_p)
    
    # Extract run_dir
    run_dir, lane, run_id = extract_run_dir(observed)
    
    if run_dir:
        print(f"  run_dir: {run_dir}")
        
        # P6: Ensure root geometry_manifest.json
        root_manifest_path, manifest_ok, manifest_skip = ensure_root_geometry_manifest(run_dir)
        
        if manifest_ok:
            manifest_relpath = "geometry_manifest.json"
            norm_manifest = normalize_path(root_manifest_path)
            # Prioritize root manifest in observed_paths
            if norm_manifest not in observed:
                observed.insert(0, norm_manifest)
            files_created.append(normalize_path(root_manifest_path))
            print(f"  Root geometry_manifest.json: OK")
        else:
            gate_codes.append("RUN_MANIFEST_ROOT_MISSING")
            skip_reasons.append(f"geometry_manifest.json: {manifest_skip}")
            print(f"  WARNING: {manifest_skip}")
        
        # M0: Generate garment_proxy_meta.json
        proxy_meta_path, proxy_ok, proxy_skip = generate_garment_proxy_meta(run_dir, lane, run_id, step_id)
        if proxy_ok:
            norm_proxy = normalize_path(proxy_meta_path)
            if norm_proxy not in observed:
                observed.insert(1, norm_proxy)  # After geometry_manifest
            files_created.append(norm_proxy)
            print(f"  Root garment_proxy_meta.json: OK")
        else:
            gate_codes.append("GARMENT_PROXY_META_MISSING")
            skip_reasons.append(f"garment_proxy_meta.json: {proxy_skip}")
            print(f"  WARNING: {proxy_skip}")
        
        # Generate facts_summary.json
        facts_path = generate_facts_summary(run_dir, lane, run_id, step_id, observed, gate_codes, manifest_relpath)
        files_created.append(normalize_path(facts_path))
        print(f"  Created: {facts_path}")
        
        # Generate RUN_README.md
        note = args.note or (active.get("note") if active else "Round completed")
        readme_path = generate_run_readme(run_dir, lane, run_id, step_id, note, files_created, skip_reasons)
        files_created.append(normalize_path(readme_path))
        print(f"  Created: {readme_path}")
        
        # Add generated files to observed
        # Prioritize generated files (minset)
        for f in reversed(files_created):
            if f in observed:
                observed.remove(f)
            observed.insert(0, f)
    else:
        gate_codes.append("RUN_DIR_EXTRACTION_FAILED")
        skip_reasons.append("Could not extract run_dir from observed_paths")
        print(f"  WARNING: Could not extract run_dir from observed_paths")
    
    # Limit observed_paths (prioritize root manifest, minset files)
    observed = observed[:5]
    
    note = args.note
    if gate_codes:
        note = f"{note} [gate_codes: {','.join(gate_codes)}]"
    
    append_event(event_type="ROUND_END", step_id=step_id, note=note, evidence=observed,
                 status=args.status or "OK", gate_codes=gate_codes if gate_codes else None)
    
    clear_active_round()
    
    print(f"ROUND_END appended: step_id={step_id}")
    print(f"  observed_paths: {observed}")
    if gate_codes:
        print(f"  gate_codes: {gate_codes}")
    if files_created:
        print(f"  files_created: {files_created}")
    print(f"  -> {LOG_FILE}")
    return 0

def main():
    parser = argparse.ArgumentParser(description="Round lifecycle wrapper for garment_lab (P6)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    start_parser = subparsers.add_parser("start", help="Record ROUND_START event")
    start_parser.add_argument("--step-id", required=True, help="Step ID (e.g., G10) - MANDATORY")
    start_parser.add_argument("--note", required=True, help="Description of round start")
    
    end_parser = subparsers.add_parser("end", help="Record ROUND_END event")
    end_parser.add_argument("--step-id", required=True, help="Step ID (e.g., G10) - MANDATORY")
    end_parser.add_argument("--note", required=True, help="Description of round end")
    end_parser.add_argument("--status", default="OK", help="Status (OK, WARN, ERROR)")
    end_parser.add_argument("--evidence", action="append", help="Additional evidence paths")
    
    args = parser.parse_args()
    
    if args.command == "start":
        sys.exit(cmd_start(args))
    elif args.command == "end":
        sys.exit(cmd_end(args))
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
