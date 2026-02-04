# DoD Claim Protocol v1 (LOCKED)

## 0. Purpose
DoD 달성(Progress Log의 dod_done_delta > 0)은 “사실 기록”이 아니라,
**증거 기반의 완료 주장(Claim)** 이다.
따라서 에이전트는 불완전/추정/선언만으로 DoD를 올릴 수 없다.

본 문서는 모든 에이전트(Cursor/Claude/Anti-gravity)가 반드시 따라야 하는
**DoD Claim(완료 주장) 잠금 규약**이다.

---

## 1. Canonical Inputs (SSoT)
- Mechanical Plan (DoD 정의/개수/증거 요구): `docs/ops/dashboard/PLAN_v0.yaml`
- Progress Log (append-only): `exports/progress/PROGRESS_LOG.jsonl`
- Dashboard Renderer: `tools/render_dashboard_v0.py`
- Work Brief Renderer: `tools/render_work_briefs_v0.py`
- Work Brief Publisher (labs): `tools/publish_work_briefs_v0.py` (있는 경우)

**중요:** DoD의 “정의/증거 요구”는 PLAN_v0.yaml이 정본이다. 다른 문서는 참고로만 취급한다.

---

## 2. Definitions
### 2.1 DoD Item
PLAN_v0.yaml에 정의된 최소 단위 체크포인트.
각 DoD item은 반드시 `Evidence:` 필드를 가진다. (파일 경로 또는 경로 집합)

### 2.2 Evidence-Complete Claim
어떤 DoD item을 “완료”로 주장하려면, 아래 조건을 **모두** 만족해야 한다.

---

## 3. HARD RULES (LOCKED)
### 3.1 No-Evidence, No-Claim
에이전트는 **증거 파일이 실제로 존재하지 않으면** 절대 `dod_done_delta > 0` 이벤트를 기록하지 않는다.

### 3.2 Evidence Matching Must Be Exact
DoD item의 `Evidence:`에 나열된 경로(들)는 “가이드”가 아니라 “요구사항”이다.
- 요구된 evidence 경로가 2개 이상이면, **모두** 존재해야 claim 가능.
- 경로가 바뀌었으면: 먼저 PLAN_v0.yaml을 업데이트(계약 변경)해야 한다. (추론으로 대체 금지)

### 3.3 Commit/PR 여부와 무관
DoD Claim은 Git 상태(커밋/PR)와 무관하게 가능하나,
**증거 파일의 존재**와 **경로 일치**만으로 결정된다. (PASS/FAIL, threshold 판단 금지)

### 3.4 Claim-Only Delta
`dod_done_delta`는 “작업량”이 아니라 “완료된 DoD 개수”만 의미한다.
- 부분 진행(예: 30% 했음) → `dod_done_delta`는 0이어야 한다.
- 부분 진행은 `note`로만 남기고, evidence_paths는 “존재하는 것”만 기록한다.

### 3.5 Facts-only 유지
DoD Claim 프로토콜은 엄격하되, 결과 표기는 facts-only로만 한다.
- PASS/FAIL 문구 금지
- 품질 평가는 금지
- “존재/미존재, 경로, 파일명, 커맨드 실행 사실”만 기록

---

## 4. Claim Procedure (Agent Checklist)
DoD Claim(= dod_done_delta > 0)을 기록하기 전, 에이전트는 아래를 수행한다.

1) PLAN 확인  
- 해당 step_id의 DoD item과 Evidence 경로를 확인한다.

2) Evidence 존재 확인 (필수)  
- Evidence로 요구된 모든 파일 경로가 실제로 존재하는지 확인한다.
- 확인 방법은 shell/PS 어디든 무방하나, “존재 사실”을 note에 남길 수 있어야 한다.

3) Progress Event append (단 1줄 JSONL)  
- evidence_paths에는 **요구된 Evidence 경로를 포함**해야 한다.
- 증거가 여러 개면 배열로 모두 기록한다.
- 증거가 부족하면 delta를 올리지 않는다.

4) (권장) ops 갱신  
- hub에서는 `update_ops_v0.py` (또는 동등한 wrapper)를 실행해 dashboard/brief를 갱신한다.

---

## 5. Event Schema Requirements (minimal)
Progress Log 이벤트는 다음 키를 반드시 포함한다.
- lab, module, step_id, dod_done_delta, dod_total, evidence_paths
선택 키: rid, note, ts(없으면 ingest/append 단계에서 생성 가능)

---

## 6. Violation Handling (facts-only)
에이전트가 evidence 없이 delta를 올리려 한다면:
- delta를 올리지 말고,
- note에 “EVIDENCE_MISSING: <path>” 형태로 기록(사실만)한다.
(시스템은 이를 경고로 표시할 수 있으나, PASS/FAIL 판정은 금지)

---
