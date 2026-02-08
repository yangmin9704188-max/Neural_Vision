#!/usr/bin/env python3
"""
P7 Backfill: run_dir 루트에 geometry_manifest.json 생성/복사.
대상: exports/runs/_smoke/20260206_170827, 20260206_171040
"""
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _patch_fingerprint(data: dict) -> dict:
    """fingerprint 없으면 inputs_fingerprint 또는 sha256:unknown 추가(compat)."""
    d = dict(data)
    if "fingerprint" not in d:
        d["fingerprint"] = d.get("inputs_fingerprint") or "sha256:unknown"
    return d


def _backfill_run_dir(run_dir: Path) -> tuple[bool, str]:
    """run_dir 루트에 geometry_manifest.json 보장. Returns (ok, message)."""
    root_geo = run_dir / "geometry_manifest.json"
    if root_geo.exists():
        try:
            data = json.loads(root_geo.read_text(encoding="utf-8"))
            if "fingerprint" not in data:
                patched = _patch_fingerprint(data)
                root_geo.write_text(json.dumps(patched, ensure_ascii=False, indent=2), encoding="utf-8")
                return True, "patched fingerprint"
        except Exception:
            pass
        return True, "already exists"

    candidates = sorted(run_dir.rglob("geometry_manifest.json"), key=lambda p: len(p.parts))
    if not candidates:
        readme = run_dir / "RUN_README.md"
        line = "\nBACKFILL FAILED: no geometry_manifest.json found under run_dir\n"
        try:
            with open(readme, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass
        return False, "no candidate, README appended"

    src = candidates[0]
    try:
        raw = src.read_text(encoding="utf-8")
        data = json.loads(raw)
        patched = _patch_fingerprint(data)
        root_geo.write_text(json.dumps(patched, ensure_ascii=False, indent=2), encoding="utf-8")
        return True, "copied+patched"
    except Exception as e:
        try:
            shutil.copy2(src, root_geo)
            raw = root_geo.read_text(encoding="utf-8")
            data = json.loads(raw)
            patched = _patch_fingerprint(data)
            root_geo.write_text(json.dumps(patched, ensure_ascii=False, indent=2), encoding="utf-8")
            return True, "copied+patched (fallback)"
        except Exception as e2:
            readme = run_dir / "RUN_README.md"
            line = f"\nBACKFILL FAILED: {e2}\n"
            try:
                with open(readme, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                pass
            return False, str(e2)


def main() -> int:
    targets = [
        REPO / "exports" / "runs" / "_smoke" / "20260206_170827",
        REPO / "exports" / "runs" / "_smoke" / "20260206_171040",
    ]
    for run_dir in targets:
        if not run_dir.is_dir():
            print(f"skip (not dir): {run_dir}")
            continue
        ok, msg = _backfill_run_dir(run_dir)
        status = "OK" if ok else "FAIL"
        print(f"{status} {run_dir.name}: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
