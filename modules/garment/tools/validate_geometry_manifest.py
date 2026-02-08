import argparse
import json
import sys
import os
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None

def main():
    parser = argparse.ArgumentParser(description="Validate geometry_manifest.json against schema")
    parser.add_argument("--manifest", required=True, help="Path to geometry_manifest.json")
    parser.add_argument("--schema", default="geometry_manifest.schema.json", help="Path to geometry_manifest.schema.json")
    
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    schema_path = Path(args.schema)

    if not manifest_path.exists():
        print(f"Error: Manifest file not found at {manifest_path}", file=sys.stderr)
        sys.exit(1)

    if not schema_path.exists():
        # Fallback: try to find schema if not at default/provided path?
        # Maybe check relative to script?
        # But for now, just error if not found.
        print(f"Error: Schema file not found at {schema_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in manifest: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in schema: {e}", file=sys.stderr)
        sys.exit(1)

    if jsonschema:
        try:
            jsonschema.validate(instance=manifest, schema=schema)
            print("Validation successful.")
            sys.exit(0)
        except jsonschema.exceptions.ValidationError as e:
            print(f"Validation Failed: {e.message}", file=sys.stderr)
            print(f"Path: {list(e.path)}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Validation Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Fallback manual validation (minimal required fields check for Step 1-min)
        print("Warning: jsonschema module not found. Performing minimal manual validation.", file=sys.stderr)
        
        required_fields = schema.get("required", [])
        missing = [field for field in required_fields if field not in manifest]
        
        if missing:
            print(f"Validation Failed: Missing required fields: {missing}", file=sys.stderr)
            sys.exit(1)
            
        # Check artifacts required properties if present
        if "artifacts" in manifest:
             # This is a bit recursive, simplified for Step 1-min
            artifacts_required = schema.get("properties", {}).get("artifacts", {}).get("required", [])
            arts = manifest["artifacts"]
            missing_arts = [field for field in artifacts_required if field not in arts]
            if missing_arts:
                print(f"Validation Failed: artifacts missing required fields: {missing_arts}", file=sys.stderr)
                sys.exit(1)

        print("Minimal validation passed (jsonschema not installed).")
        sys.exit(0)

if __name__ == "__main__":
    main()
