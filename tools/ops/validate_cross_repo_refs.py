#!/usr/bin/env python3
"""
Validate cross-repo path references against cross_repo_interface_policy_v1.

Default mode is warn-only (policy.enforcement.mode=warn), so existing legacy
references are visible without breaking ops loop. Can be upgraded to fail.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


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


def _load_policy(path: Path) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _git_ls_files(repo_root: Path) -> List[str]:
    try:
        r = subprocess.run(
            ["git", "ls-files"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        if r.returncode != 0:
            return []
        return [ln.strip().replace("\\", "/") for ln in r.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


def _match_any(path: str, patterns: List[str]) -> bool:
    p = path.replace("\\", "/")
    return any(fnmatch.fnmatch(p, pat.replace("\\", "/")) for pat in patterns)


def _scan_file(path: Path, forbidden: List[str]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings
    lines = text.splitlines()
    normalized_forbidden = [p.replace("\\", "/") for p in forbidden]
    for i, line in enumerate(lines, start=1):
        line_norm = line.replace("\\", "/")
        for pat in normalized_forbidden:
            # Convert glob to a simple contains-like check by stripping wildcard segments.
            # This avoids heavy regex and is sufficient for path literals in scripts.
            anchors = [seg for seg in pat.split("*") if seg and seg not in {"/", "//"} and len(seg.strip()) >= 3]
            if anchors and all(a in line_norm for a in anchors):
                findings.append(
                    {
                        "path": str(path).replace("\\", "/"),
                        "line": i,
                        "pattern": pat,
                        "snippet": line.strip()[:180],
                    }
                )
                break
    return findings


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate cross-repo reference policy")
    parser.add_argument("--policy", default="contracts/cross_repo_interface_policy_v1.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = _find_repo_root()
    if not repo_root:
        _safe_print("CROSS_REPO_REFS SUMMARY: FAIL")
        _safe_print("[POLICY] repo root not found")
        return 1

    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = repo_root / policy_path
    policy = _load_policy(policy_path)
    if not policy:
        _safe_print("CROSS_REPO_REFS SUMMARY: FAIL")
        _safe_print(f"[POLICY] cannot load: {policy_path}")
        return 1

    forbidden = [str(x) for x in policy.get("forbidden_path_patterns") or []]
    scope = policy.get("scan_scope") or {}
    include_globs = [str(x) for x in scope.get("include_globs") or []]
    exclude_globs = [str(x) for x in scope.get("exclude_globs") or []]
    mode = str((policy.get("enforcement") or {}).get("mode") or "warn").lower()

    files = _git_ls_files(repo_root)
    candidates = [
        p for p in files
        if _match_any(p, include_globs) and not _match_any(p, exclude_globs)
    ]

    findings: List[Dict[str, Any]] = []
    for rel in candidates:
        path = repo_root / rel
        findings.extend(_scan_file(path, forbidden))

    summary = PASS
    if findings:
        summary = WARN if mode == "warn" else FAIL

    if args.json:
        out = {
            "summary": summary,
            "enforcement_mode": mode,
            "scan_count": len(candidates),
            "findings_count": len(findings),
            "findings": findings[:200],
        }
        _safe_print(json.dumps(out, indent=2, ensure_ascii=False))
        return 1 if summary == FAIL else 0

    if summary == PASS:
        _safe_print("CROSS_REPO_REFS SUMMARY: PASS")
        return 0

    _safe_print(f"CROSS_REPO_REFS SUMMARY: {summary}")
    _safe_print(f"-- enforcement_mode: {mode}")
    _safe_print(f"-- scanned_files: {len(candidates)}")
    _safe_print(f"-- findings: {len(findings)}")
    for f in findings[:30]:
        _safe_print(
            f"[CROSS_REPO_REF] {f['path']}:{f['line']} pattern={f['pattern']} | {f['snippet']}"
        )
    if len(findings) > 30:
        _safe_print(f"... {len(findings) - 30} more")
    return 1 if summary == FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
