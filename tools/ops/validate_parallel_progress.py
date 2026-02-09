#!/usr/bin/env python3
"""
Validate parallel execution protocol for progress logs.

Checks (from contracts/parallel_execution_policy_v1.json):
  - C* steps must be logged only by body/common and only in root progress log.
  - B*/F*/G* step-to-module ownership must match.
  - lifecycle_state must be monotonic: IMPLEMENTED -> VALIDATED -> CLOSED.
  - VALIDATED/CLOSED must include required refs/evidence.

Enforcement window starts at policy.enforcement_start_ts.
Exit codes: 0=PASS/WARN, 1=FAIL.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    source: str
    line: int
    step_id: str = "N/A"
    module: str = "N/A"


def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _find_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    cur = (start or Path.cwd()).resolve()
    while True:
        if (cur / ".git").is_dir() or (cur / "project_map.md").is_file():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def _parse_ts(ts: str) -> Optional[datetime]:
    if not isinstance(ts, str) or not ts.strip():
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _path_matches_glob(path: str, pattern: str) -> bool:
    import fnmatch

    pnorm = path.replace("\\", "/")
    pat = pattern.replace("\\", "/")
    if "**" not in pat:
        return fnmatch.fnmatch(pnorm, pat)
    prefix, _, suffix = pat.partition("**")
    prefix = prefix.rstrip("/")
    suffix = suffix.lstrip("/")
    if prefix and not pnorm.startswith(prefix):
        return False
    if suffix and not pnorm.endswith(suffix):
        return False
    return True


def _iter_log_events(log_path: Path, source: str) -> Iterable[Tuple[Dict[str, Any], int, str]]:
    if not log_path.is_file():
        return
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                yield ({"__parse_error__": True, "__raw__": raw}, i, source)
                continue
            if isinstance(obj, dict):
                yield (obj, i, source)


def _collect_event_paths(ev: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("evidence", "evidence_paths", "artifacts_touched"):
        vals = ev.get(key)
        if isinstance(vals, list):
            for item in vals:
                if isinstance(item, str) and item.strip():
                    out.append(item.strip().replace("\\", "/"))
    for key in ("validation_report_ref", "closure_spec_ref"):
        val = ev.get(key)
        if isinstance(val, str) and val.strip():
            out.append(val.strip().replace("\\", "/"))
    return out


def validate(repo_root: Path, policy_path: Path) -> List[Finding]:
    findings: List[Finding] = []
    policy = _load_json(policy_path)
    if not policy:
        findings.append(Finding(FAIL, "POLICY_NOT_FOUND", f"Cannot load policy: {policy_path}", "N/A", 0))
        return findings

    enforce_from = _parse_ts(policy.get("enforcement_start_ts", "")) or datetime.min.replace(tzinfo=timezone.utc)
    common_prefix = str(policy.get("common_step_prefix", "C")).upper()
    allowed_common_modules = {str(x).lower() for x in policy.get("allowed_common_event_modules", ["body", "common"])}
    module_prefix = {k.lower(): str(v).upper() for k, v in (policy.get("module_step_prefix") or {}).items()}
    seq = [str(x).upper() for x in policy.get("lifecycle_sequence", ["IMPLEMENTED", "VALIDATED", "CLOSED"])]
    state_idx = {name: i + 1 for i, name in enumerate(seq)}

    root_log = repo_root / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    fit_log = repo_root / "modules" / "fitting" / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    gar_log = repo_root / "modules" / "garment" / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    body_mod_log = repo_root / "modules" / "body" / "exports" / "progress" / "PROGRESS_LOG.jsonl"

    raw_events: List[Tuple[datetime, int, Dict[str, Any], int, str]] = []
    seq_no = 0
    for path, source in (
        (root_log, "root"),
        (fit_log, "fitting"),
        (gar_log, "garment"),
        (body_mod_log, "body_module"),
    ):
        for ev, line, src in _iter_log_events(path, source):
            seq_no += 1
            if ev.get("__parse_error__"):
                findings.append(Finding(WARN, "JSON_PARSE_WARN", "Invalid JSON line skipped", src, line))
                continue
            ts = _parse_ts(ev.get("ts", "")) or datetime.min.replace(tzinfo=timezone.utc)
            if ts < enforce_from:
                continue
            raw_events.append((ts, seq_no, ev, line, src))

    raw_events.sort(key=lambda x: (x[0], x[1]))

    lifecycle_by_step: Dict[str, int] = {}
    for _ts, _n, ev, line, src in raw_events:
        step_id = str(ev.get("step_id") or "")
        module = str(ev.get("module") or "").lower()
        if not step_id:
            findings.append(Finding(WARN, "STEP_ID_MISSING", "step_id missing", src, line, module=module or "N/A"))
            continue

        prefix = step_id[:1].upper()

        # Ownership checks
        if prefix == common_prefix:
            if src != "root":
                findings.append(Finding(
                    FAIL, "COMMON_STEP_NON_ROOT_LOG",
                    "C* step must be appended in root exports/progress log",
                    src, line, step_id=step_id, module=module
                ))
            if module not in allowed_common_modules:
                findings.append(Finding(
                    FAIL, "COMMON_STEP_MODULE_MISMATCH",
                    f"C* step must use module in {sorted(allowed_common_modules)}",
                    src, line, step_id=step_id, module=module
                ))
        elif prefix in {"B", "F", "G"}:
            expected = None
            for mod, pfx in module_prefix.items():
                if pfx == prefix:
                    expected = mod
                    break
            if expected and module != expected:
                findings.append(Finding(
                    FAIL, "STEP_MODULE_MISMATCH",
                    f"{prefix}* step must use module={expected}",
                    src, line, step_id=step_id, module=module
                ))

        # Lifecycle checks
        lifecycle = str(ev.get("lifecycle_state") or "").upper()
        if lifecycle:
            if lifecycle not in state_idx:
                findings.append(Finding(
                    FAIL, "LIFECYCLE_INVALID",
                    f"Unknown lifecycle_state: {lifecycle}",
                    src, line, step_id=step_id, module=module
                ))
                continue
            cur = lifecycle_by_step.get(step_id, 0)
            nxt = state_idx[lifecycle]
            if nxt < cur:
                findings.append(Finding(
                    FAIL, "LIFECYCLE_REGRESSION",
                    f"Lifecycle regression: {lifecycle}",
                    src, line, step_id=step_id, module=module
                ))
            if nxt > cur + 1:
                findings.append(Finding(
                    FAIL, "LIFECYCLE_SKIP",
                    f"Lifecycle skipped: current={cur}, next={nxt}",
                    src, line, step_id=step_id, module=module
                ))
            lifecycle_by_step[step_id] = max(cur, nxt)

            paths = _collect_event_paths(ev)
            if lifecycle == "VALIDATED":
                has_report_ref = isinstance(ev.get("validation_report_ref"), str) and bool(ev.get("validation_report_ref", "").strip())
                has_report_path = any(_path_matches_glob(p, "reports/validation/**") for p in paths)
                if not (has_report_ref or has_report_path):
                    findings.append(Finding(
                        FAIL, "VALIDATED_REPORT_MISSING",
                        "VALIDATED requires validation report reference/evidence",
                        src, line, step_id=step_id, module=module
                    ))
            if lifecycle == "CLOSED":
                has_spec_ref = isinstance(ev.get("closure_spec_ref"), str) and bool(ev.get("closure_spec_ref", "").strip())
                has_spec_path = any(_path_matches_glob(p, "contracts/closure_specs/**") for p in paths)
                if not (has_spec_ref or has_spec_path):
                    findings.append(Finding(
                        FAIL, "CLOSED_SPEC_MISSING",
                        "CLOSED requires closure spec reference/evidence",
                        src, line, step_id=step_id, module=module
                    ))

    return findings


def print_report(findings: List[Finding], as_json: bool = False) -> int:
    counts = {PASS: 0, WARN: 0, FAIL: 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    summary = FAIL if counts[FAIL] > 0 else (WARN if counts[WARN] > 0 else PASS)

    if as_json:
        out = {
            "summary": summary,
            "counts": counts,
            "findings": [
                {
                    "severity": f.severity,
                    "code": f.code,
                    "message": f.message,
                    "source": f.source,
                    "line": f.line,
                    "step_id": f.step_id,
                    "module": f.module,
                }
                for f in findings
            ],
        }
        _safe_print(json.dumps(out, indent=2, ensure_ascii=False))
        return 1 if summary == FAIL else 0

    if summary == PASS:
        _safe_print("PARALLEL_PROGRESS SUMMARY: PASS")
    else:
        _safe_print(f"PARALLEL_PROGRESS SUMMARY: {summary}")
    _safe_print("")

    for sev in (FAIL, WARN):
        selected = [f for f in findings if f.severity == sev]
        if not selected:
            continue
        _safe_print(f"-- {sev} --")
        for f in selected[:50]:
            _safe_print(
                f"[{f.code}] {f.message} | source={f.source}:{f.line} step={f.step_id} module={f.module}"
            )
        if len(selected) > 50:
            _safe_print(f"... {len(selected) - 50} more")
        _safe_print("")

    return 1 if summary == FAIL else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate parallel execution protocol on progress logs")
    parser.add_argument("--policy", default="contracts/parallel_execution_policy_v1.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = _find_repo_root()
    if not repo_root:
        _safe_print("ERROR: could not find repo root")
        return 1
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = repo_root / policy_path

    findings = validate(repo_root, policy_path)
    return print_report(findings, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())

