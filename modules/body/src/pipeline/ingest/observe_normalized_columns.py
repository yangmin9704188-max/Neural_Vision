#!/usr/bin/env python3
"""
Purpose: Observe bust/underbust column existence in normalized CSV.
Inputs: normalized CSV path
Outputs: observation log (not committed)
Status: diagnostic
"""

import argparse
import pandas as pd
import json
from pathlib import Path
from typing import Dict, List


def observe_normalized_csv(csv_path: str, key_columns: List[str], bust_columns: List[str]) -> Dict:
    """
    Observe column existence and missing rates in normalized CSV.
    
    Args:
        csv_path: Path to normalized CSV file
        key_columns: List of key columns to check (human_id, sex, age, height, weight)
        bust_columns: List of bust/underbust related columns to check
    
    Returns:
        Dictionary with observation results
    """
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig', low_memory=False)
    except Exception as e:
        return {
            "file": csv_path,
            "error": str(e)
        }
    
    n_rows = len(df)
    all_columns = list(df.columns)
    
    # Check key columns existence
    key_existence = {}
    for col in key_columns:
        key_existence[col] = col in all_columns
    
    # Check bust/underbust columns existence
    bust_existence = {}
    for col in bust_columns:
        bust_existence[col] = col in all_columns
    
    # Calculate missing rates for bust/underbust columns
    bust_missing_rates = {}
    for col in bust_columns:
        if col in all_columns:
            non_null_count = df[col].notna().sum()
            missing_rate = 1.0 - (non_null_count / n_rows) if n_rows > 0 else 1.0
            bust_missing_rates[col] = {
                "non_null_count": int(non_null_count),
                "null_count": int(n_rows - non_null_count),
                "missing_rate": float(missing_rate),
                "non_null_rate": float(1.0 - missing_rate)
            }
        else:
            bust_missing_rates[col] = {
                "exists": False
            }
    
    # Check human_id uniqueness (if exists)
    human_id_stats = {}
    if "human_id" in all_columns:
        unique_count = df["human_id"].nunique()
        duplicate_rate = 1.0 - (unique_count / n_rows) if n_rows > 0 else 0.0
        human_id_stats = {
            "unique_count": int(unique_count),
            "total_count": int(n_rows),
            "duplicate_rate": float(duplicate_rate),
            "is_unique": unique_count == n_rows
        }
    else:
        human_id_stats = {"exists": False}
    
    return {
        "file": csv_path,
        "n_rows": int(n_rows),
        "n_columns": len(all_columns),
        "key_columns_existence": key_existence,
        "bust_columns_existence": bust_existence,
        "bust_columns_missing_rates": bust_missing_rates,
        "human_id_stats": human_id_stats
    }


def main():
    parser = argparse.ArgumentParser(
        description="Observe normalized CSV columns for bust/underbust availability"
    )
    parser.add_argument(
        "--csv_files",
        type=str,
        nargs="+",
        default=[
            "data/processed/raw_normalized_v0/7th_data_normalized.csv",
            "data/processed/raw_normalized_v0/8th_data_3d_normalized.csv",
            "data/processed/raw_normalized_v0/8th_data_direct_normalized.csv"
        ],
        help="Normalized CSV files to observe"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Output directory (default: exports/runs/_tools/ingest/observe_normalized_columns/<run_id>)"
    )
    
    args = parser.parse_args()
    
    from .paths import default_tool_out
    output_dir = Path(args.output_dir) if args.output_dir else default_tool_out("observe_normalized_columns")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    key_columns = ["human_id", "sex", "age", "height", "weight"]
    bust_columns = ["bust_girth", "underbust_girth", "chest_girth"]
    
    print("Observing normalized CSV columns...")
    print("=" * 80)
    
    observations = []
    
    for csv_path in args.csv_files:
        csv_file = Path(csv_path)
        if not csv_file.exists():
            print(f"\n⚠️  File not found: {csv_path}")
            continue
        
        print(f"\nProcessing: {csv_path}")
        obs = observe_normalized_csv(csv_path, key_columns, bust_columns)
        observations.append(obs)
        
        if "error" in obs:
            print(f"  Error: {obs['error']}")
            continue
        
        print(f"  Rows: {obs['n_rows']}")
        print(f"  Columns: {obs['n_columns']}")
        
        print(f"\n  Key columns existence:")
        for col, exists in obs['key_columns_existence'].items():
            status = "[OK]" if exists else "[MISSING]"
            print(f"    {status} {col}")
        
        print(f"\n  Bust/underbust columns existence:")
        for col, exists in obs['bust_columns_existence'].items():
            status = "[OK]" if exists else "[MISSING]"
            print(f"    {status} {col}")
        
        print(f"\n  Bust/underbust missing rates:")
        for col, stats in obs['bust_columns_missing_rates'].items():
            if "exists" in stats and not stats["exists"]:
                print(f"    {col}: Column does not exist")
            else:
                print(f"    {col}:")
                print(f"      Non-null: {stats['non_null_count']} ({stats['non_null_rate']*100:.1f}%)")
                print(f"      Null: {stats['null_count']} ({stats['missing_rate']*100:.1f}%)")
        
        print(f"\n  Human ID stats:")
        if "exists" in obs['human_id_stats'] and not obs['human_id_stats']['exists']:
            print(f"    human_id: Column does not exist")
        else:
            print(f"    Unique count: {obs['human_id_stats']['unique_count']}")
            print(f"    Total count: {obs['human_id_stats']['total_count']}")
            print(f"    Duplicate rate: {obs['human_id_stats']['duplicate_rate']*100:.1f}%")
            print(f"    Is unique: {obs['human_id_stats']['is_unique']}")
    
    # Save results
    output_file = output_dir / "normalized_column_observation.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "key_columns": key_columns,
            "bust_columns": bust_columns,
            "observations": observations
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n" + "=" * 80)
    print(f"Saved observation results to: {output_file}")


if __name__ == "__main__":
    main()
