#!/usr/bin/env python3
"""
Bundle OpenAPI spec by inlining all $ref references.

Usage:
    python scripts/bundle_openapi.py [--input openapi/neural-vision-api.v1.yaml] [--output openapi/dist/neural-vision-api.v1.bundle.yaml]

Requires: pyyaml
For full-featured bundling, use: npx @redocly/cli bundle
This script provides a lightweight alternative for CI without Node.js.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from copy import deepcopy

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def resolve_ref(ref: str, base_dir: Path) -> dict:
    """Resolve a $ref to a file path and load it."""
    if ref.startswith("#/"):
        # Internal ref — skip, handled by consumer
        return None

    # External file ref (may contain #/pointer)
    parts = ref.split("#", 1)
    file_path = base_dir / parts[0]

    if not file_path.exists():
        print(f"  WARNING: $ref target not found: {file_path}")
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        if file_path.suffix == ".json":
            data = json.load(f)
        elif file_path.suffix in (".yaml", ".yml"):
            if not HAS_YAML:
                print("ERROR: pyyaml required for YAML refs. pip install pyyaml")
                sys.exit(1)
            data = yaml.safe_load(f)
        else:
            print(f"  WARNING: unknown ref file type: {file_path}")
            return None

    # If there's a JSON pointer after #, resolve it
    if len(parts) > 1 and parts[1]:
        pointer = parts[1].lstrip("/").split("/")
        for key in pointer:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None

    return data


def inline_refs(obj, base_dir: Path, visited: set = None):
    """Recursively inline all external $ref in an object."""
    if visited is None:
        visited = set()

    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            if not ref.startswith("#/"):
                # External ref — resolve and inline
                ref_key = str(base_dir / ref)
                if ref_key in visited:
                    return obj  # Avoid infinite loop
                visited.add(ref_key)
                resolved = resolve_ref(ref, base_dir)
                if resolved is not None:
                    resolved = deepcopy(resolved)
                    return inline_refs(resolved, base_dir, visited)
            return obj
        else:
            return {k: inline_refs(v, base_dir, visited) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [inline_refs(item, base_dir, visited) for item in obj]
    else:
        return obj


def main():
    if not HAS_YAML:
        print("ERROR: pyyaml is required. Install with: pip install pyyaml")
        sys.exit(1)

    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Bundle OpenAPI spec")
    parser.add_argument("--input",
                        default=str(repo_root / "openapi" / "neural-vision-api.v1.yaml"))
    parser.add_argument("--output",
                        default=str(repo_root / "openapi" / "dist" / "neural-vision-api.v1.bundle.yaml"))
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}")
        sys.exit(1)

    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    base_dir = input_path.parent
    bundled = inline_refs(spec, base_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(bundled, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"Bundled OpenAPI written to: {output_path}")


if __name__ == "__main__":
    main()
