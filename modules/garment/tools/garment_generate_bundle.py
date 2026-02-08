import argparse
import sys
import subprocess
import json
from pathlib import Path

def run_command(cmd, desc):
    print(f"[{desc}] Running: {' '.join(cmd)}")
    try:
        # We allow non-zero exit for some sub-commands if we want to handle it manually,
        # but here we expect tools to run successfully (generate their part).
        # If a tool fails (crashes), we should probably fail the bundle entirely.
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"Error during {desc}: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Generate Garment Bundle (Proxy Meta + Manifest) with Hard Gate")
    parser.add_argument("--mesh", required=True, help="Path to input OBJ mesh")
    parser.add_argument("--out_dir", required=True, help="Output directory")
    parser.add_argument("--schema", default="geometry_manifest.schema.json", help="Path to schema for validation")
    parser.add_argument("--contract_version", default="garment.contract.v0", help="Contract version")
    parser.add_argument("--geometry_impl_version", default="garment_manifest_gen_v1", help="Geometry implementation version")
    
    args = parser.parse_args()
    
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    mesh_path = Path(args.mesh)
    meta_out = out_dir / "garment_proxy_meta.json"
    manifest_out = out_dir / "geometry_manifest.json"
    
    # 1. Generate Proxy Meta
    script_dir = Path(__file__).parent
    proxy_meta_script = script_dir / "garment_proxy_meta.py"
    
    cmd_meta = [
        sys.executable, str(proxy_meta_script),
        "--mesh", str(mesh_path),
        "--out", str(meta_out)
    ]
    run_command(cmd_meta, "Proxy Meta Generation")
    
    # 2. Generate Geometry Manifest
    # Note: garment_manifest.py handles validation internally if schema is found?
    # We pass the schema arg if the tool accepts it, but Step 1 `garment_manifest.py` logic
    # uses internal lookup or assumes defaults for validation.
    # We should let `garment_manifest.py` do its job.
    manifest_script = script_dir / "garment_manifest.py"
    
    cmd_manifest = [
        sys.executable, str(manifest_script),
        "--out", str(manifest_out),
        "--mesh_path", str(mesh_path), # Using absolute path or as provided
        "--contract_version", args.contract_version,
        "--geometry_impl_version", args.geometry_impl_version,
        "--contract_version", args.contract_version,
        "--geometry_impl_version", args.geometry_impl_version,
        "--schema", args.schema,
        "--aux_path", "garment_proxy_meta.json" # Relative path in output bundle
    ]
    
    # Pass proxy meta as input file to fingerprint? 
    # Prompt: "(선택) artifacts.aux_paths에 'garment_proxy_meta.json' 경로를 넣을 수 있으면 넣어라"
    # But `garment_manifest.py` calculates fingerprint from `--input_file`.
    # It might be good to include meta in fingerprint if it affects the bundle identity.
    # However, meta is *derived* from mesh. Mesh is already detecting changes.
    # We won't add it as input_file to avoid circular dependency (manifest generation -> meta generation?)
    # Meta is already generated.
    # Let's add it as input_file to ensure fingerprint covers metadata config? 
    # No, prompt says "Inputs (제공 파일)". Meta is an output.
    # We won't add it to `--input_file`.
    
    run_command(cmd_manifest, "Manifest Generation")
    
    # 3. Check Hard Gate
    # Read generated proxy meta to check flags
    try:
        with open(meta_out, 'r') as f:
            meta_data = json.load(f)
            
        flags = meta_data.get("flags", {})
        invalid_face_flag = flags.get("invalid_face_flag", False)
        # self_intersection_flag = flags.get("self_intersection_flag", False) # Not implemented efficiently yet
        
        if invalid_face_flag:
            print("![HARD GATE] Invalid faces detected. Bundle generation incomplete (logically), but artifacts preserved.")
            print(f"Check {meta_out} for details.")
            sys.exit(1) # Hard Gate Exit
            
        print("Bundle generation successful. Gate passed.")
        sys.exit(0)
        
    except Exception as e:
        print(f"Error checking Hard Gate status: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
