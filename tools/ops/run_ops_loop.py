#!/usr/bin/env python3
"""run_ops_loop.py — Standard ops loop entrypoint (Round 04 / cleanup R09 / gate R10).

Orchestrates the standard verification/progress workflow:
  - quick mode: doctor + next_step + render_status
  - full mode: doctor + u2_smokes + (optional u1 validators) + next_step + render_briefs+status

Options (composable):
  --restore-generated   Restores ops/STATUS.md and removes .tmp_pr_body.txt after the loop.
  --strict-clean        FAIL if working tree is dirty at start or end.
  --allow-pre-dirty     With --strict-clean: downgrade pre-dirty to WARN (post-dirty still FAIL).

Exit codes: 0 = PASS/WARN, 1 = FAIL
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Constants ────────────────────────────────────────────────────────

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

CORE_TOOLS = {
    "doctor": "tools/ops/doctor.py",
    "plan_lint": "tools/agent/plan_lint.py",
    "parallel_progress": "tools/ops/validate_parallel_progress.py",
    "next_step": "tools/agent/next_step.py",
    "u2_smokes": "tools/smoke/run_u2_smokes.py",
}

OPTIONAL_TOOLS = {
    "render_status": "tools/render_status.py",
    "render_work_briefs": "tools/render_work_briefs.py",
}

VALIDATORS = {
    "body": "tools/validate/validate_u1_body.py",
    "garment": "tools/validate/validate_u1_garment.py",
    "fitting": "tools/validate/validate_u1_fitting.py",
}


class ToolResult:
    """Result of a single tool execution."""
    __slots__ = ("tool_name", "exit_code", "stdout", "stderr", "severity")

    def __init__(self, tool_name: str, exit_code: int, stdout: str, stderr: str):
        self.tool_name = tool_name
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.severity = self._compute_severity()

    def _compute_severity(self) -> str:
        if self.exit_code == 0:
            # Check first line for SUMMARY indicators
            first_line = self.stdout.split("\n")[0] if self.stdout else ""
            if "SUMMARY:" in first_line:
                if "FAIL" in first_line:
                    return FAIL
                elif "WARN" in first_line:
                    return WARN
                else:
                    return PASS
            # Fallback: check full stdout
            elif "FAIL" in self.stdout:
                return FAIL
            elif "WARN" in self.stdout:
                return WARN
            else:
                return PASS
        else:
            return FAIL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "exit_code": self.exit_code,
            "severity": self.severity,
            "stdout_preview": self.stdout[:500] if self.stdout else "",
            "stderr_preview": self.stderr[:200] if self.stderr else "",
        }


# ── Repo root detection ──────────────────────────────────────────────

def find_repo_root(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find repository root by walking up until .git/ or project_map.md."""
    if start_dir is None:
        start_dir = Path.cwd()
    current = start_dir.resolve()
    while True:
        if (current / ".git").is_dir():
            return current
        if (current / "project_map.md").is_file():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


# ── Tool execution ───────────────────────────────────────────────────

def run_tool(repo_root: Path, tool_path: str, args: List[str]) -> ToolResult:
    """Execute a tool and capture result."""
    full_path = repo_root / tool_path
    if not full_path.is_file():
        return ToolResult(tool_path, 1, "", f"File not found: {full_path}")

    cmd = [sys.executable, str(full_path)] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        return ToolResult(tool_path, result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return ToolResult(tool_path, 1, "", "Timeout (>180s)")
    except Exception as exc:
        return ToolResult(tool_path, 1, "", f"Execution error: {exc}")


# ── Output formatting ────────────────────────────────────────────────

def _safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def print_summary(results: List[ToolResult], mode: str, *,
                  json_output: bool = False) -> int:
    """Print summary and return exit code."""
    worst = PASS
    counts = {PASS: 0, WARN: 0, FAIL: 0}
    for r in results:
        counts[r.severity] = counts.get(r.severity, 0) + 1
        rank = {PASS: 0, WARN: 1, FAIL: 2}.get(r.severity, 0)
        worst_rank = {PASS: 0, WARN: 1, FAIL: 2}.get(worst, 0)
        if rank > worst_rank:
            worst = r.severity

    if json_output:
        out = {
            "summary": worst,
            "mode": mode,
            "tools_run": [r.to_dict() for r in results],
        }
        _safe_print(json.dumps(out, indent=2, ensure_ascii=False))
        return 1 if worst == FAIL else 0

    # Human-readable
    if worst == PASS:
        _safe_print("OPS LOOP SUMMARY: PASS")
    else:
        _safe_print(f"OPS LOOP SUMMARY: {worst} ({counts[worst]})")
    _safe_print()

    _safe_print(f"-- Mode: {mode} --")
    _safe_print()

    for r in results:
        _safe_print(f"-- {r.tool_name} [{r.severity}] --")
        # Print first 20 lines of stdout
        lines = r.stdout.split("\n")[:20]
        for line in lines:
            _safe_print(f"  {line}")
        if len(r.stdout.split("\n")) > 20:
            _safe_print("  ...")
        if r.stderr:
            _safe_print(f"  [stderr]: {r.stderr[:200]}")
        _safe_print()

    _safe_print("-- Next Actions --")
    if worst == FAIL:
        _safe_print("  Fix FAIL items above, then re-run.")
    else:
        _safe_print("  py tools/agent/next_step.py --module all --top 5")
        _safe_print("  py tools/ops/run_ops_loop.py --mode full  # for comprehensive check")

    return 1 if worst == FAIL else 0


# ── Git working-tree check (Round 10) ────────────────────────────────

def _git_status_porcelain(repo_root: Path) -> Tuple[Optional[str], Optional[str]]:
    """Run git status --porcelain.  Returns (stdout, error_msg).
    On success error_msg is None; on failure stdout is None."""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=15,
        )
        if r.returncode == 0:
            return r.stdout, None
        return None, f"git status exit {r.returncode}: {(r.stderr or '').strip()[:120]}"
    except FileNotFoundError:
        return None, "git not found on PATH"
    except Exception as exc:
        return None, str(exc)


def _is_clean(porcelain_output: str) -> bool:
    return porcelain_output.strip() == ""


def _dirty_files_summary(porcelain_output: str, max_lines: int = 20) -> str:
    lines = [l for l in porcelain_output.strip().splitlines() if l.strip()]
    shown = lines[:max_lines]
    text = "\n".join(f"    {l}" for l in shown)
    if len(lines) > max_lines:
        text += f"\n    ... ({len(lines) - max_lines} more)"
    return text


# ── Post-loop cleanup (Round 09) ─────────────────────────────────────

# Files to restore/remove when --restore-generated is active
_GENERATED_RESTORE_TARGETS = [
    "ops/STATUS.md",
]
_TEMP_REMOVE_TARGETS = [
    ".tmp_pr_body.txt",
]


def _cleanup_generated(repo_root: Path, *, json_output: bool = False) -> None:
    """Restore generated files and remove temp files. WARN on failure, never FAIL."""
    cleanup_lines: List[str] = []

    def _log(msg: str) -> None:
        cleanup_lines.append(msg)

    _log("[CLEANUP] restore_generated: ON")

    # 1. git restore generated files
    for rel_path in _GENERATED_RESTORE_TARGETS:
        full = repo_root / rel_path
        if not full.is_file():
            _log(f"[CLEANUP] {rel_path}: missing (skipped)")
            continue
        try:
            r = subprocess.run(
                ["git", "restore", rel_path],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if r.returncode == 0:
                _log(f"[CLEANUP] {rel_path}: restored")
            else:
                stderr_brief = (r.stderr or "").strip()[:120]
                _log(f"[CLEANUP] {rel_path}: warn (git restore exit {r.returncode}: {stderr_brief})")
        except Exception as exc:
            _log(f"[CLEANUP] {rel_path}: warn ({exc})")

    # 2. Remove temp files
    for rel_path in _TEMP_REMOVE_TARGETS:
        full = repo_root / rel_path
        if not full.is_file():
            _log(f"[CLEANUP] {rel_path}: absent")
            continue
        try:
            full.unlink()
            _log(f"[CLEANUP] {rel_path}: removed")
        except OSError as exc:
            _log(f"[CLEANUP] {rel_path}: warn (delete failed: {exc})")

    # Print cleanup report
    if not json_output:
        _safe_print()
        for line in cleanup_lines:
            _safe_print(f"  {line}")


# ── Main ─────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Standard ops loop entrypoint (Round 04 / cleanup R09 / gate R10)")
    parser.add_argument("--mode", type=str, default="quick",
                        choices=["quick", "full"],
                        help="Execution mode (default: quick)")
    parser.add_argument("--top", type=int, default=5,
                        help="Number of top next steps (default: 5)")
    parser.add_argument("--module", type=str, default="all",
                        choices=["body", "garment", "fitting", "common", "all"],
                        help="Module filter for next_step (default: all)")
    parser.add_argument("--plan", type=str, default="contracts/master_plan_v1.json",
                        help="Path to plan JSON (default: contracts/master_plan_v1.json)")
    parser.add_argument("--run-dir", type=str, default=None,
                        help="Run directory for U1 validators (optional)")
    parser.add_argument("--skip-render", action="store_true",
                        help="Skip render_briefs/render_status")
    parser.add_argument("--restore-generated", action="store_true",
                        help="Restore ops/STATUS.md and remove temp files after loop (Round 09)")
    parser.add_argument("--strict-clean", action="store_true",
                        help="FAIL if working tree dirty at start or end (Round 10)")
    parser.add_argument("--allow-pre-dirty", action="store_true",
                        help="With --strict-clean: downgrade pre-dirty to WARN (Round 10)")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Output structured JSON")
    args = parser.parse_args(argv)

    # Repo root
    repo_root = find_repo_root()
    if not repo_root:
        _safe_print("ERROR: Could not find repo root. Run from repo directory.")
        return 1

    # ── 0. Pre-check: strict-clean gate (Round 10) ───────────────────
    strict = args.strict_clean
    pre_status = "clean"  # default for reporting when strict is OFF

    if strict:
        out, err = _git_status_porcelain(repo_root)
        if err is not None:
            # git failed → cannot guarantee cleanliness
            _safe_print(f"[STRICT_CLEAN] pre-check ERROR: {err}")
            _safe_print("[STRICT_CLEAN] pre=error post=skipped policy=FAIL")
            return 1
        if not _is_clean(out):
            pre_status = "dirty"
            if args.allow_pre_dirty:
                _safe_print("[STRICT_CLEAN] pre=dirty (WARN, --allow-pre-dirty)")
                _safe_print(_dirty_files_summary(out))
            else:
                _safe_print("[STRICT_CLEAN] pre=dirty policy=FAIL")
                _safe_print(_dirty_files_summary(out))
                _safe_print()
                _safe_print("Workspace is dirty before ops loop. Commit or stash first,")
                _safe_print("or use --allow-pre-dirty to downgrade to WARN.")
                return 1
        else:
            pre_status = "clean"

    results: List[ToolResult] = []

    # 1. Doctor (always)
    results.append(run_tool(repo_root, CORE_TOOLS["doctor"], []))
    results.append(run_tool(repo_root, CORE_TOOLS["plan_lint"], ["--plan", args.plan]))
    results.append(run_tool(repo_root, CORE_TOOLS["parallel_progress"], []))

    # 2. Mode-specific tools
    if args.mode == "full":
        # U2 smokes
        results.append(run_tool(repo_root, CORE_TOOLS["u2_smokes"], []))

        # U1 validators (if run-dir provided)
        if args.run_dir:
            run_dir_path = Path(args.run_dir)
            if not run_dir_path.is_absolute():
                run_dir_path = repo_root / run_dir_path

            for module, validator_path in VALIDATORS.items():
                validator_full = repo_root / validator_path
                if validator_full.is_file():
                    results.append(run_tool(repo_root, validator_path,
                                           ["--run-dir", str(run_dir_path)]))

    # 3. Next step (always)
    next_step_args = [
        "--module", args.module,
        "--top", str(args.top),
        "--plan", args.plan,
    ]
    results.append(run_tool(repo_root, CORE_TOOLS["next_step"], next_step_args))

    # 4. Render (if not skipped and mode=full)
    if not args.skip_render:
        if args.mode == "full":
            # render_work_briefs (optional)
            briefs_path = OPTIONAL_TOOLS["render_work_briefs"]
            if (repo_root / briefs_path).is_file():
                results.append(run_tool(repo_root, briefs_path, []))
            else:
                results.append(ToolResult(briefs_path, 0, "[SKIP] Not found", ""))

        # render_status (both modes)
        status_path = OPTIONAL_TOOLS["render_status"]
        if (repo_root / status_path).is_file():
            results.append(run_tool(repo_root, status_path, []))
        else:
            results.append(ToolResult(status_path, 0, "[SKIP] Not found", ""))

    # Print summary
    exit_code = print_summary(results, args.mode, json_output=args.json_output)

    # 5. Post-loop cleanup (Round 09)
    if args.restore_generated:
        _cleanup_generated(repo_root, json_output=args.json_output)

    # ── 6. Post-check: strict-clean gate (Round 10) ──────────────────
    if strict:
        out, err = _git_status_porcelain(repo_root)
        if err is not None:
            _safe_print(f"\n[STRICT_CLEAN] post-check ERROR: {err}")
            _safe_print(f"[STRICT_CLEAN] pre={pre_status} post=error policy=FAIL")
            return 1
        post_clean = _is_clean(out)
        post_status = "clean" if post_clean else "dirty"
        policy = "FAIL" if not post_clean else ("WARN" if pre_status == "dirty" else "PASS")

        if not args.json_output:
            _safe_print()
            _safe_print(f"[STRICT_CLEAN] pre={pre_status} post={post_status} policy={policy}")
            if not post_clean:
                _safe_print(_dirty_files_summary(out))

        if not post_clean:
            return 1
    elif not args.json_output:
        _safe_print()
        _safe_print("[STRICT_CLEAN] policy=OFF")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
