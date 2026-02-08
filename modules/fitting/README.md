# fitting_lab

**Local experimental laboratory for fitting operations v0.**

---

## Scope / Purpose

- **fitting_lab is a sandbox**: Development happens here first, NOT directly in the main repository
- **Refinement before porting**: Only finalized, tested results are ported to the main repo via minimal diff patches
- **Isolation**: This lab is independent and does not affect the main repo until explicit port decisions

---

## Hard Rules (Facts-Only Principles)

1. **NO PASS/FAIL judgments**: Report measurements and facts only
2. **NO thresholds or clamping**: Never drop data or clamp values to improve metrics
3. **NaN handling**: NaN allowed internally, serialized as `null` in JSON output (standard JSON compliance)
4. **Absolute crash prevention**: Any input must be handled gracefully with warnings/reasons recorded and output files generated

---

## Main Repo Port Allowlist

- **Allowed (3 files only)**:
  1. `modules/fitting/runners/run_fitting_v0_facts.py`
  2. `modules/fitting/specs/fitting_manifest.schema.json`
  3. `contracts/fitting_interface_v0.md`
- **Prohibited**: `runs/`, `samples/`, `__pycache__` must NEVER be ported.

---

## Import Policy

- **Body Input**: Reference path to `facts_summary.json` (output artifact from body RUN_DIR). DO NOT copy large datasets.
- **Sample Manifest**: Use `labs/samples/manifest_body_facts_summary.json` as a template for fitting manifest structure.
- **Cross-module**: Implementation imports strictly prohibited.

---

## Progress (Ops)

- **통로 단일화 (P5)**: progress 이벤트는 **roundwrap start/end**로만 남긴다. STEP_ID_MISSING 근절.
- **roundwrap start**: --step-id, --note 필수. 없으면 append 금지(exit!=0).
- **roundwrap end**: active round 없으면 실패(exit!=0). Run Minset(facts_summary.json, RUN_README.md, geometry_manifest.json) 자동 생성. strict-run(warn-only) 시도. ROUND_END evidence에 minset 경로 포함.
- **메인 ops 훅**: `.\tools\invoke_ops_hook.ps1 F11` (내부에서 roundwrap end 호출)
- **사용 금지**: `run_end_hook.ps1`, `progress_append.py` 등 직접 PROGRESS_LOG append 금지. 다른 훅/스크립트에서 progress 이벤트를 남기지 않는다.

---

## Smoke Test (facts_summary body source)

```powershell
# Command 1: Run fitting
py labs\runners\run_fitting_v0_facts.py --manifest labs\samples\manifest_body_facts_summary.json --out_dir runs\smoke_body_facts_summary

# Command 2: Verify output
powershell -ExecutionPolicy Bypass -File tools\inspect_run.ps1 -RunDir runs\smoke_body_facts_summary

# Command 3: Round wrap (단일 통로)
#   py tools/roundwrap.py start --step-id F11 --note "round N: ..."
#   ... 작업 ...
#   py tools/roundwrap.py end --note "round N done"
# Command 4: 메인 ops 훅 (roundwrap end 자동 호출, render 포함):
#   powershell -ExecutionPolicy Bypass -File tools\invoke_ops_hook.ps1 F11
```

**Expected Artifacts**:
- `fitting_summary.json`
- `facts_summary.json`

**Expected Fields** (Facts-only, no judgment):
- `facts_summary.json`: `nan_rate`, `reasons`, `warnings`
- `fitting_summary.json`: `metrics`

---

## Release Snapshot Policy

- **Requirement**: Create snapshot in `releases/fitting_v0_YYYYMMDD_HHMMSS/` before porting to main repo.
- **Contents**:
  1. `labs/runners/run_fitting_v0_facts.py`
  2. `labs/specs/fitting_manifest.schema.json`
  3. `contracts/fitting_interface_v0.md`
- **Purpose**: Preserve evidence and version history for port candidates.

---

## Port Policy (Project-Wide)

- **Limit**: Max 3 ports allowed per project.
- **Phases**:
  - **Port-1 (Alpha)**: Initial feature complete.
  - **Port-2 (Beta)**: Stability & full coverage.
  - **Port-3 (Final)**: Production freezing.
