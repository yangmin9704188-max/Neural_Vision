import argparse
import json
import sys
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Generate fitting_facts_summary.json (Stub) based on Garment output")
    parser.add_argument("--garment_out_dir", required=True, help="Directory containing Garment outputs (proxy meta)")
    parser.add_argument("--out", required=True, help="Output path for fitting_facts_summary.json")
    
    args = parser.parse_args()
    
    garment_dir = Path(args.garment_out_dir)
    meta_path = garment_dir / "garment_proxy_meta.json"
    
    if not meta_path.exists():
        print(f"Error: {meta_path} not found.", file=sys.stderr)
        # Requirement: Exit 1 if metadata missing
        sys.exit(1)
        
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except Exception as e:
        print(f"Error loading metadata: {e}", file=sys.stderr)
        sys.exit(1)

    # 1. Check Flags for Hard Gate
    # Support both top-level flags and nested "flags" dict
    flags = meta.get("flags", meta)
    
    negative_face = flags.get("negative_face_area_flag", False)
    self_intersect = flags.get("self_intersection_flag", False)
    # Also check invalid_face_flag since that's the primary Hard Gate in Step 2
    invalid_face = flags.get("invalid_face_flag", False)
    
    triggered_flags = []
    if invalid_face: triggered_flags.append("invalid_face_flag")
    if negative_face: triggered_flags.append("negative_face_area_flag")
    if self_intersect: triggered_flags.append("self_intersection_flag")
    
    is_hard_gate = len(triggered_flags) > 0
    
    # 2. Determine Input Path Used
    npz_path = garment_dir / "garment_proxy.npz"
    glb_path = garment_dir / "garment_proxy_mesh.glb"
    
    if npz_path.exists():
        input_used = "npz"
    elif glb_path.exists():
        input_used = "glb_fallback"
    else:
        input_used = "glb_fallback" # Default fallback per requirement
        
    # 3. Construct Output
    summary = {
        "early_exit": is_hard_gate,
        "early_exit_reason": "",
        "garment_input_path_used": input_used
    }
    
    if is_hard_gate:
        summary["early_exit_reason"] = f"garment_hard_gate_violation: {','.join(triggered_flags)}"
        
    # 4. Write Output
    out_path = Path(args.out)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        print(f"Generated stub summary at {out_path}")
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Exit 0 even if early_exit is True (logic success)
    sys.exit(0)

if __name__ == "__main__":
    main()
