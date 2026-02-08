# Neural Vision — Project Map

> 레포 전체 폴더/파일 카탈로그. 각 항목이 무엇을 하는지 한 줄로 설명한다.
> 마지막 갱신: 2026-02-08

---

## Root

```
Neural_Vision/
├── .cursorrules                # AI 에이전트 행동 규칙 (Ops 자동화 경계, 역할, 경로 정책)
├── .env                        # 환경변수 (gitignored, 시크릿)
├── .gitattributes              # Git LF/CRLF 정규화 설정
├── .gitignore                  # 추적 제외 정책 (data, exports, caches, secrets, binaries)
├── Makefile                    # Make 타겟 (postprocess, commands-update 등; 대부분 deprecated → ops/HUB.md 참고)
├── README.md                   # 프로젝트 개요 (Body 모듈 중심 설명)
│
├── .github/                    # GitHub CI/CD
├── contracts/                  # 정본 계약/스키마 (SSoT)
├── data/                       # 원시/파생 데이터 (gitignored)
├── docs/                       # 운영 문서, 리포트, 레거시 대시보드
├── exports/                    # 렌더 산출물 (generated-only, gitignored)
├── legacy/                     # 이전 구조 아카이브 (읽기 전용)
├── modules/                    # 핵심 모듈 (body, fitting, garment)
├── ops/                        # 운영 상태/대시보드/허브
├── reports/                    # 검증 리포트 (placeholder)
├── scripts/                    # 일회성/실험 스크립트
├── ssot/                       # Single Source of Truth 메타문서
├── tests/                      # 허브 레벨 테스트
└── tools/                      # 공용 도구 (렌더러, 검증기, KPI 등)
```

---

## .github/ — CI/CD 워크플로

```
.github/
└── workflows/
    ├── change-boundary.yml         # PR 변경 영역 검사 (Body vs Fitting vs Garment 분리)
    ├── commands-docs-check.yml     # 커맨드 문서 일치 검사
    ├── evidence.yml                # 증거 파일 유효성 검사
    └── guard-sync-state.yml        # 상태 동기화 가드
```

---

## contracts/ — 정본 계약 & 스키마

```
contracts/
├── README.md                           # 계약 폴더 개요
├── dependency_ledger_v1.json           # 모듈 간 의존성 원장 (producer → consumer 매핑)
├── geometry_manifest_v1.md             # geometry_manifest 스키마 설명서
├── geometry_manifest_v1.schema.json    # geometry_manifest JSON Schema
├── master_plan_v1.json                 # SSoT: unlock 조건, plan_items, artifacts 정의
├── progress_event_v1.schema.json       # PROGRESS_LOG 이벤트 JSON Schema
├── renderer_input_contract_v1.md       # 렌더러 입력 규약 (경로, 필드, 판정 규칙)
├── trace_policy_v1.md                  # 실행 추적 정책 (roundwrap, evidence 규칙)
├── unlock_signal_b2_v0.md              # B2 언락 시그널 계약
│
├── datasets/
│   └── npz_contract_v0.md              # NPZ 데이터셋 계약
│
├── fitting/
│   └── fitting_interface_v0.md         # 피팅 인터페이스 정의 (입력/출력/게이트)
│
└── measurement/
    ├── standard_keys_v0.md             # 측정 키 표준 (키 이름 + 단위)
    ├── unit_standard_v0.md             # 측정 단위 표준 (m 기본)
    └── coverage/
        ├── measurement_coverage_v0.csv         # 측정 커버리지 매트릭스
        ├── measurement_coverage_v0_source.md   # 커버리지 출처 설명
        └── sizekorea_v2.json                   # SizeKorea v2 컬럼 매핑
```

---

## data/ — 원시/파생 데이터 (전체 gitignored)

```
data/
├── README.md                   # 데이터 폴더 설명
├── column_map/                 # 컬럼 이름 매핑 파일
├── raw/                        # 원시 CSV/XLSX (SizeKorea 등)
├── external/                   # 외부 데이터소스
├── derived/                    # 파생 데이터 (curated_v0 parquet 등)
│   └── curated_v0/             # curated ingest 라운드별 출력
└── golden/
    └── s1_mesh_v0/             # S1 메시 골든 데이터셋 (manifest + meshes)
```

---

## docs/ — 운영 문서 & 리포트

```
docs/
└── ops/
    ├── B2_Threshold_Recommendations_Report.md    # B2 임계치 권고 리포트
    ├── B2_Unlock_Readiness_Auto_Report.md        # B2 언락 자동 리포트
    ├── B2_Unlock_Signal_Final_Report.md          # B2 언락 최종 리포트
    ├── measurement_refine02_report.md            # 측정 정제 리포트 (02~04)
    ├── measurement_refine03_report.md
    ├── measurement_refine04_report.md
    ├── NOTION_SYNC_v1.md                         # Notion 동기화 가이드
    ├── OPS_SYSTEM_OVERVIEW_v1.md                 # 전체 운영 시스템 개요 (Lab↔Hub 규약)
    ├── Plan.md                                   # 작업 플랜 문서
    ├── RENDERER_INPUTS_AND_DOD_MAPPING_v1.md     # 렌더러 입력 ↔ DoD 매핑
    ├── Step4_Final_Report.md                     # Step4 최종 리포트
    │
    └── dashboard_legacy/                         # 레거시 대시보드 (참조 전용)
        ├── DOD_CLAIM_PROTOCOL_v1.md              # DoD 클레임 프로토콜
        ├── EXPORT_CONTRACT_v0.md                 # export 계약 (v0)
        ├── LAB_SOURCES_v0.yaml                   # 랩 소스 경로 정의
        ├── OPS_PLANE.md                          # 운영 플레인 설명
        ├── PLAN_v0.yaml                          # 기계적 플랜 (step ID, deps)
        ├── PROJECT_DASHBOARD.md                  # 프로젝트 대시보드 (레거시)
        └── UI_STRINGS_ko.yaml                    # 한국어 UI 문자열
```

---

## exports/ — 렌더 산출물 (generated-only, gitignored)

```
exports/
├── README.md                   # exports 폴더 설명 (수동 편집 금지)
├── brief/                      # 워크 브리프 & LLM 컨텍스트 (generated)
│   ├── BODY_WORK_BRIEF.md
│   ├── LLM_CONTEXT_COMMON.md
│   ├── LLM_CONTEXT_BODY.md
│   ├── LLM_CONTEXT_FITTING.md
│   ├── LLM_CONTEXT_GARMENT.md
│   └── LLM_SYNC_FITTING_U1_READY.txt
├── briefs/                     # (레거시 placeholder)
├── dashboards/                 # (레거시 placeholder)
├── logs/                       # 운영 로그 (ops_refresh 등)
├── progress/
│   └── PROGRESS_LOG.jsonl      # Body 모듈 진행 로그 (append-only)
└── runs/                       # 실행 산출물 (facts, smoke, tools)
    ├── facts/                  # 사실 기반 실행 결과
    ├── _smoke/                 # 스모크 테스트 실행 결과
    └── _tools/                 # 도구 실행 결과 (beta_fit, centroids)
```

---

## legacy/ — 이전 구조 아카이브

```
legacy/
├── README.md                   # 읽기 전용 아카이브 설명
└── ops_legacy/
    ├── 20206Q1_CURRENT_STATE.md
    ├── 2026Q1_PROJECT_DASHBOARD.md
    ├── 2026Q1_SYNC_HUB.md
    ├── INDEX.md
    └── rounds/                 # 과거 라운드 기록
```

---

## modules/ — 핵심 모듈

### modules/body/ — Body 모듈 (SizeKorea 인제스트, VTM 측정, Geo 러너)

```
modules/body/
├── README.md                           # Body 모듈 개요 & 실행 가이드
├── assets/                             # 정적 자산 (placeholder)
├── configs/                            # 설정 파일 (placeholder)
│
├── docs/
│   ├── curated_v0_pipeline_guide.md    # curated_v0 파이프라인 가이드
│   └── specs/
│       └── geo_v0_s1_contract_v0.md    # geo_v0_s1 러너 계약
│
├── src/
│   ├── __init__.py
│   │
│   ├── measurements/                   # VTM(Virtual Tape Measure) 측정 로직
│   │   └── vtm/
│   │       ├── CATALOG.md              # VTM 모듈 카탈로그
│   │       ├── core_measurements_v0.py # 핵심 측정 함수 (키, 허리, 엉덩이 등)
│   │       ├── circumference_v0.py     # 둘레 측정 (교차 평면 방식)
│   │       ├── bust_underbust_v0.py    # 가슴/언더바스트 측정
│   │       ├── shoulder_width_v12.py   # 어깨 너비 (v12)
│   │       ├── pelvis_frame_v0.py      # 골반 좌표계 추정
│   │       └── metadata_v0.py          # 측정 메타데이터
│   │
│   ├── pipeline/
│   │   └── ingest/
│   │       ├── CATALOG.md              # 인제스트 모듈 카탈로그
│   │       ├── build_curated_v0.py     # curated_v0 parquet 빌드
│   │       ├── ingestion_units.py      # 단위 변환 로직
│   │       ├── paths.py                # 경로 해석
│   │       └── ...                     # CSV 변환, 컬럼 관찰 스크립트 등
│   │
│   ├── runners/
│   │   ├── CATALOG.md                  # 러너 카탈로그
│   │   ├── run_curated_v0_facts_round1.py  # curated_v0 팩트 러너
│   │   ├── run_geo_v0_s1_facts.py          # geo_v0_s1 팩트 러너 (메시 측정)
│   │   └── run_geo_v0_facts_round1.py      # geo_v0 팩트 러너 (round1)
│   │
│   └── utils/
│       ├── CATALOG.md                  # 유틸 카탈로그
│       ├── path_shim.py                # 경로 심 (레거시 호환)
│       ├── pose_policy.py              # 포즈 정책
│       └── smart_mapper_v001.py        # 스마트 매퍼
│
└── tests/                              # Body 모듈 테스트 (placeholder)
```

### modules/fitting/ — Fitting 모듈 (피팅 실험/검증)

```
modules/fitting/
├── README.md                       # Fitting 랩 개요 (facts-only 원칙)
├── STATUS.md                       # 로컬 상태 요약
├── .gitignore                      # 로컬 ignore (runs/, __pycache__)
│
├── .agent/                         # AI 에이전트 설정
│   ├── rules/                      # 에이전트 규칙/워크스페이스
│   └── workflows/                  # 에이전트 워크플로 (dashboard)
│
├── contracts/                      # Fitting 전용 계약
│   ├── fitting_interface_v0.md             # 피팅 인터페이스 정의
│   ├── body_consumer_path_policy_v1.md     # Body 소비자 경로 정책
│   ├── body_subset_mapping_v1.md           # Body 서브셋 매핑 규칙
│   ├── garment_consumer_path_policy_v1.md  # Garment 소비자 경로 정책
│   ├── geometry_manifest.schema.json       # geometry manifest 스키마
│   ├── geometry_manifest_v1.schema.json    # geometry manifest v1 스키마
│   ├── GEOMETRY_MANIFEST_PATH_POLICY.md    # manifest 경로 정책
│   ├── round_policy_v1.md                  # 라운드 정책
│   └── trace_policy_v1.md                  # 추적 정책
│
├── docs/smoke/                     # 스모크 테스트 문서
│
├── exports/                        # 산출물 (gitignored: runs, brief, progress)
│   ├── brief/                      # 워크 브리프 & 리포트 (generated)
│   ├── progress/                   # PROGRESS_LOG.jsonl (append-only)
│   └── runs/                       # 실행 결과 (_smoke/ 등)
│
├── labs/                           # 실험 코드 & 테스트 데이터
│   ├── runners/
│   │   └── run_fitting_v0_facts.py # Fitting v0 팩트 러너 (실험)
│   ├── samples/                    # 테스트 입력 샘플 (body, garment, manifest JSON)
│   └── specs/                      # 스키마 & 키맵 (body_subset, fit_signal, manifest 등)
│
├── modules/fitting/src/runners/    # 정식 모듈 코드
│   └── run_fitting_smoke_manifest.py  # 스모크 매니페스트 러너
│
├── runs/                           # 로컬 실행 결과 (gitignored)
│
├── tools/                          # Fitting 전용 도구
│   ├── roundwrap.py                    # 라운드 래핑 (ROUND_START/END 자동화)
│   ├── validate_fitting_manifest.py    # 매니페스트 검증기
│   ├── validate_fitting_facts_summary.py # 팩트 요약 검증기
│   ├── validate_fit_signal.py          # fit_signal 검증기
│   ├── run_fitting_smoke_e2e.py        # E2E 스모크 실행기
│   ├── run_manifest_validation_suite.py # 매니페스트 검증 스위트
│   ├── run_tier1_constraint_solver.py  # Tier1 제약 솔버
│   ├── normalize_body_subset.py        # body_subset 정규화
│   ├── progress_append.py              # 진행 로그 추가
│   └── ...                             # 기타 검증/백필/릴리스 도구
│
├── scripts                         # 스크립트 목록 (텍스트 파일)
└── tests                           # 테스트 목록 (텍스트 파일)
```

### modules/garment/ — Garment 모듈 (의류 프록시/매니페스트)

```
modules/garment/
├── README.md                       # Garment 랩 개요
├── STATUS.md                       # 로컬 상태 요약
├── walkthrough.md                  # 워크스루 가이드
├── project_tree.txt                # 프로젝트 트리 스냅샷
│
├── contracts/                      # Garment 전용 계약
│   ├── geometry_manifest_v1.schema.json   # geometry manifest 스키마
│   └── trace_policy_v1.md                 # 추적 정책
│
├── docs/smoke/                     # 스모크 테스트 문서
│   ├── smoke2_fitting_stub.md
│   └── smoke2_garment.md
│
├── exports/                        # 산출물 (gitignored)
│   ├── brief/                      # 워크 브리프 (GARMENT_WORK_BRIEF.md 등)
│   ├── progress/                   # PROGRESS_LOG.jsonl
│   └── runs/                       # 실행 결과 (_smoke/)
│
├── modules/garment/src/runners/    # 정식 모듈 코드
│   └── run_garment_smoke_manifest.py  # 스모크 매니페스트 러너
│
├── output/                         # 로컬 실행 출력 (gitignored)
├── runs/                           # 로컬 실행 결과 (gitignored)
│
├── scripts/                        # 실행 스크립트
│   ├── run_e2e_smoke2.ps1              # E2E 스모크2 실행
│   └── run_smoke2_garment.ps1          # Garment 스모크2 실행
│
├── src/                            # 소스 코드 스켈레톤
│   ├── intake/                     # 인테이크 (placeholder)
│   ├── io/                         # IO (placeholder)
│   ├── meterial_tokens/            # 소재 토큰 (placeholder)
│   ├── preprocessing/              # 전처리 (placeholder)
│   ├── proxy_mesh/                 # 프록시 메시 (placeholder)
│   ├── runners/                    # 러너 (placeholder)
│   └── texture_dna/                # 텍스처 DNA (placeholder)
│
├── tests/                          # Garment 테스트
│   ├── test_e2e_smoke2_pipeline.py         # E2E 스모크 파이프라인 테스트
│   ├── test_fitting_stub_npz_precedence.py # 피팅 스텁 우선순위 테스트
│   ├── test_hard_gate_flags.py             # 하드 게이트 플래그 테스트
│   ├── test_manifest_determinism.py        # 매니페스트 결정성 테스트
│   ├── test_smoke2_reproducible.py         # 스모크2 재현성 테스트
│   └── fixtures/                           # 테스트 픽스처
│
└── tools/                          # Garment 전용 도구
    ├── roundwrap.py                    # 라운드 래핑 자동화
    ├── garment_manifest.py             # 매니페스트 생성기
    ├── garment_proxy_meta.py           # 프록시 메타 생성기
    ├── garment_generate_bundle.py      # 번들 생성기
    ├── validate_geometry_manifest.py   # manifest 검증기
    ├── report_smoke_results.py         # 스모크 결과 리포터
    ├── backfill_root_manifest.py       # 루트 매니페스트 백필
    ├── backfill_step_id.py             # step_id 백필
    ├── progress_append.py              # 진행 로그 추가
    └── ...                             # 기타 도구
```

---

## ops/ — 운영 허브 (상태, 대시보드, 설정)

```
ops/
├── README.md                       # 운영 폴더 개요
├── HUB.md                          # 운영 진입점 (규칙, 경로, 커맨드 안내)
├── STATUS.md                       # 통합 상태 문서 (Manual + Generated 블록)
├── DASHBOARD.md                    # 대시보드 (unlock, blockers, 할 일 목록)
│
├── hub_state_v1.json               # 허브 상태 스냅샷 (artifacts, unlocks)
├── hub_events_v1.jsonl             # 허브 이벤트 로그 (unlock 이벤트)
├── run_registry.jsonl              # 실행 레지스트리 (라운드별 run 기록)
├── notion_sync_status.json         # Notion 동기화 상태
│
├── lab_roots.local.json            # 랩 루트 경로 (gitignored; modules/fitting, modules/garment)
├── lab_roots.local.json.example    # 랩 루트 예시 (커밋 가능)
├── notion.local.json.example       # Notion 설정 예시
│
├── local/                          # 로컬 전용 스크립트 (gitignored)
│   ├── build_session_start_pack.ps1    # 세션 시작 팩 빌드
│   ├── ops_refresh.ps1                 # 운영 갱신 스크립트
│   └── prepare_session_shortcuts.ps1   # 세션 단축키 준비
│
└── specs/
    ├── Ops Automation Pack(v1.0).md    # Ops 자동화 팩 명세
    └── README.md
```

---

## ssot/ — Single Source of Truth 메타문서

```
ssot/
├── README.md                       # SSoT 폴더 설명
├── repo_layout_policy_v1.md        # 정본 폴더/파일 배치 규칙 (엔트로피 방지)
├── evidence_metrics_map_v0.md      # 증거 ↔ 메트릭 매핑
├── interface_ledger_v0.md          # 인터페이스 원장
├── pipeline_ledger_v0.md           # 파이프라인 원장
└── u1_u2_dod_checklist_v0.md       # U1/U2 DoD 체크리스트
```

---

## tests/ — 허브 레벨 테스트

```
tests/
├── test_render_status_signal_quality.py    # render_status 시그널 품질 테스트 (23개)
├── test_run_registry_and_dependency.py     # 실행 레지스트리 & 의존성 테스트 (34개)
├── test_vtm_measurement_refine.py          # VTM 측정 정제 테스트 (10개)
├── test_hub_state_and_dashboard.py         # 허브 상태/대시보드 테스트
├── test_llm_context_render.py              # LLM 컨텍스트 렌더 테스트
├── test_renderer_input_contract.py         # 렌더러 입력 계약 테스트
├── test_notion_sync_mapping.py             # Notion 동기화 매핑 테스트
├── test_notion_sync_status.py              # Notion 동기화 상태 테스트
├── test_audit_manifest_conformance.py      # 매니페스트 적합성 검사 테스트
├── test_body_subset_atomic_write.py        # body_subset 원자적 쓰기 테스트
├── test_body_u1_missingness_smoke3.py      # Body U1 결측 스모크 테스트
├── test_find_latest_beta_fit_run.py        # 최신 beta_fit 탐색 테스트
├── test_fit_smplx_beta_v0.py              # SMPL-X beta 피팅 테스트
├── test_generate_384_centroids_determinism.py # 384 centroid 결정성 테스트
├── test_unlock_signal_b2_determinism.py    # B2 언락 신호 결정성 테스트
├── test_unlock_signal_b2_recommendations_determinism.py
├── test_validate_geometry_manifest.py      # geometry_manifest 검증 테스트
├── test_vtm_determinism.py                 # VTM 결정성 테스트
│
└── fixtures/                               # 테스트 픽스처 데이터
    ├── beta_fit_summary/                   # beta fit 요약 & 언락 시그널
    ├── body_u1_missingness/                # Body U1 결측 시나리오
    ├── sizekorea/                          # SizeKorea 샘플 CSV
    └── vtm_mesh/                           # VTM 메시 데이터 (npz)
```

---

## tools/ — 공용 도구 (렌더러, 검증기, 유틸)

```
tools/
├── README.md                           # 도구 폴더 설명
│
├── render_status.py                    # ops/STATUS.md BODY/FITTING/GARMENT 갱신 렌더러
├── render_work_briefs.py               # PROGRESS_LOG → WORK_BRIEF 렌더러
│
├── validate_geometry_manifest.py       # geometry_manifest 검증기
├── validate_body_measurements_subset_u1.py  # body measurements 검증기
├── validate_evidence.py                # 증거 파일 검증기
├── validate_observation.py             # 관측 검증기
├── audit_manifest_conformance.py       # 매니페스트 적합성 감사
│
├── fit_smplx_beta_v0.py                # SMPL-X beta 파라미터 피팅
├── generate_384_centroids_v0.py        # 384 centroid 생성기
├── generate_unlock_signal_b2_v0.py     # B2 언락 시그널 생성기
├── eval_hip_method_ab_v0.py            # 엉덩이 측정 A/B 비교
│
├── backfill_body_subset_m0.py          # body_subset M0 백필
├── backfill_geometry_manifest.py       # geometry_manifest 백필
├── check_beta_fit_determinism.py       # beta_fit 결정성 검사
├── kpi_diff.py                         # KPI 비교 도구
├── postprocess_round.py                # 라운드 후처리
├── summarize_facts_kpi.py              # 팩트 KPI 요약
├── update_contract_from_table.py       # 테이블 → 계약 갱신
│
├── smoke_append_progress.ps1           # 스모크 진행 추가 (PS)
├── smoke_status.ps1                    # 스모크 상태 확인 (PS)
│
├── ops/                                # 운영 자동화 도구
│   ├── append_progress_event.py            # PROGRESS_LOG에 이벤트 추가
│   ├── check_change_boundaries.py          # PR 변경 영역 검사 (CI용)
│   ├── find_latest_beta_fit_run.py         # 최신 beta_fit 실행 탐색
│   ├── generate_commands_md.py             # 커맨드 문서 자동 생성
│   ├── maybe_generate_kpi.py               # KPI 조건부 생성
│   ├── notion_sync.py                      # Notion DB 동기화
│   ├── prepare_session_shortcuts.py        # 세션 단축키 생성기
│   ├── render_hub_state.py                 # hub_state/DASHBOARD/LLM context 렌더러
│   ├── run_end_ops_hook.py                 # 실행 종료 훅 (progress → briefs → status)
│   ├── update_run_registry.py              # 실행 레지스트리 갱신
│   └── validate_renderer_inputs.py         # 렌더러 입력 검증 (warn-only)
│
└── utils/
    ├── __init__.py
    └── atomic_io.py                        # 원자적 파일 쓰기 유틸
```

---

## scripts/ — 일회성/실험 스크립트

```
scripts/
├── notion_create_task_db.py        # Notion 태스크 DB 생성
├── notion_update_task_table.py     # Notion 태스크 테이블 갱신
└── refine03_hip_eval_sweep.py      # 엉덩이 측정 정제 스윕
```

---

## reports/ — 검증 리포트

```
reports/
└── validation/                     # 검증 리포트 (placeholder)
```

---

## Root 루즈 파일 (정리 대상)

**Status**: NONE (Round 06 cleaned, 2026-02-09)

All root loose copies have been processed:
- **7 files** (identical to canonical): REMOVED
- **2 files** (different from canonical): ARCHIVED to `docs/_archive/root_loose/20260209/`

Previous loose copies (now cleaned):
- dependency_ledger_v1.json → contracts/ (REMOVED)
- fitting_interface_v0.md → contracts/fitting/ (REMOVED)
- Garment_step.md → modules/garment/docs/ (REMOVED)
- master_plan_v1.json → contracts/ (ARCHIVED - outdated)
- NOTION_SYNC_v1.md → docs/ops/ (REMOVED)
- OPS_SYSTEM_OVERVIEW_v1.md → docs/ops/ (REMOVED)
- renderer_input_contract_v1.md → contracts/ (ARCHIVED - minor diff)
- repo_layout_policy_v1.md → ssot/ (REMOVED)
- u1_u2_dod_checklist_v0.md → ssot/ (REMOVED)

See `docs/_archive/root_loose/20260209/README.md` for details.

---

## 핵심 실행 커맨드 요약

| 커맨드 | 역할 |
|--------|------|
| `py tools/render_work_briefs.py` | PROGRESS_LOG → WORK_BRIEF 렌더 |
| `py tools/render_status.py` | ops/STATUS.md 갱신 (BODY/FITTING/GARMENT) |
| `py tools/ops/render_hub_state.py` | DASHBOARD, hub_state, LLM context 갱신 |
| `py tools/ops/validate_renderer_inputs.py` | 렌더러 입력 검증 (warn-only) |
| `py tools/ops/run_end_ops_hook.py` | 실행 종료 훅 (전체 렌더 파이프라인) |
| `py tools/ops/append_progress_event.py` | PROGRESS_LOG에 이벤트 추가 |

---

## 데이터 흐름 요약

```
Lab (modules/fitting, modules/garment)
  └─ exports/progress/PROGRESS_LOG.jsonl  (append-only)
  └─ exports/runs/**/facts_summary.json   (실행 산출물)
        │
        ▼
Hub (tools/)
  ├─ render_work_briefs.py  →  exports/brief/*_WORK_BRIEF.md
  ├─ render_status.py       →  ops/STATUS.md (generated blocks)
  └─ render_hub_state.py    →  ops/DASHBOARD.md, ops/hub_state_v1.json
        │
        ▼
contracts/master_plan_v1.json  →  unlock 조건 판정  →  DASHBOARD 표시
```
