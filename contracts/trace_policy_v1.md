# Trace Policy v1 (SSoT)
본 문서는 병렬 Lab(Body/Fitting/Garment) 운영에서 “무슨 근거로 STATUS/HUB가 그렇게 말하는가”를
Round 기반으로 추적 가능하게 만드는 정본 규칙이다.

---

## 0) 목표
- STATUS/HUB가 표면화하는 모든 요약/경고/진도는 **Round 이벤트**로부터 유도 가능해야 한다.
- Round → Run(산출물 디렉토리) → Manifest → KPI → KPI_DIFF → (상태 표면화)의 연결이 일관되어야 한다.
- 초반(U1)은 **경고-only** 중심, U2부터 일부를 **Fail 승격**할 수 있도록 “기준을 계약으로” 고정한다.

---

## 1) 단일 진실원(SoT) 계층
### 1.1 Lab 단위 SoT (Facts)
각 모듈 Lab의 정본은 다음 하나로 한정한다.
- `exports/progress/PROGRESS_LOG.jsonl` (append-only)

### 1.2 메인(Body) SoT (집계/표면화)
메인 레포는 Lab의 Facts를 읽어 아래를 생성/집계한다.
- `exports/brief/*_WORK_BRIEF.md` (generated-only)
- `ops/STATUS.md` (generated blocks)
- (신규) `ops/run_registry.jsonl` (append-only, runs 인덱스)

---

## 2) Round 이벤트 최소 스키마(v1)
(자세한 Round 규칙은 Round Policy v1을 따른다.)

### 2.1 공통 필드(권장/필수 혼합)
- `ts` (필수): ISO timestamp
- `module` (필수): body|fitting|garment
- `event_type` (필수): ROUND_START|ROUND_END|STEP_DONE|NOTE|BACKFILL
- `round_id` (필수): 예) fitting_20260207_213000_ab12
- `step_id` (ROUND_START 필수): FNN/GNN/BNN
- `note` (START/END 필수): 짧은 사실

### 2.2 Trace 필드(권장 → 점진 승격)
아래 필드는 가능한 한 `ROUND_END`에 포함하도록 한다.
- `lane` (권장): fitting_v0 / garment_v0 / curated_v0 등
- `run_id` (권장): run 디렉토리 식별자
- `dataset_tag` (권장): UNSPECIFIED → real tag 전환 시점 추적용
- `baseline_ref` (선택): baseline_tag 또는 baseline_run_id
- `observed_paths` 또는 `evidence_paths` 또는 `artifacts_touched` (필수 중 1개, 길이>=1)
- `gate_codes` (선택): 경고/게이트 코드 리스트
- `dod_done_delta` (선택): 기본 0 허용

**원칙**
- 사람이 lane/run_id를 직접 타이핑하지 않아도 되도록, roundwrap(end)가
  `observed_paths`에서 자동 파싱해 채우는 방향을 권장한다.

---

## 3) Run(산출물) 규칙
### 3.1 Run 디렉토리 표준
각 모듈은 가능하면 아래 형태를 따른다(모듈별 lane은 다를 수 있음).
- `exports/runs/<lane>/<run_id>/...`

### 3.2 Run의 최소 증거 세트(M0 권장)
Run이 존재한다면 아래 파일 중 최소 1개 이상이 관측되어야 한다.
- `geometry_manifest.json`
- `*facts_summary*.json` (또는 동등한 요약)
- `RUN_README.md` (사유/스킵/입력 요약)

> U1에서는 최소 1개 관측만으로도 OK(경고-only). U2부터는 세트를 승격 가능.

---

## 4) ops/run_registry.jsonl (메인 집계 레저)
### 4.1 목적
- “최근 run 목록/근거 파일/연결된 round”를 단일 파일로 append-only 기록한다.
- KPI/KPI_DIFF, dependency 검사 결과를 붙일 수 있는 anchor가 된다.

### 4.2 레코드(1줄 JSON) 최소 필드(v1)
- `ts`
- `module`
- `lane` (가능하면)
- `run_id` (가능하면)
- `round_id` (가능하면)
- `step_id` (가능하면)
- `manifest_path` (가능하면: run 내부 상대경로 선호)
- `evidence_paths` (0~3개, 상대경로/표시용)
- `gate_codes` (0개 이상)

### 4.3 등록 규칙
- 메인 렌더가 Lab의 최근 `ROUND_END` 이벤트에서 lane/run_id를 추출할 수 있으면 registry에 append한다.
- 추출이 불가능하면 등록하지 않는다(경고-only로 STATUS에 표면화 가능).

### 4.4 manifest_path selection rule v1 (SSoT)
1) `manifest_path`는 evidence_paths 중에서 `exports/runs/<lane>/<run_id>/` prefix와 일치하는 `geometry_manifest.json`을 최우선 선택한다.
2) 해당 prefix와 일치하는 항목이 없으면 가장 최근 ts의 geometry_manifest를 선택하되, `gate_codes`에 `REGISTRY_MANIFEST_MISMATCH`를 부여한다.
3) `exports/runs/<lane>/<run_id>/geometry_manifest.json` (루트)이 존재하면 항상 그것을 우선한다.

### 4.5 geometry_manifest fingerprint (canonical field, SSoT)
- **canonical field**: `fingerprint` — geometry_manifest의 단일 진실원(SoT) 필드명.
- **legacy alias**: `inputs_fingerprint` — 단기 호환을 위한 읽기 전용 alias. m1_checks 평가 시 `fingerprint`가 없으면 `inputs_fingerprint`가 있으면 pass(compat)로 처리.
- **U2 이후**: `inputs_fingerprint` deprecate 계획(문서화만, 시점은 별도 결정).

---

## 5) KPI/KPI_DIFF v1 (가능한 lane부터)
### 5.1 KPI
- 경로(권장): `exports/runs/<lane>/<run_id>/kpi.json`
- 최소 필드:
  - `schema_version`, `module`, `lane`, `run_id`, `round_id`, `created_at`
  - `metrics`(dict), `warnings`(list)

### 5.2 KPI_DIFF
- 경로(권장): `exports/runs/<lane>/<run_id>/kpi_diff.json`
- 최소 필드:
  - `baseline_ref`, `created_at`, `delta`(dict), `degradation_flags`(list)

### 5.3 초기 단계 원칙
- KPI 생성이 불가능하면 “SKIPPED” 사유 파일을 남기고 통과(M0).
- U2 이후에 KPI 생성/비교를 점진 승격.

---

## 6) STATUS/HUB 표면화 규칙(요지)
- STATUS의 모든 “진도(last_step)”는 `ROUND_START/STEP_DONE` 기반이어야 하며,
  `UNSPECIFIED`는 진도 계산에서 제외(경고만 유지)하는 방향을 권장한다.
- BLOCKERS Top N은 최근 이벤트/registry에서 gate_codes 집계로 생성한다.
- dependency/maturity는 ledger 기반 경고-only → unlock 시점에 승격.

(끝)
