#!/usr/bin/env python3
"""
Rule F0: Change Boundary Blocker

Prevents mixing Body (legacy) region changes with Fitting region changes in the same PR.
This enables safe parallel development by different agents without merge conflicts.

Usage:
    python tools/ops/check_change_boundaries.py --base origin/main --head HEAD

    Or use environment variables:
    BASE=origin/main HEAD=HEAD python tools/ops/check_change_boundaries.py

Exit codes:
    0: No boundary violation (safe to merge)
    1: Boundary violation detected (merge blocked)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


# Boundaries (modules/body/ added for NEW_REPO layout)
BODY_REGIONS = [
    "core/",
    "verification/",
    "modules/body/",
]

FITTING_REGIONS = [
]

GARMENT_REGIONS = [
]
LEGACY_MIRROR_REGIONS = [
    "modules/fitting/",
    "modules/garment/",
]

# Blocklist: local-only paths that must never be committed (ops automation)
FORBIDDEN_LOCAL = [
    "ops/lab_roots.local.json",
    "ops/local/",
    "exports/logs/",
]

# Allowlist: shared paths that don't trigger boundary violations
# tools/ops/ = shared hub infrastructure (renderers, hooks, etc.)
# tools/ (non-ops) scripts that are shared across modules
ALLOWLIST = [
    "specs/",
    "docs/ops/rounds/",
    "docs/ops/BACKFILL_LOG.md",
    "specs/common/geometry_manifest.schema.json",
    ".cursorrules",
    "docs/ops/GUARDRAILS.md",
    "CLAUDE.md",
    "tools/ops/",
    "tools/render_status.py",
    "tools/render_work_briefs.py",
]


def normalize_path(path: str) -> str:
    """Normalize path to use forward slashes (OS-independent)."""
    return Path(path).as_posix()


def is_forbidden_local(file_path: str) -> bool:
    """Check if file is in forbidden local-only paths (never commit)."""
    normalized = normalize_path(file_path)
    for pattern in FORBIDDEN_LOCAL:
        if pattern.endswith("/"):
            if normalized == pattern.rstrip("/") or normalized.startswith(pattern):
                return True
        else:
            if normalized == pattern or normalized.startswith(pattern + "/"):
                return True
    return False


def is_allowlisted(file_path: str) -> bool:
    """Check if file is in allowlist."""
    normalized = normalize_path(file_path)
    for allowed in ALLOWLIST:
        if normalized == allowed or normalized.startswith(allowed):
            return True
    return False


def is_body_region(file_path: str) -> bool:
    """Check if file is in body (legacy) region."""
    normalized = normalize_path(file_path)
    for region in BODY_REGIONS:
        if normalized.startswith(region):
            return True
    return False


def is_fitting_region(file_path: str) -> bool:
    """Check if file is in fitting region."""
    normalized = normalize_path(file_path)
    for region in FITTING_REGIONS:
        if normalized.startswith(region):
            return True
    return False


def is_garment_region(file_path: str) -> bool:
    """Check if file is in garment region."""
    normalized = normalize_path(file_path)
    for region in GARMENT_REGIONS:
        if normalized.startswith(region):
            return True
    return False


def get_changed_files(base: str, head: str) -> list[str]:
    """Get list of changed files between base and head."""
    try:
        # Use git diff to get changed files
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...{head}"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        return files
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to get changed files: {e}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)


def classify_files(files: list[str]) -> dict[str, list[str]]:
    """
    Classify files into categories.

    Returns:
        dict with keys: allowlisted, body_triggering, fitting_triggering, garment_triggering, legacy_mirror_triggering, other
    """
    result = {
        "allowlisted": [],
        "body_triggering": [],
        "fitting_triggering": [],
        "garment_triggering": [],
        "legacy_mirror_triggering": [],
        "other": [],
    }

    for file in files:
        if is_allowlisted(file):
            result["allowlisted"].append(file)
        elif any(normalize_path(file).startswith(prefix) for prefix in LEGACY_MIRROR_REGIONS):
            result["legacy_mirror_triggering"].append(file)
        elif is_body_region(file):
            result["body_triggering"].append(file)
        elif is_fitting_region(file):
            result["fitting_triggering"].append(file)
        elif is_garment_region(file):
            result["garment_triggering"].append(file)
        else:
            result["other"].append(file)

    return result


def print_diagnostics(classified: dict[str, list[str]]):
    """Print clear diagnostics about file classifications."""
    print("=" * 70)
    print("Change Boundary Analysis (Rule F0)")
    print("=" * 70)

    if classified["body_triggering"]:
        print(f"\n[BODY] Body region files ({len(classified['body_triggering'])}):")
        for f in classified["body_triggering"]:
            print(f"  - {f}")

    if classified["fitting_triggering"]:
        print(f"\n[FITTING] Fitting region files ({len(classified['fitting_triggering'])}):")
        for f in classified["fitting_triggering"]:
            print(f"  - {f}")

    if classified["garment_triggering"]:
        print(f"\n[GARMENT] Garment region files ({len(classified['garment_triggering'])}):")
        for f in classified["garment_triggering"]:
            print(f"  - {f}")

    if classified["legacy_mirror_triggering"]:
        print(f"\n[LEGACY MIRROR] Deprecated in-repo fitting/garment paths ({len(classified['legacy_mirror_triggering'])}):")
        for f in classified["legacy_mirror_triggering"]:
            print(f"  - {f}")

    if classified["allowlisted"]:
        print(f"\n[OK] Allowlisted files ({len(classified['allowlisted'])}):")
        for f in classified["allowlisted"]:
            print(f"  - {f}")

    if classified["other"]:
        print(f"\n[OTHER] Other files ({len(classified['other'])}):")
        for f in classified["other"]:
            print(f"  - {f}")


def check_boundary_violation(classified: dict[str, list[str]]) -> bool:
    """
    Check if there's a boundary violation.

    Returns:
        True if violation detected (body changes mixed with fitting or garment changes), False otherwise
    """
    has_body = len(classified["body_triggering"]) > 0
    has_fitting = len(classified["fitting_triggering"]) > 0
    has_garment = len(classified["garment_triggering"]) > 0
    has_legacy_mirror = len(classified["legacy_mirror_triggering"]) > 0

    # Body cannot be mixed with fitting or garment in the same PR
    return has_legacy_mirror or (has_body and (has_fitting or has_garment))


def suggest_action(classified: dict[str, list[str]]):
    """Suggest actions to fix boundary violation."""
    print("\n" + "=" * 70)
    print("[FAIL] BOUNDARY VIOLATION DETECTED")
    print("=" * 70)
    if classified["legacy_mirror_triggering"]:
        print("\nThis PR touches deprecated in-repo fitting/garment mirror paths.")
    else:
        print("\nThis PR contains changes in BOTH Body and Fitting/Garment regions.")
    print("This violates Rule F0 which prevents parallel work collisions.\n")

    print("Suggested actions:")
    print("  1. Split this PR into two separate PRs:")
    print("     - PR-A: Body region changes only")
    print("     - PR-B: Fitting region changes only")
    print("  2. Move shared changes to allowlisted paths:")
    print("     - specs/** for schema/spec changes")
    print("     - docs/ops/rounds/roundXX_<module>_<agent>.md for round notes")
    print("  3. If changes are truly interdependent, request exception approval")
    print("  4. Do not edit modules/fitting/** or modules/garment/** in this repo")
    print("     (those modules are now external sibling repos)")
    print("\nAllowlisted paths (these don't trigger violations):")
    for allowed in ALLOWLIST:
        print(f"  - {allowed}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Check change boundaries between Body and Fitting regions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/ops/check_change_boundaries.py --base origin/main --head HEAD
  BASE=origin/main HEAD=HEAD python tools/ops/check_change_boundaries.py

Boundaries:
  Body region:    core/, verification/, modules/body/
  Fitting region: external repo only
  Garment region: external repo only
  Deprecated in-repo mirrors: modules/fitting/, modules/garment/ (do not edit)
  Shared (allowlisted): tools/ops/, tools/render_*.py, specs/, .cursorrules, etc.
        """,
    )

    parser.add_argument(
        "--base",
        default=os.environ.get("BASE", "origin/main"),
        help="Base branch/commit (default: origin/main or $BASE)",
    )
    parser.add_argument(
        "--head",
        default=os.environ.get("HEAD", "HEAD"),
        help="Head branch/commit (default: HEAD or $HEAD)",
    )

    args = parser.parse_args()

    print(f"Checking change boundaries: {args.base}...{args.head}")

    # Get changed files
    changed_files = get_changed_files(args.base, args.head)

    if not changed_files:
        print("\n[PASS] No files changed. Boundary check: PASS")
        sys.exit(0)

    # Check for forbidden local-only files (ops automation)
    forbidden = [f for f in changed_files if is_forbidden_local(f)]
    if forbidden:
        print("\n[FAIL] Local-only files must not be committed:")
        for f in forbidden:
            print(f"  - {f}")
        print("These paths are gitignored (ops/local/, exports/logs/, ops/lab_roots.local.json).")
        sys.exit(1)

    # Classify files
    classified = classify_files(changed_files)

    # Print diagnostics
    print_diagnostics(classified)

    # Check for violations
    if check_boundary_violation(classified):
        suggest_action(classified)
        print("\n[FAIL] Boundary check: FAIL")
        sys.exit(1)
    else:
        print("\n" + "=" * 70)
        print("[PASS] Boundary check: PASS")
        print("=" * 70)
        print("\nNo boundary violation detected. Safe to merge.")
        sys.exit(0)


if __name__ == "__main__":
    main()
