# Pipeline Ledger v0 (Body / Garment / Fitting)

목표: 폴더 구조가 아니라 SSoT/Contract/Unlock 문서에 근거해
- 단계(프로세스) 순서
- 단계별 입력/출력 산출물(파일)
- 산출물 규격(필수 필드/단위/버전키/경고)
- 정합성/무결성 체크(Soft/Degraded/Hard gate)
- KPI / KPI_DIFF 생성 규칙과 저장 위치
를 facts-only로 고정한다.

---

## 0) 공통 규칙 (3 모듈 공통)

### 0.1 Run Output 공통 산출물 (모듈 공통)
- Outputs (필수)
  - geometry_manifest.json (모든 모듈 run output 디렉토리에 반드시 존재)

### 0.2 geometry_manifest.json (Freeze: 최소 스펙)
- 최소 필드
  - schema_version: "geometry_manifest.v1"
  - module_name: "body" | "fitting" | "garment"
  - contract_version: 모듈 계약 버전 문자열
  - created_at: "YYYY-MM-DDTHH:MM:SSZ" (UTC Z, 밀리초 금지)
  - inputs_fingerprint: 필수(결정적)
  - version_keys: 4종 필수
    - snapshot_version
    - semantic_version
    - geometry_impl_version
    - dataset_version
  - artifacts: run output root 기준 상대경로만
  - (선택) warnings 또는 warnings_path, provenance_path

- 결정성 규칙
  - created_at은 inputs_fingerprint에 포함하지 않는다.

- inputs_fingerprint 규칙
  - 알고리즘: SHA-256
  - canonicalization(최소):
    - JSON 키 정렬 필수
    - 공백 제거(또는 동등 직렬화)
    - 숫자 반올림/정규화 금지(원본 유지)
  - 포함 요소(최소):
    - Body 입력 신호 + Garment 입력 신호를 포함해야 한다.

- version_keys 규칙
  - 4개 키는 null 금지
  - 미지정 시 "UNSPECIFIED"로 기록 + warnings에 VERSION_KEY_UNSPECIFIED:<key> 추가

- artifacts 규칙
  - artifacts.*.path는 run output root 기준 상대경로만 허용
  - 절대경로 금지

### 0.3 단위 표준 (프로젝트 공통)
- 모든 측정 값 canonical unit: meters (m)
- 표시/보고/문서/UI/exports:
  - 0.001m round-half-up 권장(안정적 diff 목적)
- Raw는 원단위 유지 가능
- processed/canonical은 meters(m) 강제
- ingestion provenance 최소:
  - source unit
  - conversion applied
  - quantization policy

### 0.4 Run Dir / 라운드 문서(Ops Plane 기반)
- run_dir 패턴(검증 런 계열 예):
  - exports/runs/<lane>/round*_YYYYMMDD_HHMMSS
- 라운드 기록 문서:
  - reports/ops/rounds/roundXX.md (새 파일 추가로만 기록, LOCKED)

---

## 1) Body 모듈

### 1.1 Stage: Body → Fitting (U1 Interface Producer)
- Inputs
  - (내부 입력 소스는 본 문서에서 확정 불가: U1은 산출물 존재/규격으로만 요구됨)

- Outputs (필수)
  - body_mesh.npz
  - body_measurements_subset.json (Official Interface Artifact)
  - geometry_manifest.json

- Output Spec (Freeze): body_measurements_subset.json 최소 스키마
  - unit: "m" (필수)
  - pose_id: "PZ1" (필수)
  - keys: 최소 3개 포함
    - BUST_CIRC_M
    - WAIST_CIRC_M
    - HIP_CIRC_M
  - 결측
    - null 허용
    - NaN 금지
  - warnings: array (필수, empty 허용)

- Integrity Gates (Freeze): 결측 정책
  - 3키 중 1개 null까지: Soft Warning
  - 3키 중 2개 이상 null: Degraded / High Warning

- Metrics (U1 관점)
  - 3키 존재/결측 등급(Soft vs Degraded)을 facts 신호로 취급

- Where Stored
  - run output 디렉토리(동일 디렉토리 내 파일 존재로 DoD 판단)

---

## 2) Garment 모듈

### 2.1 Stage: Garment → Fitting (U1 Interface Producer)
- Outputs
  - REQUIRED
    - garment_proxy_mesh.glb
    - garment_proxy_meta.json
    - geometry_manifest.json
  - RECOMMENDED
    - garment_proxy.npz
      - 존재 시 Fitting 우선 사용
      - 없으면 glb+meta fallback

- Integrity Gates (Freeze): Hard Gate / Fast Fail
  - garment_proxy_meta.json에서
    - negative_face_area_flag == true OR self_intersection_flag == true → Hard Gate
  - Hard Gate 처리 규칙
    - Garment: 거부(Hard Gate)
    - Fitting: 루프 없이 즉시 Hard Fail(Early Exit)
    - Hard Gate라도 반드시 생성(추적성)
      - garment_proxy_meta.json
      - geometry_manifest.json
    - 생략 가능(하드게이트 시)
      - garment_proxy_mesh.glb
      - garment_proxy.npz

- Where Stored
  - run output 디렉토리(동일 디렉토리 내 파일 존재로 DoD 판단)

---

## 3) Fitting 모듈

### 3.1 Stage: Fitting (U1 Consumer/Runner)
- Inputs (Freeze): Garment 입력 우선순위
  1) garment_proxy.npz 존재 시 우선 사용
  2) 없으면 garment_proxy_mesh.glb + garment_proxy_meta.json fallback
- 금지(Freeze)
  - legacy garment_template_params.json(또는 template_params 류) 언급/사용은 U1/U2 범위에서 0회

- Outputs (필수, U1)
  - geometry_manifest.json
  - fitting_facts_summary.json (REQUIRED)

- Output Spec (Freeze): fitting_facts_summary.json 최소 필드
  - garment_input_path_used: "npz" | "glb_fallback"
  - early_exit: boolean
  - early_exit_reason: string | null
  - warnings_summary: array (또는 구조화 리스트)
  - degraded_state: "none" | "high_warning_degraded"

- Integrity Gates
  - Garment Hard Gate 발생 시
    - 루프 재시도 없이 즉시 종료(Early Exit)
    - fitting_facts_summary.json에 early_exit 신호 기록

- Where Stored
  - run output 디렉토리(동일 디렉토리 내 파일 존재로 DoD 판단)

---

## Step2) 384 centroid generation (Phase0)

- **Determinism (Lock)**
  - Stable subject ordering: sort by `subject_id` (string-stable) before any clustering.
  - Fixed `random_seed` default (e.g. 42); must be recorded in output metadata.
  - Tie-break rules: stable sort by (distance, subject_id) for clustering/assignment.
- **Atomic writes (Lock)**
  - All Step2 outputs must be written via tmp → flush+fsync → os.replace (reuse `tools.utils.atomic_io.atomic_save_json` or equivalent). No partial final files.
- Outputs: centroids artifact + diagnostics; JSON must not contain NaN/Inf (use null + warnings).

---

## 4) KPI / KPI_DIFF (Ops Plane 기반: 생성 규칙 단위)
- baseline 구성(고정값, curated_v0 lane 기준 예)
  - baseline_tag(alias): curated-v0-realdata-v0.1
  - baseline_run_dir: exports/runs/curated_v0/round20_20260125_164801
  - baseline_report: reports/validation/curated_v0_facts_round1.md
  - lane: curated_v0

- prev_run_dir 추론 규칙
  - 동일 lane에서 시간상 가장 최근 run_dir
  - prev 없으면 baseline_run_dir로 fallback (경고만, 빌드 안 깨짐)
  - prev == baseline이면 KPI_DIFF == 0 수렴은 정상

- postprocess 입력 계약(3종 고정)
  - tools/postprocess_round.py는 항상
    - current_run_dir
    - prev_run_dir
    - baseline_run_dir
    를 사용한다.

- KPI/KPI_DIFF 파일명/위치(확정)
  - exports/runs/<lane>/<run_id>/KPI.json
  - exports/runs/<lane>/<run_id>/KPI_DIFF.md

---