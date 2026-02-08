#!/usr/bin/env python3
"""autorender_tick.py — Gated entrypoint for periodic status refresh (Round 08).

If the scheduler (Windows Task Scheduler or any cron) calls this script,
it checks ops/autorender.local.json.  Default behaviour is **no-op**
(enabled=false).

Config file: ops/autorender.local.json  (gitignored)
Example:     ops/autorender.local.example.json  (tracked)

Schema:
    {"enabled": false, "mode": "quick"}
    enabled: bool  — must be explicitly true to run
    mode: "quick" | "full"  — maps to run_ops_loop.py --mode

Exit codes: 0 = success or disabled-noop, 1 = error
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _find_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from *start* (default: script dir) looking for .git/."""
    cur = (start or Path(__file__).resolve().parent).resolve()
    for _ in range(20):
        if (cur / ".git").is_dir():
            return cur
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent
    return None


def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def main() -> int:
    repo_root = _find_repo_root()
    if repo_root is None:
        _safe_print("AUTORENDER: ERROR — repo root not found")
        return 1

    config_path = repo_root / "ops" / "autorender.local.json"

    # ── Read config (missing = disabled) ─────────────────────────────
    enabled = False
    mode = "quick"

    if config_path.is_file():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            enabled = data.get("enabled", False) is True
            mode = data.get("mode", "quick")
            if mode not in ("quick", "full"):
                _safe_print(f"AUTORENDER: WARN — invalid mode '{mode}', defaulting to 'quick'")
                mode = "quick"
        except (json.JSONDecodeError, OSError) as exc:
            _safe_print(f"AUTORENDER: WARN — config parse error: {exc}, treating as disabled")
            enabled = False

    # ── Gate: disabled → no-op ───────────────────────────────────────
    if not enabled:
        _safe_print("AUTORENDER: DISABLED (no-op)")
        return 0

    # ── Enabled → run ops loop ───────────────────────────────────────
    _safe_print(f"AUTORENDER: ENABLED (mode={mode})")
    _safe_print("WARNING: This will update ops/STATUS.md (workspace may become dirty)")

    loop_script = repo_root / "tools" / "ops" / "run_ops_loop.py"
    if not loop_script.is_file():
        _safe_print(f"AUTORENDER: ERROR — {loop_script} not found")
        return 1

    cmd = [sys.executable, str(loop_script), "--mode", mode]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            timeout=300,
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        _safe_print("AUTORENDER: ERROR — run_ops_loop.py timed out (>300s)")
        return 1
    except Exception as exc:
        _safe_print(f"AUTORENDER: ERROR — {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
