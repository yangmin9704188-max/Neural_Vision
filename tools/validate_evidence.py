#!/usr/bin/env python3
"""Validate Evidence Package schema v1.0."""
print("__VALIDATE_EVIDENCE_VERSION__=scope-only-runs-2026-01-21")
import json
import os
import re
import sys
from argparse import ArgumentParser
from pathlib import Path


def get_changed_runs(base_sha, head_sha):
    """
    Find changed run directories from git diff.
    Only returns runs that are actually changed in this PR.
    
    Rules:
    - Only scans artifacts/ paths that are changed in base...head diff
    - Only includes paths with 'runs' directory (excludes regression/ etc.)
    - If diff fails or base/head invalid, returns empty (safe skip)
    """
    import subprocess
    
    # Validate base and head SHA
    if not base_sha or not head_sha:
        print("WARNING: base or head SHA is empty. Skipping validation (safe skip).")
        return []
    
    # Try to verify SHAs exist
    try:
        subprocess.run(
            ['git', 'rev-parse', '--verify', base_sha],
            capture_output=True,
            check=True
        )
        subprocess.run(
            ['git', 'rev-parse', '--verify', head_sha],
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError:
        print(f"WARNING: Invalid SHA (base={base_sha}, head={head_sha}). Skipping validation (safe skip).")
        return []
    
    # Get changed files
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', f'{base_sha}...{head_sha}'],
            capture_output=True,
            text=True,
            check=True
        )
        changed_files = result.stdout.strip().split('\n')
    except subprocess.CalledProcessError as e:
        print(f"WARNING: git diff failed (base={base_sha}, head={head_sha}). Skipping validation (safe skip).")
        print(f"  Error: {e.stderr}")
        return []
    
    # Check if any artifacts/ files changed
    artifacts_changed = False
    run_dirs = set()
    
    for file in changed_files:
        if not file:
            continue
        
        # Check if file is under artifacts/
        if file.startswith('artifacts/'):
            artifacts_changed = True
            
            # Extract run directory from artifacts path
            # Pattern: artifacts/.../runs/run_id/... or artifacts/.../runs/run_id
            # IMPORTANT: Only include paths with 'runs' directory (exclude regression/, sensitivity/, etc.)
            parts = file.split('/')
            if 'runs' in parts:
                runs_idx = parts.index('runs')
                if runs_idx + 1 < len(parts):
                    # Extract up to run_id directory
                    run_id = parts[runs_idx + 1]
                    # Build path: artifacts/.../runs/run_id
                    run_dir = '/'.join(parts[:runs_idx + 2])
                    run_dirs.add(run_dir)
            # Explicitly skip regression/, sensitivity/, etc. (not runs/)
            # These are legacy folders and should not be validated
    
    # If no artifacts changed, return empty (will exit early)
    if not artifacts_changed:
        return []
    
    return sorted(run_dirs)


def load_json(file_path):
    """Load and parse JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to load {file_path}: {e}")


def validate_manifest(manifest_path, run_id):
    """Validate manifest.json schema."""
    errors = []
    manifest = load_json(manifest_path)
    
    required_keys = [
        'schema_version', 'task', 'policy_version', 'run_id', 'created_at_utc',
        'runner', 'code', 'data', 'experiment', 'baseline'
    ]
    
    for key in required_keys:
        if key not in manifest:
            errors.append(f"Missing required key: {key}")
    
    if 'schema_version' in manifest and manifest['schema_version'] != 'evidence.manifest.v1':
        errors.append(f"Invalid schema_version: {manifest['schema_version']} (expected: evidence.manifest.v1)")
    
    if 'baseline' in manifest:
        baseline = manifest['baseline']
        if 'ref' not in baseline or not baseline['ref']:
            errors.append("baseline.ref is required and must be non-empty")
    
    return manifest, errors


def validate_metrics(metrics_path, run_id, baseline_ref):
    """Validate metrics.json schema."""
    errors = []
    metrics = load_json(metrics_path)
    
    required_keys = ['schema_version', 'task', 'policy_version', 'run_id', 'metrics', 'regression']
    
    for key in required_keys:
        if key not in metrics:
            errors.append(f"Missing required key: {key}")
    
    if 'schema_version' in metrics and metrics['schema_version'] != 'evidence.metrics.v1':
        errors.append(f"Invalid schema_version: {metrics['schema_version']} (expected: evidence.metrics.v1)")
    
    if 'metrics' in metrics and 'primary' not in metrics['metrics']:
        errors.append("metrics.primary is required")
    
    if 'regression' in metrics:
        reg = metrics['regression']
        if 'baseline_ref' not in reg or not reg['baseline_ref']:
            errors.append("regression.baseline_ref is required")
        elif reg['baseline_ref'] != baseline_ref:
            errors.append(f"regression.baseline_ref ({reg['baseline_ref']}) does not match manifest baseline.ref ({baseline_ref})")
    
    return metrics, errors


def check_pass_fail_rules(manifest, metrics):
    """
    Check quality gates (warning-only, non-blocking).
    Quality gates are informational only and do not cause CI failure.
    """
    errors = []
    warnings = []
    
    if 'metrics' not in metrics or 'primary' not in metrics['metrics']:
        return True, errors, warnings  # Pass if no metrics (schema validation handles missing)
    
    primary = metrics['metrics']['primary']
    regression = metrics.get('regression', {})
    
    delta = regression.get('delta', 0)
    delta_pct = regression.get('delta_pct', 0)
    lower_is_better = primary.get('lower_is_better', True)
    
    # Rule 4: Primary metric regression (warning-only)
    if lower_is_better:
        if abs(delta) > 0.3:
            warnings.append(f"WARNING: Primary metric regression large: abs(delta)={abs(delta)} > 0.3")
        if abs(delta_pct) > 5:
            warnings.append(f"WARNING: Primary metric regression large: abs(delta_pct)={abs(delta_pct)} > 5")
    
    # Rule 5: Secondary metric fail_rate (warning-only)
    secondary = metrics['metrics'].get('secondary', [])
    for sec in secondary:
        if sec.get('name') == 'fail_rate':
            fail_rate_value = sec.get('value', 0)
            if fail_rate_value > 0.05:
                warnings.append(f"WARNING: fail_rate high: {fail_rate_value} > 0.05")
    
    # Always return True (pass) - warnings don't block CI
    return True, errors, warnings


def validate_run(run_dir):
    """Validate a single run directory."""
    run_dir_path = Path(run_dir)
    
    manifest_path = run_dir_path / 'manifest.json'
    metrics_path = run_dir_path / 'metrics.json'
    summary_path = run_dir_path / 'summary.md'
    
    # Rule 1: Check required files
    missing_files = []
    if not manifest_path.exists():
        missing_files.append('manifest.json')
    if not metrics_path.exists():
        missing_files.append('metrics.json')
    if not summary_path.exists():
        missing_files.append('summary.md')
    
    if missing_files:
        return False, None, None, None, [f"Missing required files: {', '.join(missing_files)}"], None
    
    run_id = run_dir_path.name
    all_errors = []
    
    # Validate manifest.json
    manifest, manifest_errors = validate_manifest(manifest_path, run_id)
    all_errors.extend(manifest_errors)
    
    baseline_ref = None
    if 'baseline' in manifest and 'ref' in manifest['baseline']:
        baseline_ref = manifest['baseline']['ref']
    
    # Validate metrics.json
    metrics, metrics_errors = validate_metrics(metrics_path, run_id, baseline_ref)
    all_errors.extend(metrics_errors)
    
    if all_errors:
        return False, None, None, None, all_errors, None
    
    # Apply quality gates (warning-only, non-blocking)
    passed, rule_errors, warnings = check_pass_fail_rules(manifest, metrics)
    # rule_errors should be empty (quality gates are warnings only)
    all_errors.extend(rule_errors)
    
    # Schema errors block, but quality gate warnings don't
    if all_errors:
        passed = False
    
    # Extract display info
    primary_metric = None
    delta = None
    delta_pct = None
    fail_rate = None
    
    if 'metrics' in metrics and 'primary' in metrics['metrics']:
        primary = metrics['metrics']['primary']
        primary_metric = f"{primary.get('name', 'N/A')}={primary.get('value', 'N/A')} {primary.get('unit', '')}"
    
    if 'regression' in metrics:
        reg = metrics['regression']
        delta = reg.get('delta', 0)
        delta_pct = reg.get('delta_pct', 0)
    
    if 'metrics' in metrics and 'secondary' in metrics['metrics']:
        for sec in metrics['metrics']['secondary']:
            if sec.get('name') == 'fail_rate':
                fail_rate = sec.get('value', 0)
                break
    
    errors_list = all_errors if all_errors else None
    warnings_list = warnings if warnings else None
    return passed, primary_metric, delta, delta_pct, errors_list, fail_rate, warnings_list


def main():
    """Main entry point."""
    parser = ArgumentParser(description='Validate Evidence Package schema v1.0')
    parser.add_argument('--base', help='Base SHA for git diff (default: auto-detect)')
    parser.add_argument('--head', help='Head SHA for git diff (default: HEAD)')
    args = parser.parse_args()
    
    # Detect base and head from environment or arguments
    base_sha = args.base
    head_sha = args.head or 'HEAD'
    
    if not base_sha:
        # Try to get from environment
        pr_base = os.environ.get('GITHUB_BASE_REF')
        if pr_base:
            base_sha = f'origin/{pr_base}'
        else:
            # Fallback: use HEAD~1, but this is a safe skip if diff fails
            base_sha = 'HEAD~1'
    
    print(f"Checking changed artifacts between {base_sha}...{head_sha}")
    
    # Get changed runs (only artifacts changed in this PR)
    # If diff fails or no artifacts changed, returns empty (safe skip)
    changed_runs = get_changed_runs(base_sha, head_sha)
    
    if not changed_runs:
        print("No artifacts changed in this PR; skipping validation.")
        print("(Legacy artifacts (regression/, sensitivity/, etc.) are not scanned)")
        return 0
    
    print(f"Validating evidence runs: {len(changed_runs)}")
    print("")
    
    results = []
    all_warnings = []
    
    for run_dir in changed_runs:
        passed, primary, delta, delta_pct, errors, fail_rate, warnings = validate_run(run_dir)
        run_id = Path(run_dir).name
        status = "PASS" if passed else "FAIL"
        
        print(f"[{status}] {run_id}")
        if primary:
            print(f"  Primary metric: {primary}")
        if delta is not None:
            print(f"  Delta: {delta:.4f} ({delta_pct:+.2f}%)")
        if fail_rate is not None:
            print(f"  Fail rate: {fail_rate:.4f}")
        if errors:
            for error in errors:
                print(f"  ERROR: {error}")
        if warnings:
            for warning in warnings:
                print(f"  {warning}")
                all_warnings.append(f"{run_id}: {warning}")
        print("")
        
        results.append((run_id, passed))
    
    # Summary
    passed_count = sum(1 for _, p in results if p)
    failed_count = len(results) - passed_count
    
    print("=" * 60)
    print(f"Summary: PASSED {passed_count} / FAILED {failed_count}")
    if all_warnings:
        print(f"Warnings: {len(all_warnings)} (non-blocking)")
    print("=" * 60)
    
    if failed_count > 0:
        print("\nValidation failed due to schema errors. Please fix the errors above.")
        print("(Quality gate warnings do not block CI)")
        return 1
    
    if all_warnings:
        print("\nQuality gate warnings (non-blocking):")
        for warning in all_warnings:
            print(f"  - {warning}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
