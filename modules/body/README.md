# Body

## Purpose
- Body 모듈: ingest(SizeKorea 정제), VTM 측정, geo/curated runners.

## Do / Don't
- Do: src/pipeline, src/measurements, src/runners 사용.
- Don't: 비 Body 로직 혼입 금지.

## Key files
- src/pipeline/ingest/build_curated_v0.py
- src/runners/run_geo_v0_s1_facts.py
- src/measurements/vtm/core_measurements_v0.py

## How to run
```bash
py -m modules.body.src.pipeline.ingest.build_curated_v0 --mapping data/column_map/sizekorea_v2.json --output <path> --format parquet
py -m modules.body.src.runners.run_geo_v0_s1_facts --manifest data/golden/s1_mesh_v0/s1_manifest_v0_round71.json --out_dir exports/runs/geo_v0_s1/<run_id>
```

## Outputs
- data/derived/curated_v0/<RUN_ID>/curated_v0.parquet
- exports/runs/geo_v0_s1/<run_id>/

## SMPL-X Path Contract
- Base model directory (fixed): `data/external/smplx`
- Expected files:
  - `data/external/smplx/SMPLX_MALE.pkl`
  - `data/external/smplx/SMPLX_FEMALE.pkl`
  - `data/external/smplx/SMPLX_NEUTRAL.pkl`
- `modules/body/src/utils/smart_mapper_v001.py` uses `ext="pkl"`.
- For any mapper/tuning run, set `model_path` to `data/external/smplx` explicitly.
- Tuned outputs path (local-only): `data/derived/body/smplx_tuned/<run_id>/`

## Execution Guardrails
- Do not treat `tools/fit_smplx_beta_v0.py` dummy provider output as final SMPL-X tuning completion.
- Completion state must be recorded via lifecycle events:
  - `IMPLEMENTED`
  - `VALIDATED` (with `reports/validation/...` reference)
  - `CLOSED` (with `contracts/closure_specs/...` reference)

## References
- contracts/, ssot/, [ingest/README.md](src/pipeline/ingest/README.md)
