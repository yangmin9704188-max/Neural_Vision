# Ops HUB

## Purpose
- 운영 진입점: 링크/규칙/현재 상태 위치 안내
- STATUS.md에서 모듈별 상태를 확인한다.
- 병렬 실행 워크보드: `ops/PARALLEL_WORKBOARD_20260209.md`

## Global Rules (Do/Don't)
- Do: evidence-first, 링크로만 참조, data/**/exports/**는 로컬 전용
- Don't: 모듈 간 파일 직접 수정 금지, 섹션 침범 금지

## Common Step Ownership (C-steps)
- Owner: Body main (Hub orchestrator) executes all `common` steps (`step_id` starts with `C`).
- Fitting/Garment agents must not append `C*` milestones.
- Module agents append only their module steps (`B*`, `F*`, `G*`) to their own progress logs.
- Hub/body main validates readiness via `py tools/agent/next_step.py --module all --top 10` and appends `C*`.
- Goal: prevent cross-agent conflicts on shared orchestration state.

## Write Boundary (facts-only)
- data/**, exports/**는 로컬 전용, 커밋 금지
- Hub가 외부 lab에 쓸 수 있는 경로는 `exports/brief/**` 뿐 (레거시 [EXPORT_CONTRACT_v0](docs/ops/dashboard_legacy/EXPORT_CONTRACT_v0.md) 인용)

## DoD Claim 규약
- evidence 없으면 claim 금지. 경로 정확 일치 필요.
- 레거시 [DOD_CLAIM_PROTOCOL_v1](docs/ops/dashboard_legacy/DOD_CLAIM_PROTOCOL_v1.md) 참조

## Commands
### Standard Loop (Round 04 / R09 cleanup / R10 gate)
- `py tools/ops/run_ops_loop.py --mode quick` — 표준 루프: doctor + next_step + render_status
- `py tools/ops/run_ops_loop.py --mode full` — 전체 검증: doctor + u2_smokes + next_step + render_briefs+status
- **마감 커맨드**: `py tools/ops/run_ops_loop.py --mode full --restore-generated --strict-clean`
- `py tools/ops/run_end_ops_hook.py --restore-generated --strict-clean` — run 마무리 훅 (clean 강제)

### Individual Tools
- `py tools/ops/doctor.py` — 레포 부트스트랩/헬스 체크 (read-only, --fix로 누락 디렉토리 생성)
- `py tools/smoke/run_u2_smokes.py` — U2 스모크 3종 실행 (Freeze §3: OK/HardGate/Degraded)
- `py tools/agent/plan_lint.py --plan contracts/master_plan_v1.json` — Plan 구조 검증
- `py tools/agent/next_step.py --module all --top 5` — 다음 할 일 계산 (facts-only)
- `py tools/ops/show_parallel_status.py` — body/garment/fitting 최신 진행상태 + m1 신호 스냅샷
- `py tools/ci/ci_guard.py` — CI 경계 가드 (exports/data 커밋, PROGRESS_LOG append-only, 루트 사본 수정 차단)
- `py tools/ops/run_end_ops_hook.py` — run 마무리 훅: progress append → render_work_briefs → render_status
- `py tools/ops/append_progress_event.py` — PROGRESS_LOG.jsonl append (append-only)
- `py tools/render_work_briefs.py` — PROGRESS_LOG → WORK_BRIEF 렌더
- `py tools/render_status.py` — STATUS.md BODY/FITTING/GARMENT 갱신 (brief 인용)

## Progress logging
- PROGRESS_LOG.jsonl은 append-only. `exports/progress/PROGRESS_LOG.jsonl` 에 1줄 JSON 객체로 기록.
- 예: `py tools/ops/append_progress_event.py --lab-root . --module body --step-id B01 --event note --note "checkpoint" --status OK`
- 예: `py tools/ops/append_progress_event.py --lab-root $env:FITTING_LAB_ROOT --module fitting --step-id F01 --event note --note "smoke" --status OK`
- run-end 훅: `py tools/ops/run_end_ops_hook.py` (FITTING_LAB_ROOT/GARMENT_LAB_ROOT, FITTING_STEP_ID/GARMENT_STEP_ID via ENV)
- docs/ops/dashboard_legacy/ 는 참조용, 실행 비권장

## Module Shortcuts
- [Body Status](./STATUS.md#body)
- [Fitting Status](./STATUS.md#fitting)
- [Garment Status](./STATUS.md#garment)

## Evidence Surfaces (read-only)
- Body:
  - curated: data/derived/curated_v0/<RUN_ID>/
  - geo runs: exports/runs/geo_v0_s1/<run_id>/
- Fitting: exports/runs/fitting_v0/<run_id>/ (placeholder)
- Garment: exports/runs/garment_v0/<run_id>/ (placeholder)
- Progress log: `exports/progress/PROGRESS_LOG.jsonl` (append-only, local only)
- Canonical evidence paths: data/** (local), exports/runs/** (generated-only)
- Legacy verification/* references are supported via shim; verification/ is not canonical

## Work Briefs (generated from PROGRESS_LOG.jsonl)
- `py tools/render_work_briefs.py` 가 각 lab의 `exports/progress/PROGRESS_LOG.jsonl` 을 읽어 `exports/brief/*_WORK_BRIEF.md` 를 생성한다.
- lab roots: ENV(`FITTING_LAB_ROOT`, `GARMENT_LAB_ROOT`) > `ops/lab_roots.local.json`. Body lab = repo root.
- step별 `dod_done_delta` 누적, `last_event_ts`/`last_step_id`/`last_note` 추출. `dod_done > dod_total` 이면 warning.
- PLAN은 `docs/ops/dashboard_legacy/PLAN_v0.yaml` (read-only). 렌더 순서: render_work_briefs → render_status.

## External Lab Brief Contract
- 외부 랩은 `<lab_root>/exports/brief/{FITTING,GARMENT}_WORK_BRIEF.md` 를 유지한다.
- 메인 레포 STATUS는 각 brief의 상단 12줄만 인용(헤더 key: value 순서 고정).
- lab root 지정 우선순위: ENV(`FITTING_LAB_ROOT`, `GARMENT_LAB_ROOT`) > `ops/lab_roots.local.json`
- `ops/lab_roots.local.json` 은 로컬 전용(gitignore). `ops/lab_roots.local.json.example` 참고.
- brief가 없으면 STATUS에 N/A + warning으로 표기됨.

## Standard Operating Mode (Monorepo Labs)
- 랩 위치: modules/fitting, modules/garment (모노레포 내부).
- 랩 책임(Writer): 각 랩은 `<lab_root>/exports/progress/PROGRESS_LOG.jsonl` 에 append-only로 이벤트 기록.
  - 권장 훅: `<lab_root>/tools/run_end_hook.ps1` (event=run_finished, dod_done_delta=0).
- 메인 책임(Renderer): 메인은 랩의 exports/progress를 read하여
  - `py tools/render_work_briefs.py` → `<lab_root>/exports/brief/*_WORK_BRIEF.md` 생성/갱신
  - `py tools/render_status.py` → ops/STATUS.md 마커 내부만 갱신
- 경로: ENV(`FITTING_LAB_ROOT`, `GARMENT_LAB_ROOT`) > `ops/lab_roots.local.json` (기본값: modules/fitting, modules/garment).
- 쓰기 경계: 메인이 랩에 쓰는 것은 `exports/brief/**` 만 (progress는 랩이 씀).
- DoD claim: 자동 dod_done_delta 증가 금지(증거 기반 claim은 별도 프로토콜).

One-liner run:
- `py tools/render_work_briefs.py`
- `py tools/render_status.py`

### Ops Auto-Refresh (Local) — Round 08 updated
- **Default: OFF.** Periodic auto-refresh is disabled by default.
- Entrypoint: `py tools/ops/autorender_tick.py` (checks `ops/autorender.local.json`; default = no-op)
- Config: `ops/autorender.local.json` (gitignored). Example: `ops/autorender.local.example.json` (enabled=false)
- To enable periodic refresh: copy example → local, set `"enabled": true`
- Windows Scheduled Task: `NeuralVision-Ops-Refresh` (legacy, should be **disabled**)
  - Detect: `powershell -ExecutionPolicy Bypass -File tools/ops/find_autorender_tasks.ps1`
  - Disable: `powershell -ExecutionPolicy Bypass -File tools/ops/disable_autorender_tasks.ps1 -Execute`
  - Re-enable (rollback): `powershell -ExecutionPolicy Bypass -File tools/ops/enable_autorender_tasks.ps1 -Execute`
- Local script: `ops/local/ops_refresh.ps1` (gitignored, delegates to autorender_tick.py)
- Lab roots: `ops/lab_roots.local.json` (local-only; gitignored)

### Milestone Refresh Commands (Round 08)
- PR 직전:    `py tools/ops/run_ops_loop.py --mode full`
- merge 직후: `py tools/ops/run_ops_loop.py --mode quick`
- 라운드 종료: `py tools/ops/run_end_ops_hook.py`

## Status Source Policy (v1)
- Contract: `contracts/status_source_policy_v1.json`
- Module status source selection:
  - candidates: `*_WORK_BRIEF.md` (from PROGRESS_LOG), `SMOKE_STATUS_SUMMARY.json`
  - rule: latest `updated_at` wins
- M1 `ops/signals/m1/*/LATEST.json` is readiness signal only (not a status source).
- Dashboard noise policy:
  - hide raw run paths in STATUS generated block
  - show evidence class counts only
