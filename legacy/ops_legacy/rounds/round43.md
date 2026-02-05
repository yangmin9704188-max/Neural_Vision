> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 43

## Goal
torso-only NaN=100%의 원인 유형을 분해(관측가능성 강화)하고, 최소 1개 케이스에서 torso-only 값 방출까지 도달하는 것.
- torso-only 파이프라인을 단계별로 계측해 facts_summary에 기록
- 루프/폴리곤 생성 단계를 최소 침습으로 보강

## Changes
- `core/measurements/core_measurements_v0.py` 수정:
  - `_find_connected_components_2d`: Round43 diagnostics 추가 (n_intersection_points, n_segments, n_components, failure_reason)
  - `_order_component_points_for_loop`: Round43 컴포넌트 점들을 closed loop로 정렬하는 함수 추가 (polar angle sorting)
  - `_compute_component_stats`: Round43 try_ordering 파라미터 추가하여 closed loop 생성 시도
  - `_compute_circumference_at_height`: Round43 diagnostics 수집 및 torso_perimeter 계산 시 ordering 시도

- `verification/runners/run_geo_v0_s1_facts.py` 수정:
  - Round43: torso-only 실패 이유 코드 집계 (per-key 및 topK)
  - Round43: torso diagnostics summary 집계 (n_intersection_points, n_segments, n_components, component area/perimeter stats)

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round43_20260127_183519`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round43_20260127_183519/facts_summary.json`
- **report**: `reports/validation/lanes/geo_v0_s1/round43_20260127_183519_facts.md`
- **KPI**: `verification/runs/facts/geo_v0_s1/round43_20260127_183519/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round43_20260127_183519/KPI_DIFF.md`

## PR Link
[PR 링크는 추후 추가]

## Notes
- torso-only 파이프라인 단계별 계측 추가: n_intersection_points, n_segments, n_components, failure_reason
- component area/perimeter 요약 통계 추가 (p50/p95, top3)
- 실패 이유 코드 표준화: TORSO_FAIL_NO_INTERSECTION, EXTRACT_EMPTY, SINGLE_COMPONENT_ONLY, NOT_CLOSED_LOOP, NUMERIC_ERROR 등
- 루프/폴리곤 생성 단계 보강: polar angle sorting으로 closed loop 생성 시도
- 기존 *_CIRC_M (full) 로직에는 영향 없음
- 현재 실행 결과: 모든 torso 키가 NaN (단일 컴포넌트만 존재하거나 분리 실패) - 관측가능성 정보는 facts_summary에 기록됨
