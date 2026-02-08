# Round Policy v1 (SSoT)

## 규칙

1. **작업 시작 시** `py tools/roundwrap.py start --step-id FNN --note "..."` 실행
2. **작업 종료 시** `py tools/roundwrap.py end --note "..."` 실행
3. round_start 없이 round_end 금지 (active round 없으면 end 실패)
4. ROUND_END에는 observed_paths(evidence) 최소 1개 포함

## 이벤트

- `event=round_start`: round_id 생성, .round_active.json 저장
- `event=round_end`: observed_paths 자동 수집, active 해제
