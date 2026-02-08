# Smoke-2: Garment Hard Gate Reproduction

## Purpose
To verify that the Garment module correctly handles "Hard Gate" scenarios (invalid meshes) by deterministic triggering of early exit, while still producing required artifacts for debugging and traceability.

## Execution

### Windows (PowerShell)
```powershell
./scripts/run_smoke2_garment.ps1
```

### Manual Execution
```bash
python tools/garment_generate_bundle.py \
  --mesh tests/fixtures/invalid_mesh.obj \
  --out_dir runs/smoke/smoke2/manual_test \
  --schema contracts/geometry_manifest.schema.json
```

## Expected Results

1. **Exit Code**: non-zero (typically 1)
   - Indicates "Hard Gate triggered" (Invalid Face).
2. **Artifacts Present**:
   - `runs/smoke/smoke2/.../garment_proxy_meta.json`
   - `runs/smoke/smoke2/.../geometry_manifest.json`
3. **Manifest Validation**: PASS
   - The produced manifest must be valid despite the hard gate.
4. **Determinism**:
   - Repeated runs with the same input mesh must produce identical `inputs_fingerprint` and `flags`.

## Troubleshooting

### "OUTPUTS_PRESENT: Missing"
- **Cause**: The tool crashed *before* writing files, or the Hard Gate logic exited too early.
- **Fix**: Check `garment_generate_bundle.py`. Artifact generation must happen *before* the Hard Gate check.

### "MANIFEST_VALIDATE: Failed"
- **Cause**: Schema mismatch or invalid JSON structure.
- **Fix**: Ensure `contracts/geometry_manifest.schema.json` matches the generated `geometry_manifest.v1`.

### "HARD_GATE: False (Exit 0)"
- **Cause**: The mesh was deemed valid, or the gate logic is broken.
- **Fix**: Check `invalid_mesh.obj` contains degenerate faces. Check `invalid_face_flag` in proxy meta.
