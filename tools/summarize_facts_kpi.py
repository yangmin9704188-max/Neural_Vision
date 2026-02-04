#!/usr/bin/env python3
"""
Facts Summary KPI Header Generator

입력: facts_summary.json 경로
출력: markdown string (KPI HEADER)을 stdout으로 출력

KPI 5개를 안정적으로 출력:
1. total_cases / valid_cases / expected_fail_cases (키가 없으면 N/A)
2. NaN rate Top5 keys (가능하면)
3. failure_reason Top5 (가능하면)
4. HEIGHT_M 분포 요약 p50/p95 (있으면)
5. BUST/WAIST/HIP p50 (있으면)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np


def safe_get(data: Dict[str, Any], *keys: str, default: Any = "N/A") -> Any:
    """Safely get nested keys, return default if any key is missing."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]
    return current if current is not None else default


def get_nan_rates(summary_data: Dict[str, Any]) -> List[tuple[str, float]]:
    """Extract NaN rates from summary data. Returns list of (key, rate) tuples."""
    nan_rates = []
    
    # Try different possible structures
    summary = safe_get(summary_data, "summary", default={})
    if not summary or summary == "N/A":
        summary = safe_get(summary_data, "statistics", default={})
    
    if not isinstance(summary, dict):
        return []
    
    for key, stats in summary.items():
        if not isinstance(stats, dict):
            continue
        
        # Try different possible NaN rate keys
        nan_rate = None
        if "nan_rate_pct" in stats:
            nan_rate = float(stats["nan_rate_pct"])
        elif "nan_rate" in stats:
            nan_rate = float(stats["nan_rate"]) * 100.0
        elif "nan_rates" in stats:
            # Nested structure like {"nan_rates": {"underbust": {"rate": 0.1}}}
            nan_rates_dict = stats["nan_rates"]
            if isinstance(nan_rates_dict, dict):
                for sub_key, sub_stats in nan_rates_dict.items():
                    if isinstance(sub_stats, dict) and "rate" in sub_stats:
                        rate_val = float(sub_stats["rate"]) * 100.0
                        nan_rates.append((f"{key}.{sub_key}", rate_val))
            continue
        
        if nan_rate is not None:
            nan_rates.append((key, nan_rate))
    
    # Sort by rate descending
    nan_rates.sort(key=lambda x: x[1], reverse=True)
    return nan_rates[:5]


def get_failure_reasons(summary_data: Dict[str, Any]) -> List[tuple[str, int]]:
    """Extract top failure reasons. Returns list of (reason, count) tuples."""
    reasons = []
    
    summary = safe_get(summary_data, "summary", default={})
    if not summary or summary == "N/A":
        summary = safe_get(summary_data, "statistics", default={})
    
    if not isinstance(summary, dict):
        return []
    
    # Look for warnings_top5 or similar structures
    for key, stats in summary.items():
        if not isinstance(stats, dict):
            continue
        
        if "warnings_top5" in stats:
            warnings = stats["warnings_top5"]
            if isinstance(warnings, list):
                for w in warnings:
                    if isinstance(w, dict):
                        reason = w.get("reason", "unknown")
                        count = w.get("n", 0)
                        if count > 0:
                            reasons.append((f"{key}:{reason}", count))
    
    # Sort by count descending
    reasons.sort(key=lambda x: x[1], reverse=True)
    return reasons[:5]


def get_percentile(values: List[float], percentile: float) -> Optional[float]:
    """Calculate percentile from list of values."""
    if not values:
        return None
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * percentile / 100.0)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def get_value_distribution(summary_data: Dict[str, Any], key: str) -> Dict[str, Optional[float]]:
    """Get p50/p95 for a specific key."""
    result = {"p50": None, "p95": None}
    
    summary = safe_get(summary_data, "summary", default={})
    if not summary or summary == "N/A":
        summary = safe_get(summary_data, "statistics", default={})
    
    if not isinstance(summary, dict):
        return result
    
    key_stats = summary.get(key, {})
    if not isinstance(key_stats, dict):
        return result
    
    # Round35: Try multiple paths for median/max (fallback for schema variations)
    # Path 1: key_stats["median"] (direct)
    # Path 2: key_stats["value_stats"]["median"] (geo_v0_s1 runner structure)
    # Path 3: key_stats["values"] -> compute median (if available)
    
    median_val = None
    max_val = None
    
    # Try direct median
    if "median" in key_stats:
        median_val = key_stats["median"]
    # Try value_stats.median
    elif "value_stats" in key_stats and isinstance(key_stats["value_stats"], dict):
        value_stats = key_stats["value_stats"]
        if "median" in value_stats:
            median_val = value_stats["median"]
        if "max" in value_stats:
            max_val = value_stats["max"]
    # Try computing from values array
    elif "values" in key_stats and isinstance(key_stats["values"], list) and len(key_stats["values"]) > 0:
        try:
            values = [float(v) for v in key_stats["values"] if isinstance(v, (int, float)) and not np.isnan(v)]
            if values:
                sorted_vals = sorted(values)
                median_val = sorted_vals[len(sorted_vals) // 2]  # Approximate median
                max_val = sorted_vals[-1]  # Max
        except (ValueError, TypeError):
            pass
    
    # Fallback: try direct max
    if max_val is None and "max" in key_stats:
        max_val = key_stats["max"]
    
    result["p50"] = median_val
    result["p95"] = max_val
    
    return result


def generate_kpi_header(summary_data: Dict[str, Any]) -> str:
    """Generate KPI header markdown."""
    lines = ["# Facts Summary KPI", ""]
    
    # 1. Total cases / valid cases / expected fail cases
    total_cases = safe_get(summary_data, "n_samples", default="N/A")
    valid_cases = safe_get(summary_data, "summary", "valid_cases", default="N/A")
    if valid_cases == "N/A":
        valid_cases = safe_get(summary_data, "statistics", "valid_cases", default="N/A")
    expected_fail_cases = safe_get(summary_data, "summary", "expected_fail_cases", default="N/A")
    if expected_fail_cases == "N/A":
        expected_fail_cases = safe_get(summary_data, "statistics", "expected_fail_cases", default="N/A")
    
    lines.append("## 1. Case Counts")
    lines.append(f"- **Total cases**: {total_cases}")
    lines.append(f"- **Valid cases**: {valid_cases}")
    lines.append(f"- **Expected fail cases**: {expected_fail_cases}")
    lines.append("")
    
    # 2. NaN rate Top5
    nan_rates = get_nan_rates(summary_data)
    lines.append("## 2. NaN Rate Top5")
    if nan_rates:
        for key, rate in nan_rates:
            lines.append(f"- **{key}**: {rate:.2f}%")
    else:
        lines.append("- N/A")
    lines.append("")
    
    # 3. Failure reason Top5
    failure_reasons = get_failure_reasons(summary_data)
    lines.append("## 3. Failure Reason Top5")
    if failure_reasons:
        for reason, count in failure_reasons:
            lines.append(f"- **{reason}**: {count}")
    else:
        lines.append("- N/A")
    lines.append("")
    
    # 4. HEIGHT_M distribution
    height_dist = get_value_distribution(summary_data, "HEIGHT_M")
    lines.append("## 4. HEIGHT_M Distribution")
    if height_dist["p50"] is not None:
        lines.append(f"- **p50**: {height_dist['p50']:.4f} m")
    else:
        lines.append("- **p50**: N/A")
    if height_dist["p95"] is not None:
        lines.append(f"- **p95**: {height_dist['p95']:.4f} m")
    else:
        lines.append("- **p95**: N/A")
    lines.append("")
    
    # 5. BUST/WAIST/HIP p50
    lines.append("## 5. BUST/WAIST/HIP p50")
    for key in ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]:
        dist = get_value_distribution(summary_data, key)
        if dist["p50"] is not None:
            lines.append(f"- **{key}**: {dist['p50']:.4f} m")
        else:
            lines.append(f"- **{key}**: N/A")
    lines.append("")
    
    return "\n".join(lines)


def generate_kpi_json(summary_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate KPI data as JSON structure."""
    kpi_data = {}
    
    # 1. Case counts
    total_cases = safe_get(summary_data, "n_samples", default="N/A")
    valid_cases = safe_get(summary_data, "summary", "valid_cases", default="N/A")
    if valid_cases == "N/A":
        valid_cases = safe_get(summary_data, "statistics", "valid_cases", default="N/A")
    expected_fail_cases = safe_get(summary_data, "summary", "expected_fail_cases", default="N/A")
    if expected_fail_cases == "N/A":
        expected_fail_cases = safe_get(summary_data, "statistics", "expected_fail_cases", default="N/A")
    
    kpi_data["case_counts"] = {
        "total": total_cases,
        "valid": valid_cases,
        "expected_fail": expected_fail_cases
    }
    
    # 2. NaN rates Top5
    nan_rates = get_nan_rates(summary_data)
    kpi_data["nan_rates_top5"] = {key: rate for key, rate in nan_rates}
    
    # 3. Failure reasons Top5
    failure_reasons = get_failure_reasons(summary_data)
    kpi_data["failure_reasons_top5"] = {reason: count for reason, count in failure_reasons}
    
    # 4. HEIGHT_M distribution
    height_dist = get_value_distribution(summary_data, "HEIGHT_M")
    kpi_data["height_m"] = {
        "p50": height_dist["p50"],
        "p95": height_dist["p95"]
    }
    
    # 5. BUST/WAIST/HIP p50
    kpi_data["circumference_p50"] = {}
    for key in ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]:
        dist = get_value_distribution(summary_data, key)
        kpi_data["circumference_p50"][key] = dist["p50"]
    
    return kpi_data


def load_facts_summary_safe(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    """Load facts_summary.json safely, return None if not found."""
    if path is None or not path.exists():
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def generate_kpi_diff(
    current_path: Path,
    prev_path: Optional[Path],
    baseline_path: Optional[Path],
    current_run_dir: str,
    prev_run_dir: Optional[str],
    baseline_run_dir: Optional[str]
) -> str:
    """Generate KPI_DIFF.md markdown."""
    from datetime import datetime
    
    # Load data
    current_data = load_facts_summary_safe(current_path)
    prev_data = load_facts_summary_safe(prev_path) if prev_path else None
    baseline_data = load_facts_summary_safe(baseline_path) if baseline_path else None
    
    lines = ["# KPI Diff", ""]
    
    # A) Header
    lines.append("## Header")
    lines.append(f"- **Current run dir**: `{current_run_dir}`")
    lines.append(f"- **Prev run dir**: `{prev_run_dir or 'N/A'}`")
    lines.append(f"- **Baseline run dir**: `{baseline_run_dir or 'N/A'}`")
    lines.append(f"- **Generated at**: {datetime.now().isoformat()}")
    lines.append("")
    
    if not current_data:
        lines.append("Error: Current facts_summary.json not found or invalid.")
        return "\n".join(lines)
    
    # Check if prev fell back to baseline
    prev_fell_back = False
    if prev_run_dir and baseline_run_dir and prev_run_dir == baseline_run_dir:
        prev_fell_back = True
    
    # B) NaN Rate Top5 변화
    lines.append("## NaN Rate Top5 Changes")
    current_nan = get_nan_rates(current_data)
    prev_nan_dict = {k: v for k, v in get_nan_rates(prev_data)} if prev_data else {}
    baseline_nan_dict = {k: v for k, v in get_nan_rates(baseline_data)} if baseline_data else {}
    
    if current_nan:
        lines.append("| Key | Current | Prev | Baseline | Δ Prev | Δ Baseline |")
        lines.append("|-----|---------|------|----------|--------|-------------|")
        for key, curr_rate in current_nan[:5]:
            prev_rate = prev_nan_dict.get(key, "N/A")
            base_rate = baseline_nan_dict.get(key, "N/A")
            
            if isinstance(prev_rate, (int, float)):
                delta_prev = curr_rate - prev_rate
                prev_str = f"{prev_rate:.2f}%"
                delta_prev_str = f"{delta_prev:+.2f}%p"
            else:
                prev_str = "N/A"
                delta_prev_str = "N/A"
            
            if isinstance(base_rate, (int, float)):
                delta_base = curr_rate - base_rate
                base_str = f"{base_rate:.2f}%"
                delta_base_str = f"{delta_base:+.2f}%p"
            else:
                base_str = "N/A"
                delta_base_str = "N/A"
            
            lines.append(f"| {key} | {curr_rate:.2f}% | {prev_str} | {base_str} | {delta_prev_str} | {delta_base_str} |")
    else:
        lines.append("No NaN rate data available.")
    lines.append("")
    
    # C) Failure Reason Top5 변화
    lines.append("## Failure Reason Top5 Changes")
    current_fail = get_failure_reasons(current_data)
    prev_fail_dict = {k: v for k, v in get_failure_reasons(prev_data)} if prev_data else {}
    baseline_fail_dict = {k: v for k, v in get_failure_reasons(baseline_data)} if baseline_data else {}
    
    if current_fail:
        lines.append("| Reason | Current | Prev | Baseline | Δ Prev | Δ Baseline |")
        lines.append("|--------|---------|------|----------|--------|-------------|")
        for reason, curr_count in current_fail[:5]:
            prev_count = prev_fail_dict.get(reason, "N/A")
            base_count = baseline_fail_dict.get(reason, "N/A")
            
            if isinstance(prev_count, int):
                delta_prev = curr_count - prev_count
                prev_str = str(prev_count)
                delta_prev_str = f"{delta_prev:+d}"
            else:
                prev_str = "N/A"
                delta_prev_str = "N/A"
            
            if isinstance(base_count, int):
                delta_base = curr_count - base_count
                base_str = str(base_count)
                delta_base_str = f"{delta_base:+d}"
            else:
                base_str = "N/A"
                delta_base_str = "N/A"
            
            lines.append(f"| {reason} | {curr_count} | {prev_str} | {base_str} | {delta_prev_str} | {delta_base_str} |")
    else:
        lines.append("No failure reason data available.")
    lines.append("")
    
    # D) Core Distributions
    lines.append("## Core Distributions")
    
    # HEIGHT_M
    curr_height = get_value_distribution(current_data, "HEIGHT_M")
    prev_height = get_value_distribution(prev_data, "HEIGHT_M") if prev_data else {"p50": None, "p95": None}
    base_height = get_value_distribution(baseline_data, "HEIGHT_M") if baseline_data else {"p50": None, "p95": None}
    
    lines.append("### HEIGHT_M")
    lines.append("| Metric | Current | Prev | Baseline | Δ Prev | Δ Baseline |")
    lines.append("|--------|---------|------|----------|--------|-------------|")
    
    for metric in ["p50", "p95"]:
        curr_val = curr_height.get(metric)
        prev_val = prev_height.get(metric)
        base_val = base_height.get(metric)
        
        if curr_val is not None:
            curr_str = f"{curr_val:.4f} m"
            if prev_val is not None:
                delta_prev = curr_val - prev_val
                prev_str = f"{prev_val:.4f} m"
                delta_prev_str = f"{delta_prev:+.4f} m"
            else:
                prev_str = "N/A"
                delta_prev_str = "N/A"
            
            if base_val is not None:
                delta_base = curr_val - base_val
                base_str = f"{base_val:.4f} m"
                delta_base_str = f"{delta_base:+.4f} m"
            else:
                base_str = "N/A"
                delta_base_str = "N/A"
            
            lines.append(f"| {metric} | {curr_str} | {prev_str} | {base_str} | {delta_prev_str} | {delta_base_str} |")
        else:
            lines.append(f"| {metric} | N/A | N/A | N/A | N/A | N/A |")
    
    lines.append("")
    
    # BUST/WAIST/HIP p50
    lines.append("### BUST/WAIST/HIP p50")
    lines.append("| Key | Current | Prev | Baseline | Δ Prev | Δ Baseline |")
    lines.append("|-----|---------|------|----------|--------|-------------|")
    
    for key in ["BUST_CIRC_M", "WAIST_CIRC_M", "HIP_CIRC_M"]:
        curr_dist = get_value_distribution(current_data, key)
        prev_dist = get_value_distribution(prev_data, key) if prev_data else {"p50": None}
        base_dist = get_value_distribution(baseline_data, key) if baseline_data else {"p50": None}
        
        curr_val = curr_dist.get("p50")
        prev_val = prev_dist.get("p50")
        base_val = base_dist.get("p50")
        
        if curr_val is not None:
            curr_str = f"{curr_val:.4f} m"
            if prev_val is not None:
                delta_prev = curr_val - prev_val
                prev_str = f"{prev_val:.4f} m"
                delta_prev_str = f"{delta_prev:+.4f} m"
            else:
                prev_str = "N/A"
                delta_prev_str = "N/A"
            
            if base_val is not None:
                delta_base = curr_val - base_val
                base_str = f"{base_val:.4f} m"
                delta_base_str = f"{delta_base:+.4f} m"
            else:
                base_str = "N/A"
                delta_base_str = "N/A"
            
            lines.append(f"| {key} | {curr_str} | {prev_str} | {base_str} | {delta_prev_str} | {delta_base_str} |")
        else:
            lines.append(f"| {key} | N/A | N/A | N/A | N/A | N/A |")
    
    lines.append("")
    
    # E) Notes
    lines.append("## Notes")
    if prev_fell_back:
        lines.append("- Prev run dir fell back to baseline (no previous entry in registry for this lane).")
    if not prev_data:
        lines.append("- Prev facts_summary.json not found or invalid.")
    if not baseline_data:
        lines.append("- Baseline facts_summary.json not found or invalid.")
    if prev_data and baseline_data and not prev_fell_back:
        lines.append("- All comparison data available.")
    lines.append("")
    
    return "\n".join(lines)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Facts Summary KPI Header Generator"
    )
    parser.add_argument(
        "facts_summary_json",
        type=str,
        help="Path to facts_summary.json"
    )
    parser.add_argument(
        "--out_json",
        type=str,
        default=None,
        help="Optional: Output KPI data as JSON to this path"
    )
    
    args = parser.parse_args()
    
    json_path = Path(args.facts_summary_json)
    if not json_path.exists():
        print(f"Error: File not found: {json_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            summary_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to read file: {e}", file=sys.stderr)
        sys.exit(1)
    
    kpi_header = generate_kpi_header(summary_data)
    print(kpi_header)
    
    # If --out_json is specified, also save JSON
    if args.out_json:
        kpi_json = generate_kpi_json(summary_data)
        out_path = Path(args.out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(kpi_json, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
