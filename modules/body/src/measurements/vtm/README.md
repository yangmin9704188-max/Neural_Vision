# VTM

## Purpose
- Virtual Tape Measure: 메쉬 기반 측정 구현(둘레, 어깨, 버스트 등).

## Do / Don't
- Do: metadata_v0, contracts/measurement 준수.
- Don't: 표준키 외 확장 시 계약 갱신.

## Key files
- core_measurements_v0.py: 코어 측정
- circumference_v0.py, bust_underbust_v0.py
- shoulder_width_v12.py, metadata_v0.py

## How to run
- run_geo_v0_s1_facts 등 runners가 import.

## Outputs
- N/A

## References
- contracts/measurement/, modules/body/src/runners/
