# Ops Index

**Purpose**: Central index for operational automation, documentation, and registry systems.

## Start Here (Canonical): SSoT Pack v1 + Dashboard

> All operational decisions must use SSoT Pack v1. Legacy docs (`docs/ops/legacy/*`) are history only.

### SSoT Pack v1 (5 Canonical Documents)

| ID | Document | Path |
|----|----------|------|
| S1 | Body Module Plan v1 | [`docs/plans/Body_Module_Plan_v1.md`](../plans/Body_Module_Plan_v1.md) |
| S2 | Fitting Module Plan v1 | [`docs/plans/fitting_module_plan_v1.md`](../plans/fitting_module_plan_v1.md) |
| S3 | Garment Product Contract v0.9-revC | [`docs/plans/garment_Product Contract v0.9-revC.md`](../plans/garment_Product%20Contract%20v0.9-revC.md) |
| S4 | Unlock Conditions u1/u2 | [`docs/plans/unlock_conditions_u1_u2.md`](../plans/unlock_conditions_u1_u2.md) |
| S5 | Phase Plan (Unlock-driven) | [`docs/plans/phase_plan_unlock_driven.md`](../plans/phase_plan_unlock_driven.md) |

- **SSoT Pack Declaration**: [`docs/ssot/SSOT_PACK_v1.md`](../ssot/SSOT_PACK_v1.md)

### Dashboard

- **Project Dashboard** (generated): [`PROJECT_DASHBOARD.md`](PROJECT_DASHBOARD.md)
- **Dashboard Plan**: [`dashboard/PLAN_v0.yaml`](dashboard/PLAN_v0.yaml)
- **Export Contract**: [`dashboard/EXPORT_CONTRACT_v0.md`](dashboard/EXPORT_CONTRACT_v0.md)
- **Lab Sources**: [`dashboard/LAB_SOURCES_v0.yaml`](dashboard/LAB_SOURCES_v0.yaml)

**One-shot ops update** (dashboard + work briefs render + publish, independent of postprocess):

```bash
cd <AI_model>
py tools/update_ops_v0.py --hub-root .
```

Dry-run (no writes/copies): `py tools/update_ops_v0.py --hub-root . --dry-run`

### History

- Legacy documents: [`legacy/`](legacy/) (immutable archive, not decision sources)
- Legacy index: [`legacy/LEGACY_INDEX.md`](legacy/LEGACY_INDEX.md)

---

## Architecture v1 Reference

현재 구조 SSoT는 [docs/architecture/LAYERS_v1.md](../../docs/architecture/LAYERS_v1.md)입니다. Architecture v1은 6 layers (Contract → Geometry → Production → Validation → Confidence → Application) + modules (body / garment / fitting) + artifact-only 통신 원칙을 따릅니다. 본 문서의 "5-Layer Organization Principle"은 레거시 인덱싱/분류 용어이며 v1 레이어 체계(6 layers)와 다릅니다.

> ⚠️ **라운드 기록 규칙 (LOCKED)**
> - 새 라운드 기록은 [`docs/ops/rounds/roundXX.md`](rounds/roundXX.md) 파일 추가로만 한다
> - 이 문서의 Round Registry(긴 목록)는 역사 보존용이며 이후 편집 금지
> - 라운드 관련 문서: [`docs/ops/rounds/README.md`](rounds/README.md)

## Baseline Configuration

### curated_v0 Lane (Fixed)
- **baseline_tag (alias)**: `curated-v0-realdata-v0.1` (주의: Git tag 아님, Round 내부 alias로만 사용)
- **baseline_run_dir**: `verification/runs/facts/curated_v0/round20_20260125_164801`
- **baseline_report**: `reports/validation/curated_v0_facts_round1.md`
- **lane**: `curated_v0` (fixed)

### prev_run_dir 추론 규칙 (정합성 강화)
- prev_run_dir는 같은 lane에서 시간상 가장 최근 run_dir
- 선택 조건:
  1) 경로가 `verification/runs/facts/<lane>/round*_YYYYMMDD_HHMMSS` 형태
  2) postprocess 산출물(KPI.md 또는 lineage/manifest 등) 존재로 run_dir임이 확인됨
- prev가 없으면 baseline_run_dir로 fallback (경고만, 빌드 깨지지 않게)
- **prev==baseline이면 KPI_DIFF가 0으로 수렴하는 것은 정상임** (비교 오염 방지)

### postprocess 입력 계약 (3종 고정)
- `tools/postprocess_round.py`는 항상 `{current_run_dir, prev_run_dir, baseline_run_dir}` 3종을 사용
- Ops 래퍼(`make curated_v0_round`)는 runner 스킵 가능하나 postprocess는 항상 실행 (죽지 않는 마감)

## Core Registries

> **라운드 기록 규칙**: 라운드 기록은 [`docs/ops/rounds/roundXX.md`](rounds/roundXX.md)로만 추가합니다.  
> Round Registry(이 파일 내 긴 목록)는 역사 보존용이며 이후 편집 금지입니다.

### Round Registry
- **Path**: [`docs/verification/round_registry.json`](../verification/round_registry.json)
- **Purpose**: Tracks all verification rounds, baseline configuration, and round history per lane
- **Schema**: `round_registry@1`
- **Round23**: geo_v0_s1 facts runner (S1 manifest input contract, meta_unit="m")
- **Round24**: geo_v0_s1 facts runner (20F OBJ/XLSX proxy mesh, mm→m normalization)
- **Round25**: geo_v0_s1 facts runner (20F OBJ 직접 로드, processed>0 목표)
- **Round26**: geo_v0_s1 facts runner (baseline lock, proxy coverage 확대, weight 경고 축소)
- **Round28**: geo_v0_s1 facts runner (20M proxy switch, baseline alias 등록, XLSX→CSV 변환)
- **Round29**: geo_v0_s1 facts runner (per-case skip reasons logging, SSoT)
- **Round30**: geo_v0_s1 facts runner (load_failed diagnostics, resolved path/exception)
- **Round31**: geo_v0_s1 facts runner (2-stage OBJ loader: trimesh optional + pure Python parser required)
- **Round32**: geo_v0_s1 facts runner (per-case skip_reasons invariant: 200 records, has_mesh_path_true=5)
- **Round33**: geo_v0_s1 facts runner (OBJ loader fallback + verts NPZ evidence for postprocess)
- **Round34**: geo_v0_s1 facts runner (NPZ 경로 연결 + KPI 집계 필드 보강)
- **Round35**: geo_v0_s1 facts runner (KPI 분포 통계 p50/p95 스키마 연결)
- **Round36**: geo_v0_s1 facts runner (둘레 계산 디버그 계측: circ_debug facts-only)
- **Round37**: geo_v0_s1 facts runner (둘레 계산 경로 안정화: polar sort + dedupe, perimeter 폭증 제거)
- **Round38**: geo_v0_s1 facts runner (S1 proxy 다양화: 20M/30M/40M 2-2-1 분산 매핑, 입력 다양성 검증)
- **Round38b**: geo_v0_s1 facts runner (HOTFIX: circumference perimeter NameError 수정)
- **Round39**: geo_v0_s1 facts runner (둘레 계산을 2D convex hull 기반으로 교체, 폭증 기하학적 해결)

### Golden Registry
- **Path**: [`docs/verification/golden_registry.json`](../verification/golden_registry.json)
- **Purpose**: Global registry for NPZ files (golden datasets), tracks provenance, schema, and metadata
- **Schema**: `golden_registry@1`

### Coverage Backlog
- **Path**: [`reports/validation/coverage_backlog.md`](../../reports/validation/coverage_backlog.md)
- **Purpose**: Facts-only tracking of all-null keys (NaN 100%) across rounds
- **Policy**: No judgment, no auto-fix, accumulation only
- **추적 태그**: 신규 항목 누적 시 행 끝에 `[RoundXX]` 또는 `run_dir=...` 또는 `ts=...` 태그 추가

## Golden S0 Freeze

**Tag**: `golden-s0-v0.1`  
**Commit**: `cc15544bc26b244d28463568d1d32660679979d3`  
**Date**: 2026-01-25

### Freeze Rule
**이후 발생하는 모든 Geometric/Validation 이슈는 S0 generator를 수정하는 것이 아니라 metadata/provenance/validation으로 해결한다.**

### Reproduce Commands
```bash
rm -f verification/datasets/golden/core_measurements_v0/s0_synthetic_cases.npz
py verification/datasets/golden/core_measurements_v0/create_s0_dataset.py
py verification/runners/run_geo_v0_facts_round1.py \
  --npz verification/datasets/golden/core_measurements_v0/s0_synthetic_cases.npz \
  --n_samples 20 \
  --out_dir verification/runs/facts/geo_v0/round17_valid10_expanded
```

### Reference
- **Documentation**: [`docs/verification/golden_s0_freeze_v0.md`](../verification/golden_s0_freeze_v0.md)
- **Baseline Report**: `reports/validation/geo_v0_facts_round17_valid10_expanded.md`

## Database

- **Guide**: [`DB_GUIDE.md`](../../DB_GUIDE.md)
- **Schema**: `db/schema.sql`
- **Purpose**: Artifact index (search/aggregation/status), not document storage

## 5-Layer Organization Principle

**LEGACY NOTE**: 이 섹션의 "5-Layer"는 레거시 인덱싱/분류 용어이며, 현재 Architecture v1의 6-layer 체계와는 다릅니다.

**5-Layer는 "폴더 분리"가 아니라 "인덱스/레지스트리로 묶기" 원칙을 따릅니다.**

- Policy/Spec/Run/Report는 artifact 타입 (교차 분류)
- 5-Layer는 논리 흐름/분류 축
- 레지스트리와 인덱스로 연결 관계를 관리
- 폴더 구조는 물리적 저장소일 뿐, 논리적 분류는 레지스트리로 표현

## Templates

- [`templates/report_facts_stub.md`](templates/report_facts_stub.md): Facts-only report template
- [`templates/adr_stub.md`](templates/adr_stub.md): Architecture Decision Record template
- [`templates/spec_stub.md`](templates/spec_stub.md): Specification template

## Operational Tools

- `baselines.json`: Lane baseline configuration
- `cursor_prompt_header.md`: Standardized prompt header for Cursor AI
- `round_runbook.md`: Round execution runbook

## Commit Policy

- **Policy**: [`COMMIT_POLICY.md`](COMMIT_POLICY.md)
- **Purpose**: Define "what to commit" based on signals (no judgment, no thresholds)
- **Key Sections**:
  - Non-negotiables (PASS/FAIL 금지, semantic 재논의 금지, 로컬 산출물 커밋 금지)
  - Commit targets / Non-targets
  - Golden candidate signals
  - Action mapping (권고/후속 작업)
  - Evidence checklist

### 커밋 금지 (Lock)
- `verification/runs/**` 및 `data/processed/**` 커밋 금지 (경로/명령만 기록)
- golden/재현 목적 NPZ는 allowlist에 한해 예외 허용 (규칙 위반 금지)

### SoT / 운영 신호 (Lock)
- **SoT**: [`SYNC_HUB.md`](../../SYNC_HUB.md)
- **운영 신호**: [`docs/sync/CURRENT_STATE.md`](../sync/CURRENT_STATE.md)
- 변경 PR은 필요 시 CURRENT_STATE 업데이트를 동반 (운영 규칙 준수)

### Visual Proxy 정책
- **best-effort**: 실패 시 warning 기록하되 DoD/완료를 차단하지 않음
- **measurement-only NPZ (verts 없음)**: 
  - `artifacts/visual/` 생성
  - `SKIPPED.txt` 또는 `README.md`에 사유 명시: `Reason: measurement-only NPZ (No verts available)`

## Judgments

- **Index**: [`../judgments/INDEX.md`](../judgments/INDEX.md)
- **Policy**: [`JUDGMENTS_POLICY.md`](JUDGMENTS_POLICY.md)
- **Runbook**: [`JUDGMENTS_RUNBOOK.md`](JUDGMENTS_RUNBOOK.md)
- **Template**: [`../judgments/templates/JUDGMENT_ENTRY_TEMPLATE.md`](../judgments/templates/JUDGMENT_ENTRY_TEMPLATE.md)
- **Purpose**: Archive lifecycle for confirmed judgment/decision documents (CANDIDATES → Judgments)

## Obsidian Navigation

- **Home**: [`OBSIDIAN_HOME.md`](OBSIDIAN_HOME.md) - 프로젝트 탐색의 단일 진입점
- **Setup Guide**: [`OBSIDIAN_SETUP.md`](OBSIDIAN_SETUP.md) - Obsidian 사용 가이드
- **Project Canvas**: [`canvas/PROJECT_MAP.canvas`](canvas/PROJECT_MAP.canvas) - 프로젝트 맵 (Canvas 뷰)
