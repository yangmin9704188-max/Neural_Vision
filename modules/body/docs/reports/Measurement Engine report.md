# REPORT: Measurement Engine (VTM/Geo) — 왜 필요한가, 무엇을 구해야 하는가 (A-method / 384 prototypes)

## 0) 목적(한 줄)
**한국인 12,000명 측정치(45 keys)를 384개 대표체형으로 요약하고, 각 대표체형을 SMPL-X shape 파라미터(β)로 변환**하여,
온라인에서는 “입력 측정치 → 가장 가까운 prototype 선택 → β로 메쉬 생성”을 결정론적으로 수행한다.

---

## 1) 전제: 우리가 하려는 방식은 A-method (384회만 최적화)
### A-method (권장)
1) 12,000명 → 384 bins (sex × height_bin × BMI_bin × age_bin)
2) bin별 측정치 centroid(robust median/trimmed mean) 생성
3) centroid(측정치 벡터) → SMPL-X β를 **384번만** 최적화해서 확보
4) 서비스(온라인): 고객 입력 측정치 x → prototype centroid와 거리 최소인 prototype 선택 → 해당 β로 메쉬 생성

### 왜 A-method인가
- “개인별 β(12,000개)”는 목표가 아님(운영/연산/실패모드 폭증)
- 384 prototypes는 B2B/PoC/MVP에서 충분한 표현력을 제공할 가능성이 높고,
- 잔차(residual) 패턴을 근거로 Δ(보정) 또는 basis 재학습 등 다음 단계 필요성을 ‘사실’로 판정할 수 있음.

---

## 2) 핵심 오해 정리: β(베타)는 “허리/키 슬라이더”가 아니다
SMPL-X에서 β는 **shape basis(블렌드쉐이프)들의 선형 결합 가중치**이다.
- β_i 하나가 “허리 +3cm” 같은 의미론적 노브가 아니다.
- 따라서 “우리 데이터의 허리둘레를 맞추려면”, 메쉬에서 허리둘레를 측정하는 연산자(=측정엔진)가 필요하다.

---

## 3) Measurement Engine(VTM/Geo)의 역할 3가지
### (R1) 최적화 정의를 가능하게 한다 (m(β) 제공)
목표 측정치 벡터 m̂(centroid)가 있을 때, β를 찾는 최적화는 아래를 최소화하는 문제다:
- loss = Σ_k w_k * ρ( m_k(β) − m̂_k ) + λ ||β||^2
여기서 m_k(β)는 **SMPL-X 메쉬에서 해당 부위를 어떻게 재는지**에 의해 결정된다.
즉, 측정엔진이 없으면 최적화 자체가 정의되지 않는다.

### (R2) “키 선택(K_fit)”을 감이 아니라 facts로 확정한다
측정엔진이 있어야, 각 키에 대해 다음을 기록할 수 있다:
- null rate / NaN rate
- 분포 폭(폭주 여부)
- 실패 reason / warning 코드 Top N
이 facts가 쌓여야 “어떤 키를 β 피팅에 넣는 게 안전한가(K_fit)”가 결정된다.

### (R3) 회귀/드리프트를 KPI/KPI_DIFF로 잡는 안전망이다
측정엔진이 고정되면, 엔진 변경/업데이트 시:
- 키별 잔차 분포 변화
- 결측률 변화
- 경고 패턴 변화
를 KPI_DIFF로 추적할 수 있고, “조용한 품질 붕괴”를 막는다.

---

## 4) 무엇을 구해야 하나 (산출물 명세: 오프라인/온라인)
### 4.1 오프라인에서 반드시 구해야 하는 것 (A-method)
#### (A) 384 centroid 측정치 (측정치-space 대표)
- prototype_id (sex/height_bin/BMI_bin/age_bin)
- centroid vector (선택된 K_fit + 필요 시 K_eval)
- per-key coverage stats (present_count / null_count)
- centroid 생성 방식: median 또는 trimmed mean (outlier에 강함)

#### (B) 384 prototype β (SMPL-X shape params) + residuals
- prototype_id → betas (β vector)
- scale 파라미터(선택): HEIGHT는 보통 β로 억지로 맞추기보다 scale로 분리 권장
- residuals: r_k = m_k(β) − m̂_k
- facts: key별 residual 분포, warning 카운트, 실패 reason

#### (C) 리포트/증거(“죽지 않는 facts”)
- facts_summary.json (counts/coverage/warnings/residual stats)
- KPI.md / KPI_DIFF.md / LINEAGE.md
- artifacts/*.jsonl (skip reasons, exec failures 등)

### 4.2 온라인에서 수행할 것 (서비스)
- 입력: 고객 측정치 x (일부 키만 들어와도 됨)
- 1차 선택: x와 prototype centroid 간 거리(측정치-space NN)
  - β-space NN은 의미가 불명확하므로 기본은 측정치-space 권장
- 출력: 선택된 prototype의 betas(+scale)로 SMPL-X mesh 생성
- (옵션) 온라인 미세보정: prototype β에서 몇 step만 추가 최적화(운영 리스크 있으므로 2단계)

---

## 5) “어디까지 측정엔진을 개발해야 하나”를 결정하는 원칙
측정엔진은 45키 “완성”이 목표가 아니라,
**A-method의 β 최적화를 안정적으로 돌릴 수 있는 최소 키 세트(K_fit)를 먼저 고정**하는 것이 목표다.

### 5.1 K_fit (β 최적화에 실제로 사용하는 키) — 최소/안정 우선
#### K_fit-MVP (권장 10개)
- HEIGHT_M  (※ 가능하면 scale로 처리; 그래도 measurement로 관측은 함)
- BUST_CIRC_M, WAIST_CIRC_M, HIP_CIRC_M
- CHEST_WIDTH_M, CHEST_DEPTH_M
- WAIST_WIDTH_M, WAIST_DEPTH_M
- HIP_WIDTH_M, HIP_DEPTH_M

**의미**
- 3대 둘레만으로는 단면 형태가 모호하므로 width/depth를 같이 넣어 수렴 안정성을 높인다.
- 이 10개가 안정하면 384회 β 최적화 실험을 실행할 수 있다.

### 5.2 K_eval (품질 감시/드리프트 탐지용) — 나중에 승격 가능
- underbust/abdomen/navel 계열은 다음 우선순위(토르소 확장, 가성비 좋음)
- 어깨/팔/길이계열은 포즈/랜드마크 민감도가 높아 초기에는 K_eval로 두는 게 안전

---

## 6) “정확도”보다 먼저 필요한 것: 결정론/안정성
A-method에서 초기 측정엔진의 성공 조건은 “인체공학적 완벽”이 아니라:
1) 같은 입력 메쉬(β/pose/scale)가 들어오면 같은 값이 나온다 (deterministic)
2) β가 조금 바뀌어도 측정치가 폭주하지 않는다 (stable/continuous-ish)
3) 실패해도 죽지 않고 null/warnings/facts_summary를 남긴다 (never-die facts)

---

## 7) 최적화 실험(384회)로 무엇을 판단하는가
K_fit-MVP로 384 centroid → β 최적화(384회)를 실행하면, 아래가 “사실”로 나온다:
- prototype별 residual norm 분포
- key별 residual 분포(어떤 키가 지속적으로 한쪽 방향으로 남는지)
- 일관된 잔차 패턴(예: 하체/머리/어깨 계열이 계속 틀어짐)

판단 규칙(개념)
- 특정 키군이 시스템적으로 남으면:
  - (가설1) 측정 정의(semantic)가 데이터와 불일치
  - (가설2) SMPL-X shape basis 표현력 부족 → Δ 보정 레이어 필요
이 판단은 감이 아니라 residual 패턴으로 한다.

---

## 8) 레포/운영 철학과의 정합(요약)
- 정본 문서: ops/HUB.md + ops/STATUS.md
- 계약/스키마: contracts/**
- data/, exports/는 로컬 전용
- verification/**는 shim으로만 흡수(부활 금지)
- PASS/FAIL 금지, facts-only 신호로 다음 행동을 제안

이 보고서는 위 철학을 유지하면서,
측정엔진을 “왜/어디까지” 개발해야 하는지를 A-method에 맞게 고정한다.

---

## 9) 다음 액션(권장 순서)
1) K_fit-MVP(10키) 측정 안정화(P0): 폭주/NaN/불연속 failure mode 감소 + debug/facts 표준화
2) 384 centroid 생성(robust) + β 최적화(384회) 실행
3) residual 패턴 리포트 생성 → K_fit 승격/보류 결정
4) 필요 시 Δ(보정) 레이어 검토 (basis 재학습은 마지막)

(끝)
