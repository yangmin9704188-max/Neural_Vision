# G10_M1_PUBLISH Validation Report

- module: garment
- step_id: G10_M1_PUBLISH
- m_level: M1
- validation_result: PASS
- validation_command: `py tools/validate/validate_u1_garment.py --run-dir ../NV_shared_data/shared_m1/garment/20260209_103620`

## Summary
- M1 publish signal points to shared run-dir and validator passes on that run.
- Signal uses relative `run_dir_rel` format and `schema_version: m1_signal.v1`.

## Evidence
- `ops/signals/m1/garment/LATEST.json`
- `../NV_shared_data/shared_m1/garment/20260209_103620/geometry_manifest.json`
- `../NV_shared_data/shared_m1/garment/20260209_103620/garment_proxy_meta.json`
- `contracts/closure_specs/garment/G10_M1_PUBLISH.closure_spec.md`
