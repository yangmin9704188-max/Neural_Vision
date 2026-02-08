# Garment Module Walkthrough

## Step 2: Proxy Meta & Hard Gate

### Invalid Face Definition
A face is considered **invalid** if:
- It is a degenerate polygon (fewer than 3 unique vertices).
- Its area calculation results in `NaN` or `Inf`.
- Its area is less than or equal to `eps_face_area` (default: `1e-12`).

### Flags Policy
- **`invalid_face_flag`**: True if `invalid_face_count > 0`. Triggers Hard Gate.
- **`negative_face_area_flag`**: Currently **always False**. Real negative area calculation is deferred to future steps. A warning `NEGATIVE_FACE_AREA_NOT_COMPUTED_STEP2` is added to meta.

### Hard Gate Behavior
If a mesh triggers a Hard Gate (e.g., has invalid faces):
1. **Artifacts are still generated**:
   - `garment_proxy_meta.json` (containing flags and stats)
   - `geometry_manifest.json` (containing inputs fingerprint)
2. **Exit Code**:
   - The bundle tool (`garment_generate_bundle.py`) exits with code **1**.
   - This signals the failure to the pipeline while preserving evidence.
   - `geometry_manifest.json` includes `garment_proxy_meta.json` in `artifacts.aux_paths` for traceability.

### Reproducibility (Smoke-2)
The `scripts/run_smoke2_garment.ps1` script verifies:
- Hard Gate is triggered for known invalid meshes.
- Exit code is non-zero.
- Output files are present and valid.
- Execution is deterministic (same input = same fingerprint).
