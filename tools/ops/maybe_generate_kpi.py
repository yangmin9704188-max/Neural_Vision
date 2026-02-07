#!/usr/bin/env python3
"""
Maybe generate kpi.json for run_registry entries (scaffolding).
When manifest_path or run dir is available, tries to create minimal kpi.json.
On failure, creates KPI_SKIPPED.txt with one-line reason.
KPI_DIFF: SKIPPED when baseline_ref is missing.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_REGISTRY = REPO_ROOT / "ops" / "run_registry.jsonl"
LAB_ROOTS_PATH = REPO_ROOT / "ops" / "lab_roots.local.json"

KPI_FILES = ("geometry_manifest.json", "facts_summary.json", "RUN_README.md", "README.txt")


def _get_lab_root(module: str) -> Path | None:
    """Resolve lab root for module. Returns None if not found."""
    cfg = {}
    if LAB_ROOTS_PATH.exists():
        try:
            with open(LAB_ROOTS_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    env_key = f"{module.upper()}_LAB_ROOT"
    val = os.environ.get(env_key, "").strip() or (cfg.get(env_key) or "").strip()
    if not val:
        return None
    p = Path(val)
    if not p.is_absolute():
        p = (REPO_ROOT / val).resolve()
    return p if p.exists() else None


def _run_dir_from_record(rec: dict, lab_root: Path | None) -> Path | None:
    """Get run directory path from registry record. Prefer manifest_path parent."""
    module = (rec.get("module") or "").strip().lower()
    root = lab_root or REPO_ROOT
    mp = rec.get("manifest_path")
    if isinstance(mp, str) and mp:
        norm = mp.replace("\\", "/")
        cand = root / norm
        if cand.is_file():
            return cand.parent
        parent = cand.parent
        if parent.exists():
            return parent
    lane = (rec.get("lane") or "").strip()
    run_id = (rec.get("run_id") or "").strip()
    if not lane or not run_id:
        return None
    cand = root / "exports" / "runs" / lane / run_id
    if cand.exists():
        return cand
    for ep in rec.get("evidence_paths") or []:
        if isinstance(ep, str) and "/" in ep:
            parts = ep.replace("\\", "/").split("/")
            if len(parts) >= 4 and "exports" in parts and "runs" in parts:
                idx = parts.index("runs") + 1
                sub = "/".join(parts[idx:])
                if sub:
                    cand = root / "exports" / "runs" / sub
                    if cand.is_file():
                        return cand.parent
                    if cand.parent.exists():
                        return cand.parent
    return None


def _count_files_and_warnings(run_dir: Path) -> tuple[dict[str, int], list[str]]:
    """Count KPI-relevant file existence and collect gate_codes from briefs/manifests."""
    metrics = {}
    for name in KPI_FILES:
        found = list(run_dir.rglob(name))
        metrics[f"has_{name.replace('.', '_')}"] = 1 if found else 0
    metrics["file_count"] = sum(1 for _ in run_dir.rglob("*") if _.is_file())
    warnings = []
    for mf in run_dir.rglob("geometry_manifest.json"):
        try:
            with open(mf, encoding="utf-8") as f:
                data = json.load(f)
            for k in ("gate_codes", "warnings"):
                for item in (data.get(k) or []):
                    if isinstance(item, str) and item:
                        warnings.append(item)
        except Exception:
            pass
    return metrics, list(dict.fromkeys(warnings))


def _write_kpi(run_dir: Path, rec: dict, metrics: dict, warnings: list[str]) -> bool:
    """Write kpi.json. Returns True on success."""
    kpi_path = run_dir / "kpi.json"
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = {
            "schema_version": "kpi.v1",
            "module": rec.get("module", ""),
            "lane": rec.get("lane", ""),
            "run_id": rec.get("run_id", ""),
            "round_id": rec.get("round_id", ""),
            "created_at": now,
            "metrics": metrics,
            "warnings": warnings,
        }
        kpi_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def _write_skipped(run_dir: Path, reason: str) -> bool:
    """Write KPI_SKIPPED.txt. Returns True on success."""
    path = run_dir / "KPI_SKIPPED.txt"
    try:
        path.write_text(reason.strip() + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def main() -> int:
    if not RUN_REGISTRY.exists():
        print("maybe_generate_kpi: run_registry not found, skip")
        return 0

    records = []
    try:
        with open(RUN_REGISTRY, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        print("maybe_generate_kpi: failed to read run_registry")
        return 0

    generated = 0
    skipped = 0
    for rec in records[-50:]:
        module = (rec.get("module") or "").strip().lower()
        lab_root = _get_lab_root(module) if module in ("fitting", "garment") else REPO_ROOT
        run_dir = _run_dir_from_record(rec, lab_root)
        if not run_dir or not run_dir.exists():
            continue
        kpi_path = run_dir / "kpi.json"
        skip_path = run_dir / "KPI_SKIPPED.txt"
        if kpi_path.exists():
            continue
        try:
            metrics, warnings = _count_files_and_warnings(run_dir)
            if _write_kpi(run_dir, rec, metrics, warnings):
                generated += 1
            else:
                _write_skipped(run_dir, "kpi write failed")
                skipped += 1
        except Exception as e:
            _write_skipped(run_dir, f"KPI generation failed: {e}")
            skipped += 1

    print(f"maybe_generate_kpi: generated={generated}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
