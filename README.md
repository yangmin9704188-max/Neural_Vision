# Neural_Vision

Numerical Input-Based Virtual Deployment Project.

## Structure
- **ssot/**: 정본 문서. contracts/ops: 계약·운영.
- **exports/**, **data/**: generated-only / gitignore. Do not edit by hand.
- **modules/body/**: Body 모듈 (ingest, VTM, runners).

## Entrypoints
```bash
# geo_v0_s1 facts runner
py -m modules.body.src.runners.run_geo_v0_s1_facts --manifest data/golden/s1_mesh_v0/s1_manifest_v0_round71.json --out_dir exports/runs/geo_v0_s1/run_<id>

# curated_v0 ingest
py -m modules.body.src.pipeline.ingest.build_curated_v0 --mapping data/column_map/sizekorea_v2.json --output data/derived/curated_v0/<RUN_ID>/curated_v0.parquet --format parquet
```

## References
- ops/HUB.md, ssot/, contracts/
