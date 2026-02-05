> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 41

## Goal
torso-only 둘레를 기하학적으로 도입하고 facts-only로 비교 신호를 남기는 것.
- 슬라이스 단면을 connected components(다중 루프)로 분리
- 각 컴포넌트의 area, perimeter, centroid, dist_to_body_center 기록
- torso-only 컴포넌트 선택 규칙 구현 (dist_to_body_center 최소 우선, tie-breaker: area 최대)
- *_CIRC_TORSO_M 키 추가 및 full vs torso-only delta 통계 기록

## Changes
- `core/measurements/core_measurements_v0.py` 수정:
  - `_find_connected_components_2d`: 슬라이스 단면을 connected components로 분리하는 함수 추가
  - `_compute_component_stats`: 각 컴포넌트의 area, perimeter, centroid, dist_to_body_center 계산 함수 추가
  - `_select_torso_component`: torso-only 컴포넌트 선택 규칙 구현 (dist_to_body_center 최소, tie-breaker: area 최대)
  - `_compute_circumference_at_height`: `return_torso_components` 파라미터 추가하여 torso-only 분석 활성화
  - `measure_circumference_v0_with_metadata`: torso keys에 대해 torso-only 분석 수행 및 debug_info에 torso_components 정보 추가

- `verification/runners/run_geo_v0_s1_facts.py` 수정:
  - `measure_all_keys`: torso keys에 대해 *_CIRC_TORSO_M 키 생성 (NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M, WAIST_CIRC_TORSO_M, HIP_CIRC_TORSO_M)
  - facts_summary에 `torso_delta_stats` 추가: full vs torso-only delta 통계 (p50/p90/p95 등)

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round41_20260127_180737`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round41_20260127_180737/facts_summary.json`
- **report**: `reports/validation/lanes/geo_v0_s1/round41_20260127_180737_facts.md`
- **KPI**: `verification/runs/facts/geo_v0_s1/round41_20260127_180737/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round41_20260127_180737/KPI_DIFF.md`

## PR Link
[PR 링크는 추후 추가]

## Notes
- 기존 표준키(*_CIRC_M)는 기존(full)로 유지
- 추가 실험 키: *_CIRC_TORSO_M를 새로 기록
- torso-only 컴포넌트 선택 실패/애매한 경우 NaN + warning으로 기록
- full vs torso-only delta 통계는 p50/p90/p95 등으로 기록
- connected components 분리는 거리 기반 connectivity (threshold=0.01m) 사용
- topology/geometry 기반으로만 처리 (클램프/임계치로 KPI 맞추기 금지)
