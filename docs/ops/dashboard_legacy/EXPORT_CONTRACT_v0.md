# Export Contract v0 — Labs Exports Surface

**Status**: CANONICAL
**Created**: 2026-01-29
**Purpose**: Labs(fitting_lab, garment_lab 등)가 중앙 Hub(ai_model)에 제공해야 하는 exports 표면 계약

---

## 1. Overview

Dashboard는 **렌더 결과물**이며, 사람이 직접 편집하지 않는다.
진행률 데이터는 각 Lab의 exports 디렉토리에서 수집하여 집계한다 (수집 방식: §5 Bootstrap vs Automated 참조).

### Canonical Sources (SSoT Pack v1)

All milestone/module semantics come from SSoT Pack v1. This file defines export mechanics only (facts-only).

| ID | Document | Path |
|----|----------|------|
| S1 | Body Module Plan v1 | `docs/plans/Body_Module_Plan_v1.md` |
| S2 | Fitting Module Plan v1 | `docs/plans/fitting_module_plan_v1.md` |
| S3 | Garment Product Contract v0.9-revC | `docs/plans/garment_Product Contract v0.9-revC.md` |
| S4 | Unlock Conditions u1/u2 | `docs/plans/unlock_conditions_u1_u2.md` |
| S5 | Phase Plan (Unlock-driven) | `docs/plans/phase_plan_unlock_driven.md` |

### Cross-Module Interface Contracts

- `contracts/interface_ledger_v0.md` — cross-module artifact interface SSoT
- `contracts/port_readiness_checklist_v0.md` — port safety checklist

---

## 2. Lab Exports Surface (v0, Canonical)

본 프로젝트는 3개 작업 폴더(hub, fitting_lab, garment_lab)가 **동일한 exports 표면**을 가진다.
대시보드/브리프 자동화는 이 exports 표면만을 읽고/쓴다. (레거시 문서/경로 추론 금지)

### 2.1 Canonical Paths (모든 폴더 공통)

#### A. Progress Log (append-only)
- Path: `exports/progress/PROGRESS_LOG.jsonl`
- Mode: **append-only** (기존 라인 수정 금지)
- Content: 1 line = 1 JSON object (compact single-line)
- Missing policy: 없으면 생성 가능. 실패 시에도 crash 금지(경고만).

#### B. Work Brief (generated-only)
- Path: `exports/brief/<MODULE>_WORK_BRIEF.md`
  - `<MODULE>` ∈ {`BODY`, `FITTING`, `GARMENT`}
- Mode: **generated-only** (사람/에이전트 수동 편집 금지)
- Producer: Hub 자동화(브리프 렌더러)가 갱신한다.
- Missing policy: 폴더 없으면 생성 가능. 실패 시에도 crash 금지(경고만).

### 2.2 Cross-folder Write Boundary (중요)

Hub(AI_model)가 **외부 폴더(fitting_lab, garment_lab)**에 쓸 수 있는 유일한 경로는:
- `exports/brief/**` 아래로 제한한다.

Progress Log(`exports/progress/PROGRESS_LOG.jsonl`)는 각 폴더에서 자신의 이벤트를 append하는 것이 원칙이며,
Hub는 기본적으로 읽기만 수행한다. (예외가 필요하면 별도 계약 버전업)

### 2.3 Facts-only
본 exports 표면은 PASS/FAIL을 포함하지 않는다.
상태는 UNLOCKED/BLOCKED, remaining DoD count, evidence paths 등 facts-only로만 표현한다.

---

## 3. Fixed Paths (고정 경로)

모든 Lab은 아래 경로 구조를 준수해야 한다.

### 3.1 Required (필수)

```
<lab_root>/exports/progress/PROGRESS_LOG.jsonl
```

- **형식**: JSON Lines (append-only)
- **규칙**: 각 줄은 독립된 JSON 객체, 한 번 기록된 줄은 수정/삭제 금지
- **인코딩**: UTF-8
- **줄바꿈**: LF (`\n`)

### 3.2 Optional (선택)

```
<lab_root>/exports/progress/PROGRESS_SNAPSHOT.json
```

- 최신 집계 상태를 single JSON으로 제공 (렌더러 성능 최적화용)
- Lab이 자체적으로 생성/갱신 가능
- 렌더러 구현 시, PROGRESS_LOG.jsonl만으로 동작 가능해야 함 (snapshot 부재 허용)

### 3.3 Release Evidence (선택, 포트 시)

```
<lab_root>/exports/releases/<lane>_<YYYYMMDD>_<HHMMSS>/
```

- 포트 증거가 필요한 경우에만 생성
- 경로 형식은 port_readiness_checklist_v0.md §3.1 준수
- **참고**: port_readiness_checklist_v0.md §3.1의 `releases/` 경로는 lab 내부 기준. export 계약의 `exports/releases/`는 exports 표면 내부 경로이며, lab 내부 `releases/`와는 독립된 사본 위치.
- 예시: `exports/releases/fitting_v0_20260129_143000/`

---

## 4. PROGRESS_LOG.jsonl Event Schema

### 4.1 Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ts` | string (ISO 8601) | Yes | 이벤트 발생 시각, UTC 권장. 예: `"2026-01-29T14:30:00Z"` |
| `lab` | string | Yes | Lab 식별자. 예: `"fitting_lab"`, `"garment_lab"` |
| `module` | string | Yes | 모듈명. `"body"`, `"fitting"`, `"garment"` 중 하나 |
| `step_id` | string | Yes | PLAN_v0.yaml에 정의된 step ID. 예: `"F01"`, `"B02"` |
| `dod_done_delta` | integer | Yes | 이 이벤트로 완료된 DoD item 수 (양수만 허용, 분자 증가분) |
| `dod_total` | integer | Yes | 해당 step의 DoD 총 item 수 (분모, PLAN_v0.yaml과 일치해야 함) |
| `evidence_paths` | array of string | Yes | 완료 증거 파일 경로 목록 (최소 1개). 빈 배열 `[]` 금지 |
| `rid` | string | No | Round ID. interface_ledger_v0.md §4.3 형식 권장 |
| `note` | string | No | 자유 형식 메모 (사람 가독용) |

### 4.2 Field Constraints

- `dod_done_delta` >= 1 (0 이벤트는 기록하지 않음)
- `dod_total`은 PLAN_v0.yaml의 해당 step.dod.total과 동일해야 함
- `evidence_paths`는 최소 1개 경로 포함 (Evidence-first 원칙)
- `ts`는 시간순 append만 허용 (과거 시점 삽입 금지)

### 4.3 Examples

**Example 1**: fitting_lab에서 F01 step의 DoD item 1개 완료

```json
{"ts":"2026-01-29T14:30:00Z","lab":"fitting_lab","module":"fitting","step_id":"F01","dod_done_delta":1,"dod_total":3,"evidence_paths":["docs/contract/fitting_interface_v0.md"],"rid":"fitting_v0_facts__M01_baseline__r01","note":"fitting_interface_v0.md ported to main"}
```

**Example 2**: fitting_lab에서 F02 step의 DoD item 2개 동시 완료

```json
{"ts":"2026-01-29T15:00:00Z","lab":"fitting_lab","module":"fitting","step_id":"F02","dod_done_delta":2,"dod_total":2,"evidence_paths":["modules/fitting/runners/run_fitting_v0_facts.py","modules/fitting/specs/fitting_manifest.schema.json"],"note":"runner + schema ported"}
```

---

## 5. PROGRESS_SNAPSHOT.json Structure (Optional)

렌더러 성능 최적화를 위한 선택적 집계 파일.

### 5.1 Schema

```json
{
  "snapshot_ts": "2026-01-29T15:00:00Z",
  "lab": "fitting_lab",
  "steps": {
    "F01": {
      "dod_done": 2,
      "dod_total": 3,
      "last_event_ts": "2026-01-29T14:30:00Z"
    },
    "F02": {
      "dod_done": 0,
      "dod_total": 2,
      "last_event_ts": null
    }
  }
}
```

### 5.2 Rules

- `dod_done`은 해당 step의 PROGRESS_LOG.jsonl 이벤트에서 `dod_done_delta`를 누적 합산한 값
- `dod_done` > `dod_total`이 되면 안 됨 (렌더러에서 경고 표시)
- snapshot은 PROGRESS_LOG.jsonl에서 재계산 가능해야 함 (snapshot ≠ SSoT, log가 SSoT)

---

## 6. Bootstrap vs Required DoD

### Mode 1: Bootstrap (현재, 수동 호환)

- Lab이 PROGRESS_LOG.jsonl을 수동으로 작성 가능
- 중앙 Hub로의 데이터 전달은 수동 복사(copy-paste) 허용
- 렌더러는 로컬 파일 경로에서 직접 읽기
- **이 모드에서도 PROGRESS_LOG.jsonl의 스키마와 append-only 규칙은 반드시 준수**

### Mode 2: Automated Collection (운영 DoD, 다음 라운드 구현 예정)

- LAB_SOURCES_v0.yaml에 정의된 경로에서 자동 수집
- 수집 스크립트가 PROGRESS_LOG.jsonl을 읽어 중앙 집계
- PROJECT_DASHBOARD.md 자동 렌더링
- **이 모드가 운영 DoD이며, Mode 1은 Bootstrap 과도기 허용**

---

## 7. Non-Goals (금지 사항)

- Dashboard는 **렌더 결과물**이다. 사람이 직접 편집하지 않는다.
- PROGRESS_LOG.jsonl에 PASS/FAIL 판정을 넣지 않는다 (facts-only).
- threshold/clamp 값을 exports에 포함하지 않는다.
- 자동 backfill 금지. 수동 backfill 시 BACKFILL_LOG.md 기록 필수.
- Canon 규칙(interface_ledger_v0.md)을 재발명하지 않고 참조한다.

---

## 8. Helper Tool (optional): append_progress_event_v0

Canonical path: `tools/append_progress_event_v0.py`

이벤트 기록 편의 도구. 계약 정본은 §3 PROGRESS_LOG.jsonl 스키마이며, 이 도구는 부가 편의 수단.

```bash
# fitting_lab에서 (CWD = fitting_lab/)
py ../AI_model/tools/append_progress_event_v0.py \
  --lab fitting_lab --module fitting --step-id F01 \
  --dod-done-delta 1 --dod-total 3 \
  --evidence-path docs/contract/fitting_interface_v0.md

# AI_model에서 hub body 이벤트
py tools/append_progress_event_v0.py \
  --log-path exports/progress/PROGRESS_LOG.jsonl \
  --lab hub --module body --step-id B01 \
  --dod-done-delta 2 --dod-total 3 \
  --evidence-path docs/contract/standard_keys.md \
  --evidence-path docs/contract/UNIT_STANDARD.md

# AI_model에서 garment_lab 대상
py tools/append_progress_event_v0.py \
  --lab-root C:/path/to/garment_lab \
  --lab garment_lab --module garment --step-id G01 \
  --dod-done-delta 1 --dod-total 2 \
  --evidence-path garment_schema.json
```

---

## 9. Appendix: File Tree Example

```
fitting_lab/
  exports/
    progress/
      PROGRESS_LOG.jsonl          # Required (append-only)
      PROGRESS_SNAPSHOT.json      # Optional
    releases/
      fitting_v0_20260129_143000/ # Optional (port evidence)
        run_fitting_v0_facts.py
        fitting_manifest.schema.json
        fitting_interface_v0.md
```
