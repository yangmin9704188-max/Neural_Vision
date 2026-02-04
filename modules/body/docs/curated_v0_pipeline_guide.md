# curated_v0 Data Pipeline Guide (Runbook + Contract Discipline)

## 0. Purpose
SizeKorea 7th/8th(Direct/3D) 3개 소스를 단일 스키마(standard keys)로 정규화하여 `curated_v0.parquet`로 산출한다.
핵심 목표는 "조용한 오답(silent wrong answer)" 리스크를 **센서 기반으로 표면화**하고, Contract/Unit 규칙으로 **재발을 봉인**하는 것이다.

## 1. Inputs / Outputs

### Inputs
- 7th: `data/raw/sizekorea_raw/7th_data.xlsx` (우선 사용)
- 8th_direct: `data/raw/sizekorea_raw/8th_data_direct.csv`
- 8th_3d: `data/raw/sizekorea_raw/8th_data_3d.csv`
- Contract(mapping): `data/column_map/sizekorea_v2.json`
- Unit standard: `docs/contract/UNIT_STANDARD.md`
- Standard keys dictionary: `docs/contract/standard_keys.md`

### Outputs (ignored by git by default)
- parquet: `data/processed/curated_v0/curated_v0.parquet`
- warnings: `verification/runs/curated_v0/warnings_v3.jsonl`
- completeness report: `verification/runs/curated_v0/completeness_report.md`
- (optional) unit fail trace: `verification/runs/curated_v0/unit_fail_trace.md`

## 2. Core Contract Rules (Non-negotiable)
1) Contract는 **exact header match만** 허용한다. (자동 유사매칭 금지)
2) 표준 단위는 **m** (kg는 WEIGHT 전용). 정밀도 목표는 0.001m(1mm).
3) 결측 센티널
- 8th_direct: `9999` (dtype 무관하게 탐지/필터)
- 공란/NaN: 결측으로 처리
4) 조용한 오답 방지:
- 단위/스케일 추정은 센서로 **의심을 기록**하고, 자동 보정/특정 키 하드코딩으로 은폐하지 않는다.
- 단, 소스별 “입력 성격”이 다른 경우(7th vs 8th)에는 **소스 전략**을 명시적으로 분리한다.

## 3. Header Policy (Primary/Secondary)
- Primary header: "표준 측정항목 명" 앵커가 포함된 row를 우선 선택한다. (row 내 모든 셀에서 탐지)
- Secondary header: 메타키(HUMAN_ID/SEX/AGE 등)는 secondary header row를 사용한다.
- Per-key header policy:
  - HUMAN_ID/SEX/AGE: secondary header
  - 나머지 측정치: primary header
- 7th/8th에서 header/code/meta row가 데이터로 유입되지 않도록 data start row를 적용하고 제거한다.

## 4. Numeric Preprocess & Parsing
- 숫자 전처리는 dtype(object/numeric) 여부와 관계없이 **소스 전략에 따라** 일관 적용되어야 한다.
- 7th는 콤마/표기/엑셀 자동형변환 이슈가 존재하므로,
  - "원본 보존(문자열 유지)" 또는
  - "dtype 무관 표준 파서 적용"
  중 하나를 선택하고 CURRENT_STATE에 facts-only로 기록한다.

## 5. Unit Normalization (Canonicalization)
- Canonical unit = meters (m)
- "m 기대 컬럼 판별"은 `.endswith('_M')` 같은 단순 규칙에 의존하지 않는다.
  - standard key가 m 스케일인지 판별하는 규칙/집합을 명확히 정의한다.
  - (예: `_CIRC_`, `_LEN_`, `_HEIGHT_`, `_WIDTH_`, `_DEPTH_` 등 패턴 기반 + `_M` 토큰 포함 판정)
- 특정 키(예: CHEST_CIRC_M_REF) 하드코딩 금지.
- 단위 메타가 없거나 불명확한 경우에는 소스 전략(예: 8th unitless mm fallback)과 경고(예: UNIT_DEFAULT_MM_NO_UNIT)를 통해 사실을 남긴다.

## 6. Quality Sensors ("3대 품질 센서")
completeness_report는 다음 리스크를 표면화한다.
- ALL_NULL_BY_SOURCE: 특정 소스에서 해당 키가 전량 null
- ALL_NULL_EXTRACTED: 추출 결과가 전량 null
- MASSIVE_NULL_INTRODUCED: 전처리/변환 과정에서 null이 급증
- RANGE_SUSPECTED: 분위수(p1~p99) 기반으로 단위/스케일 의심

센서는 PASS/FAIL 판정이 아니라, **후속 작업 전환 규칙의 근거(사실 기록)**이다.

## 7. Standard Run Command (Windows, py)
py -u pipelines/build_curated_v0.py ^
  --mapping data/column_map/sizekorea_v2.json ^
  --format parquet ^
  --output data/processed/curated_v0/curated_v0.parquet ^
  --warnings-output verification/runs/curated_v0/warnings_v3.jsonl ^
  --emit-completeness-report verification/runs/curated_v0/completeness_report.md

## 8. Freeze (봉인) Criteria (suggested)
- column_not_found = 0
- 대표 키의 7th vs 8th p50 오더가 일치(10배 스케일 의심이 해소되었거나, 센서로 명시적으로 추적 가능)
- NON_NUMERIC(메타키)가 all_null 오탐으로 기록되지 않음
- 변경사항은 CURRENT_STATE에 facts-only로 기록됨

## 9. Change Management
- Contract(= sizekorea_v2.json) 변경: exact header 변경만 허용, 변경 사유는 CURRENT_STATE에 facts-only 기록.
- 파이프라인 로직 변경: 반드시 센서/회귀 테스트 추가.
- 산출물(verification/runs, data/processed)은 기본적으로 git ignore 유지. (재현이 필요하면 경로/명령만 기록)
