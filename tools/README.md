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
- generate_384_centroids_v0.py: Step2 384 centroid 생성 (deterministic, atomic). 성공 후 ops 로깅: `--log-progress` 또는 tools/ops/append_progress_event.py에 out_dir·sha256 전달.
- fit_smplx_beta_v0.py: Step3 beta fit v0 — BUST/WAIST/HIP 목표에 맞춘 prototype별 beta 최적화. mesh_provider=dummy (SMPL-X 미연결 시). summary.json, KPI.md, KPI_DIFF.md, per-prototype fit_result.json (atomic).

## How to run
- (각 스크립트 --help 참조)

## Outputs
- N/A

## References
- modules/body/, ops/HUB.md
