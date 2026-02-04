# Ingest

## Purpose
- SizeKorea raw → curated_v0. 매핑, 단위 변환, 표준키 추출.

## Do / Don't
- Do: mapping(sizekorea_v2.json) 사용. data/external 입력.
- Don't: 매핑 하드코딩 금지.

## Key files
- build_curated_v0.py: 메인 엔트리
- ingestion_units.py: 단위 canonicalization

## How to run
```bash
py -m modules.body.src.pipeline.ingest.build_curated_v0 --mapping data/column_map/sizekorea_v2.json --output data/derived/curated_v0/<RUN_ID>/curated_v0.parquet --format parquet
```

## Outputs
- data/derived/curated_v0/<RUN_ID>/curated_v0.parquet

## References
- data/external/, contracts/, modules/body/
