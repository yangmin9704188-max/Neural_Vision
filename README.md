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

## References
- contracts/, ssot/, [ingest/README.md](src/pipeline/ingest/README.md)
