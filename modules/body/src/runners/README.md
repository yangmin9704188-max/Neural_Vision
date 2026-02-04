# Runners

## Purpose
- 실행 엔트리포인트: geo_v0_s1, curated_v0 facts.

## Do / Don't
- Do: --manifest, --out_dir 등 CLI 인자 사용.
- Don't: 하드코딩 경로 최소화.

## Key files
- run_geo_v0_s1_facts.py: U1 대표 runner
- run_geo_v0_facts_round1.py
- run_curated_v0_facts_round1.py

## How to run
```bash
py -m modules.body.src.runners.run_geo_v0_s1_facts --manifest data/golden/s1_mesh_v0/s1_manifest_v0_round71.json --out_dir exports/runs/geo_v0_s1/<run_id>
```

## Outputs
- exports/runs/geo_v0_s1/<run_id>/facts_summary.json, artifacts/

## References
- data/golden/, modules/body/src/measurements/vtm/
