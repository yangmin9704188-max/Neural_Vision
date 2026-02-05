# Ops HUB

## Purpose
- 운영 진입점: 링크/규칙/현재 상태 위치 안내
- STATUS.md에서 모듈별 상태를 확인한다.

## Global Rules (Do/Don't)
- Do: evidence-first, 링크로만 참조, data/**/exports/**는 로컬 전용
- Don't: 모듈 간 파일 직접 수정 금지, 섹션 침범 금지

## Write Boundary (facts-only)
- data/**, exports/**는 로컬 전용, 커밋 금지
- Hub가 외부 lab에 쓸 수 있는 경로는 `exports/brief/**` 뿐 (레거시 [EXPORT_CONTRACT_v0](docs/ops/dashboard_legacy/EXPORT_CONTRACT_v0.md) 인용)

## DoD Claim 규약
- evidence 없으면 claim 금지. 경로 정확 일치 필요.
- 레거시 [DOD_CLAIM_PROTOCOL_v1](docs/ops/dashboard_legacy/DOD_CLAIM_PROTOCOL_v1.md) 참조

## Commands
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

## Standard Operating Mode (External Labs)
- 랩 분리: fitting_lab / garment_lab 은 별도 폴더(깃 연동 없을 수 있음).
- 랩 책임(Writer): 각 랩은 `<lab_root>/exports/progress/PROGRESS_LOG.jsonl` 에 append-only로 이벤트 기록.
  - 권장 훅: `<lab_root>/tools/run_end_hook.ps1` (event=run_finished, dod_done_delta=0).
- 메인 책임(Renderer): 메인은 랩의 exports/progress를 read하여
  - `py tools/render_work_briefs.py` → `<lab_root>/exports/brief/*_WORK_BRIEF.md` 생성/갱신
  - `py tools/render_status.py` → ops/STATUS.md 마커 내부만 갱신
- 경로: ENV(`FITTING_LAB_ROOT`, `GARMENT_LAB_ROOT`) > `ops/lab_roots.local.json` (gitignore).
- 쓰기 경계: 메인이 외부 랩에 쓰는 것은 `exports/brief/**` 만 (progress는 랩이 씀).
- DoD claim: 자동 dod_done_delta 증가 금지(증거 기반 claim은 별도 프로토콜).

One-liner run:
- `py tools/render_work_briefs.py`
- `py tools/render_status.py`
