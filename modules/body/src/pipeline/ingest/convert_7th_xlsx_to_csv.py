#!/usr/bin/env python3
"""
Purpose: Convert 7th SizeKorea XLSX to CSV, human_id as string.
Inputs: 7th XLSX path
Outputs: CSV file
Status: active

This script ensures that human ID column is read and saved as string type,
preventing any data corruption (e.g., scientific notation, trailing .0).
"""

import argparse
import pandas as pd
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Optional
import sys


def detect_human_id_column(df_header: pd.DataFrame) -> Optional[str]:
    """
    Detect human ID column from header.
    
    Priority:
    1. Column name contains "HUMAN_ID" or "HUMAN ID"
    2. Column name contains "인체" + "ID"
    3. Column name contains "데이터" + "ID"
    
    Args:
        df_header: DataFrame with header row only
    
    Returns:
        Column name or None if not found
    """
    for col in df_header.columns:
        col_str = str(col).upper().replace(' ', '_')
        col_orig = str(col)
        if "HUMAN_ID" in col_str or "HUMAN ID" in col_orig.upper():
            return col
        if "인체" in col_orig and "ID" in col_str:
            return col
        if "데이터" in col_orig and "ID" in col_str:
            return col
    
    return None


def clean_human_id(value) -> str:
    """
    Clean human ID value to ensure it's a proper string.
    
    Handles:
    - Trailing .0 from float conversion
    - Scientific notation (e.g., 2.11606300001E11)
    - NaN/None values
    
    Args:
        value: Raw value from Excel
    
    Returns:
        Cleaned string
    """
    if pd.isna(value):
        return ""
    
    # Convert to string first
    str_val = str(value).strip()
    
    # Remove trailing .0 if present
    if str_val.endswith('.0'):
        str_val = str_val[:-2]
    
    # Handle scientific notation
    if 'E' in str_val.upper() or 'e' in str_val:
        try:
            # Try to convert from scientific notation
            num_val = float(str_val)
            # Convert to integer string if it's a whole number
            if num_val.is_integer():
                return str(int(num_val))
            else:
                # Use Decimal for precision
                return str(Decimal(str_val))
        except (ValueError, InvalidOperation):
            # If conversion fails, return original string
            print(f"  Warning: Could not convert scientific notation: {str_val}", file=sys.stderr)
            return str_val
    
    return str_val


def convert_xlsx_to_csv(input_path: Path, output_path: Path, human_id_col: Optional[str] = None, header_row: int = 6):
    """
    Convert XLSX to CSV with human ID preserved as string.
    
    Args:
        input_path: Path to input XLSX file
        output_path: Path to output CSV file
        human_id_col: Optional manual specification of human ID column
        header_row: Row index to use as header (0-indexed)
    """
    print(f"Reading XLSX: {input_path}")
    
    # Read header first to detect human ID column
    df_header = pd.read_excel(input_path, nrows=0, header=header_row, engine='openpyxl')
    
    # Detect human ID column
    if human_id_col is None:
        human_id_col = detect_human_id_column(df_header)
    
    if human_id_col is None:
        print("  Warning: Could not auto-detect human ID column.")
        print("  Top 30 column names:")
        for i, col in enumerate(df_header.columns[:30], 1):
            print(f"    {i}. {col}")
        print("\n  Please specify with --human_id_col option.")
        sys.exit(1)
    
    print(f"  Detected human ID column: {human_id_col}")
    
    # Prepare dtype mapping to force string type for human ID
    dtype_map = {human_id_col: "string"}
    
    # Read full data with string type for human ID
    try:
        df = pd.read_excel(input_path, header=header_row, engine='openpyxl', dtype=dtype_map)
    except Exception as e:
        print(f"  Error reading with dtype: {e}")
        print("  Falling back to converters approach...")
        # Fallback: read normally and convert
        df = pd.read_excel(input_path, header=header_row, engine='openpyxl')
        if human_id_col in df.columns:
            df[human_id_col] = df[human_id_col].apply(clean_human_id)
    
    # Ensure human ID is string type
    if human_id_col in df.columns:
        df[human_id_col] = df[human_id_col].astype("string")
        # Apply cleaning function
        df[human_id_col] = df[human_id_col].apply(clean_human_id)
    
    # Validation and logging
    print("\nValidation:")
    print(f"  Human ID column dtype: {df[human_id_col].dtype}")
    print(f"  Total rows: {len(df)}")
    print(f"  NaN count: {df[human_id_col].isna().sum()}")
    
    # Show top 5 values
    print("\n  Top 5 human ID values:")
    for i, val in enumerate(df[human_id_col].head(5), 1):
        print(f"    {i}. {val} (type: {type(val).__name__})")
    
    # Length distribution
    non_null = df[human_id_col].dropna()
    if len(non_null) > 0:
        lengths = non_null.str.len()
        print(f"\n  Length distribution:")
        print(f"    Min: {lengths.min()}, Max: {lengths.max()}, Mean: {lengths.mean():.1f}")
    
    # Save to CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig', quoting=1)  # quoting=1 is QUOTE_ALL
    
    print(f"\nSaved CSV: {output_path}")
    print(f"  Total columns: {len(df.columns)}")
    print(f"  Total rows: {len(df)}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert 7th SizeKorea XLSX to CSV with human ID preserved as string"
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Path to input XLSX file'
    )
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Path to output CSV file'
    )
    parser.add_argument(
        '--human_id_col',
        type=str,
        default=None,
        help='Manual specification of human ID column name'
    )
    parser.add_argument(
        '--header_row',
        type=int,
        default=6,
        help='Row index to use as header (0-indexed, default: 6)'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    
    try:
        convert_xlsx_to_csv(input_path, output_path, args.human_id_col, args.header_row)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
