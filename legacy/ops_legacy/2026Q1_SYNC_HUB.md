DEPRECATED: replaced by ops/HUB.md and ops/STATUS.md (modules layout v1)

---
Canonical: SYNC_HUB.md
Key dictionary: docs/contract/standard_keys.md
related_measurement_key ENUM: UNDERBUST|BUST|WAIST|HIP|THIGH|CIRCUMFERENCE|CHEST_LEGACY
Guard ref: .github/workflows/guard-sync-state.yml
Rule: This header block is canonical and must not be modified without explicit architect approval.
Rule: Golden dataset 재생성 시 NPZ 내부에 meta_unit='m' 및 schema_version 메타 키 포함을 필수 계약으로 정의한다.
---
### SYNC_HUB Update Triggers (운영 규칙, 매 PR 갱신 아님)
- 아래 중 하나라도 발생하면 해당 PR에 SYNC_HUB.md 업데이트를 포함한다.
- T1) Canonical header block 변경(Canonical path / Key dictionary / ENUM / Guard ref).
- T2) Standard Keys(추가/삭제/rename) 또는 Unit Standard(단위 m, 반올림/정밀도) 변경.
- T3) Contract 규칙 변경(입력 정규화 전제, NaN+warnings 정책, 허용 범위, Δ 테이블/Provenance).
- T4) Semantic 정의/금지 조건/Deprecated 승계 규칙 변경(예: CHEST legacy 의미/관계).
- T5) artifacts 인덱싱 규칙 변경(layer, related_measurement_key ENUM, extra_json 규칙).
- T6) guard-sync-state 또는 CI 가드의 감시 경로/동기화 조건 변경.
- T7) facts-driven triggers/운영 전환 규칙/Runbook 운용 규칙 변경.
- 그 외 구현/리팩터링/테스트 변경은 SYNC_HUB를 수정하지 말고 CURRENT_STATE에만 기록한다.


1. Project Overview \& Identity

Project: AI Fitting Engine

Mission: 사진 없이 신체 치수만으로 설명 가능하고 재현 가능한 3D 체형($\\beta$) 생성 엔진 구축

Core Principle: 6-Layer R\&D 파이프라인(Contract → Geometry → Production → Validation → Confidence → Application)의 엄격한 분리 및 지적 정직성(GIGO) 유지. Modules: body / garment / fitting. 레이어 간 코드 호출 금지(artifact-only) 원칙은 [docs/architecture/LAYERS_v1.md](docs/architecture/LAYERS_v1.md)를 SSoT로 참조합니다.

**Note**: "5-Layer"는 레거시 용어이며, 현재 원칙은 v1 6-layer 구조입니다.

**Architecture v1 고정**: Layer/Module 구조는 [docs/architecture/LAYERS_v1.md](docs/architecture/LAYERS_v1.md)를 SSoT로 합니다.

2. Milestone Achievements (누적 성과)

2. Milestone Achievements (누적 성과)

Current Milestone: curated_v0 Data Contract & Pipeline Stabilization v3 (Freeze Candidate)

Accomplishments (facts-only, high-level):
- SizeKorea 7th/8th(Direct/3D) 3-source 통합 파이프라인 구축: curated_v0.parquet 산출
- Contract(sizekorea_v2.json) exact-match 매핑 정리로 column_not_found=0 달성
- Sentinel 정책 정합성 확립: 8th_direct의 9999 dtype 무관 필터링 + SENTINEL_MISSING 스키마 정합
- 단위/스케일 조용한 오답 리스크를 "센서"로 표면화:
  - completeness_report 기반: ALL_NULL_BY_SOURCE, ALL_NULL_EXTRACTED, MASSIVE_NULL_INTRODUCED, RANGE_SUSPECTED
- 시스템 무결성 원칙 확정:
  - 특정 키 하드코딩 금지(if key == ... 금지)
  - “m 기대 컬럼 판별” 규칙을 단순 suffix(.endswith('_M'))가 아닌 패턴/토큰 기반으로 정본화


3. Terminology \& Standard Keys (Single Source of Truth)
   3.1 Standard Keys (Internal)

UNDERBUST\_CIRC\_M : 밑가슴/흉곽 둘레(구조 Anchor), meters

BUST\_CIRC\_M : 젖가슴 최대 둘레(볼륨), meters

**Standard Keys Dictionary**: See [docs/contract/standard_keys.md](docs/contract/standard_keys.md) for the complete authoritative list.

Contract: Coverage v0 (45 keys) now enumerated in docs/contract/standard_keys.md.

3.1.1 related_measurement_key ENUM Rule

See header block for ENUM definition. **Rule**: related_measurement_key must use domain tokens (UNDERBUST, BUST, etc.), not full standard keys (UNDERBUST_CIRC_M) or arbitrary strings.

3.2 Legacy Handling

기존 단일 정의였던 CHEST는 표준 키에서 제외(Deprecated) 한다.

과거 CHEST v0 산출물은 legacy reference로만 유지하며, 앞으로 가슴 계열은 UNDERBUST/BUST로만 표준화한다.
(즉, “CHEST = 표준 가슴”이라는 표현은 금지)

4. Current Status \& Active Strategy

4. Current Status & Active Strategy

Current Track: Track A (Data): Contract + curated_v0 Stabilization (Freeze -> Tag)

Strategic Direction:
- 파이프라인의 목적은 "정답을 만들기"가 아니라, 조용한 오답을 '경고/센서'로 드러내고 Contract로 봉인하는 것
- Contract는 exact match만 허용하며, 자동 유사매칭을 금지한다
- Unit canonicalization은 meters(m) 정본화이며, “m 기대 컬럼 판별”은 시스템 규칙(패턴/토큰 기반)으로만 결정한다

5. Bra Input Spec (MVP, Normative)
   5.1 Input Format

브라 사이즈 입력 표준: 문자열 "75A" 형식 (한국 사용자 친화)

5.2 Parsing Rule

"75A" →

band\_cm = 75

cup = 'A'

5.3 Allowed Range (MVP)

band\_cm: 65–90 (초기 운영 범위; 확장 가능)

cup: A–F (초기 운영 범위; 확장 가능)

5.4 Cup Delta Table (대표값, cm)

A: 10.0

B: 12.5

C: 15.0

D: 17.5

E: 20.0

F: 22.5

5.5 Computation (Unit-Consistent, meters)

UNDERBUST\_CIRC\_M = band\_cm / 100.0

BUST\_CIRC\_M = UNDERBUST\_CIRC\_M + (DELTA\_CM\[cup] / 100.0)

## Canonical Unit Standard
- Canonical unit for all measurements: **meters (m)**
- Precision target: **0.001 m (1 mm)** for reporting/exports
- Ingestion must normalize raw units (e.g., cm → m) and record provenance
- Reference: `docs/contract/UNIT_STANDARD.md`


6. Male Rule (Normative)

Male은 별도 키를 추가하지 않고 동일 키(UNDERBUST\_CIRC\_M, BUST\_CIRC\_M)를 사용한다.

다만 남성의 경우 Δ = (BUST - UNDERBUST)는 0에 가깝게 수축(≈0) 되도록 모델링/제약한다.
(큰 Δ가 관측되면 자동 보정하지 않고 Warning 신호로 기록)

7. Today’s Objective (Current Focus)

Objective: Bust/Underbust 이원화 체계의 Semantic \& Contract 논리 완결성 확보 + 키 맵핑 최신화

Key Tasks:

UNDERBUST\_CIRC\_M, BUST\_CIRC\_M에 대한 Semantic → Contract 문서 작성/정리

프로젝트 전체 Standard Key Mapping 업데이트(가슴 계열 우선)

legacy CHEST 관련 문서에서 Deprecated 처리 및 참조 관계 명시

Ops Hygiene (Backlog):

레포지토리 내 불필요한 레거시 README 및 중복 파일 정리 (핵심 작업 완료 후)

8. Operational Guardrails (AI Notes)

Do NOT: Validation 레이어에 판정 임계값(PASS/FAIL)을 넣지 말 것 (오직 사실 기록)

Do NOT: 시스템 재설계 제안 금지
Do NOT: tools/, db/, pipelines/, tests/, .github/workflows/ 및 측정 러너/검증 경로 변경 PR은 docs/sync/CURRENT\_STATE.md에 (a) changed\_paths, (b) 2~4줄 변경 요약을 반영하기 전에는 머지하지 말 것.
Focus on: 가슴 계열 이원화 정의의 논리적 완결성(Semantic \& Contract) + 키 표준화

Focus on: L4 Validation 산출물 경로는 verification/reports/<measurement\_key>\_v0/로 고정한다(예: validation\_summary.json은 warnings 기반 사실 기록 요약).

**Guard ref**: See header block for official definition location.

Do NOT:
- 특정 키 하드코딩(if key == '...')으로 문제를 숨기지 말 것
- Contract에 자동 유사매칭을 도입하지 말 것
- Validation 레이어에 PASS/FAIL 임계값을 직접 박지 말 것 (facts-only 신호 기록)

Must:
- pipelines/tests/.github/workflows/contract 변경 PR은 반드시 docs/sync/CURRENT_STATE.md facts-only 업데이트 동반
- 산출물 정책:
  - data/processed/**, verification/runs/** 는 커밋 금지(경로/명령만 기록)
  - golden NPZ는 재현 목적에 한해 allowlist로만 커밋 허용

8.1 Ops Contract (Memo)

SoT = `/SYNC_HUB.md`, 운영 신호 = `/docs/sync/CURRENT_STATE.md`. PR에 core/, tests/, verification/, tools/, db/, pipelines/, .github/workflows/ 변경이 포함되면 `docs/sync/CURRENT_STATE.md`를 같은 PR에 업데이트(guard-sync-state 준수). `.gitignore` 정책: `data/` 본문은 기본 ignore, 단 `data/README.md`는 track. `verification/runs/`는 항상 ignore(산출물 커밋 금지). `verification/datasets/**/*.npz`는 golden/재현 목적에 한해 커밋 허용(allowlist). facts output은 `verification/runs/facts/...` 경로에 저장하되 커밋 금지.

8.2 Semantic v0 Freeze Declaration

**Semantic v0 봉인 선언 (2026-01-24 기준)**:
- Semantic v0 이후 Geometric/Validation 이슈는 **Semantic을 수정**하지 않는다.
- 해결은 **metadata/provenance + facts-only validation 신호**로만 흡수한다.
- auto substitution 금지 원칙 유지.
- 변경이 필요하면 **Semantic v1**로 새 문서/새 태그로만 진행한다.

Reference: `docs/semantic/measurement_semantics_v0.md` (Freeze Declaration 섹션 참조)

8.3 Round 13: S0 FAST MODE + Scale Persisted + Runner E2E Success

**Round 13 Facts (2026-01-25)**:
- S0 synthetic dataset 생성기에 FAST MODE 추가 (`--only-case` / `ONLY_CASE` env var)
- Scale normalization이 NPZ에 실제로 반영됨 (re-open proof 통과)
- Runner가 NPZ 로드/처리/리포트 저장까지 성공 (e2e 통과)
- Valid case 1개 (normal_1) 기준: HEIGHT_M median=1.710m, WAIST/HIP width/depth NaN율=0%, slice sharing=100%
- Expected fail cases 5개 정상 포함 및 처리됨

Reference: `reports/validation/geo_v0_facts_round13_fastmode_normal1_runner.md`

8.4 Golden S0 (Round17 Freeze)

**Round17 완료 (2026-01-25)**:
- Valid ≥10 (normal_1~5, varied_1~5), expected_fail 5 유지. No clamp.
- **Tag**: `golden-s0-v0.1` | **Commit**: `cc15544` | **날짜**: 2026-01-25
- **원칙**: 이후 이슈는 **generator를 수정하지 않고** metadata/provenance/validation으로 처리한다.
- **Next step**: curated_v0 실데이터로 runner 교체 준비.

Reference: `docs/verification/golden_s0_freeze_v0.md`, `reports/validation/geo_v0_facts_round17_valid10_expanded.md`

9. Provenance

Snapshot Tag: snapshot-20260122-bust-underbust-mvp1

Commit (main HEAD): 9b7ef4a9539e051d43b8e95ed8e1bd6d35845fa0

### 🚀 Operations & Validation History

| Round | Lane | Baseline Alias | Status | Key Artifacts |
| :--- | :--- | :--- | :--- | :--- |
| **Round 20** | `curated_v0` | `curated-v0-realdata-v0.1` | ✅ Finalized | KPI, KPI_DIFF, LINEAGE, Registries (Visual: Skip) |

10. Sealed Anchors (v1)- Ops Plane is sealed at tag `opsplane-v1` (merge commit `a80aec0`).
- Architecture v1 is sealed at tag `arch-v1` (merge commit `9166fe4`).
- Structural changes require v2 docs addition only (do not edit v1).
- Round notes are added only via `docs/ops/rounds/roundXX.md` (append-only).