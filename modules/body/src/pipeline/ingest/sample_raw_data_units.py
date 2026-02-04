#!/usr/bin/env python3
"""
Purpose: Sample value ranges in raw data for unit observation.
Inputs: raw CSV path
Outputs: stdout (not committed)
Status: diagnostic
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path


def sample_csv_units(csv_path: str, n_samples: int = 20, columns: list[str] = None):
    """
    Sample N rows from CSV and report value ranges for specified columns.
    
    Args:
        csv_path: Path to CSV file
        n_samples: Number of rows to sample
        columns: List of column names to analyze (if None, auto-detect numeric columns)
    
    Returns:
        Dictionary with column statistics
    """
    df = pd.read_csv(csv_path)
    
    # Auto-detect numeric columns if not specified
    if columns is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        columns = numeric_cols[:10]  # Limit to first 10 numeric columns
    
    # Sample rows
    if len(df) > n_samples:
        sampled_df = df.sample(n=n_samples, random_state=42)
    else:
        sampled_df = df
    
    stats = {}
    for col in columns:
        if col not in df.columns:
            continue
        
        values = sampled_df[col].dropna()
        if len(values) == 0:
            continue
        
        stats[col] = {
            "min": float(values.min()),
            "max": float(values.max()),
            "mean": float(values.mean()),
            "sample_values": values.head(5).tolist(),
            "n_valid": len(values),
        }
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Sample raw data to observe unit/scale patterns"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="data/raw/sizekorea_raw/7th_data.csv",
        help="Path to CSV file (default: data/raw/sizekorea_raw/7th_data.csv)"
    )
    parser.add_argument(
        "--n",
        type=int,
        default=20,
        help="Number of rows to sample (default: 20)"
    )
    parser.add_argument(
        "--columns",
        type=str,
        nargs="+",
        default=None,
        help="Column names to analyze (default: auto-detect numeric columns)"
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output file path (default: stdout only, not saved)"
    )
    
    args = parser.parse_args()
    
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        return
    
    print(f"Sampling from: {csv_path}")
    print(f"Number of samples: {args.n}")
    print("=" * 80)
    
    stats = sample_csv_units(str(csv_path), n_samples=args.n, columns=args.columns)
    
    for col, col_stats in stats.items():
        print(f"\nColumn: {col}")
        print(f"  Min: {col_stats['min']}")
        print(f"  Max: {col_stats['max']}")
        print(f"  Mean: {col_stats['mean']:.2f}")
        print(f"  Valid samples: {col_stats['n_valid']}")
        print(f"  Sample values: {col_stats['sample_values']}")
    
    # Save to file if requested
    if args.out:
        import json
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print(f"\nSaved statistics to: {output_path}")


if __name__ == "__main__":
    main()
