import argparse
import json
import sys
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Generate fitting_facts_summary.json stub")
    parser.add_argument("--garment_out_dir", required=True, help="Directory containing garment outputs")
    parser.add_argument("--out", required=True, help="Path to output fitting_facts_summary.json")
    
    args = parser.parse_args()
    
    garment_dir = Path(args.garment_out_dir)
    out_path = Path(args.out)
    
    # 1. Load garment_proxy_meta.json to check flags
    meta_path = garment_dir / "garment_proxy_meta.json"
    if not meta_path.exists():
        print(f"Error: {meta_path} not found", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except Exception as e:
        print(f"Error reading {meta_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
    flags = meta.get("flags", {})
    
    # 2. Check Hard Gate Condition
    # early_exit: true if ANY of the following are true
    hard_gate_flags = [
        "invalid_face_flag",
        "negative_face_area_flag",
        "self_intersection_flag"
    ]
    
    early_exit = False
    early_exit_reason = ""
    
    for flag_name in hard_gate_flags:
        if flags.get(flag_name, False):
            early_exit = True
            early_exit_reason = f"garment_hard_gate_violation: {flag_name}"
            break
            
    # 3. Determine garment_input_path_used
    # Precedence: npz > glb > None (error?)
    # Based on tests: if npz exists, use "npz". Else if glb exists, use "glb_fallback".
    
    npz_path = garment_dir / "garment_proxy.npz"
    glb_path = garment_dir / "garment_proxy_mesh.glb"
    
    garment_input_path_used = "unknown"
    
    if npz_path.exists():
        garment_input_path_used = "npz"
    elif glb_path.exists():
        garment_input_path_used = "glb_fallback"
    else:
        # If neither exists, what should happen? Use "unknown" or error? 
        # For now, let's keep it robust as "unknown" but maybe print a warning.
        print(f"Warning: neither garment_proxy.npz nor garment_proxy_mesh.glb found in {garment_dir}", file=sys.stderr)

    # 4. Construct Output JSON
    output_data = {
        "early_exit": early_exit,
        "early_exit_reason": early_exit_reason,
        "garment_input_path_used": garment_input_path_used
    }
    
    # 5. Write Output
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
        print(f"Successfully generated {out_path}")
    except Exception as e:
        print(f"Error writing to {out_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
