# Tools

## Purpose
- 공용 실행 스크립트 (KPI, postprocess, summarize 등).

## Do / Don't
- Do: 비즈니스 로직은 modules/에 둠.
- Don't: 데이터/산출물 직접 생성 금지(modules가 출력).

## Key files
- kpi_diff.py: KPI 비교
- postprocess_round.py: 라운드 후처리
- summarize_facts_kpi.py: facts/KPI 요약

## How to run
- (각 스크립트 --help 참조)

## Outputs
- N/A

## References
- modules/body/, ops/HUB.md
