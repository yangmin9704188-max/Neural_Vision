# OPS System Overview v1 (Body 메인 + Fitting/Garment Lab 병렬 운영)

## 0) 목적
이 문서는 1인 개발 환경에서 **Body(메인 레포) + Fitting/Garment(별도 lab 폴더)** 병렬 개발을
“실시간 소통” 대신 **artifact + log + 렌더링(STATUS/HUB)** 로 운영하기 위한 최소 운영 헌법이다.

이 문서를 읽은 AI/에이전트는:
- 어디에 무엇을 기록해야 하는지
- 어떤 산출물이 무엇의 전제인지(의존성)
- 어떤 파일은 수동 편집 금지인지(generated)
- 어떤 명령으로 상태가 갱신되는지
를 이해하고, 변경 시에는 이 규칙을 깨지 않도록 작업한다.

---

## 1) 시스템 구성(역할)
### 1.1 Body 메인 레포 (GitHub 연동, 중앙 허브)
Body 레포가 중앙 허브이며, 다음을 담당한다.
- SSoT 계약/정책 문서(contracts/**)
- 상태 표면화(ops/STATUS.md, ops/HUB.md)
- Lab 로그 수집 및 브리프 렌더(exports/brief/*)
- 경고/의존성/위생 신호 계산(warn-only)

### 1.2 Fitting/Garment Lab (별도 폴더, Git 미사용 가능)
각 lab은 독립 개발 공간이며, Body 메인에 “사실”을 아래 2종으로 제공한다.
- Facts(기계용): `exports/progress/PROGRESS_LOG.jsonl` (append-only)
- Run outputs: `exports/runs/<lane>/<run_id>/...` (minset 포함)

Lab은 메인 레포 파일을 직접 수정하지 않는다.

---

## 2) 단일 진실원(SoT)과 generated 규칙
### 2.1 SoT (Lab)
- `exports/progress/PROGRESS_LOG.jsonl`  
  append-only 사실 기록. 사람이 보는 요약/STATUS는 여기서 유도된다.

### 2.2 Generated-only (메인)
- `exports/brief/*_WORK_BRIEF.md` : generated-only (수동 편집 금지)
- `ops/STATUS.md` : generated 블록은 수동 편집 금지(그 외 섹션은 허용 가능)
- `ops/HUB.md` : generated 영역은 렌더가 덮어쓴다

**원칙:** generated 파일은 머지/충돌보다 “재생성”이 정답이다.

### 2.3 판단 로직 정본 (master_plan)
- **contracts/master_plan_v1.json** 이 언락/아티팩트 관측·다음 할 일 판단의 **단일 정본(SSoT)** 이다.
- 코드는 이 파일만 해석(interpreter)하며, 별도 스파게티 로직을 두지 않는다. 모든 동작은 **warn-only**(FAIL 금지).

### 2.4 Hub Dashboard 및 LLM 브리핑
- `py tools/ops/render_hub_state.py` 로 **ops/hub_state_v1.json**, **ops/hub_events_v1.jsonl**, **exports/brief/LLM_SYNC_*.txt**, **ops/DASHBOARD.md** 를 생성/갱신한다.
- **민영이(사용자) 사용법:** **ops/DASHBOARD.md** 상단만 보고, “복붙 파일”에 적힌 **LLM_SYNC_*.txt** 경로의 파일을 복사·붙여넣기하면 된다. 별도 판단 없이 대시보드 지시대로 진행하면 된다.

---

## 3) 맥락 공유(자동 공유) 범위
본 운영 구조에서 “맥락 공유”는 대화가 아니라 아래 신호로 공유한다.

### 3.1 진행도/스텝
- last_step, roundwrap start/end 기록 기반

### 3.2 증거 경로(관측 경로)
- ROUND_END 이벤트의 evidence_paths/observed_paths 및
- 메인에서 exports/runs를 스캔하여 observed_paths를 보강

### 3.3 런 인덱스(run_registry)
- 메인이 lab 로그에서 exports/runs 패턴을 추출해 `ops/run_registry.jsonl`에 append-only로 축적

### 3.4 의존성(Dependency) 표면화 (warn-only)
- `contracts/dependency_ledger_v1.json` 기준으로
  필요한 산출물(예: body_measurements_subset.json, garment_proxy_meta.json)을 관측 경로에서 확인
- 누락/불일치 시 STATUS warnings에 `*_MISSING_OR_INVALID`로 표면화(FAIL 금지)

### 3.5 위생/신호 품질(Hygiene/Signal Quality)
- STEP_ID_MISSING, EVENT_THIN, STALE_PROGRESS 등
- BACKFILL(=STEP_ID_BACKFILLED)로 STEP_ID_MISSING을 net 기준으로 해소 가능

---

## 4) Lab 운영 규칙(최소)
### 4.1 “통로 단일화”: progress 기록은 roundwrap start/end만 사용
- 다른 방식으로 PROGRESS_LOG를 만지지 않는다.
- step_id는 필수(빈 값 금지). 누락 시 append 자체가 실패해야 한다.

### 4.2 ROUND_END 최소 규격(가장 중요)
각 작업 세션은 **하루 최소 1회 ROUND_END**를 남긴다(dod_done_delta=0 가능).
ROUND_END evidence_paths에는 최소 다음 2개를 포함한다:
- `exports/runs/<lane>/<run_id>/facts_summary.json`
- `exports/runs/<lane>/<run_id>/geometry_manifest.json` (run_dir 루트)

### 4.3 Run Minset(루트 3종)
run_dir 루트에 아래 3종은 항상 존재해야 한다.
- `geometry_manifest.json` (루트)
- `facts_summary.json`
- `RUN_README.md`

### 4.4 STEP_ID 누락의 정리(backfill)
과거에 step_id 누락(UNSPECIFIED)이 발견되면:
- BACKFILL 이벤트 1줄 + gate_code `STEP_ID_BACKFILLED`
- 메인은 STEP_ID_MISSING을 net 기준으로 감소시키는 로직을 가진다.

---

## 5) 의존성 산출물(M0 stub OK)
병렬 개발에서 “품질”보다 “준비성(artifact readiness)”이 먼저다.
U1 단계에서는 warn-only이며, 최소 스텁(M0)로 존재성을 만족시킨다.

- Body → Fitting:
  - `exports/runs/<lane>/<run_id>/body_measurements_subset.json` (M0 stub OK)
- Garment → Fitting:
  - `exports/runs/<lane>/<run_id>/garment_proxy_meta.json` (M0 stub OK)

M1 체크(필드/키/단위/NaN 등)는 warn-only로 먼저 돌리고, U2에서 FAIL 승격한다.

---

## 6) 메인 레포에서의 상태 갱신(사용자 루틴)
메인 레포에서 상태 갱신은 아래 3줄이 표준이다.

```bash
py tools/ops/update_run_registry.py
py tools/render_work_briefs.py
py tools/render_status.py
이후 확인 포인트(최소):

RUN_MINSET_MISSING이 0인지

STEP_ID_MISSING이 net 기준 감소/0인지

dependency 경고(*_MISSING_OR_INVALID)가 줄어드는지

7) 머지/충돌 최소화(1인 개발, 최소 운영)
generated 파일(STATUS/HUB/brief)은 충돌이 잦으므로 아래를 적용한다:

.gitattributes에 다음을 추가하여 merge=ours로 처리:

ops/STATUS.md merge=ours

ops/HUB.md merge=ours

exports/brief/*_WORK_BRIEF.md merge=ours

머지 후에는 항상 렌더로 재생성하여 최신을 커밋한다.

8) 에이전트 행동 규칙(Do / Don’t)
DO
작업 종료 시 ROUND_END 1줄 남기기

run_dir 루트 minset 3종 유지

dependency 산출물은 M0 stub라도 먼저 생성

DON’T
generated 파일(brief/STATUS generated 블록)을 사람이 직접 편집

메인 레포에서 lab 개발 내용을 수동으로 통합

로그를 덮어쓰기(append-only 위반)

9) 실패/이상 징후 트러블슈팅(빠른 진단)
STATUS가 얕게 보임(last_step만 갱신):
→ lab PROGRESS_LOG에 step 이벤트/ROUND_END가 부족한 것 (ROUND_END 규격부터 지키기)

RUN_MINSET_MISSING 경고:
→ run_dir 루트에 facts_summary/RUN_README/루트 geometry_manifest 누락

STEP_ID_MISSING 잔존:
→ BACKFILL 1줄 추가로 net=0 만들기

dependency 경고 지속:
→ 해당 파일을 run_dir 루트에 M0 stub로 생성 + ROUND_END evidence_paths에 포함