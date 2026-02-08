#!/usr/bin/env python3
"""
Round wrap: ROUND_START/ROUND_END 이벤트를 PROGRESS_LOG.jsonl에 기록.
- start: step-id, note 필수 → round_id 생성, .round_active.json 저장
- end: note 필수, active round 존재 필수 → observed_paths 수집, ROUND_END append, active 해제

운영: 작업 시작 시 roundwrap start, 작업 종료 시 roundwrap end (run_end_hook/invoke_ops_hook 전에).
"""
import argparse
import json
import re
import random
import string
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
LOG_DIR = REPO / "exports" / "progress"
LOG_PATH = LOG_DIR / "PROGRESS_LOG.jsonl"
ACTIVE_PATH = LOG_DIR / ".round_active.json"

# exports/runs/<lane>/<run_id>/ 패턴 (메인 update_run_registry에서 탐지)
EXPORTS_RUNS_PATTERN = re.compile(r"exports/runs/([^/]+)/([^/]+)(?:/|$)")

# observed_paths 우선순위 (하드코딩, 메인 run_registry appended>=1 목표)
# P1: exports/runs/**/geometry_manifest.json
# P2: exports/runs/**/*facts_summary*.json
# P3: exports/runs/**/RUN_README.md
# P4: fallback (최근 수정 파일)


def _ts_now() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    except ImportError:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _to_rel(path: Path, repo: Path) -> str | None:
    try:
        return str(path.relative_to(repo)).replace("\\", "/")
    except ValueError:
        return None


def _collect_observed_paths(repo: Path, within_minutes: int = 60, max_paths: int = 3) -> tuple[list[str], list[str], str | None, str | None]:
    """
    observed_paths 수집. 반드시 exports/runs/<lane>/<run_id>/ 패턴 1개 이상 포함.
    Returns: (observed_paths, gate_codes, lane, run_id)
    """
    cutoff = datetime.now().timestamp() - (within_minutes * 60)
    cutoff_long = datetime.now().timestamp() - (7 * 24 * 60 * 60)  # 7일

    def is_recent(p: Path, strict: bool = False) -> bool:
        try:
            m = p.stat().st_mtime
            return m >= (cutoff if strict else cutoff_long)
        except OSError:
            return False

    p1: list[tuple[float, Path]] = []
    p2: list[tuple[float, Path]] = []
    p3: list[tuple[float, Path]] = []
    p4: list[tuple[float, Path]] = []

    runs_dir = repo / "exports" / "runs"
    if runs_dir.exists():
        for p in runs_dir.rglob("*"):
            if not p.is_file():
                continue
            rel = _to_rel(p, repo)
            if not rel or "exports/runs/" not in rel:
                continue
            m = p.stat().st_mtime
            name = p.name.lower()
            if "geometry_manifest.json" in name:
                p1.append((m, p))
            elif "facts_summary" in name:
                p2.append((m, p))
            elif "run_readme" in name or name in ("readme.md", "readme.txt"):
                p3.append((m, p))
            elif is_recent(p, strict=False):
                p4.append((m, p))

    # P1 > P2 > P3 > P4, 각각 최신순
    for lst in (p1, p2, p3, p4):
        lst.sort(key=lambda x: -x[0])

    result: list[str] = []
    seen = set()
    has_exports_runs = False
    lane_out, run_id_out = None, None

    def add(path: Path) -> bool:
        nonlocal has_exports_runs, lane_out, run_id_out
        rel = _to_rel(path, repo)
        if not rel or rel in seen:
            return False
        m = EXPORTS_RUNS_PATTERN.search(rel)
        if m:
            has_exports_runs = True
            if lane_out is None:
                lane_out, run_id_out = m.group(1), m.group(2)
        seen.add(rel)
        result.append(rel)
        return True

    for m, p in p1 + p2 + p3:
        if add(p) and len(result) >= max_paths:
            break

    if not has_exports_runs:
        for m, p in p4:
            if add(p):
                break

    gate_codes: list[str] = []
    if not has_exports_runs:
        gate_codes.append("RUN_PATH_MISSING")
        if not result:
            result.append("exports/progress/PROGRESS_LOG.jsonl")
        rw = repo / "tools" / "roundwrap.py"
        if rw.exists() and len(result) < max_paths:
            rel = _to_rel(rw, repo)
            if rel and rel not in seen:
                result.append(rel)

    return result[:max_paths], gate_codes, lane_out, run_id_out


def _ensure_run_minset(
    repo: Path,
    run_dir: Path,
    lane: str,
    run_id: str,
    round_id: str,
    step_id: str,
    note: str,
    observed: list[str],
    gate_codes: list[str],
    skip_reasons: list[str],
) -> tuple[list[str], str | None, list[str]]:
    """
    Run Minset: geometry_manifest.json(루트 보장), facts_summary.json, RUN_README.md 보장.
    Returns (created, root_geo_rel, missing_minset).
    """
    import shutil

    created: list[str] = []
    missing_minset: list[str] = []
    run_dir.mkdir(parents=True, exist_ok=True)
    run_dir_rel = _to_rel(run_dir, repo) or f"exports/runs/{lane}/{run_id}/"
    root_geo_path = run_dir / "geometry_manifest.json"
    root_geo_rel = f"exports/runs/{lane}/{run_id}/geometry_manifest.json"

    # 1) geometry_manifest.json - 루트에 항상 보장
    geo_at_root = root_geo_path.exists()
    if not geo_at_root:
        # 후보: exports/runs/<lane>/<run_id>/**/geometry_manifest.json
        geo_candidates = list(run_dir.rglob("geometry_manifest.json"))
        for c in geo_candidates:
            if c == root_geo_path:
                continue
            try:
                raw = c.read_text(encoding="utf-8")
                data = json.loads(raw)
                if "fingerprint" not in data:
                    data["fingerprint"] = data.get("inputs_fingerprint") or "sha256:unknown"
                root_geo_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                geo_at_root = True
                if root_geo_rel not in created:
                    created.append(root_geo_rel)
                break
            except Exception as e:
                skip_reasons.append(f"geometry_manifest copy failed: {e}")
                gate_codes.append("RUN_MANIFEST_ROOT_MISSING")
                break
        if not geo_at_root and not geo_candidates:
            gate_codes.append("RUN_MANIFEST_ROOT_MISSING")
            missing_minset.append("geometry_manifest.json")
            skip_reasons.append("geometry_manifest.json: not found under run_dir")
        elif not geo_at_root:
            gate_codes.append("RUN_MANIFEST_ROOT_MISSING")
            missing_minset.append("geometry_manifest.json")
            skip_reasons.append("geometry_manifest.json: copy to root failed")
    minset_ok = geo_at_root and not missing_minset

    # 2) facts_summary.json
    facts_path = run_dir / "facts_summary.json"
    facts_rel = _to_rel(facts_path, repo)
    try:
        facts_data = {
            "schema_version": "facts_summary.v1",
            "module": "fitting",
            "lane": lane,
            "run_id": run_id,
            "round_id": round_id,
            "step_id": step_id,
            "created_at": _ts_now(),
            "observed_paths_count": len(observed),
            "gate_codes_count": len(gate_codes),
            "manifest_relpath": "geometry_manifest.json" if geo_at_root else None,
            "run_dir": run_dir_rel,
            "minset_ok": minset_ok,
            "missing_minset": missing_minset,
        }
        facts_path.write_text(json.dumps(facts_data, ensure_ascii=False, indent=2), encoding="utf-8")
        if facts_rel and facts_rel not in created:
            created.append(facts_rel)
    except Exception as e:
        skip_reasons.append(f"facts_summary.json: {e}")

    # 3) strict-run 시도 (warn-only, RUN_README에 기록용)
    validator = repo / "tools" / "validate_fitting_manifest.py"
    if validator.exists():
        try:
            r = subprocess.run(
                [sys.executable, str(validator), "--run-dir", str(run_dir), "--strict-run"],
                capture_output=True, text=True, cwd=str(repo), timeout=10,
            )
            if r.returncode != 0:
                skip_reasons.append("strict-run: SKIPPED (no fitting_manifest or validation failed)")
        except Exception as e:
            skip_reasons.append(f"strict-run: SKIPPED ({e})")
    else:
        skip_reasons.append("strict-run: SKIPPED (validator not found)")

    # 4) RUN_README.md
    readme_path = run_dir / "RUN_README.md"
    readme_rel = _to_rel(readme_path, repo)
    try:
        lines = [
            f"# Run {run_id}",
            "",
            f"- lane: {lane}",
            f"- round_id: {round_id}",
            f"- step_id: {step_id}",
            f"- note: {note}",
            "",
        ]
        if skip_reasons:
            lines.append("## Skip reasons")
            for s in skip_reasons:
                lines.append(f"- {s}")
            lines.append("")
        lines.append("## Minset files")
        lines.append("- facts_summary.json")
        lines.append("- RUN_README.md")
        if geo_at_root:
            lines.append("- geometry_manifest.json (root)")
        else:
            lines.append("- geometry_manifest.json (MISSING)")
        readme_path.write_text("\n".join(lines), encoding="utf-8")
        if readme_rel:
            created.append(readme_rel)
    except Exception as e:
        skip_reasons.append(f"RUN_README.md: {e}")

    return created, (root_geo_rel if geo_at_root else None), missing_minset


def _append_event(ev: dict) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(ev, ensure_ascii=False) + "\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
        return 0
    except Exception as e:
        print(f"roundwrap: FAIL {e}", file=sys.stderr)
        return 1


def cmd_start(step_id: str, note: str) -> int:
    if not step_id or not note:
        print("roundwrap start: --step-id and --note required", file=sys.stderr)
        return 1
    if not re.match(r"^F\d{2}$", step_id):
        print("roundwrap start: --step-id must match Fnn (e.g. F09)", file=sys.stderr)
        return 1

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    round_id = f"fitting_{ts}_{suffix}"

    ev = {
        "ts": _ts_now(),
        "module": "fitting",
        "step_id": step_id,
        "event": "round_start",
        "round_id": round_id,
        "run_id": "N/A",
        "status": "OK",
        "dod_done_delta": 0,
        "note": note,
        "evidence": [],
        "warnings": [],
    }
    if _append_event(ev) != 0:
        return 1

    ACTIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    active = {"round_id": round_id, "step_id": step_id, "started_at": ev["ts"]}
    try:
        with open(ACTIVE_PATH, "w", encoding="utf-8") as f:
            json.dump(active, f, ensure_ascii=False, indent=0)
    except Exception as e:
        print(f"roundwrap: could not save active round: {e}", file=sys.stderr)
        return 1

    print(f"roundwrap: ROUND_START round_id={round_id} step={step_id}")
    return 0


def cmd_end(note: str) -> int:
    if not note:
        print("roundwrap end: --note required", file=sys.stderr)
        return 1

    if not ACTIVE_PATH.exists():
        print("roundwrap end: no active round. Run 'roundwrap start' first.", file=sys.stderr)
        return 1

    try:
        with open(ACTIVE_PATH, encoding="utf-8") as f:
            active = json.load(f)
    except Exception as e:
        print(f"roundwrap end: invalid .round_active.json: {e}", file=sys.stderr)
        ACTIVE_PATH.unlink(missing_ok=True)
        return 1

    round_id = active.get("round_id", "unknown")
    step_id = active.get("step_id", "F??")
    observed, gate_codes, lane, run_id_parsed = _collect_observed_paths(REPO, within_minutes=60, max_paths=3)
    if not observed:
        observed = ["exports/progress/PROGRESS_LOG.jsonl"]

    minset_created: list[str] = []
    root_geo_rel: str | None = None
    skip_reasons: list[str] = []
    if lane and run_id_parsed and "RUN_PATH_MISSING" not in gate_codes:
        run_dir = REPO / "exports" / "runs" / lane / run_id_parsed
        minset_created, root_geo_rel, _ = _ensure_run_minset(
            REPO, run_dir, lane, run_id_parsed, round_id, step_id, note,
            observed, gate_codes, skip_reasons,
        )
        # evidence에 minset 파일 반드시 포함 (루트 geometry, facts_summary, RUN_README)
        merged: list[str] = []
        for p in [root_geo_rel] + minset_created if root_geo_rel else minset_created:
            if p and p not in merged:
                merged.append(p)
        for p in observed:
            if p not in merged and len(merged) < 5:
                merged.append(p)
        observed = merged[:5] if merged else observed

    note_final = note
    if gate_codes:
        note_final = f"{note} [WARN] no exports/runs path observed in this round"

    ev = {
        "ts": _ts_now(),
        "module": "fitting",
        "step_id": step_id,
        "event": "round_end",
        "round_id": round_id,
        "run_id": run_id_parsed if run_id_parsed else "N/A",
        "status": "OK",
        "dod_done_delta": 0,
        "note": note_final,
        "evidence": observed,
        "warnings": [f"[{g}]" for g in gate_codes],
    }
    if lane:
        ev["lane"] = lane
    if run_id_parsed:
        ev["run_id"] = run_id_parsed
    if gate_codes:
        ev["gate_codes"] = gate_codes
    if minset_created:
        ev["minset_created"] = minset_created
    if _append_event(ev) != 0:
        return 1

    try:
        ACTIVE_PATH.unlink()
    except OSError:
        pass
    gc_str = f" gate_codes={gate_codes}" if gate_codes else ""
    minset_str = f" minset={minset_created}" if minset_created else ""
    print(f"roundwrap: ROUND_END round_id={round_id} observed_paths={observed}{gc_str}{minset_str}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Round wrap: ROUND_START/ROUND_END to PROGRESS_LOG")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="Start round (step-id, note required)")
    p_start.add_argument("--step-id", required=True, help="e.g. F09")
    p_start.add_argument("--note", required=True, help="round start note")

    p_end = sub.add_parser("end", help="End round (note required, active round required)")
    p_end.add_argument("--note", required=True, help="round end note")

    args = parser.parse_args()
    if args.cmd == "start":
        return cmd_start(args.step_id, args.note)
    return cmd_end(args.note)


if __name__ == "__main__":
    sys.exit(main())
