# UNLOCK 조건(DoD) — U1/U2 (Freeze)

## 0. 범위(Scope)
- 본 문서는 모듈 병렬 작업을 위한 **언락(Unlock) 조건(DoD)** 을 정의한다.
- **U1(Interface Unlock), U2(Runnable Unlock)** 만 정의하며, 이 두 단계는 **동결(Freeze)** 한다.
- **U3(운영/성능/Ops)** 은 본 문서 범위 밖이며, 후속 문서/후속 Phase에서 정의한다.

---

## 1. 공통 규칙(3모듈 공통)

### 1.1 geometry_manifest.json (REQUIRED)
모든 모듈의 run output 디렉토리에는 `geometry_manifest.json`이 **반드시** 존재해야 한다.

#### 1.1.1 필수 필드(최소)
- `schema_version`: `"geometry_manifest.v1"`
- `module_name`: `"body" | "fitting" | "garment"`
- `contract_version`: 모듈 문서/계약 버전 문자열  
  - 예: Body `"v1.1"`, Fitting `"v1.0-revH"`, Garment `"v0.9-revD"`
- `created_at`: UTC ISO 8601 + `Z` 고정, **밀리초 금지**
  - 형식: `YYYY-MM-DDTHH:MM:SSZ`
  - 예시: `2026-01-30T15:00:00Z`
- `inputs_fingerprint`: **필수**, 결정적(deterministic)
- `version_keys`: **필수**, 4개 키
  - `snapshot_version`, `semantic_version`, `geometry_impl_version`, `dataset_version`
- `artifacts`: run output root 기준 **상대경로** 링크 목록
- (선택) `warnings`(배열) 또는 `warnings_path`(상대경로)
- (선택) `provenance_path`(상대경로)

#### 1.1.2 created_at 규칙(Freeze)
- `created_at`은 **inputs_fingerprint 산정에 포함하지 않는다.**
  - 이유: 동일 입력이면 fingerprint가 동일해야 캐시/회귀가 깨지지 않는다.

#### 1.1.3 inputs_fingerprint 규칙(Freeze)
- 해시 알고리즘: **SHA-256**
- Canonicalization(최소 규칙):
  - JSON 키 정렬은 **필수**
  - 공백 제거(또는 동등한 결정적 직렬화)
  - 숫자값 추가 반올림/정규화 금지(원본 값 유지)
- Fingerprint 포함 요소(최소): **Body 입력 신호 + Garment 입력 신호를 모두 포함**

**Body 측 최소 구성 요소**
- `body_measurements_subset.json`의 canonical hash
- `body_mesh.npz`의 content hash (또는 결정적 `mesh_digest`)
- `pose_id`

**Garment 측 최소 구성 요소**
- `garment_proxy_meta.json`의 canonical hash
- `garment_proxy.npz`가 존재하면: `garment_proxy.npz` content hash  
  없으면: `garment_proxy_mesh.glb` content hash

> 주의: `created_at`은 fingerprint에 포함하지 않는다(1.1.2).

#### 1.1.4 version_keys 규칙(Freeze)
- 4개 버전키는 **null 금지**
- 미지정 시 `"UNSPECIFIED"`로 기록하고, warnings에 아래 형식으로 추가한다:
  - `VERSION_KEY_UNSPECIFIED:<key>`

#### 1.1.5 artifacts 경로 규칙(Freeze)
- `artifacts.*.path`는 **run output root 기준 상대경로만 허용**
- 절대경로 금지

---

## 2. U1 — Interface Unlock (병렬 착수 가능)

### 2.1 Body → Fitting (U1)
#### REQUIRED 산출물
- `body_mesh.npz`
- `body_measurements_subset.json` (**Official Interface Artifact: REQUIRED**)
- `geometry_manifest.json`

#### body_measurements_subset.json 최소 스키마(Freeze)
- `unit`: `"m"` (필수)
- `pose_id`: `"PZ1"` (필수)
- `keys`: 최소 아래 3종 포함
  - `BUST_CIRC_M`, `WAIST_CIRC_M`, `HIP_CIRC_M`
  - 결측은 **null 허용**, NaN 금지
- `warnings`: 배열(필수, empty 허용)

#### 결측 정책(Freeze)
- 3키 중 **1개 null까지**: Soft Warning
- 3키 중 **2개 이상 null**: Degraded / High Warning
  - 파이프라인은 진행 가능하나, degraded/warning 등급을 facts/manifest warnings에 남겨야 한다.

---

### 2.2 Garment → Fitting (U1)
#### REQUIRED 산출물(외부 계약)
- `garment_proxy_mesh.glb`
- `garment_proxy_meta.json`
- `geometry_manifest.json`

#### RECOMMENDED 산출물(내부 성능)
- `garment_proxy.npz`
  - 존재 시 Fitting은 우선 사용한다.
  - 미존재 시 Fitting은 `glb + meta`로 fallback 한다.

#### Hard Gate / Fast Fail:
  - `garment_proxy_meta.json`의 flags 중 하나라도 true면 즉시 중단(Early Exit):
    - `negative_face_area_flag == true` OR
    - `self_intersection_flag == true` OR
    - `invalid_face_flag == true`
  - `invalid_face_flag`는 "degenerate/invalid face 등 기하학적 불량"을 의미하는 호환 신호이며, Smoke-2 재현의 1차 기준으로 사용될 수 있다.
  - 이때 Fitting은 `fitting_facts_summary.json`에 `early_exit: true`를 기록하고 종료.
- Hard Gate라도 **추적성 확보를 위해** 아래는 반드시 생성:
  - `garment_proxy_meta.json` (필수)
  - `geometry_manifest.json` (필수)
- `garment_proxy_mesh.glb` / `garment_proxy.npz`는 **생략 가능**

---

### 2.3 Fitting (U1)
#### 입력 우선순위(Freeze)
1) `garment_proxy.npz` 존재 → 우선 사용
2) 미존재 → `garment_proxy_mesh.glb + garment_proxy_meta.json` fallback
- Legacy `garment_template_params.json`(또는 template_params 류) 언급은 **금지**
  - Fitting 문서/계약 내 언급 횟수는 **0회**여야 한다.

#### REQUIRED 산출물
- `geometry_manifest.json`
- `fitting_facts_summary.json` (REQUIRED)

`fitting_facts_summary.json` 최소 필드(Freeze):
- `garment_input_path_used`: `"npz"` | `"glb_fallback"`
- `early_exit`: boolean
- `early_exit_reason`: string 또는 null
- `warnings_summary`: array(또는 구조화된 리스트)
- `degraded_state`: `"none" | "high_warning_degraded"` (해당 시)

---

## 3. U2 — Runnable Unlock (Freeze: Smoke 3종 고정)
U2는 아래 3개 스모크 시나리오가 “고정된 형태로” 실행 가능해야 달성된다.

### Smoke-1 정상 케이스
- End-to-End 성공 종료
- `geometry_manifest.json` + `fitting_facts_summary.json` 존재

### Smoke-2 Garment Hard Gate 케이스:
  - 입력: `garment_proxy_meta.json`에 `negative_face_area_flag=true` 또는 `self_intersection_flag=true` 또는 `invalid_face_flag=true` 설정.
  - 기대: Fitting이 `early_exit: true`를 출력하고 정상 종료(Exit 0).
  - `fitting_facts_summary.json`의 `early_exit_reason`에는 실제 발생한 플래그명(들)이 포함되어야 한다. (예: "garment_hard_gate_violation: invalid_face_flag")
- `garment_proxy_meta.json` + `geometry_manifest.json` 존재
- `fitting_facts_summary.json`에 early_exit 신호가 기록됨

### Smoke-3 Body subset null 케이스
- Case A: 3키 중 정확히 1개 null → Soft Warning
- Case B: 3키 중 2개 이상 null → Degraded / High Warning
- warning/degraded 등급이 facts/manifest warnings에 반영됨

---

## 4. 비목표(Non-goals)
- U3(운영/성능: cache TTL, retry/timeout telemetry, cost tracking, 성능 최적화, garment_proxy.npz 생성 표준화 등)는 본 문서 범위 밖이다.
