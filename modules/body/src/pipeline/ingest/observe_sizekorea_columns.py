#!/usr/bin/env python3
"""
Purpose: Observe raw CSV column names for mapping preparation.
Inputs: raw CSV path
Outputs: column list log (not committed)
Status: diagnostic
"""

import argparse
import pandas as pd
import json
from pathlib import Path
from typing import List, Set


def observe_csv_columns(csv_path: str, header_row: int = None) -> dict:
    """
    Observe column names and row count from CSV file.
    
    Args:
        csv_path: Path to CSV file
        header_row: Row index to use as header (None = auto-detect)
    
    Returns:
        Dictionary with column information
    """
    try:
        # Try to read first few rows to detect header
        df_sample = pd.read_csv(csv_path, encoding='utf-8-sig', nrows=10, header=None)
        
        # Check if first row looks like header (contains Korean text or measurement names)
        first_row = df_sample.iloc[0].astype(str).tolist()
        has_korean = any(any(ord(c) >= 0xAC00 and ord(c) <= 0xD7A3 for c in str(v)) for v in first_row[:10])
        
        # If header_row is not specified, try to find it
        if header_row is None:
            # Check rows 0-4 for potential header
            for i in range(min(5, len(df_sample))):
                row = df_sample.iloc[i].astype(str).tolist()
                if any(any(ord(c) >= 0xAC00 and ord(c) <= 0xD7A3 for c in str(v)) for v in row[:10]):
                    header_row = i
                    break
        
        # Read with detected header
        if header_row is not None:
            df = pd.read_csv(csv_path, encoding='utf-8-sig', header=header_row, nrows=0)
            skip_rows = header_row + 1
        else:
            # Default: use first row as header
            df = pd.read_csv(csv_path, encoding='utf-8-sig', nrows=0)
            skip_rows = 1
        
        columns = list(df.columns)
        
        # Count rows (read full file with same header setting)
        if header_row is not None:
            df_full = pd.read_csv(csv_path, encoding='utf-8-sig', header=header_row)
        else:
            df_full = pd.read_csv(csv_path, encoding='utf-8-sig')
        n_rows = len(df_full)
        
        return {
            "file": csv_path,
            "n_rows": n_rows,
            "n_columns": len(columns),
            "header_row": header_row if header_row is not None else 0,
            "columns": columns
        }
    except Exception as e:
        return {
            "file": csv_path,
            "error": str(e)
        }


def find_common_columns(column_lists: List[List[str]]) -> dict:
    """
    Find common columns (intersection) and unique columns (difference) across files.
    
    Args:
        column_lists: List of column name lists from each file
    
    Returns:
        Dictionary with intersection and differences
    """
    if not column_lists:
        return {"intersection": [], "differences": {}}
    
    # Convert to sets
    column_sets = [set(cols) for cols in column_lists]
    
    # Intersection (common columns)
    intersection = set.intersection(*column_sets) if column_sets else set()
    
    # Differences per file
    differences = {}
    for i, cols in enumerate(column_lists):
        unique = set(cols) - intersection
        if unique:
            differences[f"file_{i}"] = sorted(list(unique))
    
    return {
        "intersection": sorted(list(intersection)),
        "differences": differences
    }


def main():
    parser = argparse.ArgumentParser(
        description="Observe SizeKorea raw CSV column names"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Output directory (default: exports/runs/_tools/ingest/observe_sizekorea_columns/<run_id>)"
    )
    parser.add_argument(
        "--files",
        type=str,
        nargs="+",
        default=None,
        help="CSV files to observe (default: data/external/sizekorea_raw 7th/8th CSVs)"
    )
    
    args = parser.parse_args()

    from .paths import default_tool_out
    output_dir = Path(args.output_dir) if args.output_dir else default_tool_out("observe_sizekorea_columns")
    
    if args.files is None:
        from . import paths as _paths
        args.files = [
            str(_paths.EXTERNAL_7TH_CSV),
            str(_paths.EXTERNAL_8TH_3D_CSV),
            str(_paths.EXTERNAL_8TH_DIRECT_CSV),
        ]
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Observing SizeKorea raw CSV columns...")
    print("=" * 80)
    
    observations = []
    column_lists = []
    
    for csv_path in args.files:
        print(f"\nProcessing: {csv_path}")
        obs = observe_csv_columns(csv_path)
        observations.append(obs)
        
        if "error" not in obs:
            print(f"  Rows: {obs['n_rows']}")
            print(f"  Columns: {obs['n_columns']}")
            print(f"  First 10 columns: {obs['columns'][:10]}")
            column_lists.append(obs['columns'])
        else:
            print(f"  Error: {obs['error']}")
    
    # Find common columns
    common_info = find_common_columns(column_lists)
    
    print("\n" + "=" * 80)
    print("Common Columns (Intersection):")
    print(f"  Count: {len(common_info['intersection'])}")
    print(f"  Columns: {common_info['intersection'][:20]}...")
    
    print("\nUnique Columns per File:")
    for file_key, unique_cols in common_info['differences'].items():
        print(f"  {file_key}: {len(unique_cols)} unique columns")
        print(f"    First 10: {unique_cols[:10]}")
    
    # Save results
    output_file = output_dir / "column_observation.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "observations": observations,
            "common_columns": common_info
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved observation results to: {output_file}")
    
    # Save column lists as text files
    for i, obs in enumerate(observations):
        if "error" not in obs:
            col_file = output_dir / f"{Path(obs['file']).stem}_columns.txt"
            with open(col_file, "w", encoding="utf-8") as f:
                f.write(f"File: {obs['file']}\n")
                f.write(f"Rows: {obs['n_rows']}\n")
                f.write(f"Columns: {obs['n_columns']}\n")
                f.write("\nColumn List:\n")
                for col in obs['columns']:
                    f.write(f"  {col}\n")
            print(f"Saved column list to: {col_file}")


if __name__ == "__main__":
    main()
