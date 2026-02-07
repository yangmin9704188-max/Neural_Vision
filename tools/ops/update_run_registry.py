#!/usr/bin/env python3
"""
Update ops/run_registry.jsonl (append-only).
Reads ROUND_END events from lab PROGRESS_LOG files, extracts lane/run_id from
exports/runs/<lane>/<run_id>/ paths, appends deduplicated records.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_REGISTRY = REPO_ROOT / "ops" / "run_registry.jsonl"
LAB_ROOTS_PATH = REPO_ROOT / "ops" / "lab_roots.local.json"
MAX_LINES_READ = 200
DEDUP_LOOKBACK = 1000

RUNS_PATTERN = re.compile(r"exports/runs/([^/]+)/([^/]+)(?:/|$)")


def _extract_lane_run_id(path: str) -> tuple[str, str] | None:
    """Extract (lane, run_id) from path matching exports/runs/<lane>/<run_id>/."""
    norm = path.replace("\\", "/")
    m = RUNS_PATTERN.search(norm)
    if m:
        return (m.group(1), m.group(2))
    return None


def _get_paths_from_event(ev: dict) -> list[str]:
    """Collect path strings from observed_paths, evidence_paths, evidence, artifacts_touched."""
    paths = []
    for key in ("observed_paths", "evidence_paths", "evidence", "artifacts_touched"):
        val = ev.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    raw = item.split(":")[0].strip() if ":" in item else item
                    raw = raw.replace("\\", "/").strip()
                    if raw:
                        paths.append(raw)
    return paths


def _is_round_end(ev: dict) -> bool:
    """True if event is ROUND_END (event or event_type)."""
    et = ev.get("event_type") or ev.get("event") or ""
    return str(et).lower() == "round_end"


def _read_last_n_lines(path: Path, n: int) -> list[str]:
    """Read last n non-empty lines from file."""
    if not path.exists():
        return []
    lines = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
    except Exception:
        return []
    return lines[-n:] if len(lines) > n else lines


def _read_round_end_events(lab_root: Path, module: str) -> list[dict]:
    """Read last N lines, parse JSON, return ROUND_END events for module."""
    log_path = lab_root / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    raw_lines = _read_last_n_lines(log_path, MAX_LINES_READ)
    events = []
    mod_lower = module.lower()
    for line in raw_lines:
        try:
            ev = json.loads(line)
            if ev.get("module", "").lower() == mod_lower and _is_round_end(ev):
                events.append(ev)
        except json.JSONDecodeError:
            continue
    return events


def _get_existing_keys(registry_path: Path) -> set[tuple[str, str, str, str]]:
    """Read last DEDUP_LOOKBACK lines, return set of (module, lane, run_id, round_id)."""
    if not registry_path.exists():
        return set()
    lines = []
    try:
        with open(registry_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
    except Exception:
        return set()
    lines = lines[-DEDUP_LOOKBACK:]
    keys = set()
    for line in lines:
        try:
            rec = json.loads(line)
            mod = (rec.get("module") or "").strip()
            lane = (rec.get("lane") or "").strip()
            run_id = (rec.get("run_id") or "").strip()
            round_id = (rec.get("round_id") or "").strip()
            keys.add((mod, lane, run_id, round_id))
        except json.JSONDecodeError:
            continue
    return keys


def _get_lab_roots() -> list[tuple[Path, str]]:
    """Return [(lab_root, module), ...] for body, fitting, garment."""
    import os

    roots = []
    # Body: main repo
    body_progress = REPO_ROOT / "exports" / "progress" / "PROGRESS_LOG.jsonl"
    if body_progress.exists():
        roots.append((REPO_ROOT, "body"))
    # Fitting, Garment: ENV > lab_roots.local.json
    cfg = {}
    if LAB_ROOTS_PATH.exists():
        try:
            with open(LAB_ROOTS_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    for env_key, mod in [("FITTING_LAB_ROOT", "fitting"), ("GARMENT_LAB_ROOT", "garment")]:
        val = os.environ.get(env_key, "").strip() or (cfg.get(env_key) or "").strip()
        if val:
            p = Path(val)
            if not p.is_absolute():
                p = (REPO_ROOT / val).resolve()
            else:
                p = p.resolve()
            if p.exists():
                roots.append((p, mod))
    return roots


def main() -> int:
    existing = _get_existing_keys(RUN_REGISTRY)
    appended = 0

    for lab_root, module in _get_lab_roots():
        for ev in _read_round_end_events(lab_root, module):
            paths = _get_paths_from_event(ev)
            lane, run_id = None, None
            evidence_paths = []
            for p in paths:
                extracted = _extract_lane_run_id(p)
                if extracted:
                    lane, run_id = extracted
                    evidence_paths.append(p)
                    if len(evidence_paths) >= 3:
                        break
            if not lane or not run_id:
                continue
            round_id = (ev.get("round_id") or "").strip()
            key = (module, lane, run_id, round_id)
            if key in existing:
                continue
            existing.add(key)
            rec = {
                "ts": ev.get("ts", ""),
                "module": module,
                "lane": lane,
                "run_id": run_id,
                "round_id": round_id,
                "step_id": (ev.get("step_id") or ""),
                "evidence_paths": evidence_paths[:3],
                "gate_codes": ev.get("gate_codes") or ev.get("gate_code") or [],
            }
            if isinstance(rec["gate_codes"], str):
                rec["gate_codes"] = [rec["gate_codes"]] if rec["gate_codes"] else []
            manifest_path = None
            for ep in evidence_paths:
                if "manifest" in ep.lower() or "geometry_manifest" in ep:
                    manifest_path = ep
                    break
            if manifest_path:
                rec["manifest_path"] = manifest_path
            try:
                RUN_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
                with open(RUN_REGISTRY, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                appended += 1
            except Exception:
                pass

    print(f"update_run_registry: appended={appended}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
