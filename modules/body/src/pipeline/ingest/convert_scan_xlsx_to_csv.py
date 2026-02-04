#!/usr/bin/env python3
"""
Convert scan XLSX to CSV with unit normalization (mm -> m).

Purpose: Round24 – Convert 20F_data.xlsx to normalized CSV (meta_unit="m").
Facts-only: no semantic mapping, no answer validation, unit conversion only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_meta_line(meta_str: str) -> Dict[str, str]:
    """Parse meta line: "성별 : F / 연령 : 20" -> {gender: "F", age: "20"}"""
    gender_match = re.search(r'성별\s*:\s*([MF])', meta_str)
    age_match = re.search(r'연령\s*:\s*(\d+)', meta_str)
    
    gender = gender_match.group(1) if gender_match else None
    age = age_match.group(1) if age_match else None
    
    return {"gender": gender, "age": age}


def convert_xlsx_to_csv(
    input_xlsx: Path,
    out_dir: Path,
    source_id: str,
    raw_unit: str = "mm",
    meta_unit: str = "m",
    precision: float = 0.001,
    major_names: Optional[List[str]] = None,
) -> tuple[Path, Optional[Path]]:
    """
    Convert scan XLSX to CSV with unit normalization.
    
    Args:
        input_xlsx: Input XLSX file path (relative paths resolved from cwd)
        out_dir: Output directory
        source_id: Source identifier (e.g., "scan_6th_20F")
        raw_unit: Raw unit (default: "mm")
        meta_unit: Target unit (default: "m")
        precision: Precision for rounding (default: 0.001)
        major_names: Optional list of major item names to filter
    
    Returns:
        (full_csv_path, major_csv_path or None)
    """
    # Resolve input_xlsx: absolute paths as-is, relative paths from cwd
    input_xlsx_original = input_xlsx
    if input_xlsx.is_absolute():
        input_xlsx_resolved = input_xlsx.resolve()
    else:
        # Relative path: resolve from current working directory
        input_xlsx_resolved = (Path.cwd() / input_xlsx).resolve()
    
    # Resolve out_dir: relative paths from repo root (for consistency with other tools)
    if out_dir.is_absolute():
        out_dir_resolved = out_dir.resolve()
    else:
        out_dir_resolved = (_REPO_ROOT / out_dir).resolve()
    
    out_dir_resolved.mkdir(parents=True, exist_ok=True)
    
    # Error message with full context
    if not input_xlsx_resolved.exists():
        cwd = Path.cwd()
        exists = input_xlsx_resolved.exists()
        error_msg = [
            "ERROR: Input XLSX not found",
            f"  cwd: {cwd}",
            f"  input_xlsx (original): {input_xlsx_original}",
            f"  input_xlsx (resolved): {input_xlsx_resolved}",
            f"  exists: {exists}",
        ]
        print("\n".join(error_msg))
        sys.exit(1)
    
    input_xlsx = input_xlsx_resolved
    out_dir = out_dir_resolved
    
    print(f"[XLSX] Reading: {input_xlsx} (resolved from: {input_xlsx_original})")
    
    # Read first 3 rows to parse structure
    df_meta = pd.read_excel(input_xlsx, nrows=1, header=None, engine='openpyxl')
    df_header = pd.read_excel(input_xlsx, nrows=2, header=None, engine='openpyxl')
    df_data = pd.read_excel(input_xlsx, header=1, engine='openpyxl')
    
    # Parse meta line (row 0)
    meta_line = str(df_meta.iloc[0, 0]) if len(df_meta) > 0 and pd.notna(df_meta.iloc[0, 0]) else ""
    meta = parse_meta_line(meta_line)
    gender = meta.get("gender", "UNKNOWN")
    age = meta.get("age", "UNKNOWN")
    
    print(f"[META] gender: {gender}, age: {age}")
    
    # Expected header columns (row 1): No., 측정항목 코드, 측정항목명, 측정값
    expected_cols = ["No.", "측정항목 코드", "측정항목명", "측정값"]
    
    # Find actual column indices
    header_row = df_header.iloc[1] if len(df_header) > 1 else None
    if header_row is None:
        print("ERROR: Could not find header row")
        sys.exit(1)
    
    col_map = {}
    for i, val in enumerate(header_row):
        val_str = str(val).strip() if pd.notna(val) else ""
        for exp_col in expected_cols:
            if exp_col in val_str or val_str == exp_col:
                col_map[exp_col] = i
                break
    
    if len(col_map) < len(expected_cols):
        print(f"ERROR: Could not find all expected columns. Found: {col_map}")
        print(f"Header row values: {header_row.tolist()}")
        sys.exit(1)
    
    # Read full data
    df = pd.read_excel(input_xlsx, header=1, engine='openpyxl')
    
    # Map columns
    no_col = df.columns[col_map["No."]]
    code_col = df.columns[col_map["측정항목 코드"]]
    name_col = df.columns[col_map["측정항목명"]]
    value_col = df.columns[col_map["측정값"]]
    
    # Build output DataFrame
    output_rows = []
    
    for idx, row in df.iterrows():
        if pd.isna(row[no_col]) and pd.isna(row[code_col]) and pd.isna(row[name_col]):
            continue  # Skip empty rows
        
        no = str(row[no_col]).strip() if pd.notna(row[no_col]) else ""
        item_code = str(row[code_col]).strip() if pd.notna(row[code_col]) else ""
        item_name_ko = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
        value_raw = row[value_col]
        
        # Convert value
        if pd.isna(value_raw) or not isinstance(value_raw, (int, float)):
            value_m = None
        else:
            # Unit conversion: mm -> m
            if raw_unit == "mm" and meta_unit == "m":
                value_m = float(value_raw) / 1000.0
            else:
                print(f"WARNING: Unsupported unit conversion: {raw_unit} -> {meta_unit}")
                value_m = float(value_raw)
            
            # Round to precision
            if value_m is not None:
                value_m = round(value_m / precision) * precision
        
        output_rows.append({
            "source_id": source_id,
            "gender": gender,
            "age": age,
            "no": no,
            "item_code": item_code,
            "item_name_ko": item_name_ko,
            "value_raw": value_raw if pd.notna(value_raw) else None,
            "raw_unit": raw_unit,
            "value_m": value_m,
            "meta_unit": meta_unit,
        })
    
    # Create output DataFrame
    df_output = pd.DataFrame(output_rows)
    
    # Save full CSV
    full_csv_path = out_dir / f"{source_id}_measurements_m.csv"
    df_output.to_csv(full_csv_path, index=False, encoding='utf-8-sig')
    print(f"[CSV] Saved full CSV: {full_csv_path} ({len(df_output)} rows)")
    
    # Save major CSV if major_names provided
    major_csv_path = None
    if major_names:
        df_major = df_output[df_output["item_name_ko"].isin(major_names)].copy()
        major_csv_path = out_dir / f"{source_id}_major_measurements_m.csv"
        df_major.to_csv(major_csv_path, index=False, encoding='utf-8-sig')
        print(f"[CSV] Saved major CSV: {major_csv_path} ({len(df_major)} rows)")
        print(f"[CSV] Major items: {', '.join(major_names)}")
    
    return full_csv_path, major_csv_path


def main():
    parser = argparse.ArgumentParser(
        description="Convert scan XLSX to CSV with unit normalization (mm -> m)"
    )
    parser.add_argument(
        "--input_xlsx",
        type=str,
        required=True,
        help="Input XLSX file path (e.g., 20F_data.xlsx)"
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        required=True,
        help="Output directory for CSV files"
    )
    parser.add_argument(
        "--source_id",
        type=str,
        required=True,
        help="Source identifier (e.g., scan_6th_20F)"
    )
    parser.add_argument(
        "--raw_unit",
        type=str,
        default="mm",
        help="Raw unit (default: mm)"
    )
    parser.add_argument(
        "--meta_unit",
        type=str,
        default="m",
        help="Target unit (default: m)"
    )
    parser.add_argument(
        "--precision",
        type=float,
        default=0.001,
        help="Precision for rounding (default: 0.001)"
    )
    parser.add_argument(
        "--major_names",
        type=str,
        default=None,
        help="Comma-separated list of major item names to filter (e.g., '키,가슴둘레,배꼽수준허리둘레')"
    )
    
    args = parser.parse_args()
    
    major_names_list = None
    if args.major_names:
        major_names_list = [name.strip() for name in args.major_names.split(",")]
    
    full_path, major_path = convert_xlsx_to_csv(
        Path(args.input_xlsx),
        Path(args.out_dir),
        args.source_id,
        raw_unit=args.raw_unit,
        meta_unit=args.meta_unit,
        precision=args.precision,
        major_names=major_names_list,
    )
    
    print(f"[DONE] Full CSV: {full_path}")
    if major_path:
        print(f"[DONE] Major CSV: {major_path}")


if __name__ == "__main__":
    main()
