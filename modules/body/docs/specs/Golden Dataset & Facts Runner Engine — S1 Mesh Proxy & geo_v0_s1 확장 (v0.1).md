1. 목적과 범위
1.1 목적

Geometric/Validation 레이어에서 “조용한 오답(스케일 붕괴, 로더 실패, 단면 공백, 둘레 폭증, 팔 간섭 등)”을 Facts Runner로 조기에 표면화하고, 이를 재현 가능한 Golden Dataset + S1 Manifest로 고정하여 회귀 검증 기반의 개발 루프를 안정화한다.

Golden Real-data (curated_v0 기반): 실측 분포 기반 facts 확보

Golden S1 Mesh Proxy (OBJ 기반): 실제 스캔 OBJ 입력 계약 + 운영 마감(postprocess) 체계 검증을 위한 proxy slot 기반 검증

1.2 범위(포함)

S1 Manifest 기반 Mesh 입력 계약(일부 케이스에 OBJ 매핑) 및 단위/스키마 메타 기록

geo_v0_s1 Facts Runner로 mesh load → 단면/측정 → facts_summary → KPI/KPI_DIFF 생성

스킵 분류(Manifest null vs file_not_found vs load_failed 등) 및 증거 파일 기록

OBJ 스케일(mm/m) 자동 감지 및 변환(로더 계층) + 경고 근거 기록

둘레(CIRC) 계산의 성능/정합성 개선(정지/폭증 방지) 및 회귀 검증

1.3 범위(비포함)

Semantic 재해석 및 인체공학적 “정답” 확정

PASS/FAIL 판정(임계값 박기)

curated_v0 파이프라인/단위 변환 재논의(봉인)

대규모 리팩터링/폴더 이동/삭제(git rm)

2. 시스템 구성 요소
2.1 실행 엔트리포인트

(A) Real-data Golden 생성기 (curated_v0 → NPZ)

스크립트: verification/datasets/golden/core_measurements_v0/create_real_data_golden.py

출력: verification/datasets/golden/core_measurements_v0/golden_real_data_v0.npz

메타: meta_unit=m, schema_version, created_at, source_path 등

(B) S1 Mesh Manifest (Proxy 입력 계약)

파일: verification/datasets/golden/s1_mesh_v0/s1_manifest_v0.json

필수 메타:

schema_version: s1_mesh_v0@1

meta_unit: "m" (모든 mesh/verts는 meters 기준)

케이스별:

case_id

mesh_path (없으면 null)

verts_path (현 단계에서는 주로 null; mesh 로드 기반으로 진행)

(C) S1 Facts Runner (geo_v0_s1)

스크립트: verification/runners/run_geo_v0_s1_facts.py

입력: S1 manifest에서 mesh_path 확인 후 로드(필요 시 스케일 변환)

출력(공통):

facts_summary.json

artifacts/visual/SKIPPED.txt (best-effort, DoD 차단 금지)

artifacts/skip_reasons.jsonl (케이스별 스킵/실패 사유 라인 로그)

(D) Postprocess (라운드 마감 강제)

스크립트: tools/postprocess_round.py

라운드 완료 정의: postprocess 마감까지 완료된 상태만 “완료”

생성:

KPI.md, KPI_DIFF.md, LINEAGE.md

reports/validation/round_registry.json 업데이트

coverage_backlog.md 단일 누적 업데이트(규칙: NaN 100% 키만)

2.2 산출물/커밋 정책(운영)

verification/runs/**: 런 산출물 디렉토리 → 커밋 금지(경로/명령만 기록)

verification/datasets/**: Golden/manifest 등 재현 목적 자산은 allowlist 정책 하에 커밋 가능

coverage_backlog: 단일 누적 파일 고정

reports/validation/coverage_backlog.md (facts-only)

3. 입력 데이터 및 전제
3.1 Golden Real-data (curated_v0)

소스: data/processed/curated_v0/curated_v0.parquet

단위 전제: meters(m)

목적: “Synthetic에서만 맞는 엔진”을 조기 차단

3.2 Golden S1 Mesh Proxy (OBJ)

소스 예:

6th_20M.obj(고해상도, verts ~ 87k)

6th_30M.obj / 6th_40M.obj (다양성 검증용)

전제:

OBJ는 mm로 저장될 수 있음 → 로더에서 감지 후 m로 변환

Proxy slot은 “curated_v0 1:1 identity” 보장하지 않음(문서에 note 유지)

4. 처리 파이프라인(단계별)
Stage 1 — S1 Manifest Precheck

목표: 입력 계약 위반을 빠르게 분류

분류:

(A) mesh_path=null → manifest_path_is_null 로 스킵

(B) mesh_path는 있는데 파일 없음 → file_not_found

(C) 파일은 있는데 로드 실패 → load_failed (예: 라이브러리/MTL/파싱)

Stage 2 — Mesh Load (best-effort)

로더 전략:

기본: trimesh

실패 시: 재질/색상(MTL) 무시 + “정점만” 로드 가능한 경로를 우선

로드 증거:

loaded_verts, loaded_faces, loader_name

실패 시: skip_reasons.jsonl에 stage/reason 기록(200-line invariant 유지 목표)

Stage 3 — Scale Detect & Normalize (mm → m)

감지: bbox max_abs 휴리스틱 기반(예: 1752.03 → mm로 추정)

변환: verts *= 0.001

기록: 경고/메타(예: SCALE_ASSUMED_MM_TO_M, max_abs)

Stage 4 — Measure (core_measurements_v0)

단면 공유(Artifact Layer) 기반으로 CIRC/WIDTH/DEPTH를 중복 없이 측정

둘레(CIRC) 계산 개선(오늘 작업 범위):

성능 정지 방지: dedupe + 정렬/벡터화 등으로 계산 병목 제거

폭증 방지: 경로 꼬임 해결을 위해 Convex Hull 기반 외곽선 둘레 계산으로 교체

Clamp 금지 원칙 유지(기하학적 개선으로만 해결)

Stage 5 — Facts Summary & Postprocess 마감

facts_summary.json: 원천 데이터(values/value_stats 포함)

summarize_facts_kpi.py → KPI.md 생성

postprocess_round.py → KPI_DIFF/LINEAGE/registry/backlog/visual proxy best-effort 마감

5. 품질 센서(Validation 관측 신호)
5.1 핵심 관측 지표

processed/skipped 카운트(특히 proxy 대상 processed 수)

스킵 사유 분포(Top reasons)

key별 NaN rate

분포 통계(p50/p95) wire-up 여부(KPI가 N/A가 아닌지)

스케일 경고(자동 변환 발생 여부)

둘레 폭증 경고(PERIMETER_LARGE 등) 발생 여부

5.2 오늘의 핵심 리스크와 처리 방향(요약)

(해결) OBJ 로드 실패: trimesh 기반 로더 확보 + MTL 무시 경로 고려

(해결) mm/m 스케일 붕괴: bbox 기반 감지 후 자동 변환 + 근거 로그

(해결) 둘레 폭증: Convex Hull 기반 둘레 계산으로 경로 꼬임 해결

(잔존) 팔 간섭: hull이 팔/손까지 포함할 수 있어 torso-only 둘레를 위해 **torso guard(단면 제한/세그먼트)**가 다음 라운드 과제

6. Runbook (bash / Windows Git Bash, py)
6.1 S1 Facts Runner 실행 + postprocess 마감(권장)
RUN_DIR="verification/runs/facts/geo_v0_s1/roundXX_$(date +%Y%m%d_%H%M%S)" \
&& py verification/runners/run_geo_v0_s1_facts.py --out_dir "$RUN_DIR" \
&& py tools/postprocess_round.py --current_run_dir "$RUN_DIR"

6.2 스킵 근거 확인
head -n 80 "$RUN_DIR/artifacts/skip_reasons.jsonl" \
&& echo "----" \
&& cat "$RUN_DIR/artifacts/visual/SKIPPED.txt"

7. Freeze(봉인) 규칙 및 운영 메모
7.1 Freeze 원칙(재확인)

기존 Freeze 대상(S0 generator 등)은 수정하지 않고, 이후 이슈는 metadata/provenance/validation에서 해결

facts-only 원칙 유지: PASS/FAIL 판정 금지, 신호 기록만

7.2 Baseline/Alias/Prev 규칙(운영 잠금)

baseline_tag는 Git tag가 아니라 Round 내부 alias

prev_run_dir는 동일 lane에서 최신을 사용(없으면 baseline fallback; 경고만)

postprocess는 {current_run_dir, prev_run_dir, baseline_run_dir} 입력 계약 준수(자동 추론/경고 허용)

8. 테스트 전략(결정성/회귀)

Proxy slot 기반 결정성: 동일 OBJ를 여러 케이스에 매핑하여 값이 안정적으로 재현되는지 확인

다양성 검증: 서로 다른 OBJ(20M/30M/40M 등) 매핑으로 분포가 분산되는지 확인

둘레 알고리즘 회귀:

폭증(수십~수백 m) 재발 여부

성능 정지 재발 여부(고해상도 8만+ 정점에서 멈추지 않는지)

부록: 오늘 추가된 운영적 “사실”

Visual proxy는 best-effort이며, 실패 시 warning만 남기고 DoD를 막지 않음
단, measurement-only NPZ 또는 npz_path_not_found일 때는 artifacts/visual 폴더와 SKIPPED 근거 파일을 유지.