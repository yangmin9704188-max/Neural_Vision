> ⚠️ STATUS: LEGACY NAMING
> New rounds use folder-split format: docs/ops/rounds/<lane_slug>/<milestone_id>/round_<NN>.md
> This file preserved for history.
---

# Round 40

## Goal
완전 freeze 직전 마지막 문서 정리: facts-only 강화 작업
- Coverage 사실을 더 명시적으로 기록 (has_mesh_path_true/null, skip_reasons 집계)
- SCALE_ASSUMED_MM_TO_M 경고 상세화 (scale_warnings_detailed Top-K 20)
- Round41 대비 관측가능성 지표 추가 (best-effort, per-case debug)

## Changes
- `verification/runners/run_geo_v0_s1_facts.py` 수정:
  - Coverage 사실 기록 강화: `has_mesh_path_true`, `has_mesh_path_null`, `skip_reasons` 집계를 top-level로 추가
  - SCALE_ASSUMED_MM_TO_M 경고 상세화: `scale_warnings_detailed` (Top-K 20) 형태로 `{case_id, max_abs, trigger_rule, source_path}` 추가
  - Round41 대비 관측가능성 지표: per-case debug 지표 추가 (슬라이스 단면 컴포넌트 수, centroid 거리, 면적 등, best-effort)

## Artifacts
- **run_dir**: `verification/runs/facts/geo_v0_s1/round40_20260127_175549`
- **facts_summary**: `verification/runs/facts/geo_v0_s1/round40_20260127_175549/facts_summary.json`
- **report**: `reports/validation/lanes/geo_v0_s1/round40_20260127_175549_facts.md`
- **KPI**: `verification/runs/facts/geo_v0_s1/round40_20260127_175549/KPI.md`
- **KPI_DIFF**: `verification/runs/facts/geo_v0_s1/round40_20260127_175549/KPI_DIFF.md`

## PR Link
[PR 링크는 추후 추가]

## Notes
- 구조 변경 없이 facts-only 신호만 강화
- 입력이 비어있는 케이스는 null/skip으로 남김 (억지로 처리하지 않음)
- scale_warnings_detailed는 Top-K 20으로 제한하여 로그 폭발 방지
- per_case_debug는 best-effort로 수집, 실패해도 라운드 전체 마감을 막지 않음
- UnicodeEncodeError 수정: 체크마크 문자(✓)를 "OK"로 변경하여 Windows 콘솔 호환성 확보
