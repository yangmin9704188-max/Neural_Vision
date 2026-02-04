#!/usr/bin/env python3
"""
KPI Diff Generator

facts_summary.json 두 개를 비교하여 KPI_DIFF.md를 생성합니다.
Facts-only 비교이며, 판정 문구 없이 사실만 표기합니다.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from tools.summarize_facts_kpi import (
    get_nan_rates,
    get_failure_reasons,
    get_value_distribution,
    safe_get
)


def load_facts_summary_safe(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    """Load facts_summary.json safely."""
    if path is None or not path.exists():
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def generate_diff_section(
    current_data: Dict[str, Any],
    ref_data: Optional[Dict[str, Any]],
    label: str
) -> List[str]:
    """Generate a single diff section (vs prev or vs baseline)."""
    lines = [f"## Diff vs {label}", ""]
    
    if not ref_data:
        lines.append(f"{label}: N/A")
        lines.append("")
        return lines
    
    # Total cases
    current_total = safe_get(current_data, "n_samples", default="N/A")
    ref_total = safe_get(ref_data, "n_samples", default="N/A")
    
    lines.append("### Total Cases")
    lines.append(f"- **Current**: {current_total}")
    lines.append(f"- **{label}**: {ref_total}")
    if isinstance(current_total, (int, float)) and isinstance(ref_total, (int, float)):
        delta = current_total - ref_total
        lines.append(f"- **Δ**: {delta:+d}")
    lines.append("")
    
    # HEIGHT_M p50/p95
    current_height = get_value_distribution(current_data, "HEIGHT_M")
    ref_height = get_value_distribution(ref_data, "HEIGHT_M")
    
    lines.append("### HEIGHT_M Distribution")
    for metric in ["p50", "p95"]:
        curr_val = current_height.get(metric)
        ref_val = ref_height.get(metric)
        
        if curr_val is not None and ref_val is not None:
            delta = curr_val - ref_val
            lines.append(f"- **{metric}**: {curr_val:.4f}m → {ref_val:.4f}m (Δ: {delta:+.4f}m)")
        elif curr_val is not None:
            lines.append(f"- **{metric}**: {curr_val:.4f}m → N/A")
        elif ref_val is not None:
            lines.append(f"- **{metric}**: N/A → {ref_val:.4f}m")
        else:
            lines.append(f"- **{metric}**: N/A")
    lines.append("")
    
    # BUST/WAIST/HIP p50
    lines.append("### BUST/WAIST/HIP p50")
    for key in ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]:
        curr_dist = get_value_distribution(current_data, key)
        ref_dist = get_value_distribution(ref_data, key)
        
        curr_val = curr_dist.get("p50")
        ref_val = ref_dist.get("p50")
        
        if curr_val is not None and ref_val is not None:
            delta = curr_val - ref_val
            lines.append(f"- **{key}**: {curr_val:.4f}m → {ref_val:.4f}m (Δ: {delta:+.4f}m)")
        elif curr_val is not None:
            lines.append(f"- **{key}**: {curr_val:.4f}m → N/A")
        elif ref_val is not None:
            lines.append(f"- **{key}**: N/A → {ref_val:.4f}m")
        else:
            lines.append(f"- **{key}**: N/A")
    lines.append("")
    
    # NaN Rate Top5 변화
    current_nan = get_nan_rates(current_data)
    ref_nan = get_nan_rates(ref_data)
    
    current_nan_dict = {k: v for k, v in current_nan[:5]}
    ref_nan_dict = {k: v for k, v in ref_nan[:5]}
    
    all_nan_keys = set(current_nan_dict.keys()) | set(ref_nan_dict.keys())
    
    if all_nan_keys:
        lines.append("### NaN Rate Top5 Changes")
        lines.append("| Key | Current | Ref | Δ | Status |")
        lines.append("|-----|---------|-----|---|--------|")
        
        for key in sorted(all_nan_keys):
            curr_rate = current_nan_dict.get(key)
            ref_rate = ref_nan_dict.get(key)
            
            if curr_rate is not None and ref_rate is not None:
                delta = curr_rate - ref_rate
                status = "same" if abs(delta) < 0.01 else ("increased" if delta > 0 else "decreased")
                lines.append(f"| {key} | {curr_rate:.2f}% | {ref_rate:.2f}% | {delta:+.2f}%p | {status} |")
            elif curr_rate is not None:
                lines.append(f"| {key} | {curr_rate:.2f}% | N/A | new in top5 |")
            elif ref_rate is not None:
                lines.append(f"| {key} | N/A | {ref_rate:.2f}% | dropped from top5 |")
        
        # Summary
        intersection = set(current_nan_dict.keys()) & set(ref_nan_dict.keys())
        current_only = set(current_nan_dict.keys()) - set(ref_nan_dict.keys())
        ref_only = set(ref_nan_dict.keys()) - set(current_nan_dict.keys())
        
        lines.append("")
        lines.append("**Summary:**")
        lines.append(f"- Common keys: {len(intersection)}")
        if current_only:
            lines.append(f"- New in current top5: {', '.join(sorted(current_only))}")
        if ref_only:
            lines.append(f"- Dropped from top5: {', '.join(sorted(ref_only))}")
    else:
        lines.append("### NaN Rate Top5 Changes")
        lines.append("No NaN rate data available.")
    lines.append("")
    
    # Failure Reason Top5 변화
    current_fail = get_failure_reasons(current_data)
    ref_fail = get_failure_reasons(ref_data)
    
    current_fail_dict = {k: v for k, v in current_fail[:5]}
    ref_fail_dict = {k: v for k, v in ref_fail[:5]}
    
    all_fail_reasons = set(current_fail_dict.keys()) | set(ref_fail_dict.keys())
    
    if all_fail_reasons:
        lines.append("### Failure Reason Top5 Changes")
        lines.append("| Reason | Current | Ref | Δ | Status |")
        lines.append("|--------|---------|-----|---|--------|")
        
        for reason in sorted(all_fail_reasons):
            curr_count = current_fail_dict.get(reason)
            ref_count = ref_fail_dict.get(reason)
            
            if curr_count is not None and ref_count is not None:
                delta = curr_count - ref_count
                status = "same" if delta == 0 else ("increased" if delta > 0 else "decreased")
                lines.append(f"| {reason} | {curr_count} | {ref_count} | {delta:+d} | {status} |")
            elif curr_count is not None:
                lines.append(f"| {reason} | {curr_count} | N/A | new in top5 |")
            elif ref_count is not None:
                lines.append(f"| {reason} | N/A | {ref_count} | dropped from top5 |")
        
        # Summary
        intersection = set(current_fail_dict.keys()) & set(ref_fail_dict.keys())
        current_only = set(current_fail_dict.keys()) - set(ref_fail_dict.keys())
        ref_only = set(ref_fail_dict.keys()) - set(current_fail_dict.keys())
        
        lines.append("")
        lines.append("**Summary:**")
        lines.append(f"- Common reasons: {len(intersection)}")
        if current_only:
            lines.append(f"- New in current top5: {', '.join(sorted(current_only))}")
        if ref_only:
            lines.append(f"- Dropped from top5: {', '.join(sorted(ref_only))}")
    else:
        lines.append("### Failure Reason Top5 Changes")
        lines.append("No failure reason data available.")
    lines.append("")
    
    return lines


def compute_degradation_signals(
    current_data: Dict[str, Any],
    baseline_data: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute lightweight degradation signals (baseline vs current).
    Returns: {degradation_flag, degraded_keys_top3, height_p50_shift}
    """
    result = {
        "degradation_flag": False,
        "degraded_keys_top3": "N/A",
        "height_p50_shift": "N/A"
    }
    
    if not baseline_data:
        return result
    
    # Get NaN rates
    current_nan = get_nan_rates(current_data)
    baseline_nan = get_nan_rates(baseline_data)
    
    # Find degraded keys (baseline 대비 NaN rate가 악화된 키)
    baseline_nan_dict = {k: v for k, v in baseline_nan}
    degraded_keys = []
    
    for key, curr_rate in current_nan:
        baseline_rate = baseline_nan_dict.get(key, 0.0)
        # NaN rate가 증가한 경우 (악화)
        if curr_rate > baseline_rate:
            delta = curr_rate - baseline_rate
            degraded_keys.append((key, delta))
    
    # Sort by degradation amount (descending) and take top 3
    degraded_keys.sort(key=lambda x: x[1], reverse=True)
    degraded_keys_top3 = [k for k, _ in degraded_keys[:3]]
    
    if degraded_keys_top3:
        result["degradation_flag"] = True
        result["degraded_keys_top3"] = ", ".join(degraded_keys_top3)
    
    # Get HEIGHT_M p50 shift
    current_height = get_value_distribution(current_data, "HEIGHT_M")
    baseline_height = get_value_distribution(baseline_data, "HEIGHT_M")
    
    curr_p50 = current_height.get("p50")
    baseline_p50 = baseline_height.get("p50")
    
    if curr_p50 is not None and baseline_p50 is not None:
        shift = curr_p50 - baseline_p50
        result["height_p50_shift"] = f"{shift:+.4f}m"
    
    return result


def generate_kpi_diff(
    current_path: Path,
    prev_path: Optional[Path],
    baseline_path: Optional[Path],
    current_run_dir: str,
    prev_run_dir: Optional[str],
    baseline_run_dir: Optional[str]
) -> str:
    """Generate KPI_DIFF.md with prev and baseline sections."""
    # Load data
    current_data = load_facts_summary_safe(current_path)
    prev_data = load_facts_summary_safe(prev_path) if prev_path else None
    baseline_data = load_facts_summary_safe(baseline_path) if baseline_path else None
    
    lines = ["# KPI Diff", ""]
    lines.append(f"*Generated at: {datetime.now().isoformat()}*")
    lines.append("")
    lines.append(f"- **Current run dir**: `{current_run_dir}`")
    lines.append(f"- **Prev run dir**: `{prev_run_dir or 'N/A'}`")
    lines.append(f"- **Baseline run dir**: `{baseline_run_dir or 'N/A'}`")
    lines.append("")
    
    if not current_data:
        lines.append("Error: Current facts_summary.json not found or invalid.")
        return "\n".join(lines)
    
    # Degradation signals (baseline vs current)
    signals = compute_degradation_signals(current_data, baseline_data)
    lines.append("## Degradation Signals (Baseline vs Current)")
    lines.append("")
    lines.append(f"- **DEGRADATION_FLAG**: `{str(signals['degradation_flag']).lower()}`")
    lines.append(f"- **DEGRADED_KEYS_TOP3**: `{signals['degraded_keys_top3']}`")
    lines.append(f"- **HEIGHT_P50_SHIFT**: `{signals['height_p50_shift']}`")
    lines.append("")
    lines.append("*Note: These are signals only, not PASS/FAIL judgments.*")
    lines.append("")
    
    # A) Diff vs Prev
    lines.extend(generate_diff_section(current_data, prev_data, "Prev"))
    
    # B) Diff vs Baseline
    lines.extend(generate_diff_section(current_data, baseline_data, "Baseline"))
    
    return "\n".join(lines)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate KPI_DIFF.md from facts_summary.json files"
    )
    parser.add_argument(
        "--current",
        type=str,
        required=True,
        help="Path to current facts_summary.json"
    )
    parser.add_argument(
        "--prev",
        type=str,
        default=None,
        help="Path to prev facts_summary.json (optional)"
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Path to baseline facts_summary.json (optional)"
    )
    parser.add_argument(
        "--current_run_dir",
        type=str,
        required=True,
        help="Current run directory (relative path)"
    )
    parser.add_argument(
        "--prev_run_dir",
        type=str,
        default=None,
        help="Prev run directory (relative path, optional)"
    )
    parser.add_argument(
        "--baseline_run_dir",
        type=str,
        default=None,
        help="Baseline run directory (relative path, optional)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output KPI_DIFF.md path"
    )
    
    args = parser.parse_args()
    
    current_path = (project_root / args.current).resolve()
    prev_path = (project_root / args.prev).resolve() if args.prev else None
    baseline_path = (project_root / args.baseline).resolve() if args.baseline else None
    
    diff_md = generate_kpi_diff(
        current_path=current_path,
        prev_path=prev_path,
        baseline_path=baseline_path,
        current_run_dir=args.current_run_dir,
        prev_run_dir=args.prev_run_dir,
        baseline_run_dir=args.baseline_run_dir
    )
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(diff_md)
    
    print(f"Generated: {output_path}")


if __name__ == "__main__":
    main()
