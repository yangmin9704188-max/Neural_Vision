import argparse
import json
import hashlib
import sys
import os
from datetime import datetime
from pathlib import Path

def calculate_fingerprint(module, schema_version, contract_version, geometry_impl_version, input_files):
    """
    Calculates a deterministic fingerprint based on inputs.
    Content-based hashing for input files.
    """
    # 1. Collect inputs in a stable structure
    data = {
        "module": module,
        "schema_version": schema_version,
        "contract_version": contract_version,
        "geometry_impl_version": geometry_impl_version,
        "input_files_hashes": {}
    }

    # 2. Hash input files content
    if input_files:
        # Sort files to ensure deterministic order if list order varies (though caller should probably sort too)
        # We rely on the provided order or sort here? 
        # Requirement: "inputs_fingerprint는 아래 요소만으로 결정론적으로 계산할 것(순서 고정/정규화)"
        # Let's sort by path to be safe and consistent.
        sorted_inputs = sorted(input_files)
        
        for file_path_str in sorted_inputs:
            path = Path(file_path_str)
            try:
                content = path.read_bytes()
                # Use SHA256 for file content
                file_hash = hashlib.sha256(content).hexdigest()
                # Key validation: Use just the filename or partial path? 
                # Prompt says: "경로 문자열만 해시 금지", "내용 해시를 포함할 것"
                # We store the hash mapped to the filename for the canonical dict?
                # Or just a list of hashes?
                # To be robust against path changes (e.g. running from diff dir but same file content),
                # maybe we should just use the content hashes. 
                # But if we change input file *name* it might matter?
                # Let's map "filename -> hash" to be descriptive in the canonical dict 
                # but maybe just use list of hashes for strict content-only?
                # Requirement: "E) 입력 파일이 주어지면(옵션): garment 입력 파일들의 '내용 해시'를 포함할 것"
                # Let's use the file name as key to distinguish distinct inputs.
                data["input_files_hashes"][path.name] = file_hash
            except Exception as e:
                print(f"Error reading input file {file_path_str}: {e}", file=sys.stderr)
                sys.exit(1)

    # 3. Create canonical JSON string
    # sort_keys=True is CRITICAL for determinism
    canonical_json = json.dumps(data, sort_keys=True, separators=(',', ':'))
    
    # 4. Generate final fingerprint
    fingerprint = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    return fingerprint

def main():
    parser = argparse.ArgumentParser(description="Generate geometry_manifest.json for Garment module")
    parser.add_argument("--out", required=True, help="Output path for geometry_manifest.json")
    parser.add_argument("--mesh_path", required=True, help="Path to the mesh file")
    parser.add_argument("--contract_version", default="garment.contract.v0", help="Contract version")
    parser.add_argument("--geometry_impl_version", default="garment_manifest_gen_v1", help="Geometry implementation version")
    parser.add_argument("--schema", default="geometry_manifest.schema.json", help="Path to geometry_manifest.schema.json for validation")
    parser.add_argument("--input_file", action="append", help="Input files to include in fingerprint calculation")
    parser.add_argument("--aux_path", action="append", help="Auxiliary file paths to include in artifacts (not fingerprint)")
    parser.add_argument("--warnings_created_at", action="store_true", help="Add created_at timestamp to warnings")
    
    args = parser.parse_args()

    # Constants
    MODULE = "garment"
    SCHEMA_VERSION = "geometry_manifest.v1"

    # Calculate Fingerprint
    fingerprint = calculate_fingerprint(
        MODULE,
        SCHEMA_VERSION,
        args.contract_version,
        args.geometry_impl_version,
        args.input_file
    )

    # Build Manifest
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "module": MODULE,
        "contract_version": args.contract_version,
        "geometry_impl_version": args.geometry_impl_version,
        "inputs_fingerprint": fingerprint,
        "artifacts": {
            "mesh_path": args.mesh_path
            # Optional fields like measurements_path, npz_path, aux_paths can be added later if inputs provided
        },
        "measurements_summary": {} # Empty for Step 1-min
    }

    if args.aux_path:
        manifest["artifacts"]["aux_paths"] = args.aux_path

    # Add warnings if requested
    if args.warnings_created_at:
        timestamp = datetime.now().isoformat()
        manifest["warnings"] = [f"CREATED_AT:{timestamp}"]

    # Write Manifest
    out_path = Path(args.out)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"Error writing manifest to {out_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Validate Manifest
    # internal call to validate_geometry_manifest logic or script
    # For loose coupling, let's call the script if possible, or just duplicate simple logic?
    # Requirement: "즉시 json-schema validate까지 실행(내부적으로 validate 호출)"
    # We will try to import the validator tool or subprocess it. 
    # Since they are likely in the same dir, let's try subprocess to be safe with path resolution?
    # Or better, import if we structure it right. 
    # Let's try subprocess to keep it simple and independent.
    
    script_dir = Path(__file__).parent
    validator_script = script_dir / "validate_geometry_manifest.py"
    
    # We assume the schema is available. 
    # But where is the schema? The user provided input said `geometry_manifest.schema.json` is input. 
    # But we don't have a path arg for schema in `garment_manifest.py`. 
    # The validator tool has `--schema`.
    # `garment_manifest.py` spec didn't ask for `--schema` arg.
    # We might need to guess the schema location or expect it in a default location.
    # The inputs listed `geometry_manifest.schema.json` as provided file.
    # Let's assume it's in the same directory or CWD? 
    # Actually, command line for validator has a default. 
    # Let's see if we can find it.
    
    # We will look for schema in standard locations or just skip if not found (but exit 1 if valid fail).
    # Since we can't reliably know where the schema is without an arg...
    # Wait, the PROMPT says "INPUTS (제공 파일) - geometry_manifest.schema.json".
    # And "validate_geometry_manifest.py" has a default.
    # We will try to run validation.
    
    import subprocess
    
    # We'll try to find the schema. 
    # Common convention: contracts folder?
    # Let's just run validate script with its defaults, which hopefully finds it.
    # If the user didn't provide schema path to the tool, maybe we assume it's in a known relative path?
    # The validator default is "geometry_manifest.schema.json" (current dir).
    
    cmd = [sys.executable, str(validator_script), "--manifest", str(out_path), "--schema", args.schema]
    
    # If we know where the schema is (e.g. from prompt context: `fitting_lab/contracts/geometry_manifest.schema.json`)
    # But this tool is "independent". 
    # Let's stick to the Spec: "즉시 json-schema validate까지 실행".
    # We'll run the command.
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Validation failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        else:
            print("Manifest generated and validated successfully.")
    except Exception as e:
        print(f"Validation execution error: {e}", file=sys.stderr)
        sys.exit(1)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
