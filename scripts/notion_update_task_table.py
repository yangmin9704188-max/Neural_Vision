#!/usr/bin/env python3
"""
Notion Master Plan DB에 태스크 표 업데이트.
.env의 NOTION_TOKEN, NOTION_DATA_SOURCE_ID(또는 NOTION_DATABASE_ID) 사용.
Data source 스키마를 조회해 존재하는 속성만 전송합니다.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

try:
    from dotenv import load_dotenv
    _env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    load_dotenv(_env_path, encoding="utf-8-sig", override=True)
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("requests 필요: pip install requests", file=sys.stderr)
    sys.exit(1)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"

# 업데이트할 태스크 표 (사용자 제공)
TASK_TABLE = [
    {"태스크 명": "Manifest Schema & Validator", "phase": 0, "step": 1, "module": "Common", "내용": "모든 결과물의 형식을 통일하고 자동 검증하기 위해", "dod": "[U1 Common Enforceable] 1. 필수 필드 스키마 고정 2. created_at 변경에도 fingerprint 동일 테스트 통과 3. Validator 0/1 반환", "touched_paths": "contracts/, tools/"},
    {"태스크 명": "SizeKorea 12k 데이터 전처리", "phase": 0, "step": 1, "module": "Body", "내용": "12,000명의 원본 데이터를 m/kg 단위로 정규화하여 엔진 기초 데이터를 만들기 위해", "dod": "[Body Data Readiness] 1. 단위 정규화 완료 2. 필수 4종(성별/나이/키/몸무게) 결측치 클렌징", "touched_paths": "data/raw/, modules/body/"},
    {"태스크 명": "Body U1 산출물 규격 고정", "phase": 0, "step": 2, "module": "Body", "내용": "바디 측정 데이터를 피팅 팀이 정확히 읽을 수 있게 약속하기 위해", "dod": "[Body→Fitting U1 Unlock] 1. subset.json 생성(unit=m, 3키 필수, NaN 금지) 2. 1개 null(Soft)/2개+ null(High) 경고 기록 로직", "touched_paths": "contracts/, modules/body/"},
    {"태스크 명": "Body subset 파서 구현", "phase": 0, "step": 2, "module": "Fitting", "내용": "바디 데이터를 읽어 결측 시에도 시스템이 죽지 않고 상태를 기록하게 하기 위해", "dod": "[Fitting U1 Stub Ready] fitting_facts_summary.json에 warnings_summary, degraded_state 기록 골격 마련", "touched_paths": "modules/fitting/"},
    {"태스크 명": "Garment U1 규격 & Hard Gate", "phase": 0, "step": 3, "module": "Garment", "내용": "불량 옷 데이터를 미리 거르고 모델링 파일 경로를 확정하기 위해", "dod": "[Garment→Fitting U1 Unlock] 1. Hard Gate 플래그(negative_face_area 등) 필수화 2. 불량 시에도 meta/manifest 상시 생성", "touched_paths": "contracts/, modules/garment/"},
    {"태스크 명": "Fitting Fast-Fail & 수신기", "phase": 0, "step": 3, "module": "Fitting", "내용": "불량 옷 감지 시 헛된 연산을 멈추고 즉시 종료 보고를 하기 위해", "dod": "[Fitting U1 Fast-Fail] 1. npz > glb 우선순위 로직 2. Hard Gate 시 즉시 early_exit=true 및 사유 기록", "touched_paths": "modules/fitting/"},
    {"태스크 명": "384개 대표 체형(Binning) 추출", "phase": 1, "step": 1, "module": "Body", "내용": "12,000명 데이터를 384개 그룹으로 압축해 표준 체형 뱅크를 구축하기 위해", "dod": "[Prototype Bank B1 Unlock] 4D Binning 수행 및 384개 메도이드 기반 prototype_index.json 생성", "touched_paths": "modules/body/src/"},
    {"태스크 명": "Smoke-3(결측) 시나리오 생산", "phase": 1, "step": 1, "module": "Body", "내용": "치수가 빠진 데이터에서도 시스템이 버티는지 시험할 fixture를 만들기 위해", "dod": "[P1 Body Exit] Case A/B(null 데이터) 재현 시나리오가 매니페스트/warnings에 반영됨", "touched_paths": "verification/fixtures/"},
    {"태스크 명": "SMPL-X β 최적화 & Loss", "phase": 1, "step": 2, "module": "Body", "내용": "384개 체형을 SMPL-X 모델에 맞추고 오차가 1cm 이내인지 검증하기 위해", "dod": "[Calibration B2 Unlock] 1. β 파라미터 산출 2. quality_score 70점 미만 차단 로직 (측정오차+메쉬안정성)", "touched_paths": "modules/body/src/"},
    {"태스크 명": "Smoke-2(Hard Gate) 생산", "phase": 1, "step": 2, "module": "Garment", "내용": "불량 옷 상황에서 시스템 중단 로직이 도는지 시험할 fixture를 만들기 위해", "dod": "[P1 Garment Exit] Hard Gate 플래그가 포함된 meta/manifest fixture 상시 생성", "touched_paths": "verification/fixtures/"},
    {"태스크 명": "Tier-1 Constraint Solver", "phase": 1, "step": 3, "module": "Fitting", "내용": "옷이 몸을 뚫지 않게 제약 조건을 계산하고 피팅 품질을 점수화하기 위해", "dod": "[Fitting Solver F4 Unlock] 1. 1.5s 이내 연산 완료 2. clipping 등 3종 품질 점수 산출", "touched_paths": "modules/fitting/src/"},
    {"태스크 명": "Fingerprint 결정론 검증", "phase": 1, "step": 3, "module": "Common", "내용": "동일 입력 시 항상 동일한 결과가 나오는지 시스템 신뢰성을 확인하기 위해", "dod": "[U2 Determinism Ready] Canonicalization 규칙 적용 후 동일 입력 → 동일 fingerprint(해시) 일치 확인", "touched_paths": "tools/, contracts/"},
    {"태스크 명": "Fitting Smoke 1/2/3 E2E", "phase": 2, "step": 1, "module": "Fitting", "내용": "준비된 시나리오 데이터를 통해 시스템이 실제로 끝까지 돌아가는지 봉인하기 위해", "dod": "[U2 Sealed] 실패/성공 무관 facts_summary + manifest 항상 생성 및 상태값(exit/degraded) 기록", "touched_paths": "runs/, verification/"},
    {"태스크 명": "Online Inference & 서빙", "phase": 3, "step": 1, "module": "Body", "내용": "사용자 입력(키, 몸무게)에 실시간으로 대응하는 엔진을 완성하기 위해", "dod": "[U3 Body Ops] 1. p95 latency 2.0s 이내 2. 버전 키 변화 시 캐시 무효화 동작 확인", "touched_paths": "modules/body/"},
    {"태스크 명": "Regeneration Loop (Inflate)", "phase": 3, "step": 2, "module": "Fitting", "내용": "품질이 낮을 때 자동으로 팽창(Inflate)시켜 다시 입혀보는 루프를 위해", "dod": "[U3 Fitting Ops] 1. Max Retry 2회 준수 2. 팽창 반경(falloff) 가이드 로직 및 3.0s 상한 강제", "touched_paths": "modules/fitting/src/"},
    {"태스크 명": "Round Close & KPI 안정화", "phase": 3, "step": 3, "module": "Common", "내용": "작업 결과를 자동 마감하고 성능 지표(KPI)가 안정적인지 추적하기 위해", "dod": "[U3 Ops Stable] 라운드 마감 자동화 및 KPI_DIFF 회귀 추적 안정화", "touched_paths": "ops/, verification/"},
]


def _parse_touched_paths(s: str) -> list[str]:
    """'contracts/, tools/' -> ['contracts/', 'tools/']"""
    return [p.strip() for p in re.split(r"[,;]", s) if p.strip()]


def fetch_data_source_schema(headers: dict, data_source_id: str) -> dict:
    """GET /v1/data_sources/:id 로 스키마 조회. properties 이름·타입 반환."""
    r = requests.get(
        f"{NOTION_API_BASE}/data_sources/{data_source_id}",
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    if d.get("archived") or d.get("in_trash"):
        print(
            "  [경고] 이 데이터 소스는 보관됨(archived) 또는 휴지통에 있습니다. "
            "Notion에서 복원 후 다시 시도하세요.",
            file=sys.stderr,
        )
    return d.get("properties", {})


def get_headers():
    token = os.environ.get("NOTION_TOKEN")
    ds_id = os.environ.get("NOTION_DATA_SOURCE_ID")
    db_id = os.environ.get("NOTION_DATABASE_ID")
    if not token:
        raise SystemExit(".env에 NOTION_TOKEN이 필요합니다.")
    if not ds_id and not db_id:
        raise SystemExit(".env에 NOTION_DATA_SOURCE_ID 또는 NOTION_DATABASE_ID가 필요합니다.")
    parent_id = ds_id or db_id
    parent_type = "data_source_id" if ds_id else "database_id"
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }, parent_id, parent_type


def build_props_for_schema(row: dict, schema: dict) -> dict:
    """스키마에 존재하는 속성만으로 properties 객체 생성.
    title 속성명은 스키마에서 자동 감지 (이름, 태스크 명, Name 등).
    """
    props = {}
    touched = _parse_touched_paths(row.get("touched_paths", ""))
    dod_text = f"{row.get('내용', '')}\n\n언락 조건 & DoD: {row.get('dod', '')}"
    dod_text = (dod_text[:2000]) if len(dod_text) > 2000 else dod_text

    # 스키마에 맞는 title 속성명 찾기
    title_prop = None
    for name, meta in schema.items():
        if meta.get("type") == "title":
            title_prop = name
            break
    if title_prop:
        props[title_prop] = {"title": [{"type": "text", "text": {"content": row["태스크 명"][:2000]}}]}

    # 나머지: 스키마에 존재할 때만 포함
    if "Phase" in schema and schema["Phase"].get("type") == "number":
        props["Phase"] = {"number": row["phase"]}
    if "Step" in schema and schema["Step"].get("type") == "number":
        props["Step"] = {"number": row["step"]}
    if "Module" in schema and schema["Module"].get("type") == "multi_select":
        props["Module"] = {"multi_select": [{"name": row["module"]}]}
    if "Scope" in schema and schema["Scope"].get("type") == "select":
        props["Scope"] = {"select": {"name": "Local"}}
    if "Status" in schema and schema["Status"].get("type") == "select":
        props["Status"] = {"select": {"name": "To do"}}
    if "Touched Paths" in schema and schema["Touched Paths"].get("type") == "multi_select" and touched:
        props["Touched Paths"] = {"multi_select": [{"name": p} for p in touched]}
    if "Gate Level" in schema and schema["Gate Level"].get("type") == "select":
        props["Gate Level"] = {"select": {"name": "None"}}
    if "DoD" in schema and schema["DoD"].get("type") == "rich_text":
        props["DoD"] = {"rich_text": [{"type": "text", "text": {"content": dod_text[:2000]}}]}

    return props


def create_page(
    headers: dict,
    parent_id: str,
    parent_type: str,
    row: dict,
    schema: dict,
) -> dict:
    """DB에 페이지(행) 생성. schema에 맞는 속성만 전송."""
    props = build_props_for_schema(row, schema)
    if not props:
        raise ValueError("스키마에 전송 가능한 속성이 없습니다. title 속성이 필요합니다.")

    if parent_type == "data_source_id":
        parent_obj = {"type": "data_source_id", "data_source_id": parent_id}
    else:
        parent_obj = {"type": "database_id", "database_id": parent_id}
    body = {"parent": parent_obj, "properties": props}
    r = requests.post(f"{NOTION_API_BASE}/pages", headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Notion Master Plan DB에 태스크 추가")
    parser.add_argument("--dry-run", action="store_true", help="실제 전송 없이 스키마와 첫 행만 출력")
    parser.add_argument("--debug", action="store_true", help="에러 시 전체 응답 본문 출력")
    args = parser.parse_args()

    headers, parent_id, parent_type = get_headers()

    # data_source_id 사용 시 스키마 조회
    schema = {}
    if parent_type == "data_source_id":
        try:
            schema = fetch_data_source_schema(headers, parent_id)
            if args.dry_run:
                print("스키마 속성:", list(schema.keys()))
        except requests.HTTPError as e:
            print(f"스키마 조회 실패: {e}", file=sys.stderr)
            if args.debug and e.response is not None:
                print(e.response.text[:1500], file=sys.stderr)
            sys.exit(1)
    else:
        # database_id 사용 시 Master Plan 기본 스키마 가정
        schema = {
            "태스크 명": {"type": "title"},
            "Phase": {"type": "number"},
            "Step": {"type": "number"},
            "Module": {"type": "multi_select"},
            "Scope": {"type": "select"},
            "Status": {"type": "select"},
            "Touched Paths": {"type": "multi_select"},
            "Gate Level": {"type": "select"},
            "DoD": {"type": "rich_text"},
        }

    print(f"Notion DB ({parent_id})에 {len(TASK_TABLE)}개 태스크 추가 중...")
    if args.dry_run:
        props = build_props_for_schema(TASK_TABLE[0], schema)
        print("첫 행 props 키:", list(props.keys()))
        print("(실제 전송 건너뜀)")
        return

    ok = 0
    for i, row in enumerate(TASK_TABLE, 1):
        try:
            create_page(headers, parent_id, parent_type, row, schema)
            print(f"  [{i}/{len(TASK_TABLE)}] {row['태스크 명'][:50]}...")
            ok += 1
        except requests.HTTPError as e:
            err = e.response.text if e.response and hasattr(e.response, "text") else str(e)
            print(f"  [실패] {row['태스크 명'][:40]}: {e}", file=sys.stderr)
            print(f"    응답: {err[:1500] if args.debug else err[:500]}", file=sys.stderr)

    print(f"\n완료: {ok}/{len(TASK_TABLE)} 추가됨")
    print(f"  DB: https://notion.so/{parent_id.replace('-', '')}")


if __name__ == "__main__":
    main()
