# Smoke-2: Fitting Stub for Early Exit Validation

## Purpose
This stub (`tools/gen_fitting_facts_summary_stub.py`) simulates the behavior of the Fitting module when receiving a "Hard Gated" input from Garment. It is used to verify that the pipeline correctly handles early exits and records the necessary facts.

## Hard Gate Logic (OR Condition)
The stub triggers an `early_exit: true` if **ANY** of the following flags are `true` in `garment_proxy_meta.json`:
- `invalid_face_flag` (Primary check for Smoke-2)
- `negative_face_area_flag`
- `self_intersection_flag`

## Usage

### Command Line Interface
```bash
python tools/gen_fitting_facts_summary_stub.py \
  --garment_out_dir <path/to/garment/output> \
  --out <path/to/output/fitting_facts_summary.json>
```

### Arguments
- `--garment_out_dir`: Directory containing `garment_proxy_meta.json` and assets (`garment_proxy.npz` or `garment_proxy_mesh.glb`).
- `--out`: Full path where the `fitting_facts_summary.json` should be validated.

## Pass Criteria (Smoke-2 E2E)

When running against a Hard Gated Garment output (e.g. from `run_smoke2_garment.ps1`):

1. **Execution Success**: The stub script must exit with code **0** (normal operation).
2. **Output Content**: `fitting_facts_summary.json` must contain:
   - `early_exit`: **`true`**
   - `early_exit_reason`: Must contain the name of the triggered flag (e.g. `"garment_hard_gate_violation: invalid_face_flag"`).
   - `garment_input_path_used`: Must be `"npz"` or `"glb_fallback"` (depending on asset availability).

## Example JSON Output
```json
{
  "early_exit": true,
  "early_exit_reason": "garment_hard_gate_violation: invalid_face_flag",
  "garment_input_path_used": "glb_fallback"
}
```
