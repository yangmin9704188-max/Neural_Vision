# Notion Sync v1 (ops)

## 목적
`ops/hub_events_v1.jsonl`에 기록된 **UNLOCKED** 이벤트를 Notion DB에 반영한다.  
대시보드/렌더(`render_hub_state.py`)는 Notion을 호출하지 않으며, 연동은 **tools/ops/notion_sync.py** 단일 스크립트로만 수행한다.  
실패해도 레포 운영이 깨지지 않는다(FAIL 금지, warn-only).

---

## Notion 연동 준비

1. **Notion Integration 생성**
   - [Notion Developers](https://www.notion.so/my-integrations)에서 새 Integration 생성.
   - Capabilities: Read content, Update content, Insert content.
   - Internal Integration Token 복사.

2. **DB 공유**
   - 연동할 Notion DB 페이지를 열고, 우측 상단 `...` → **Connections** → 방금 만든 Integration 추가.
   - DB URL에서 `database_id` 추출: `https://www.notion.so/xxxxx?v=yyy` → `xxxxx` 부분(32자 hex).

3. **DB 속성**
   - 다음 컬럼이 있다고 가정(이름은 `ops/notion.local.json`에서 override 가능):
     - **Plan ID** (Rich text)
     - **Status** (Status) — 값 예: Done
     - **Target Agent** (Rich text)
     - **LLM Briefing Path** (Rich text)
     - **Last Sync** (Date, optional)
     - **Last Event ID** (Rich text, optional)

---

## 로컬 설정

1. **ops/notion.local.json** (gitignore, 커밋 금지)
   - `ops/notion.local.json.example`을 복사해 `ops/notion.local.json` 생성.
   - `token`: Notion Integration Token.
   - `database_id`: DB ID (32자).
   - `properties`: 컬럼명이 다르면 여기서 매핑.

2. **실행**
   ```bash
   py tools/ops/notion_sync.py
   ```
   - `hub_events_v1.jsonl`에서 `event_type=="UNLOCKED"`만 읽음.
   - `ops/notion_sync_cursor.json`으로 마지막 처리 라인 저장 → 새 이벤트만 처리.
   - `contracts/master_plan_v1.json`의 `unlocks[].maps_to_plan_ids`로 unlock_id → Plan ID 매핑.
   - 해당 Plan ID row를 찾아 Status=Done, Target Agent, LLM Briefing Path, Last Sync, Last Event ID 업데이트.

3. **실패 시**
   - 스크립트는 항상 exit 0. 오류는 stderr에 경고만 출력.
   - **대시보드/렌더(render_hub_state, render_status, render_work_briefs)에는 영향 없음.**

---

## 자동 실행 순서 (로컬 권장)

문서상 권장 순서만 안내한다. 실제 `ops/local/ops_refresh.ps1` 등은 로컬에서 직접 유지(gitignore).

1. `py tools/render_work_briefs.py`
2. `py tools/render_status.py`
3. `py tools/ops/render_hub_state.py`
4. `py tools/ops/notion_sync.py`

---

## 참고

- 이벤트 형식: `{ts, event_type:"UNLOCKED", unlock_id, module, target_agent, brief_path}`.
- 판단 로직 정본: `contracts/master_plan_v1.json` (Notion sync는 매핑만 사용).
