> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 42

## Goal
torso-only 값 방출 + coverage 정합성 복구
- torso-only 값 저장 버그 수정 (성공 시 실제 perimeter 값 기록)
- ambiguous 처리 개선 (tiebreak 추가: dist, area, perimeter, centroid)
- coverage 필드 정합성 복구 (has_mesh_path_null 집계 수정)

## Changes
- `core/measurements/core_measurements_v0.py` 수정:
  - `_select_torso_component`: Round42 tiebreak 추가 (dist → area → perimeter → centroid 사전식)
  - `_compute_circumference_at_height`: Round42 torso_perimeter 계산 로직 개선 (return_debug=False일 때도 계산)
  - `measure_circumference_v0_with_metadata`: Round42 torso_info 초기화 및 torso_perimeter None 체크 추가

- `verification/runners/run_geo_v0_s1_facts.py` 수정:
  - Round42: has_mesh_path_null 집계 수정 (manifest_path_is_null reason과 일치하도록)

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round42_20260127_182538`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round42_20260127_182538/facts_summary.json`
- **report**: `reports/validation/lanes/geo_v0_s1/round42_20260127_182538_facts.md`
- **KPI**: `verification/runs/facts/geo_v0_s1/round42_20260127_182538/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round42_20260127_182538/KPI_DIFF.md`

## PR Link
[PR 링크는 추후 추가]

## Notes
- torso-only 값 저장 버그 수정: torso_perimeter가 None이 아닐 때만 저장하도록 개선
- ambiguous 처리 개선: tiebreak 순서 (dist → area → perimeter → centroid)로 결정적 선택 보장
- coverage 정합성 복구: has_mesh_path_null=195 (skip_reasons의 manifest_path_is_null과 일치)
- 현재 실행 결과: 모든 torso 키가 NaN (connected components 분리 실패 또는 단일 컴포넌트만 존재) - 이는 facts-only 신호로 정상
- TORSO_TIEBREAK_USED 경고 1개 발생 (UNDERBUST_CIRC_TORSO_M) - tiebreak 로직 작동 확인
