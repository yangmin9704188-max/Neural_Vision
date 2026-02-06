# Repo Layout Policy v1 (SSoT)

## Purpose
- 이 문서는 본 레포의 **폴더/파일 배치 규칙 정본(anti-entropy)** 입니다.
- 새 파일·폴더 생성 시 반드시 이 규칙에 따라 위치를 결정합니다. Cursor/에이전트는 생성 전 이 문서를 먼저 읽고 준수합니다.

## Canonical folders
| 폴더 | 목적 (1줄) |
|------|------------|
| **ssot/** | 파이프라인/증거/DoD/ledger/map 등 메타 정보 정본 |
| **contracts/** | 입출력 규격·스키마·키·유닛·계약 문서 정본 |
| **ops/** | 운영 진입점(HUB), 상태(STATUS), 런북, 자동화 사용법 |
| **tools/** | 실행 스크립트, 검증기, 렌더러, CLI |
| **modules/body/** | Body 모듈 구현 및 모듈 전용 문서/스펙 |
| **legacy/** | 과거 문서·이전 레포 산출물 아카이브 (수정 금지) |
| **data/** | 로컬 데이터 (gitignore, generated-only) |
| **exports/** | 로컬 산출물·런 결과·progress (gitignore, generated-only) |

## Filing Decision Tree
- **입출력 규격/스키마/키/유닛** → `contracts/**`
- **파이프라인/증거/DoD/ledger/map** → `ssot/**`
- **운영 진입점/상태/런북/자동화 사용법** → `ops/**`
- **실행 스크립트/검증기/렌더러/CLI** → `tools/**`
- **body 구현/모듈 특화 문서** → `modules/body/docs/**`
- **과거 문서/이전 레포 산출물** → `legacy/**` (수정 금지)
- **로컬 데이터/산출물** → `data/**`, `exports/**` (gitignore, generated-only)

## Naming rules
- **버전 규칙**: `*_v0.md`, `*_v1.md` 등 접미로 버전 명시.
- **접미 규칙**: `*_ledger_v0.md`, `*_map_v0.md`, `*_checklist_v0.md` 등 용도별 접미 사용.
- **run_id**: `exports/`, `data/` 내부에서만 사용. 코드/문서에 run_id를 하드코딩하지 말 것 (paths.default_tool_out 등 단일 진실원 사용).

## Duplication policy
- **정본은 1곳만**: contracts, ssot, ops 등에서 각 주제당 하나의 정본 문서만 둡니다.
- **다른 위치**: 정본이 아닌 곳에는 “포인터 문서(정본 링크)”만 허용. 내용 복사 금지.

## Catalog rules for src
- **src 하위 코드 폴더**에는 `CATALOG.md` 필수.
- **새 파일 만들기 전** 해당 폴더 `CATALOG.md` 읽기.
- **파일 생성/삭제 시** `CATALOG.md` 업데이트.
- **각 .py 상단** 3~5줄 헤더 코멘트 필수 (Purpose, Inputs, Outputs, Status 등).
