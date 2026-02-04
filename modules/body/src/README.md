# Body src

## Purpose
- Body 모듈 소스: pipeline, measurements, runners, utils.

## Do / Don't
- Do: 절대 import (modules.body.src.*).
- Don't: 상위 modules 밖에서 직접 import 금지.

## Key files
- pipeline/ingest/: build_curated_v0, 정제 스크립트
- runners/: run_geo_v0_s1_facts, run_curated_v0_facts_round1
- measurements/vtm/: core_measurements_v0, circumference_v0

## How to run
- pipeline/ingest, runners/ README 참조

## Outputs
- N/A (실행은 runners/ingest에서)

## References
- [pipeline/ingest/README.md](pipeline/ingest/README.md), [runners/README.md](runners/README.md)
