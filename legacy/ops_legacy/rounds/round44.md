> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 44

## Goal
(A) 관측 지표가 KPI_DIFF까지 표면화되게 wiring 고정 (Failure Reason Top5 Changes가 실제로 출력되도록).
(B) torso-only 값을 최소 1개라도 방출 (loop ordering 실패 시 2D convex hull perimeter fallback 추가).

## Changes
- **Observability wiring (A)**:
  - runner: torso_failure_reasons 집계 후 `facts_summary["summary"]["failure_reasons"]`에 `warnings_top5: [{"reason", "n"}]` 형태로 alias 기록 — postprocess `get_failure_reasons()`가 읽는 형식과 일치.
  - core: torso 실패 시에도 `debug_info["torso_components"]`를 metadata에 반드시 포함하도록 수정 (기존엔 성공 시에만 전달되어 runner가 수집 불가였음).
  - runner: metadata_v0가 `metadata["debug"]`에 넣는 것에 맞춰, aggregation/measure_all_keys에서 `debug_info`를 `metadata.get("debug_info") or metadata.get("debug")`로 읽도록 수정.
- **Torso hull fallback (B)**:
  - core_measurements_v0: loop ordering/perimeter 실패 시, 선택된 component의 2D convex hull 둘레로 torso_perimeter 계산하는 fallback 추가. 사용 시 `torso_diagnostics["TORSO_FALLBACK_HULL_USED"] = True` 기록.
  - runner: `torso_components`에서 `TORSO_FALLBACK_HULL_USED`를 케이스/키별 집계해 `facts_summary["torso_fallback_hull_used_count"]`, `torso_fallback_hull_used_by_key` 기록 (건수 > 0일 때만).

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round44_20260127_184841`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round44_20260127_184841/facts_summary.json`
- **KPI**: `verification/runs/facts/geo_v0_s1/round44_20260127_184841/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round44_20260127_184841/KPI_DIFF.md`
- **report**: (해당 라운드 리포트 경로)

## PR Link
[Round44 PR 링크는 Step 2에서 생성]

## Notes
- KPI_DIFF에서 "Failure Reason Top5 Changes"가 실제 데이터로 출력됨 (예: `failure_reasons:SINGLE_COMPONENT_ONLY | 5 | N/A | new in top5`).
- torso 키(NECK_CIRC_TORSO_M, BUST_CIRC_TORSO_M, UNDERBUST_CIRC_TORSO_M)에 값 방출 성공 (nan_count 0, 5케이스 모두 값 있음).
- TORSO_FALLBACK_HULL_USED: 본 Run에서는 0건 (hull fallback 미사용; ordering/기본 perimeter 경로로 값 산출).
- full 키(*_CIRC_M) 로직 변경 없음.
