1. 목적과 범위
1.1 목적

3개 작업 폴더(허브/랩)에서 병렬로 작업하더라도, 추론 없이(facts-only) 아래를 자동으로 유지한다.

진행상황 단일 뷰: docs/ops/PROJECT_DASHBOARD.md 자동 갱신

모듈별 작업 브리프: 각 모듈의 “지금 가능한 일 / 다음 언락 목표 / 최근 이벤트 / 경고” 문서 자동 생성

작업 종료 기록 자동 수집: 라운드 마감(postprocess) 시 round 문서의 이벤트를 Progress Log로 ingest(append-only)

랩 분리 유지: 허브(AI_model)가 랩(fitting_lab, garment_lab)을 “읽기/브리프 배포” 중심으로 다루고, 랩은 “자기 로그 append”로 책임 분리

1.2 범위(포함)

Dashboard 계약 문서/입출력 계약(Exports Surface)

Progress Log(JSONL) append-only 기록

Round 문서에 포함된 Progress Events(JSONL) ingest

Dashboard 렌더러 및 Work Brief 렌더러/퍼블리셔

postprocess 종료 시 자동 호출 훅(대시보드/ingest/브리프)

1.3 범위(비포함)

“오늘 할 일 추천” 자동 생성(인간 판단 영역)

PASS/FAIL/임계값 기반 판정(금지; facts-only)

대규모 폴더 이동/리팩터링(ops 자동화 외 범위)

랩 폴더 내부의 세부 구현(랩은 독립 실험실로 유지)

2. 시스템 구성 요소
2.1 작업 폴더(3개)

Hub(Main Repo / Body 중심): C:\Users\caino\Desktop\AI_model

Fitting Lab: C:\Users\caino\Desktop\fitting_lab

Garment Lab: C:\Users\caino\Desktop\garment_lab

2.2 계약(SSoT)

모듈 세부 플랜 3개 + unlock/phase 문서(SSoT Pack v1)

Directory Charter v1: 폴더 규칙/성역/통폐합 원칙

Dashboard Contract Pack(v0):

docs/ops/dashboard/PLAN_v0.yaml

docs/ops/dashboard/LAB_SOURCES_v0.yaml

docs/ops/dashboard/EXPORT_CONTRACT_v0.md

원칙: 기계가 읽을 규약/스키마는 contracts/, 사람이 읽는 운영 문서는 docs/** (Directory Charter 경계 준수)

3. Exports Surface (v0) — 폴더 공통 표면

대시보드/브리프 자동화는 레거시 경로 추론 없이 아래 “표면”만 읽고/쓴다.

3.1 Canonical Paths (모든 폴더 공통)
A. Progress Log (append-only)

Path: exports/progress/PROGRESS_LOG.jsonl

Mode: append-only (기존 라인 수정 금지)

Content: 1 line = 1 JSON object (compact single-line)

Missing policy: 파일/폴더 없으면 생성 가능. 실패해도 crash 금지(경고만)

B. Work Brief (generated-only)

Path: exports/brief/<MODULE>_WORK_BRIEF.md

<MODULE> ∈ {BODY, FITTING, GARMENT}

Mode: generated-only (수동 편집 금지)

Producer: 허브 자동화(브리프 렌더러/업데이터)가 갱신

Missing policy: 폴더 없으면 생성 가능. 실패해도 crash 금지(경고만)

3.2 Cross-folder Write Boundary (중요)

허브(AI_model)가 외부 폴더(fitting_lab, garment_lab)에 쓸 수 있는 유일한 경로

<lab_root>/exports/brief/**

Progress Log(exports/progress/PROGRESS_LOG.jsonl)는 각 폴더가 자기 이벤트를 append하는 것이 원칙.

Hub는 기본적으로 read-only (예외는 계약 버전업 필요)

3.3 Facts-only

PASS/FAIL/threshold/clamp 금지

상태 표기는 UNLOCKED/BLOCKED, remaining DoD, evidence paths 등 “관측 가능한 사실”만

4. 파이프라인(단계별)
Stage 1 — Events 생성(에이전트/인간)

작업이 끝났을 때, 해당 모듈 폴더의 Progress Log에 이벤트 1줄 append

이벤트는 “Done delta, total, evidence_paths” 중심으로 기록 (사실만)

Stage 2 — Round 마감 시 ingest (Hub)

tools/postprocess_round.py가 round 문서 경로를 확정/스텁 보장

tools/ingest_round_progress_events_v0.py가 round md의 ## Progress Events (dashboard) 섹션 내 jsonl fenced block을 파싱하여 Hub의 Progress Log에 append

Stage 3 — Dashboard 렌더 (Hub)

tools/render_dashboard_v0.py가 다음을 읽음:

PLAN_v0.yaml (plan)

LAB_SOURCES_v0.yaml (sources)

각 폴더의 exports/progress/PROGRESS_LOG.jsonl (events)

결과를 다음에 씀:

docs/ops/PROJECT_DASHBOARD.md (generated-only)

Stage 4 — Work Brief 렌더/배포 (Hub)

tools/render_work_briefs_v0.py: Hub에서 3개 브리프 생성

exports/brief/BODY_WORK_BRIEF.md

exports/brief/FITTING_WORK_BRIEF.md

exports/brief/GARMENT_WORK_BRIEF.md

tools/publish_work_briefs_v0.py: Hub → 각 Lab으로 브리프 복사

허용 쓰기 경로: <lab_root>/exports/brief/** 만

5. 도구(Tools) 목록
5.1 Renderer

tools/render_dashboard_v0.py

Dashboard 생성기

항상 exit 0 (오류는 Warnings 섹션에만 기록)

tools/render_work_briefs_v0.py

모듈별 Work Brief 생성기

5.2 Publisher

tools/publish_work_briefs_v0.py

Hub에서 lab으로 브리프 배포(쓰기 경로 제한 준수)

5.3 Event Writer

tools/append_progress_event_v0.py

PROGRESS_LOG.jsonl에 이벤트 1줄 append하는 CLI

5.4 Ingest

tools/ingest_round_progress_events_v0.py

Round md의 Progress Events(jsonl fenced block) → Progress Log로 append

5.5 Ops Updater(운영 엔트리포인트)

tools/update_ops_v0.py (현재 운영 표준 엔트리포인트로 가정)

“아침 시작/수동 갱신”을 위해 Dashboard+Brief를 한 번에 최신화하는 목적

(구현이 분리되어 있다면: 내부적으로 render_dashboard_v0.py, render_work_briefs_v0.py, publish_work_briefs_v0.py 호출)

6. Round 문서 이벤트 섹션(표준)

Round md에는 아래 섹션을 포함할 수 있다(없어도 동작해야 함).

## Progress Events (dashboard)
```jsonl
{"lab":"hub","module":"body","step_id":"B02","dod_done_delta":1,"dod_total":3,"evidence_paths":["docs/ops/rounds/.../round_XX.md"],"note":"..."}


- 1 line = 1 event (JSON object)
- 파싱 실패/필수 키 누락 시: skip + warning (crash 금지)
- `ts`가 없으면 ingest 시점에 추가(현재시각 기록)

---

## 7. 품질 센서(관측 신호)

### 7.1 핵심 관측 지표(대시보드/브리프에 노출)
- 모듈/스텝별 DoD 진행도 (done/total)
- Unlock Status(UNLOCKED/BLOCKED)
- Available Work(지금 가능한 스텝 중 remaining > 0)
- Next Unlock Targets(막고 있는 dependency와 그 진행도)
- Recent Events(최대 N개, evidence sample 포함)
- Warnings(경로 TBD, 파일 없음, 파싱 실패 등)

### 7.2 실패/오류 처리 원칙
- 모든 자동화 스크립트는 **exit 0** 지향
- 오류는 “중단”이 아니라 “경고”로 표면화(Warnings 섹션)
- 대시보드/브리프는 **generated-only**: 수동 편집을 금지(변경은 코드/계약으로만)

---

## 8. Runbook (bash / Git Bash 기준)

### 8.1 아침: 작업 시작(허브에서 최신화)
```bash
cd ~/Desktop/AI_model
py tools/update_ops_v0.py


기대 결과:

docs/ops/PROJECT_DASHBOARD.md 갱신

exports/brief/*_WORK_BRIEF.md 갱신

fitting_lab / garment_lab에 브리프 배포(경로가 설정된 경우)

8.2 수동: 대시보드만 갱신
py tools/render_dashboard_v0.py --hub-root .

8.3 수동: 브리프만 갱신 + 배포
py tools/render_work_briefs_v0.py --hub-root .
py tools/publish_work_briefs_v0.py --hub-root .

8.4 작업 종료: 이벤트 1줄 기록(각 폴더에서 자기 로그에 append)

Hub(Body)

py tools/append_progress_event_v0.py \
  --log-path "exports/progress/PROGRESS_LOG.jsonl" \
  --lab "hub" --module "body" --step-id "B02" \
  --dod-done-delta 1 --dod-total 3 \
  --evidence "PATH/TO/EVIDENCE" \
  --note "optional"


Fitting Lab / Garment Lab

각 lab의 exports/progress/PROGRESS_LOG.jsonl에 append(랩 루트에서 실행)

8.5 라운드 마감(허브)
py tools/postprocess_round.py --current_run_dir "<RUN_DIR>"


기대 결과:

Round md → ingest → dashboard render 자동 호출(훅이 연결되어 있다면)

최종적으로 docs/ops/PROJECT_DASHBOARD.md 갱신

9. Freeze(봉인) 규칙 및 운영 메모

SSoT Pack v1이 “판단 근거”의 유일한 소스(레거시는 history)

Directory Charter v1의 Sanctuary/Depth 제한 준수

exports/brief/는 generated-only이며, Git 추적 정책은 .gitignore로 제어(레포 오염 방지)

레거시 이동은 docs/ops/legacy/ 하위에만 축적(계보는 legacy_index.md append-only)

10. 테스트 전략(결정성/회귀)

Dry-run 테스트

publish/ingest는 --dry-run에서 파일 생성/복사 없이 “would do” 출력 + exit 0

경로/소스 결손 테스트

LAB_SOURCES에 TBD인 경우: Warnings에만 기록되고 전체 파이프라인은 계속 진행

이벤트 파싱 회귀

JSONL 라인 1개 성공 / 1개 실패가 섞인 케이스에서:

성공 라인만 append

실패 라인은 skip + warning

exit 0 유지

부록 A: 산출물(Generated Files)

Dashboard:

docs/ops/PROJECT_DASHBOARD.md

Briefs (Hub):

exports/brief/BODY_WORK_BRIEF.md

exports/brief/FITTING_WORK_BRIEF.md

exports/brief/GARMENT_WORK_BRIEF.md

Briefs (Labs, 배포됨):

fitting_lab/exports/brief/FITTING_WORK_BRIEF.md

garment_lab/exports/brief/GARMENT_WORK_BRIEF.md

Logs:

각 폴더의 exports/progress/PROGRESS_LOG.jsonl