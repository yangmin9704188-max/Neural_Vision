# Garment M0 Runbook v1

## Purpose
- Generate a minimal Garment output for U1 validation without upstream Body/Fitting outputs.

## Generate M0 Output
```powershell
py modules/garment/tools/generate_m0_fixture.py --run-dir .tmp/garment_m0_u1 --mode hard-gate
```

Optional normal mode with mesh:
```powershell
py modules/garment/tools/generate_m0_fixture.py --run-dir .tmp/garment_m0_u1_normal --mode normal
```

## Validate U1
```powershell
py tools/validate/validate_u1_garment.py --run-dir .tmp/garment_m0_u1
```

## Expected WARN Patterns
- `meta:invalid_face_flag` is `true` in hard-gate mode.
- `hard_gate` warning is expected in hard-gate mode.
- `garment_proxy_mesh.glb` may be missing in hard-gate mode (optional by rule).

## Notes
- All artifact paths in generated `geometry_manifest.json` are repo-relative file names (no absolute paths).
- `generate_m0_fixture.py` is deterministic for the same mode/mesh option.
- For M1 publish logging, append an explicit progress event:
```powershell
py tools/ops/append_progress_event.py --lab-root modules/garment --module garment --step-id G10_M1_PUBLISH --event note --status OK --m-level M1 --note "Garment U1-valid output published at M1"
```
