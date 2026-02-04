DEPRECATED: replaced by ops/HUB.md and ops/STATUS.md (modules layout v1)

# SYNC\_STATE

**Guard ref**: [.github/workflows/guard-sync-state.yml](../../.github/workflows/guard-sync-state.yml) - Official definition of guard-sync-state CI rule.

**Architecture v1 반영**: Architecture v1 is 6 layers + modules; any '5-layer' mentions below refer to legacy indexing/history, not current layer model. Layer/Module 구조가 v1로 고정되었습니다. 자세한 내용은 [docs/architecture/LAYERS_v1.md](../../architecture/LAYERS_v1.md) 및 [DoD Checklists](../../architecture/DoD_CHECKLISTS_v1.md)를 참조하세요.

**Sealed Anchors**: As of 2026-01-27, `opsplane-v1` and `arch-v1` anchors are set (merge commits `a80aec0`, `9166fe4`). See [SYNC_HUB.md](../../SYNC_HUB.md#10-sealed-anchors-v1) for details.

snapshot:
id:
status: candidate
last\_change: code
version\_keys:
snapshot: false
semantic: false
geometry\_impl: false
dataset: false

pipeline:
position: rd | local\_validation | promotion | release\_hold | production
position: local\_validation
active\_runbook:
- DB/metadata pipeline updated: artifacts table added for 5-Layer indexing
- Migration script with auto-backup: tools/migrate_add_artifacts_table.py
- db_upsert.py enhanced: artifacts upsert with layer inference, section_id/method_tag in extra_json
- Smoke test added: tests/test_db_artifacts_smoke.py
- bust/underbust geometric v0 엔트리포인트 추가 (core/measurements/bust_underbust_v0.py)
- contract violation = NaN+warnings 정책을 테스트로 봉인 (tests/test_bust_underbust_v0_smoke.py)
- UNDERBUST verts-based 측정 v0 heuristic 구현 (NOT_IMPLEMENTED 경고 제거, 실패 시 warnings 태그로 사실 기록)
- perimeter 계산을 polar angle sorting 기반으로 안정화 (unordered slice points에서도 의미 있는 circumference 산출)
- smoke test로 unordered ring 회귀 봉인
- facts-only runner 추가 (verification/tools/run_bust_underbust_facts_v0.py): 무판정 통계 기록, NaN rate/warnings 빈도/co-occurrence 집계, JSON+CSV 출력
- NPZ loader가 object-array verts/case_id를 지원하도록 안정화 (스키마 불일치 시 크래시 대신 0케이스 summary 기록 후 정상 종료, out_dir 자동 생성)
- bust_underbust_v0 S0 synthetic golden dataset 생성기 추가 (verification/datasets/golden/bust_underbust_v0/create_s0_dataset.py): VALIDATION_FRAME Tier S0 케이스 반영 (정상 2개, 퇴화 1개, 극소 N 1개, 스케일 오류 의심 1개, 랜덤 노이즈 1개, 남성 Δ≈0 1개), meters 단위, meta_unit/schema_version 메타 키 포함
- S0 NPZ 파일 레포 커밋: verification/datasets/golden/bust_underbust_v0/s0_synthetic_cases.npz (meta_unit='m', schema_version='bust_underbust_v0_s0@1' 포함)
- facts runner 기본 입력 NPZ를 bust_underbust_v0 S0로 변경 (verification/datasets/golden/bust_underbust_v0/s0_synthetic_cases.npz), Golden 입력에 한해 strict shape 적용 (meta_unit/schema_version 누락 시 warning, shape (N,V,3) 강제)
- Contract/SYNC_HUB 규칙 보강: CONTRACT_INTERFACE_BUST_UNDERBUST_V0.md에 Ingestion 단계 meters 확정 규칙 추가, SYNC_HUB.md에 Golden NPZ meta_unit/schema_version 필수 계약 추가
- Ingestion 단계 meters canonicalization 엔트리포인트 추가 (data/ingestion.py::canonicalize_units_to_m): mm/cm/m -> m 변환, 0.001m 양자화(round-half-up), provenance 기록, 예외 금지(NaN+warnings 정책)
- data/README.md에서 processed 단위 서술을 m 기준으로 정정 (모든 processed 데이터는 meters 단위 강제, 0.001m 해상도)
- NPZ meta_unit 검증 로직 추가 (verification/tools/run_bust_underbust_facts_v0.py): Golden NPZ의 meta_unit != "m" 또는 누락 시 UNIT_FAIL warning 기록
- 실데이터 단위/스케일 샘플링 스크립트 추가 (tools/sample_raw_data_units.py): raw 데이터에서 N행 샘플링하여 주요 측정 컬럼 값 범위 관측 (단위 혼재 가능성 확인용, 추론 금지)
- processed/m_standard 경로 도입 (data/regenerate_processed_m_standard.py): 기존 cm 기반 processed와 혼선 방지를 위해 m 기반 processed를 별도 경로에 저장, source_unit 명시적 지정 필수
- bust/underbust Golden(실데이터 기반) 재생성 경로 추가 (verification/datasets/golden/bust_underbust_v0/create_real_data_golden.py): processed(m_standard) 입력, 출력 파일명 golden_real_data_v0.npz, meta_unit="m" + schema_version="bust_underbust_v0_real@1" + ingestion_provenance 메타 포함, 스키마 불일치 시 warnings 기록 후 skip (예외 금지)
- NPZ meta_unit 검증이 실데이터 Golden 경로에서도 적용됨 (verification/tools/run_bust_underbust_facts_v0.py의 기존 검증 로직 활용)
- real-data golden NPZ 생성 및 Run B 실행 런북 추가 (verification/datasets/golden/bust_underbust_v0/README_REAL_DATA_GOLDEN.md): processed(m_standard) 재생성 방법, golden NPZ 생성 커맨드, facts runner Run B 실행 커맨드 문서화
- data/processed/m_standard/ 경로 상태 확인: 현재 존재하지 않음, 재생성 필요 (data/README.md에 상태 및 재생성 방법 문서화)
- SizeKorea raw 데이터 컬럼명 관측 스크립트 추가 (tools/observe_sizekorea_columns.py): raw CSV 파일별 row 수, 컬럼 목록, 공통 컬럼 교집합/차집합 요약 관측 (출력: verification/runs/column_observation/, 커밋 금지)
- SizeKorea 한국어 컬럼명 → 영문 표준 키 매핑 테이블 v0 생성 (data/column_map/sizekorea_v0.json): 최소 세트 매핑 (human_id, sex, age, height, weight, chest_girth, bust_girth, underbust_girth, waist_girth, hip_girth 등), unmapped 컬럼은 ko__ 접두사 + __unmapped 접미사로 보존
- SizeKorea 헤더 정규화 스크립트 추가 (data/normalize_sizekorea_headers.py): raw CSV (한국어 헤더) → raw_normalized_v0 (영문 헤더) 변환, 매핑 성공률/미매핑 목록 출력 (커밋 금지), 예외 금지 (warnings 기록)
- data/processed/raw_normalized_v0/ 경로 도입: 영문 헤더 정규화 중간 단계 데이터 저장, 다음 단계로 curated_v0 통합으로 이어짐
- v0 매핑 적용 완료: 7th_data.csv, 8th_data_3d.csv, 8th_data_direct.csv → raw_normalized_v0 변환 완료 (data/processed/raw_normalized_v0/ 경로에 저장, 커밋 금지)
- 정규화된 컬럼 관측 스크립트 추가 (tools/observe_normalized_columns.py): key columns (human_id, sex, age, height, weight) 및 bust/underbust columns (bust_girth, underbust_girth, chest_girth) 존재 여부 및 결측률 관측 (출력: verification/runs/column_observation/normalized_column_observation.json, 커밋 금지)
- Contract: measurement_coverage_v0.csv (45 keys) frozen
- tools: 7th xlsx->csv converter 추가 (human id 문자열 고정)
- verification/tools/convert_scan_xlsx_to_csv.py 추가 (Round24): scan XLSX→CSV 변환, mm→m 단위 정규화, major 항목 필터링
- verification/datasets/golden/s1_mesh_v0/ 경로 추가: S1 manifest, meshes/, metadata/ (proxy mesh 연결)
- tools: context sample extractor 추가 (커밋 금지 산출물 생성)
- curated_v0 데이터셋 생성 파이프라인 추가 (pipelines/build_curated_v0.py): sizekorea_v1 매핑 기반 컬럼 추출, 단위 canonicalization (mm/cm/m -> m), warnings 기록 (예외 금지), 출력 경로 data/processed/curated_v0/curated_v0.parquet
- curated_v0 warnings 스키마 문서 추가 (docs/data/curated_v0_warnings_schema.md): 경고 포맷 정의 (JSONL 형식, reason 코드, 필드 구조)
- curated_v0 파이프라인 테스트 추가 (tests/test_build_curated_v0.py): dry-run 모드로 매핑/헤더/경고 포맷 검증
- curated_v0 run summary 기록 (verification/runs/curated_v0/2026-01-23_run1.md): 실행 커맨드, 입력/출력 경로, row 수, warnings 카운트, unit canonicalization/outlier rules 적용 여부 (사실만)
- curated_v0 unit heuristic 안전장치 테스트 추가 (tests/test_build_curated_v0.py): ambiguous scale 입력 시 NaN + warnings 동작 검증 (unit_undetermined), 명확한 스케일 입력 시 변환 적용 검증
- curated_v0 파이프라인 mapping v2 사용 반영 (pipelines/build_curated_v0.py): 기본값을 sizekorea_v2.json으로 변경, 테스트 업데이트 (tests/test_build_curated_v0.py), v2 실행 요약 기록 (verification/runs/curated_v0/2026-01-23_v2_run1.md)
- curated_v0 ingest 규칙 강화 (pipelines/build_curated_v0.py): 동적 헤더 탐색(표준 측정항목 명 매칭), 7th 콤마 제거, sentinel 결측 처리(9999/empty → NaN + SENTINEL_MISSING warnings), 성별 정규화(남/여 → M/F), 테스트 추가(sentinel/comma 파싱 검증)
- curated_v0 하드닝 (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py, docs/data/curated_v0_warnings_schema.md): 헤더 탐색 앵커 우선순위("표준 측정항목 명" 1순위), warnings 중복 방지(sentinel_missing → value_missing 중복 차단), warnings 스키마 정합성(SENTINEL_MISSING, numeric_parsing_failed 추가), 테스트 assert 기반 하드닝(헤더/sentinel/comma/dedup 검증)
- curated_v0 정합성 완성 (pipelines/build_curated_v0.py, docs/data/curated_v0_warnings_schema.md, tests/test_build_curated_v0.py): warnings 필드 정합성(sentinel_value, optional sentinel_count 기록), 8th_direct 9999 치환 dtype 무관 처리, value_missing 집계 정교화(sentinel_count 제외), 테스트 결정성 강화(synthetic CSV 앵커 검증)
- curated_v0 7th XLSX 우선 및 키별 헤더 선택 (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): 7th prefers XLSX in data/raw/sizekorea_raw; per-key header selection (HUMAN_ID/SEX secondary only); HUMAN_ID excluded from numeric/unit processing
- curated_v0 primary/secondary header detection (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): Primary header uses '표준 측정항목 명' row (anchor may be in non-first cell); meta keys (HUMAN_ID/SEX/AGE) use secondary header row
- curated_v0 header contamination prevention (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): Drops header/code/meta rows using data_start_row=max(primary,code,secondary)+1 to prevent header contamination; numeric_parsing_failed from header rows eliminated
- curated_v0 parquet dtype hardening (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): Force-cast WEIGHT_KG to numeric before parquet write; normalize non-finite values to NaN with aggregated warnings to prevent pyarrow conversion failure and silent invalids
- sizekorea_v2 contract update from table (data/column_map/sizekorea_v2.json): Updated sizekorea_v2 contract mappings from curated_v0 table; meta keys use secondary(7th row6), measurements use primary(row4)
- curated_v0 WEIGHT_KG parquet cast (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): Force-cast WEIGHT_KG to numeric before parquet write to avoid pyarrow conversion failure when mixed string/float values exist
- sizekorea_v2 exact-match contract update (data/column_map/sizekorea_v2.json): Normalized mappings to exact primary/secondary headers from v3_run2; column_not_found reduced from 74 to 6 (68 reduction); HUMAN_ID mapped (7th: "HUMAN ID", 8th: "HUMAN_ID")
- curated_v0 v3 실행 완료 (verification/runs/curated_v0/2026-01-23_v3_run1.md, tools/aggregate_warnings_v3.py): v3 실행 결과 facts-only 요약 생성, warnings 집계 도구 추가, 총 393 warnings (value_missing 133, unit_undetermined 123, column_not_found 93, column_not_present 38, 기타 6), 총 8249 rows 처리 (7th: 6414, 8th_direct: 5092, 8th_3d: 4546)
- aggregate_warnings_v3 supports parquet dataset input (tools/aggregate_warnings_v3.py): --dataset-parquet argument added; parquet file reading supported for dataset analysis; --dataset-csv also available for backward compatibility
- curated_v0 v3 (data/processed/curated_v0/curated_v0.parquet): output_parquet=data/processed/curated_v0/curated_v0.parquet, rows=12365, columns=46, warnings_total=362, column_not_found=0, warning_breakdown: OUTLIER_RULES_NOT_FOUND=3, SENTINEL_MISSING=2, age_filter_applied=3, column_not_present=26, unit_conversion_applied=35, unit_conversion_failed=77, unit_undetermined=88, value_missing=128
- Contract update (data/column_map/sizekorea_v2.json): Added exact headers for 7 keys (ABDOMEN_CIRC_M, BACK_LEN_M, FRONT_CENTER_LEN_M, ANKLE_MAX_CIRC_M, MIN_CALF_CIRC_M, BICEPS_CIRC_M, FOREARM_CIRC_M); 8th_3d headers updated for 4 keys; 2 new keys added (BICEPS_CIRC_M, FOREARM_CIRC_M). Post-update run: warnings_total=374, column_not_present=22, value_missing=134
- curated_v0 quality summary (pipelines/build_curated_v0.py): --emit-quality-summary option added; generates source×key completeness metrics (non_null_count, missing_count, missing_rate) and duplicate header detection (base header with .1/.2 suffixes); quality summary emitted to specified markdown path
- curated_v0 header candidates diagnostic (pipelines/build_curated_v0.py): --emit-header-candidates option added; finds header candidates for ARM_LEN_M and KNEE_HEIGHT_M in 8th_direct/8th_3d sources; outputs facts-only markdown with candidate columns and non-null counts for manual confirmation
- curated_v0 ARM/KNEE trace diagnostic (pipelines/build_curated_v0.py): --emit-arm-knee-trace option added; traces ARM_LEN_M and KNEE_HEIGHT_M values through processing stages (after_extraction_before_preprocess, after_preprocess, after_unit_conversion) for 8th_direct/8th_3d sources; outputs facts-only markdown with dtype, sample_values, non_null_count, non_finite_count, min/max at each stage; trace output: docs/data/curated_v0_arm_knee_trace.md
- curated_v0 unit conversion fallback (pipelines/build_curated_v0.py): unitless fallback mm->m for 8th_direct/8th_3d when unit=m keys (length/height/circumference) have unit_undetermined; prevents non-finite collapse in unit conversion; applies mm->m (÷1000) with aggregated UNIT_DEFAULT_MM_NO_UNIT warnings; latest run: rows=12365, columns=48, warnings_total=472, value_missing=134
- curated_v0 warnings source_key hardening (pipelines/build_curated_v0.py): unit warnings now always include source_key; unknown removed; unit_conversion_failed, unit_undetermined, unit_conversion_applied warnings use source_key from processing context (7th/8th_direct/8th_3d) or "system" for system-level operations; ensures traceability of unit-related warnings to source
- curated_v0 unit-fail trace diagnostic (pipelines/build_curated_v0.py): --emit-unit-fail-trace option added; traces NECK_WIDTH_M, NECK_DEPTH_M, UNDERBUST_CIRC_M, CHEST_CIRC_M_REF through processing stages (after_extraction_before_preprocess, after_preprocess, after_unit_conversion) for all sources (7th/8th_direct/8th_3d); outputs facts-only markdown with dtype, non_null_count, non_finite_count, sample_values (prioritizing non-finite values) at each stage; trace output: verification/runs/curated_v0/unit_fail_trace.md
- curated_v0 unit-fail trace crash fix (pipelines/build_curated_v0.py): trace crash fix (dtype-safe non-finite detection); collect_unit_fail_trace now uses pd.to_numeric with errors='coerce' before np.isfinite check to handle object dtype columns safely; non_finite_count counts numeric values that are inf/-inf; non_numeric_count counts values that couldn't be converted to numeric; sample_values include both raw_sample_values and processed numeric samples
- curated_v0 unit warnings source/file dict literal cleanup (pipelines/build_curated_v0.py): cleaned up source/file field assignments in unit warning dict literals; removed redundant key assignments; tests assert no unknown source in unit warnings
- Contract finalization for ARM_LEN_M and KNEE_HEIGHT_M (data/column_map/sizekorea_v2.json): Updated contract headers for ARM_LEN_M and KNEE_HEIGHT_M based on header candidates; ARM_LEN_M: all sources use '팔길이'; KNEE_HEIGHT_M: all sources use '앉은무릎높이'; ran curated_v0 build and recorded counters (rows=12365, columns=48, warnings_total=374, value_missing=134)
- curated_v0 v3 unit conversion dtype/object hardening (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): numeric coercion applied before unit conversion scaling; pd.to_numeric(errors='coerce') ensures object dtype columns are safely converted; coercion_nan_increase tracked in details; unit_conversion_failed only counts inf/-inf from numeric float (not object dtype); prevents CHEST_CIRC_M_REF null collapse
- curated_v0 validation warnings hardening (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): ALL_NULL_EXTRACTED, MASSIVE_NULL_INTRODUCED, SCALE_SUSPECTED, RANGE_SUSPECTED sensors added; ALL_NULL_EXTRACTED checks non_null_count==0 after extraction; MASSIVE_NULL_INTRODUCED checks drop_rate>=0.95 AND drop_count>=1000 between after_preprocess and after_unit_conversion; SCALE_SUSPECTED checks p50>10.0 or p50<0.01 for expected_unit='m' keys; RANGE_SUSPECTED checks out_of_range_count>=50 for expected_unit='m' keys with physical range constraints
- curated_v0 completeness report (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): --emit-completeness-report option added; generates facts-only markdown report with standard_key×source completeness metrics (non_null_count, total_rows, non_null_rate, min/p1/p50/p99/max percentiles); includes scale suspicion observations (mm_scale_suspected, double_division_suspected, normal_scale) for meter-unit keys; report generated from final df after all processing stages
- curated_v0 all-null warnings separation (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): ALL_NULL_BY_SOURCE warning added (distinct from ALL_NULL_EXTRACTED); checks non_null_count==0 for key×source combination in final state; emits 1 warning per key×source (no duplicates); details include total_rows and non_null_count=0; prevents all-null keys from being mixed with unit_fail/invalid warnings
- curated_v0 parsing hardening (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): 7th comma parsing distinguishes decimal comma (79,5 -> 79.5) vs thousands separator (1,736 -> 1736) using regex pattern; unit_conversion_failed calculation uses np.isinf() instead of ~np.isfinite() to exclude NaN; collect_unit_fail_trace and collect_arm_knee_trace updated to only count inf/-inf; parquet write normalization uses np.isinf() for consistency; run summary: rows=12365, columns=48, warnings_total=514, unit_conversion_failed=87 (inf/-inf only, NaN excluded), unit_conversion_applied=205, value_missing=98, RANGE_SUSPECTED=38, ALL_NULL_BY_SOURCE=24
- curated_v0 7th decimal-comma parsing order hardening (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): parse_numeric_str function enforces decimal comma pattern ^\d{1,4},\d{1,2}$ processed FIRST before thousands separator removal; prevents 10x scale error (e.g., 245,0 -> 245.0, not 2450); regression test added with 245,0 case; run summary: rows=12365, columns=48, warnings_total=514
- curated_v0 v3: 7th parser strategy added to disambiguate decimal-comma vs thousands-comma (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): 7th-specific numeric string parser strategy with explicit pattern matching (European decimal comma ^\d+,\d{1,2}$ -> replace with dot; thousands separator ^\d{1,3}(,\d{3})+$ -> remove comma); prevents 10x scale collapse from comma parsing conflicts; regression tests verify "245,0"->245.0 and "1,736"->1736 parsing, end-to-end mm->m conversion; warnings schema updated with euro_decimal_comma handling note
- curated_v0 v3: 7th comma parser strategy unified; regression tests for euro-decimal comma + thousands comma; sensors label non-numeric separately (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): unified parse_numeric_string_7th function applied to all 7th numeric conversion paths (preprocess_numeric_columns and apply_unit_canonicalization); prevents 10x scale collapse from comma parsing order conflicts; regression tests for ANKLE_MAX_CIRC_M/WRIST_CIRC_M/HIP_DEPTH_M euro-decimal comma (245,0->245.0->0.245m) and HEIGHT_M thousands comma (1,736->1736->1.736m); NON_NUMERIC_VALUES sensor added to avoid false ALL_NULL_* warnings for HUMAN_ID/SEX/AGE; warnings schema updated
- curated_v0 v3: 7th unit override heuristic added to mitigate suspected cm/mm mismatch; warning emitted when triggered (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): 7th-specific unit override checks if cm->m conversion results in unrealistic values (p50 > 2.5 or p99 > 3.5); applies additional /10 scale correction (treating as mm instead of cm); emits UNIT_OVERRIDE_SUSPECTED_MM warning with source_key, standard_key, p50, p99, applied_scale_before/after; regression tests verify mm-scale values (795, 804) convert to 0.795, 0.804 and normal cm-scale values (90.0) do not trigger override
- curated_v0 v3: 7th unit inference default mm for unit=m keys (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): sample_units function accepts source_key parameter; for 7th source, unit=m standard keys (_CIRC_M, _LEN_M, _HEIGHT_M, _WIDTH_M, _DEPTH_M) default to mm (no cm heuristic); cm estimation (median > 10 => cm) disabled for 7th; apply_unit_canonicalization fallback includes 7th for unitless unit=m keys; regression test verifies ANKLE_MAX_CIRC_M=245, WRIST_CIRC_M=153, HIP_DEPTH_M=212, HEIGHT_M=1657 convert to 0.245, 0.153, 0.212, 1.657 m; run summary: rows=12365, columns=48, warnings_total=494, unit_conversion_applied=217, unit_conversion_failed=93, value_missing=98; 7th p50 values: ANKLE_MAX_CIRC_M=0.245m, WRIST_CIRC_M=0.155m, HIP_DEPTH_M=0.220m, HEIGHT_M=1.656m
- curated_v0 v3: 7th unit override source-level rule (anti-10x) (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): 7th source-level rule forces mm for all unit=m keys regardless of unit meta (cm/m); prevents 10x scale errors when unit meta incorrectly says 'cm' or 'm'; UNIT_OVERRIDE_SUSPECTED_MM heuristic removed (source-level rule takes precedence); regression test verifies CHEST_CIRC_M_REF=920 with unit meta 'cm' converts to 0.92 m (not 9.2 m); synthetic unit conversion regression test added (test_7th_unit_override_synthetic_regression); facts-only contract: "7th is all mm-based except weight"
- curated_v0 v3: non-numeric column labeling (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): completeness_report labels non-numeric columns (HUMAN_ID/SEX/AGE as object dtype) as NON_NUMERIC (not all_null=true); prevents false all_null sensor triggers for meta columns; regression test verifies HUMAN_ID/SEX are labeled as NON_NUMERIC in completeness report; sensors (check_all_null_extracted, check_all_null_by_source) already handle non-numeric columns separately
- curated_v0 v3: 7th euro-decimal-comma disambiguation 강화 및 dtype 무관 적용 (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): parse_numeric_string_7th 함수 강화 - 유럽식 소수 콤마 패턴 ^[+-]?\d{1,4},\d+$ 명시적 구현 (920,0->920.0, 245,0->245.0, 79,5->79.5); 천단위 콤마 패턴 ^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$ 명시적 구현 (1,736->1736); preprocess_numeric_columns와 apply_unit_canonicalization에서 7th는 dtype 무관하게 string 변환 후 파싱 적용 (Excel 자동 형변환으로 이미 10배가 되어 들어오는 경로 차단); 회귀 테스트 추가 (test_parse_numeric_string_7th_cases, test_end_to_end_7th_comma_decimal_prevents_10x); CHEST_CIRC_M_REF="920,0"가 최종 0.92m로 변환되는지 검증 (키별 특례 금지, source_key='7th' 규칙으로만)
- curated_v0 v3: integrity fix - unit-expected key classification predicate (pipelines/build_curated_v0.py, tests/test_build_curated_v0.py): problem - unit-expected key classification predicate was overly narrow (e.g., endswith('_M')), so meter-expected keys with '_M' in the middle (e.g., CHEST_CIRC_M_REF) bypassed source-level mm→m scaling, yielding 10× scale artifacts in 7th; anti-pattern - per-key special casing (e.g., if key == 'CHEST_CIRC_M_REF') was introduced/considered to compensate, violating contract-driven invariants; fix - replaced the predicate with an invariant-preserving rule (expects_meter()) that covers all meter-expected keys (suffix and mid-token cases) and routes 7th meter-expected measures through the unified mm→m scaling path without per-key exceptions; result - 7th scaling is consistently applied via the unified predicate; per-key exceptions removed/avoided; regression test verifies CHEST_CIRC_M_REF=920 (mm) converts to 0.92m (not 9.2m) via expects_meter() predicate

signals:
validation:
status: pass | warning | fail
uncertainty\_trend: up | stable | down

status: warning

uncertainty\_trend: stable
cost:
pure: up | stable | down
egress: up | stable | down
cost\_model\_version:
latency: up | stable | down

decision:
promotion: not\_reviewed | deferred | eligible | blocked
release: not\_started | hold | released
authority: rd\_lead+ops\_lead
artifacts:
adr:
validation\_report:

constraints:
technical:
- HIP measurement function (core/measurements/hip\_v0.py) not yet implemented
- CHEST measurement function (core/measurements/chest\_v0.py) not yet implemented
- UNDERBUST verts-based measurement uses v0 heuristic (y-axis slicing, median perimeter selection)
operational:
-

## allowed\_actions:

## forbidden\_actions:

last\_update:
date: 2026-01-22
trigger: underbust_verts_geometric_v0_impl

changed\_paths:

* .github/workflows/guard-sync-state.yml (renamed from ci-guard-sync-state.yml)
* core/measurements/bust_underbust_v0.py
* tests/test_bust_underbust_v0_smoke.py
* verification/runners/verify\_circumference\_v0.py
* verification/runners/verify\_chest\_v0.py
* verification/runners/verify\_hip\_v0.py
* verification/datasets/golden/circumference\_v0/
* verification/datasets/golden/chest\_v0/
* verification/datasets/golden/hip\_v0/
* tests/test\_circumference\_v0\_validation\_contract.py
* tests/test\_chest\_v0\_validation\_contract.py
* tests/test\_hip\_v0\_validation\_contract.py
* docs/policies/measurements/VALIDATION\_FRAME\_CIRCUMFERENCE\_V0.md
* docs/policies/measurements/VALIDATION\_FRAME\_CHEST\_V0.md
* docs/policies/measurements/VALIDATION\_FRAME\_HIP\_V0.md

---

remediation:
  date: 2026-01-26
  reason: post_merge_ci_guard_backfill
  items:
    - merge_commit: 39a29f9
      pr_hint: "#172"
      merge_subject: "Merge pull request #172 from yangmin9704188-max/ops/round8-judgment-scaffold"
      changed_paths:
        - Makefile
        - tools/judgments.py
      scopes:
        - .
        - tools
    - merge_commit: 2ddd588
      pr_hint: "#171"
      merge_subject: "Merge pull request #171 from yangmin9704188-max/ops/cleanup-untracked-round6-tail"
      changed_paths: []
      scopes: []
    - merge_commit: 2dcc130
      pr_hint: "ops-round6"
      merge_subject: "Merge branch 'ops/round6-ops-lock-text-sensor'"
      changed_paths:
        - .gitignore
        - docs/ops/pr_bodies/pr_body_round1_make_round_wrapper.md
        - docs/ops/pr_bodies/pr_body_round2_pr_template_round_checklist.md
        - docs/ops/pr_bodies/pr_body_round3_auto_prev_baseline.md
        - docs/ops/pr_bodies/pr_body_round3_coverage_backlog.md
        - docs/ops/pr_bodies/pr_body_round3_root_cleanup.md
        - docs/ops/pr_bodies/pr_body_round4_round_registry.md
        - docs/ops/pr_bodies/pr_body_round4_slim_coverage_backlog.md
        - docs/ops/pr_bodies/pr_body_round5_kpi_diff.md
        - docs/ops/pr_bodies/pr_body_round5_kpi_diff_signal_line.md
        - docs/ops/pr_bodies/pr_body_round6_lineage_golden_registry.md
        - docs/ops/pr_bodies/pr_body_round6_ops_lock_text_sensor.md
        - docs/ops/pr_bodies/pr_body_round7_visual_provenance.md
        - docs/ops/pr_bodies/pr_body_round7b_visual_skip_artifacts.md
        - docs/semantic/legacy_handling.md
        - docs/verification/coverage_backlog.md
        - docs/verification/curated_v0_gate_draft_v0.md
        - docs/verification/golden_registry.json
        - docs/verification/round_registry.json
        - reports/validation/curated_v0_facts_round1.md
        - reports/validation/round_registry.json
      scopes:
        - .
        - docs
        - reports
    - merge_commit: b63b3cf
      pr_hint: "#169"
      merge_subject: "Merge pull request #169 from yangmin9704188-max/ops/round6-ops-lock-text-sensor"
      changed_paths:
        - Makefile
        - docs/ops/cursor_prompt_header.md
        - tools/kpi_diff.py
        - tools/ops/check_ops_lock.py
      scopes:
        - .
        - docs
        - tools
    - merge_commit: ddb0dee
      pr_hint: "#167"
      merge_subject: "Merge pull request #167 from yangmin9704188-max/ops/round4-slim-coverage-backlog"
      changed_paths:
        - docs/verification/coverage_backlog.md
        - tools/coverage_backlog.py
      scopes:
        - docs
        - tools
    - merge_commit: 2a334d6
      pr_hint: "#165"
      merge_subject: "Merge pull request #165 from yangmin9704188-max/ops/round2-pr-template-round-checklist"
      changed_paths:
        - .github/pull_request_template.md
      scopes:
        - .github
    - merge_commit: b98c81b
      pr_hint: "#164"
      merge_subject: "Merge pull request #164 from yangmin9704188-max/ops/round1-make-round-wrapper"
      changed_paths:
        - Makefile
        - docs/ops/round_runbook.md
      scopes:
        - .
        - docs
    - merge_commit: 23c7720
      pr_hint: "#160"
      merge_subject: "Merge pull request #160 from yangmin9704188-max/ops/round5-kpi-diff-prev-baseline"
      changed_paths:
        - docs/verification/kpi_diff_contract_v0.md
        - tools/kpi_diff.py
        - tools/postprocess_round.py
      scopes:
        - docs
        - tools
    - merge_commit: 33a33f9
      pr_hint: "#159"
      merge_subject: "Merge pull request #159 from yangmin9704188-max/ops/round4-round-registry"
      changed_paths:
        - docs/verification/round_registry.json
        - docs/verification/round_registry_contract_v0.md
        - tools/postprocess_round.py
        - tools/round_registry.py
      scopes:
        - docs
        - tools
    - merge_commit: 4c1c4b5
      pr_hint: "#156"
      merge_subject: "Merge pull request #156 from yangmin9704188-max/ops/round2-kpi-diff"
      changed_paths:
        - tools/postprocess_round.py
        - tools/summarize_facts_kpi.py
      scopes:
        - tools
    - merge_commit: f7991c7
      pr_hint: "#155"
      merge_subject: "Merge pull request #155 from yangmin9704188-max/ops/round1-postprocess-entrypoint"
      changed_paths:
        - docs/ops/baselines.json
        - tools/postprocess_round.py
      scopes:
        - docs
        - tools
    - merge_commit: 986e463
      pr_hint: "#150"
      merge_subject: "Merge pull request #150 from yangmin9704188-max/feat/round20-curated-v0-facts"
      changed_paths:
        - reports/validation/INDEX.md
        - reports/validation/curated_v0_facts_round1.md
        - verification/datasets/golden/core_measurements_v0/create_real_data_golden.py
        - verification/runners/run_curated_v0_facts_round1.py
      scopes:
        - reports
        - verification
    - merge_commit: 43b28f8
      pr_hint: "#121"
      merge_subject: "Merge pull request #121 from yangmin9704188-max/docs/semantic-v0-freeze-round2"
      changed_paths:
        - SYNC_HUB.md
        - docs/semantic/measurement_semantics_v0.md
      scopes:
        - .
        - docs
