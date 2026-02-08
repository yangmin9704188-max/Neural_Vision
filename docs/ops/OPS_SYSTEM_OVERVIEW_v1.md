Fitting/Garment Lab 병렬

이 문서는 당신(LLM/에이전트) 이 Fitting/Garment Lab에서 작업할 때 반드시 지켜야 하는 출력 규약과, Body 메인 레포가 그것을 어떻게 읽고(스키마/경로) 상태를 계산하는지(대시보드/언락)를 정의한다.
목표: 실시간 소통 없이도 “기록 → 관측 → 판정 → 다음 지시”가 자동으로 굴러가게 한다.

0) 시스템 한 줄 요약

Lab(Fitting/Garment)은 “사실”만 남긴다. (append-only log + runs 산출물)

Body 메인은 그 사실을 읽어 STATUS/HUB/DASHBOARD/LLM_SYNC를 만든다.

판단 로직은 contracts/master_plan_v1.json 하나만 본다(SSoT).

운영은 warn-only(FAIL 금지) 가 기본이며, FAIL은 Lab 내부에서만 “입력 누락 방지(예: step_id)” 용도로 제한한다.

1) 레포/폴더 경계(정본 위치)
1.1 Body 메인 레포(중앙 허브, GitHub 연동)

정본 계약/정책: contracts/**

상태/대시보드 산출: ops/**

메인에서 Lab을 읽어 생성:

exports/brief/*_WORK_BRIEF.md (generated-only)

ops/STATUS.md (generated 블록)

ops/DASHBOARD.md, ops/hub_state_v1.json, ops/hub_events_v1.jsonl

exports/brief/LLM_SYNC_*.txt

1.2 Lab(Fitting/Garment) — 너(에이전트)의 작업 공간

Lab은 메인을 수정하지 않는다. Lab의 책임은 오직 2가지다:

Facts(기계용) 로그:
<lab_root>/exports/progress/PROGRESS_LOG.jsonl (append-only)

Run outputs(산출물 묶음):
<lab_root>/exports/runs/<lane>/<run_id>/... (minset 포함)

2) “렌더러가 실제로 읽는 입력” (스키마/파일명 고정)
2.1 PROGRESS_LOG 이벤트 스키마(필수 필드)

이벤트 1줄 = JSON 1개(JSONL)
아래는 “메인 렌더러 및 validate_renderer_inputs가 기대하는 최소 규격”이다.

필수 키:

ts (ISO-8601 권장, +09:00 권장)

module : "body" | "fitting" | "garment"

step_id : 예) "F10", "G11" 등 (빈 값 금지)

event_type 또는 event : 예) "ROUND_START", "ROUND_END", "BACKFILL", "INFO" 등

둘 중 하나는 반드시 있어야 함 (레거시 라인이 없도록)

권장 키(있으면 좋음):

round_id

status : "OK" | "WARN" | "PASS" | ...

evidence_paths 또는 evidence : 리스트/사전 형태 가능(단, ROUND_END에는 paths 리스트 권장)

gate_codes : 리스트(예: ["STEP_ID_BACKFILLED"])

note

dod_done_delta, dod_total

절대 금지: 이미 쓴 라인을 수정/삭제(append-only 위반)

3) Lab의 “통로 단일화” 규칙 (가장 중요)
3.1 PROGRESS_LOG는 오직 roundwrap start/end로만 기록한다

Lab에서 PROGRESS_LOG에 라인을 추가하는 통로는 roundwrap(start/end) 하나로 고정한다.

임의로 “note 이벤트”를 수동 append 하지 않는다. (스키마 불일치/호환성 낭비의 1번 원인)

3.2 step_id는 강제(누락은 Lab에서 즉시 실패)

roundwrap start/end 시 step_id가 없으면 exit non-zero로 실패해야 한다.

이유: 메인에서는 warn-only라 “누락이 계속 남는” 문제가 생김 → Lab에서 선제 차단이 정답.

4) ROUND_END에서 반드시 지켜야 하는 최소 규격(=관측/언락의 핵심)
4.1 매 작업 세션은 최소 1회 ROUND_END를 남긴다

하루 1회 기준(권장). dod_done_delta=0이어도 된다.

4.2 ROUND_END의 evidence_paths(또는 evidence)에 “run_minset”을 포함

ROUND_END 이벤트의 evidence_paths에는 최소 아래를 포함해야 한다:

exports/runs/<lane>/<run_id>/facts_summary.json

exports/runs/<lane>/<run_id>/RUN_README.md

exports/runs/<lane>/<run_id>/geometry_manifest.json (run_dir 루트에 존재해야 함)

메인 레포는 artifact_observed 판단을 위해 exports/runs를 스캔한다.
ROUND_END에 이 경로들이 들어가면 “관측”이 빨라지고 오탐이 줄어든다.

5) Run Minset(루트 3종) 규칙 — run_dir 루트에 항상 존재

<lab_root>/exports/runs/<lane>/<run_id>/ 아래에 반드시 존재:

geometry_manifest.json (루트)

facts_summary.json

RUN_README.md

geometry_manifest가 subdir(예: *_smoke_v1/)에만 있으면 RUN_MANIFEST_ROOT_MISSING 같은 혼선이 생긴다.
루트에 1개는 항상 둔다(M0 stub라도 OK).

6) Backfill(레거시/누락 정리) 규칙
6.1 STEP_ID 누락(UNSPECIFIED)이 과거에 있었다면

BACKFILL 이벤트 1줄 추가 + gate_codes=["STEP_ID_BACKFILLED"]

메인 렌더러는 STEP_ID_MISSING을 net = max(0, UNSPECIFIED - BACKFILLED) 로 계산한다.

6.2 스키마 위반 레거시 라인은 “tombstone”으로만 종결

과거 라인이 event_type/event 누락 등 스키마 위반이면,

기존 라인은 수정하지 말고, INFO 이벤트를 append:

gate_codes=["SCHEMA_VIOLATION_BACKFILLED"]

note에 referenced_line=N 포함

(선택) 메인 validate가 tombstone referenced_line을 skip하도록 개선 가능.

7) “언락/다음 할 일” 판단 로직의 정본(SSoT)
7.1 절대 원칙: 코드는 master_plan만 해석한다

contracts/master_plan_v1.json 이 유일한 판단 정본이다.

render/validator 코드는 master_plan을 읽는 인터프리터일 뿐이다.

로직을 코드에 하드코딩하지 않는다(스파게티 방지).

7.2 에이전트(너)가 보는 지시의 출처

ops/DASHBOARD.md

“현재 해금됨/아직 잠김/지금 할 일”이 여기서 나온다.

exports/brief/LLM_SYNC_*.txt

언락이 발생했을 때 “바로 다음 지시”가 떨어지는 복붙용 프롬프트 파일이다.

8) 너(에이전트)의 실무 체크리스트(작업 끝낼 때 20초)

Lab에서 매 세션 종료 시 아래를 만족시켜라:

roundwrap end를 실행해 ROUND_END 이벤트 1줄 append

run_dir 루트에 minset 3종 존재 확인

ROUND_END evidence_paths에 minset 3종 경로가 포함되었는지 확인

step_id 누락이 있었으면 BACKFILL 이벤트로 정리

9) 무엇을 절대 하지 말아야 하나(Don’t)

메인 레포의 generated 파일(STATUS/HUB/brief)을 Lab에서 편집

PROGRESS_LOG를 덮어쓰기/수정하기(append-only 위반)

roundwrap 외 경로로 임의 이벤트 추가(스키마 불일치 재발)

geometry_manifest를 subdir에만 두고 루트에 안 두기(관측 혼선)

10) 사용자가(민영) 하는 최소 루틴(참고)

민영은 “판단”을 하지 않고, 아래만 수행한다:

py tools/ops/update_run_registry.py
py tools/ops/render_hub_state.py
# 필요시:
py tools/render_work_briefs.py
py tools/render_status.py


그리고 ops/DASHBOARD.md 상단을 보고 LLM_SYNC 파일을 복붙하여 각 모듈 GPT 세션에 전달한다.

11) 트러블슈팅(증상 → 원인 → 해결)

SCHEMA_VIOLATION 경고:
원인) 레거시 이벤트가 event_type/event 없음
해결) tombstone(INFO + referenced_line) append + (선택) validate에서 skip 처리

STEP_ID_MISSING 잔존:
원인) 과거 UNSPECIFIED 이벤트
해결) BACKFILL 1줄 + gate_code STEP_ID_BACKFILLED

dependency 경고 지속(*_MISSING_OR_INVALID):
원인) M0 stub 산출물이 아직 없음/관측 안 됨
해결) run_dir 루트에 M0 stub 생성 + ROUND_END evidence_paths 포함

첨부 메모(이 문서의 목적)

이 문서는 “사람이 기억해서 소통”하는 운영이 아니라,
Lab이 어떤 형태로 뱉어야 메인이 제대로 읽는지를 규정해 병렬 개발 낭비를 줄이기 위한 프로토콜 문서다.

### Lab 기록 규율(중요)
- Lab은 PROGRESS_LOG.jsonl을 `roundwrap start/end`로만 기록한다(수동 append 금지).
- 신규 라인은 validate_renderer_inputs 기준 warning=0을 목표로 한다.
- 레거시 스키마 위반은 수정/삭제 대신 tombstone(INFO + referenced_line)로 종결한다(append-only).
- 상세 규약(정본): `contracts/renderer_input_contract_v1.md`
