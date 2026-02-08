# CLAUDE.md — Neural Vision (Codex/Agent Bootstrap)

## 0) TL;DR (에이전트가 길 잃지 않게 하는 6줄)
- 이 레포는 Hub(메인) + Lab(모듈) 구조다. Hub는 기본 read-only이며, Lab로의 쓰기는 예외적으로 허용된 경계만 가능하다.
- “정본(SSoT)”은 contracts/ 와 docs/ 아래에 있다. 루트에 있는 유사 문서는 대체로 사본이다(수정 금지).
- 작업은 facts-only + evidence-first로만 기록/판단한다. evidence 경로 없으면 claim 금지.
- exports/brief/** 는 generated-only, exports/progress/PROGRESS_LOG.jsonl 은 append-only다(수동 편집 금지).
- U1/U2는 Freeze(동결)이다: geometry_manifest 규칙 + U1 인터페이스 + U2 스모크 3종 정의는 바꾸지 않는다.
- Git 작업은: 브랜치 → 커밋/푸시 → PR → CI green이면 즉시 merge(보류 사유가 없으면).

---

## 1) 시스템 개요(온라인/오프라인)
- Offline: (Body) 12K→캘리브레이션→prototype bank / (Garment) 판매자 입력→latent asset / (Fitting) SDF/테이블 등 전처리
- Online: user request → Body output → Garment proxy → Fitting(충돌/클리핑) → Generation(IP-adapter 포함) → delivery

---

## 2) “정본” 문서 인덱스(이 순서대로만 본다)
### Ops/항법(운영)
- HUB: ./HUB.md
- STATUS: ./STATUS.md
- Ops Pack: ./Ops Automation Pack(v1.0).md
- Repo map: ./project_map.md

### Unlock/Phase(Freeze)
- UNLOCK (U1/U2): ./unlock_conditions_u1_u2.md
- Phase plan: ./phase_plan_unlock_driven.md

> 루트에 동일/유사 문서가 있더라도, project_map.md에 “사본”이라고 적혀 있으면 사본이다. 사본은 수정 금지.

---

## 3) 절대 규칙 (Non-negotiable)
### 3.1 Evidence-first / Facts-only
- evidence 경로 없으면 claim 금지(추론/가정 금지).
- 상태 표기는 “관측 가능한 사실”만: UNLOCKED/BLOCKED, remaining DoD, evidence paths, warnings 등.
- PASS/FAIL/threshold/clamp 같은 임의 판정/임계치 도입 금지(Freeze 범위 밖).

### 3.2 Write Boundary (Hub ↔ Lab)
- Hub가 외부 Lab 폴더에 쓸 수 있는 유일 경로: `<lab_root>/exports/brief/**`
- 그 외 경로에 대한 cross-folder write는 금지.
- PROGRESS_LOG는 각 폴더가 자기 이벤트를 append하는 것이 원칙.

### 3.3 Generated-only / Append-only
- `exports/brief/**` : generated-only (수동 편집 금지)
- `exports/progress/PROGRESS_LOG.jsonl` : append-only (기존 라인 수정 금지)
- `data/**` 와 `exports/**` 는 로컬 전용(커밋 금지)

---

## 4) U1/U2 (Freeze) — 인터페이스 요약(에이전트용)
### 4.1 공통: geometry_manifest.json (REQUIRED)
- schema_version = "geometry_manifest.v1"
- module_name, contract_version 필수
- created_at: `YYYY-MM-DDTHH:MM:SSZ` (UTC Z, 밀리초 금지)
- created_at은 inputs_fingerprint에 포함하지 않는다(결정성 유지)
- inputs_fingerprint: SHA-256 + 결정적 canonicalization(JSON 키 정렬 등)
- version_keys: snapshot_version, semantic_version, geometry_impl_version, dataset_version (null 금지; 미지정은 "UNSPECIFIED"+warning)
- artifacts: run output root 기준 상대경로만(절대경로 금지)

### 4.2 Body → Fitting (U1)
REQUIRED outputs:
- body_mesh.npz
- body_measurements_subset.json (Official Interface Artifact)
- geometry_manifest.json

body_measurements_subset.json 최소 스키마(요약):
- unit="m", pose_id="PZ1"
- 3키(BUST/WAIST/HIP) 필수
- NaN 금지(필요 시 null만)
- warnings 배열
- 결측 정책: 1개 null=soft, 2개 이상 null=degraded/high warning

### 4.3 Garment → Fitting (U1)
REQUIRED outputs:
- garment_proxy_mesh.glb
- garment_proxy_meta.json
- geometry_manifest.json

RECOMMENDED:
- garment_proxy.npz (있으면 Fitting이 우선 사용)

Hard Gate / Fast Fail:
- garment_proxy_meta.json flags 중 하나라도 true면 즉시 중단(Early Exit):
  - negative_face_area_flag OR self_intersection_flag OR invalid_face_flag
- Hard Gate라도 추적성 확보 위해 반드시 생성:
  - garment_proxy_meta.json, geometry_manifest.json
- garment_proxy_mesh.glb / garment_proxy.npz 는 생략 가능

### 4.4 Fitting (U1)
입력 우선순위(Freeze):
1) garment_proxy.npz 존재 → 우선 사용
2) 미존재 → garment_proxy_mesh.glb + garment_proxy_meta.json fallback
- legacy template_params 류 언급 금지(문서/계약 내 0회)

REQUIRED outputs:
- geometry_manifest.json
- fitting_facts_summary.json (REQUIRED)

fitting_facts_summary.json 최소 필드(요약):
- garment_input_path_used: "npz" | "glb_fallback"
- early_exit: boolean
- early_exit_reason: string|null
- warnings_summary: array(또는 구조화 리스트)
- degraded_state: "none" | "high_warning_degraded"

### 4.5 U2 — Runnable Unlock (Freeze: Smoke 3종)
- Smoke-1: 정상 E2E 완료 + manifest/facts 존재
- Smoke-2: Hard Gate 즉시 종료 + meta/manifest 존재 + facts에 early_exit 기록
- Smoke-3: null 정책이 soft vs degraded/high warning으로 facts/manifest warnings에 반영

---

## 5) 표준 커맨드(운영 루프)
### 5.1 Hub에서 “상태 최신화”
- (부팅 점검) `py tools/ops/doctor.py`  # 레포 부트스트랩/헬스 체크 (read-only)
- (표준 엔트리) `py tools/update_ops_v0.py`  # dashboard+brief 갱신(구현/연결된 경우)
- (수동) `py tools/render_work_briefs.py`
- (수동) `py tools/render_status.py`

### 5.2 작업 종료 훅(권장)
- `py tools/ops/run_end_ops_hook.py`
  - progress append → brief 렌더 → status 갱신을 한 번에 수행(연결된 경우)

### 5.3 진행 이벤트 기록(각 폴더에서 “자기 로그”에 append)
- Hub(Body): exports/progress/PROGRESS_LOG.jsonl 에 1줄 append
- Lab(Fitting/Garment): 각 lab의 exports/progress/PROGRESS_LOG.jsonl 에 1줄 append

### 5.4 U1 Validators (run-dir 기준 검증)
- `py tools/validate/validate_geometry_manifest.py --run-dir <dir>`  # geometry_manifest.json 규칙 강제
- `py tools/validate/validate_u1_body.py --run-dir <dir>`  # Body→Fitting U1 검증
- `py tools/validate/validate_u1_garment.py --run-dir <dir>`  # Garment→Fitting U1 검증
- `py tools/validate/validate_u1_fitting.py --run-dir <dir>`  # Fitting U1 검증

### 5.5 U2 Smoke (Runnable Unlock)
- `py tools/smoke/run_u2_smokes.py`  # U2 스모크 3종 실행 (Freeze §3: OK/HardGate/Degraded)

### 5.6 Task Graph & Next Step Navigator (Round 03)
- `py tools/agent/plan_lint.py --plan contracts/master_plan_v1.json`  # Plan 구조 검증
- `py tools/agent/next_step.py --module all --top 5`  # 다음 할 일 계산 (facts-only)

### 5.7 Standard Loop (Round 04)
- `py tools/ops/run_ops_loop.py --mode quick`  # 표준 루프: doctor + next_step + render_status
- `py tools/ops/run_ops_loop.py --mode full`  # 전체 검증: doctor + u2_smokes + next_step + render_briefs+status

### 5.8 CI Guard (Round 05)
- `py tools/ci/ci_guard.py`  # 경계 위반 탐지: exports/data 커밋, PROGRESS_LOG append-only, 루트 사본 수정

---

## 6) 루트 산재 문서(사본) 정책
- project_map.md의 “Root 루즈 파일(정리 대상)” 목록에 있는 파일은 사본이다.
- 사본은 수정 금지. 반드시 표시된 정본 경로(contracts/ 또는 docs/ 또는 modules/*/docs)로 가서 수정한다.
- 아직 이관(정리) 라운드 전이라면, 이동/삭제는 하지 말고 “정본만 수정” 원칙만 지킨다.

---

## 7) 작업 방식(실행 규율)
- 에이전트는 “추론” 대신 “검증 가능한 산출물”만 만든다:
  - 스키마/검증기/스모크/E2E/PROGRESS_LOG 증거
- 변경은 항상 최소 touched paths로 제한한다.
- Git 추적 영역을 오염시키지 않는다(data/**, exports/** 커밋 금지).
