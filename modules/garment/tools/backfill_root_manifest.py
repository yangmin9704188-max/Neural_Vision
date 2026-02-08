#!/usr/bin/env python
"""
tools/backfill_root_manifest.py - Backfill root geometry_manifest.json for past runs

Usage:
  py backfill_root_manifest.py exports/runs/_smoke/20260206_171153
  py backfill_root_manifest.py --all  # Process all run_dirs missing root manifest
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime

def ensure_fingerprint(manifest_path):
    """Ensure 'fingerprint' field exists. If missing, copy from 'inputs_fingerprint'."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        modified = False
        
        # Check if fingerprint is missing
        if "fingerprint" not in data:
            if "inputs_fingerprint" in data:
                data["fingerprint"] = data["inputs_fingerprint"]
                modified = True
                print(f"  Patched: fingerprint <- inputs_fingerprint")
            else:
                # Generate a simple fingerprint if none exists
                data["fingerprint"] = f"backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                modified = True
                print(f"  Patched: fingerprint <- generated")
        
        if modified:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        
        return True
    except Exception as e:
        print(f"  ERROR patching fingerprint: {e}")
        return False

def backfill_run_dir(run_dir):
    """Backfill root geometry_manifest.json for a single run_dir."""
    run_path = Path(run_dir)
    
    if not run_path.exists():
        print(f"ERROR: run_dir does not exist: {run_dir}")
        return False
    
    root_manifest = run_path / "geometry_manifest.json"
    
    if root_manifest.exists():
        print(f"  Root manifest already exists: {root_manifest}")
        # Still ensure fingerprint field
        ensure_fingerprint(root_manifest)
        return True
    
    # Search for geometry_manifest.json in subdirectories
    sub_manifests = list(run_path.glob("**/geometry_manifest.json"))
    
    if sub_manifests:
        # Sort by modification time (newest first)
        sub_manifests = sorted(sub_manifests, key=lambda x: x.stat().st_mtime, reverse=True)
        source = sub_manifests[0]
        
        try:
            shutil.copy2(source, root_manifest)
            print(f"  Copied to root from: {source}")
            
            # Ensure fingerprint field
            ensure_fingerprint(root_manifest)
            
            return True
        except Exception as e:
            print(f"  ERROR copying: {e}")
            # Append to RUN_README.md
            readme = run_path / "RUN_README.md"
            try:
                with open(readme, "a", encoding="utf-8") as f:
                    f.write(f"\n## BACKFILL FAILED\n- {datetime.now().isoformat()}: {e}\n")
            except:
                pass
            return False
    else:
        print(f"  WARNING: No geometry_manifest.json found in subdirectories")
        # Append to RUN_README.md
        readme = run_path / "RUN_README.md"
        try:
            with open(readme, "a", encoding="utf-8") as f:
                f.write(f"\n## BACKFILL FAILED\n- {datetime.now().isoformat()}: No source manifest found\n")
        except:
            pass
        return False

def main():
    parser = argparse.ArgumentParser(description="Backfill root geometry_manifest.json")
    parser.add_argument("run_dirs", nargs="*", help="Run directories to process")
    parser.add_argument("--all", action="store_true", help="Process all run_dirs in exports/runs")
    
    args = parser.parse_args()
    
    if args.all:
        # Find all run_dirs that might need backfill
        base = Path("exports/runs")
        if not base.exists():
            print("ERROR: exports/runs does not exist")
            sys.exit(1)
        
        run_dirs = []
        for lane in base.iterdir():
            if lane.is_dir():
                for run in lane.iterdir():
                    if run.is_dir() and not (run / "geometry_manifest.json").exists():
                        run_dirs.append(str(run))
        
        if not run_dirs:
            print("No run_dirs need backfill.")
            sys.exit(0)
    else:
        run_dirs = args.run_dirs
    
    if not run_dirs:
        parser.print_help()
        sys.exit(1)
    
    success = 0
    failed = 0
    
    for run_dir in run_dirs:
        print(f"\nProcessing: {run_dir}")
        if backfill_run_dir(run_dir):
            success += 1
        else:
            failed += 1
    
    print(f"\n=== Summary ===")
    print(f"Success: {success}")
    print(f"Failed: {failed}")
    
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
