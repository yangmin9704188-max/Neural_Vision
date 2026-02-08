#!/usr/bin/env python3
"""
Neural Vision Master Plan → Notion DB 생성 및 플랜 데이터 입력.
.env의 NOTION_TOKEN, PAGE_ID 사용. Notion API 2025-09-03.
"""
from __future__ import annotations

import os
import sys

# Load .env - 프로젝트 루트의 .env (절대 경로)
try:
    from dotenv import load_dotenv
    _env_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
    load_dotenv(_env_path, encoding="utf-8-sig", override=True)
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("requests 패키지가 필요합니다: pip install requests")
    sys.exit(1)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"

# Neural Vision Master Plan 데이터 (플랜 데이터)
MASTER_PLAN_DATA = [
    {"태스크 명": "Manifest Schema v1 고정", "phase": 0, "step": 1, "module": ["Common"], "scope": "Global", "touched_paths": ["contracts/"], "gate_level": "None", "dod": "geometry_manifest.json 필수 필드 및 스키마 문서화 완료"},
    {"태스크 명": "Manifest Validator 구현", "phase": 0, "step": 1, "module": ["Common"], "scope": "Global", "touched_paths": ["tools/"], "gate_level": "None", "dod": "1. Validator가 0/1 exit code 반환  2. created_at 변경에도 fingerprint 동일 테스트 통과"},
    {"태스크 명": "Body U1 산출물 규격 고정", "phase": 0, "step": 2, "module": ["Body"], "scope": "Local", "touched_paths": ["contracts/"], "gate_level": "Soft", "dod": "body_measurements_subset.json (unit=m, PZ1, 3키 필수, NaN 금지)"},
    {"태스크 명": "Body subset 파서 구현", "phase": 0, "step": 2, "module": ["Fitting"], "scope": "Local", "touched_paths": ["modules/fitting/"], "gate_level": "Degraded", "dod": "결측 발생 시 degraded_state 및 warnings_summary 기록 골격 마련"},
    {"태스크 명": "Garment U1 산출물 규격 고정", "phase": 0, "step": 3, "module": ["Garment"], "scope": "Local", "touched_paths": ["contracts/"], "gate_level": "Hard", "dod": "meta/manifest 항상 생성, glb/npz 경로 규칙, fingerprint 포함 정의"},
    {"태스크 명": "Garment 입력 우선순위 로직", "phase": 0, "step": 3, "module": ["Fitting"], "scope": "Local", "touched_paths": ["modules/fitting/"], "gate_level": "Hard", "dod": "npz > glb+meta fallback 구현 및 garment_input_path_used 기록"},
    {"태스크 명": "Garment Hard Gate 플래그 구현", "phase": 0, "step": 3, "module": ["Garment"], "scope": "Local", "touched_paths": ["modules/garment/"], "gate_level": "Hard", "dod": "negative_face_area_flag, self_intersection_flag meta 기록"},
    {"태스크 명": "Fitting Fast-Fail 구현", "phase": 0, "step": 3, "module": ["Fitting"], "scope": "Local", "touched_paths": ["modules/fitting/"], "gate_level": "Hard", "dod": "Hard Gate 감지 시 즉시 early_exit=true 및 사유 기록"},
    {"태스크 명": "레거시 파라미터 0회 달성", "phase": 0, "step": 4, "module": ["Common"], "scope": "Global", "touched_paths": ["modules/"], "gate_level": "None", "dod": "rg 검색 시 garment_template_params 언급 0줄 확인"},
    {"태스크 명": "Smoke-3(결측) 시나리오 생산", "phase": 1, "step": 1, "module": ["Body"], "scope": "Local", "touched_paths": ["verification/"], "gate_level": "Degraded", "dod": "Case A(1개 null), Case B(2개+ null) 재현 fixture 생성"},
    {"태스크 명": "Smoke-2(Hard Gate) 시나리오 생산", "phase": 1, "step": 2, "module": ["Garment"], "scope": "Local", "touched_paths": ["verification/"], "gate_level": "Hard", "dod": "Hard Gate 플래그가 포함된 meta fixture 상시 생성"},
    {"태스크 명": "Fingerprint 결정론 체크 고정", "phase": 1, "step": 3, "module": ["Common"], "scope": "Global", "touched_paths": ["tools/"], "gate_level": "None", "dod": "대상(Body subset, Garment meta, Manifest)의 canonicalize 규칙 고정"},
    {"태스크 명": "Fitting Smoke-1 (정상) E2E", "phase": 2, "step": 1, "module": ["Fitting"], "scope": "Local", "touched_paths": ["runs/"], "gate_level": "None", "dod": "정상 종료 확인 및 facts_summary.json 생성"},
    {"태스크 명": "Fitting Smoke-2 (Hard Gate) E2E", "phase": 2, "step": 2, "module": ["Fitting"], "scope": "Local", "touched_paths": ["runs/"], "gate_level": "Hard", "dod": "early_exit=true 기록 및 루프 없이 즉시 종료 확인"},
    {"태스크 명": "Fitting Smoke-3 (결측) E2E", "phase": 2, "step": 3, "module": ["Fitting"], "scope": "Local", "touched_paths": ["runs/"], "gate_level": "Degraded", "dod": "null 개수에 따른 degraded_state 정확도 검증"},
    {"태스크 명": "Online Inference & Telemetry", "phase": 3, "step": 1, "module": ["Body"], "scope": "Local", "touched_paths": ["modules/body/"], "gate_level": "None", "dod": "p95 latency 및 VRAM 예산 관측 가능 상태"},
    {"태스크 명": "Swatch & Reprocessing Loop", "phase": 3, "step": 2, "module": ["Garment"], "scope": "Local", "touched_paths": ["modules/garment/"], "gate_level": "Soft", "dod": "이물질 탐지 및 소재 데이터 재가공 루프 안정화"},
    {"태스크 명": "SDF Bank & Budget Enforcement", "phase": 3, "step": 3, "module": ["Fitting"], "scope": "Local", "touched_paths": ["modules/fitting/"], "gate_level": "Hard", "dod": "SDF 캐시 및 3.0s 지연시간 상한 강제"},
    {"태스크 명": "Round Close & KPI 안정화", "phase": 3, "step": 4, "module": ["Common"], "scope": "Global", "touched_paths": ["ops/"], "gate_level": "None", "dod": "라운드 마감 자동화 및 KPI_DIFF 회귀 추적 안정화"},
]


def get_headers():
    token = os.environ.get("NOTION_TOKEN")
    page_id = os.environ.get("PAGE_ID")
    if not token:
        raise SystemExit(".env에 NOTION_TOKEN이 필요합니다.")
    if not page_id:
        raise SystemExit(".env에 PAGE_ID(부모 페이지 ID)가 필요합니다.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }, page_id


def create_database(headers: dict, page_id: str) -> dict:
    """Neural Vision Master Plan DB 생성. (Status 타입은 API 미지원으로 Select 사용)"""
    body = {
        "parent": {"type": "page_id", "page_id": page_id},
        "title": [{"type": "text", "text": {"content": "Neural Vision Master Plan"}}],
        "initial_data_source": {
            "properties": {
                "태스크 명": {"title": {}},
                "Phase": {"number": {"format": "number"}},
                "Step": {"number": {"format": "number"}},
                "Module": {
                    "multi_select": {
                        "options": [
                            {"name": "Common", "color": "blue"},
                            {"name": "Body", "color": "green"},
                            {"name": "Garment", "color": "purple"},
                            {"name": "Fitting", "color": "orange"},
                        ]
                    }
                },
                "Scope": {
                    "select": {
                        "options": [
                            {"name": "Global", "color": "blue"},
                            {"name": "Local", "color": "gray"},
                        ]
                    }
                },
                "Status": {
                    "select": {
                        "options": [
                            {"name": "To do", "color": "gray"},
                            {"name": "In progress", "color": "blue"},
                            {"name": "Done", "color": "green"},
                        ]
                    }
                },
                "Touched Paths": {"multi_select": {"options": []}},
                "Gate Level": {
                    "select": {
                        "options": [
                            {"name": "None", "color": "default"},
                            {"name": "Soft", "color": "yellow"},
                            {"name": "Degraded", "color": "orange"},
                            {"name": "Hard", "color": "red"},
                        ]
                    }
                },
                "DoD": {"rich_text": {}},
            }
        },
    }
    r = requests.post(f"{NOTION_API_BASE}/databases", headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def add_dependencies_relation(headers: dict, data_source_id: str) -> None:
    """Dependencies self-relation 속성 추가 (생성 후 수동 연결 가능)."""
    body = {
        "properties": {
            "Dependencies": {
                "type": "relation",
                "relation": {
                    "data_source_id": data_source_id,
                    "dual_property": {"synced_property_name": "Dependent of"},
                },
            }
        }
    }
    r = requests.patch(
        f"{NOTION_API_BASE}/data_sources/{data_source_id}",
        headers=headers,
        json=body,
        timeout=30,
    )
    if r.status_code != 200:
        print(f"   [참고] Dependencies 속성 추가 실패(수동 연결 가능): {r.status_code}")


def get_data_source_id(headers: dict, database_id: str) -> str:
    r = requests.get(f"{NOTION_API_BASE}/databases/{database_id}", headers=headers, timeout=30)
    r.raise_for_status()
    sources = r.json().get("data_sources", [])
    if not sources:
        raise SystemExit("데이터베이스에 data source가 없습니다.")
    return sources[0]["id"]


def create_page(headers: dict, data_source_id: str, row: dict) -> dict:
    props = {
        "태스크 명": {"title": [{"type": "text", "text": {"content": row["태스크 명"][:2000]}}]},
        "Phase": {"number": row["phase"]},
        "Step": {"number": row["step"]},
        "Module": {"multi_select": [{"name": m} for m in row["module"]]},
        "Scope": {"select": {"name": row["scope"]}},
        "Status": {"select": {"name": "To do"}},
        "Touched Paths": {"multi_select": [{"name": p} for p in row["touched_paths"]]},
        "Gate Level": {"select": {"name": row["gate_level"]}},
        "DoD": {"rich_text": [{"type": "text", "text": {"content": row["dod"][:2000]}}]},
    }
    body = {
        "parent": {"type": "data_source_id", "data_source_id": data_source_id},
        "properties": props,
    }
    r = requests.post(f"{NOTION_API_BASE}/pages", headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    headers, page_id = get_headers()

    print("1. Neural Vision Master Plan DB 생성 중...")
    db = create_database(headers, page_id)
    database_id = db["id"]
    print(f"   생성됨: database_id={database_id}")

    print("2. Data source ID 조회 중...")
    data_source_id = get_data_source_id(headers, database_id)
    print(f"   data_source_id={data_source_id}")

    print("3. Dependencies self-relation 속성 추가 시도...")
    try:
        add_dependencies_relation(headers, data_source_id)
        print("   Dependencies 속성 추가 완료")
    except Exception as e:
        print(f"   [참고] Dependencies는 수동 연결: {e}")

    print("4. 플랜 데이터 입력 중...")
    for i, row in enumerate(MASTER_PLAN_DATA, 1):
        try:
            create_page(headers, data_source_id, row)
            print(f"   [{i}/{len(MASTER_PLAN_DATA)}] {row['태스크 명'][:50]}...")
        except requests.HTTPError as e:
            print(f"   [실패] {row['태스크 명'][:40]}: {e}")
            if e.response is not None and hasattr(e.response, "text"):
                print(f"   응답: {e.response.text[:500]}")

    print("\n완료.")
    print(f"  Database: https://notion.so/{database_id.replace('-', '')}")


if __name__ == "__main__":
    main()
