#!/usr/bin/env python3
"""
Local-only: Copy latest ops/docs files to shortcut folder for session start.
Never commit shortcut/**. Exit 0 always; failures surface as warnings.
"""
from __future__ import annotations

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHORTCUT_ROOT = REPO_ROOT / "shortcut"
SUBDIRS = ("common", "body", "fitting", "garment")


def _warn(msg: str) -> None:
    print(f"  [SKIP] {msg}")


def _copy(src: Path, dst: Path) -> bool:
    """Copy file; return True on success."""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        _warn(f"{src.name}: {e}")
        return False


def _find_by_patterns(repo: Path, patterns: list[str]) -> Path | None:
    """Find first file matching any pattern; prefer shortest path (closest to root). Excludes shortcut/."""
    found: list[Path] = []
    for p in patterns:
        for f in repo.rglob(p):
            if not f.is_file():
                continue
            if "shortcut" in f.parts:
                continue  # exclude our output folder
            found.append(f)
    if not found:
        return None
    return min(found, key=lambda x: len(x.parts))


def _ensure_dirs() -> None:
    for sub in SUBDIRS:
        (SHORTCUT_ROOT / sub).mkdir(parents=True, exist_ok=True)


def _collect_common() -> tuple[list[str], list[str]]:
    copied, skipped = [], []
    d = SHORTCUT_ROOT / "common"
    items = [
        ("ops/DASHBOARD.md", "DASHBOARD.md"),
        ("ops/hub_state_v1.json", "hub_state_v1.json"),
        ("contracts/master_plan_v1.json", "master_plan_v1.json"),
        ("contracts/renderer_input_contract_v1.md", "renderer_input_contract_v1.md"),
        ("ops/STATUS.md", "STATUS.md"),  # optional
    ]
    for rel, name in items:
        src = REPO_ROOT / rel
        if not src.exists():
            if "STATUS" in rel:
                continue
            skipped.append(rel)
            _warn(f"{rel} not found")
            continue
        if _copy(src, d / name):
            copied.append(f"common/{name}")
        else:
            skipped.append(rel)
    return copied, skipped


def _collect_body() -> tuple[list[str], list[str]]:
    copied, skipped = [], []
    d = SHORTCUT_ROOT / "body"

    # Body plan: search by name patterns (fallback: modules/body README)
    body_plan = _find_by_patterns(REPO_ROOT, ["*Body*Plan*.md", "*body*plan*.md", "*body*module*.md"])
    if not body_plan and (REPO_ROOT / "modules/body/README.md").exists():
        body_plan = REPO_ROOT / "modules/body/README.md"
    if body_plan:
        if _copy(body_plan, d / body_plan.name):
            copied.append(f"body/{body_plan.name}")
    else:
        skipped.append("Body_Module_Plan_v1.md (not found)")
        _warn("Body plan doc not found (searched *Body*Plan*.md, *body*plan*.md)")

    for rel, name in [
        ("contracts/dependency_ledger_v1.json", "dependency_ledger_v1.json"),
        ("contracts/trace_policy_v1.md", "trace_policy_v1.md"),
        ("ops/run_registry.jsonl", "run_registry.jsonl"),
    ]:
        src = REPO_ROOT / rel
        if not src.exists():
            continue
        if _copy(src, d / name):
            copied.append(f"body/{name}")
        else:
            skipped.append(rel)
    return copied, skipped


def _latest_llm_sync_brief(folder: Path, prefer: str | None) -> Path | None:
    """Latest LLM_SYNC*.txt by mtime; prefer FITTING/GARMENT if given."""
    files = list(folder.glob("LLM_SYNC_*.txt"))
    if not files:
        return None
    if prefer:
        prefixed = [f for f in files if prefer.upper() in f.name.upper()]
        files = prefixed if prefixed else files
    return max(files, key=lambda f: f.stat().st_mtime)


def _collect_fitting() -> tuple[list[str], list[str]]:
    copied, skipped = [], []
    d = SHORTCUT_ROOT / "fitting"
    brief_dir = REPO_ROOT / "exports" / "brief"

    # LLM_SYNC fitting
    if brief_dir.exists():
        latest = _latest_llm_sync_brief(brief_dir, "FITTING")
        if latest:
            if _copy(latest, d / latest.name):
                copied.append(f"fitting/{latest.name}")
        else:
            skipped.append("LLM_SYNC_FITTING*.txt")
            _warn("No LLM_SYNC_FITTING*.txt in exports/brief")
    else:
        _warn("exports/brief not found")

    # fitting plan
    fit_plan = _find_by_patterns(REPO_ROOT, ["*fitting*plan*.md", "*fitting*module*.md", "*fitting_interface*.md"])
    if fit_plan:
        if _copy(fit_plan, d / fit_plan.name):
            copied.append(f"fitting/{fit_plan.name}")
    else:
        _warn("fitting plan doc not found")

    # interface SSoT
    for cand in ["ssot/interface_ledger_v0.md", "contracts/fitting/fitting_interface_v0.md"]:
        src = REPO_ROOT / cand
        if src.exists():
            if _copy(src, d / src.name):
                copied.append(f"fitting/{src.name}")
            break
    return copied, skipped


def _collect_garment() -> tuple[list[str], list[str]]:
    copied, skipped = [], []
    d = SHORTCUT_ROOT / "garment"
    brief_dir = REPO_ROOT / "exports" / "brief"

    # LLM_SYNC garment
    if brief_dir.exists():
        latest = _latest_llm_sync_brief(brief_dir, "GARMENT")
        if latest:
            if _copy(latest, d / latest.name):
                copied.append(f"garment/{latest.name}")
        else:
            skipped.append("LLM_SYNC_GARMENT*.txt")
            _warn("No LLM_SYNC_GARMENT*.txt in exports/brief")
    else:
        _warn("exports/brief not found")

    # garment contract
    garment_doc = _find_by_patterns(
        REPO_ROOT,
        ["*garment*Product*Contract*.md", "*garment*Contract*.md", "*garment*step*.md", "*Garment*.md"],
    )
    if garment_doc:
        if _copy(garment_doc, d / garment_doc.name):
            copied.append(f"garment/{garment_doc.name}")
    else:
        _warn("garment contract/plan doc not found")

    # garment interface (optional; skip if same file already copied as main doc)
    step_md = REPO_ROOT / "modules/garment/docs/Garment_step.md"
    already_copied = garment_doc and str(step_md.resolve()) == str(garment_doc.resolve())
    if step_md.exists() and not already_copied:
        if _copy(step_md, d / step_md.name):
            copied.append(f"garment/{step_md.name}")
    return copied, skipped


def main() -> int:
    _ensure_dirs()
    all_copied: list[str] = []
    all_skipped: list[str] = []

    for name, collect in [
        ("common", _collect_common),
        ("body", _collect_body),
        ("fitting", _collect_fitting),
        ("garment", _collect_garment),
    ]:
        c, s = collect()
        all_copied.extend(c)
        all_skipped.extend(s)

    print("prepare_session_shortcuts:")
    if all_copied:
        print("  copied:")
        for p in all_copied:
            print(f"    {p}")
    if all_skipped:
        print("  skipped:")
        for p in all_skipped:
            print(f"    {p}")
    if not all_copied and not all_skipped:
        print("  (no files processed)")
    print(f"  done. shortcut_root={SHORTCUT_ROOT}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
