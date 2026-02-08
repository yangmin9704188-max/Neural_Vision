import argparse
import json
import sys
import math
from pathlib import Path

# Constants
EPS_FACE_AREA_DEFAULT = 1e-12

def parse_obj(file_path):
    vertices = []
    faces = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.startswith('v '):
                    parts = line.strip().split()
                    vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
                elif line.startswith('f '):
                    parts = line.strip().split()
                    # OBJ indices are 1-based, handle potential v/vt/vn format
                    face_idxs = [int(p.split('/')[0]) - 1 for p in parts[1:]]
                    faces.append(face_idxs)
    except Exception as e:
        print(f"Error parsing OBJ {file_path}: {e}", file=sys.stderr)
        sys.exit(1)
    return vertices, faces

def calculate_cross_product_norm(v1, v2):
    # Cross product of two 3D vectors
    cx = v1[1] * v2[2] - v1[2] * v2[1]
    cy = v1[2] * v2[0] - v1[0] * v2[2]
    cz = v1[0] * v2[1] - v1[1] * v2[0]
    return math.sqrt(cx*cx + cy*cy + cz*cz)

def analyze_mesh(vertices, faces, eps_area):
    invalid_face_count = 0
    min_face_area = float('inf')
    
    for face in faces:
        if len(face) < 3:
            # Degenerate polygon (point or line)
            invalid_face_count += 1
            min_face_area = min(min_face_area, 0.0)
            continue
            
        # Triangle decomposition for area (polygons > 3 vertices)
        # Simple fan triangulation for area approximation check
        face_area = 0.0
        v0 = vertices[face[0]]
        
        # Check for degenerate indices (same vertex used multiple times)
        if len(set(face)) != len(face):
            invalid_face_count += 1
            min_face_area = min(min_face_area, 0.0)
            continue

        for i in range(1, len(face) - 1):
            v1 = vertices[face[i]]
            v2 = vertices[face[i+1]]
            
            vec1 = [v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2]]
            vec2 = [v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2]]
            
            try:
                tri_area = calculate_cross_product_norm(vec1, vec2) / 2.0
                if math.isnan(tri_area) or math.isinf(tri_area):
                    face_area = float('nan')
                    break
                face_area += tri_area
            except Exception:
                face_area = float('nan')
                break
        
        if math.isnan(face_area) or math.isinf(face_area) or face_area <= eps_area:
            invalid_face_count += 1
            # Treat NaN/Inf as effectively 0 or negative for min comparison purposes? 
            # Or just ignore for min?
            # Requirement: "min_face_area 기록"
            # If NaN, we probably shouldn't set min_area to NaN unless all are NaN.
            # Let's verify standard behavior. If NaN is found, invalid_face_count++.
            # If area is 0, min_area = 0.
            if not math.isnan(face_area):
                min_face_area = min(min_face_area, face_area)
        else:
            min_face_area = min(min_face_area, face_area)

    # If no faces, min area is 0? Or Inf?
    if not faces:
        min_face_area = 0.0
    elif min_face_area == float('inf'):
        # If all faces were invalid and not valid numbers?
        min_face_area = 0.0 

    return invalid_face_count, min_face_area

def main():
    parser = argparse.ArgumentParser(description="Generate garment_proxy_meta.json from input mesh")
    parser.add_argument("--mesh", required=True, help="Path to input OBJ mesh")
    parser.add_argument("--out", required=True, help="Path to output JSON")
    parser.add_argument("--eps_face_area", type=float, default=EPS_FACE_AREA_DEFAULT, help="Epsilon for minimal face area")
    
    args = parser.parse_args()
    
    mesh_path = Path(args.mesh)
    if not mesh_path.exists():
        print(f"Error: Mesh file not found: {args.mesh}", file=sys.stderr)
        sys.exit(1)

    # 1. Parse Mesh
    vertices, faces = parse_obj(str(mesh_path))
    
    # 2. Analyze Mesh
    invalid_face_count, min_face_area = analyze_mesh(vertices, faces, args.eps_face_area)
    
    # 3. Construct Meta Data
    invalid_face_flag = invalid_face_count > 0
    
    data = {
        "schema_version": "garment_proxy_meta.v1",
        "source_mesh_path": str(mesh_path).replace("\\", "/"), # Normalize path separators
        "mesh_stats": {
            "num_vertices": len(vertices),
            "num_faces": len(faces),
            "invalid_face_count": invalid_face_count,
            "min_face_area": min_face_area
        },
        "flags": {
            "invalid_face_flag": invalid_face_flag,
            "negative_face_area_flag": False, # Step 2 Policy: Always false
            "self_intersection_flag": False   # Step 2 Policy: Placeholder
        },
        "metrics": {
            "eps_face_area": args.eps_face_area,
            "self_intersection_count": -1     # Not computed
        },
        "warnings": []
    }
    
    # 4. Add warnings per policy
    data["warnings"].append("NEGATIVE_FACE_AREA_NOT_COMPUTED_STEP2")
    data["warnings"].append("SELF_INTERSECTION_NOT_AVAILABLE")
    
    if invalid_face_flag:
        data["warnings"].append(f"Hard Gate Triggered: {invalid_face_count} invalid faces detected (<= {args.eps_face_area})")

    # 5. Write Deterministic JSON
    try:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, sort_keys=True)
        print(f"Successfully generated {out_path}")
    except Exception as e:
        print(f"Error writing output to {args.out}: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    main()
