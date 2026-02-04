#!/usr/bin/env python3
"""
Purpose: Extract column headers inventory from SizeKorea raw (union/intersection).
Inputs: raw CSV paths
Outputs: column_inventory (not committed)
Status: diagnostic
"""

import argparse
import pandas as pd
import json
import csv
from pathlib import Path
from typing import List, Set, Dict, Optional
from datetime import datetime


def find_header_row_csv(csv_path: Path, encoding: str, max_check: int = 5) -> Optional[int]:
    """
    Find header row index in CSV file by checking for Korean characters.
    
    Args:
        csv_path: Path to CSV file
        encoding: Encoding to use
        max_check: Maximum number of rows to check
    
    Returns:
        Header row index or None if not found
    """
    try:
        df_sample = pd.read_csv(csv_path, encoding=encoding, nrows=max_check, header=None)
        for i in range(min(max_check, len(df_sample))):
            row = df_sample.iloc[i].astype(str).tolist()
            # Check if row contains Korean characters (common in SizeKorea headers)
            has_korean = any(any(ord(c) >= 0xAC00 and ord(c) <= 0xD7A3 for c in str(v)) for v in row[:10] if pd.notna(v))
            if has_korean:
                return i
        # If no Korean found, assume first row is header
        return 0
    except:
        return 0


def read_csv_columns(csv_path: Path) -> Dict:
    """
    Read column names from CSV file, trying multiple encodings.
    
    Args:
        csv_path: Path to CSV file
    
    Returns:
        Dictionary with file info and columns
    """
    encodings = ['utf-8-sig', 'cp949', 'utf-8', 'latin-1']
    
    for encoding in encodings:
        try:
            # Find header row
            header_row = find_header_row_csv(csv_path, encoding)
            
            # Read with detected header
            df_header = pd.read_csv(csv_path, encoding=encoding, nrows=0, header=header_row)
            columns = list(df_header.columns)
            
            # Filter out unnamed columns that are likely empty
            columns = [col for col in columns if not (str(col).startswith('Unnamed:') and pd.isna(df_header[col].iloc[0]) if len(df_header) > 0 else True)]
            
            # Try to get row count (read minimal data)
            try:
                df_full = pd.read_csv(csv_path, encoding=encoding, header=header_row)
                n_rows = len(df_full)
                # Re-read columns from full read to get actual column names
                columns = [col for col in df_full.columns if not str(col).startswith('Unnamed:') or df_full[col].notna().any()]
            except:
                n_rows = None
            
            return {
                "file": str(csv_path),
                "n_rows": n_rows,
                "n_columns": len(columns),
                "encoding": encoding,
                "header_row": header_row,
                "columns": columns,
                "error": None
            }
        except UnicodeDecodeError:
            continue
        except Exception as e:
            # If it's not an encoding error, try next encoding anyway
            continue
    
    # If all encodings failed
    return {
        "file": str(csv_path),
        "n_rows": None,
        "n_columns": 0,
        "encoding": None,
        "header_row": None,
        "columns": [],
        "error": "Failed to read with all attempted encodings"
    }


def find_header_row_xlsx(xlsx_path: Path, max_check: int = 5) -> Optional[int]:
    """
    Find header row index in Excel file by checking for Korean characters.
    
    Args:
        xlsx_path: Path to Excel file
        max_check: Maximum number of rows to check
    
    Returns:
        Header row index or None if not found
    """
    try:
        df_sample = pd.read_excel(xlsx_path, nrows=max_check, header=None, engine='openpyxl')
        for i in range(min(max_check, len(df_sample))):
            row = df_sample.iloc[i].astype(str).tolist()
            # Check if row contains Korean characters
            has_korean = any(any(ord(c) >= 0xAC00 and ord(c) <= 0xD7A3 for c in str(v)) for v in row[:10] if pd.notna(v))
            if has_korean:
                return i
        # If no Korean found, assume first row is header
        return 0
    except:
        return 0


def read_xlsx_columns(xlsx_path: Path) -> Dict:
    """
    Read column names from Excel file (header only, minimal load).
    
    Args:
        xlsx_path: Path to Excel file
    
    Returns:
        Dictionary with file info and columns
    """
    try:
        # Find header row
        header_row = find_header_row_xlsx(xlsx_path)
        
        # Read with detected header
        df_header = pd.read_excel(xlsx_path, nrows=0, header=header_row, engine='openpyxl')
        columns = list(df_header.columns)
        
        # Filter out unnamed columns
        columns = [col for col in columns if not str(col).startswith('Unnamed:')]
        
        # Try to get row count and actual columns
        try:
            df_full = pd.read_excel(xlsx_path, header=header_row, engine='openpyxl')
            n_rows = len(df_full)
            # Re-read columns from full read to get actual column names
            columns = [col for col in df_full.columns if not str(col).startswith('Unnamed:') or df_full[col].notna().any()]
        except:
            n_rows = None
        
        return {
            "file": str(xlsx_path),
            "n_rows": n_rows,
            "n_columns": len(columns),
            "encoding": "xlsx",
            "header_row": header_row,
            "columns": columns,
            "error": None
        }
    except Exception as e:
        return {
            "file": str(xlsx_path),
            "n_rows": None,
            "n_columns": 0,
            "encoding": None,
            "header_row": None,
            "columns": [],
            "error": str(e)
        }


def read_file_columns(file_path: Path) -> Dict:
    """
    Read column names from file (CSV or Excel).
    
    Args:
        file_path: Path to file
    
    Returns:
        Dictionary with file info and columns
    """
    if file_path.suffix.lower() == '.xlsx':
        return read_xlsx_columns(file_path)
    else:
        return read_csv_columns(file_path)


def create_union_csv(file_infos: List[Dict], output_path: Path):
    """
    Create CSV with union of all columns, showing which files contain each column.
    
    Args:
        file_infos: List of file info dictionaries
        output_path: Path to save CSV
    """
    # Collect all unique columns
    all_columns = set()
    for info in file_infos:
        if info.get("error") is None:
            all_columns.update(info["columns"])
    
    # Create mapping: column -> list of files containing it
    column_sources = {}
    for col in sorted(all_columns):
        sources = []
        for info in file_infos:
            if info.get("error") is None and col in info["columns"]:
                file_name = Path(info["file"]).name
                sources.append(file_name)
        column_sources[col] = sources
    
    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['column_name', 'in_files', 'file_count'])
        for col in sorted(all_columns):
            sources = column_sources[col]
            writer.writerow([col, '; '.join(sources), len(sources)])


def create_intersection_csv(file_infos: List[Dict], output_path: Path):
    """
    Create CSV with intersection (common columns across all files).
    
    Args:
        file_infos: List of file info dictionaries
        output_path: Path to save CSV
    """
    # Get column sets from files without errors
    column_sets = []
    for info in file_infos:
        if info.get("error") is None:
            column_sets.append(set(info["columns"]))
    
    if not column_sets:
        # No valid files
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['column_name'])
        return
    
    # Find intersection
    common_columns = set.intersection(*column_sets) if column_sets else set()
    
    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['column_name'])
        for col in sorted(common_columns):
            writer.writerow([col])


def main():
    parser = argparse.ArgumentParser(
        description="Extract column headers inventory from SizeKorea raw files"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Output directory (default: verification/runs/column_inventory/<timestamp>)"
    )
    
    args = parser.parse_args()
    
    # Determine target files
    raw_dir = Path("data/raw/sizekorea_raw")
    target_files = []
    
    # Check for 7th_data (prefer xlsx, fallback to csv)
    xlsx_7th = raw_dir / "7th_data.xlsx"
    csv_7th = raw_dir / "7th_data.csv"
    if xlsx_7th.exists():
        target_files.append(xlsx_7th)
    elif csv_7th.exists():
        target_files.append(csv_7th)
    
    # Add 8th files
    target_files.append(raw_dir / "8th_data_direct.csv")
    target_files.append(raw_dir / "8th_data_3d.csv")
    
    # Filter to existing files
    target_files = [f for f in target_files if f.exists()]
    
    if not target_files:
        print("Error: No target files found in data/raw/sizekorea_raw/")
        return
    
    # Create output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"verification/runs/column_inventory/{timestamp}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("SizeKorea Column Header Inventory")
    print("=" * 80)
    print(f"\nTarget files: {len(target_files)}")
    for f in target_files:
        print(f"  - {f.name}")
    print(f"\nOutput directory: {output_dir}")
    print("\n" + "=" * 80)
    
    # Read columns from each file
    file_infos = []
    for file_path in target_files:
        print(f"\nProcessing: {file_path.name}")
        info = read_file_columns(file_path)
        file_infos.append(info)
        
        if info.get("error"):
            print(f"  ERROR: {info['error']}")
        else:
            print(f"  Rows: {info['n_rows'] if info['n_rows'] is not None else 'N/A'}")
            print(f"  Columns: {info['n_columns']}")
            print(f"  Encoding: {info['encoding']}")
    
    # Save columns_by_file.json
    columns_by_file = {}
    for info in file_infos:
        file_name = Path(info["file"]).name
        columns_by_file[file_name] = {
            "file_path": info["file"],
            "n_rows": info["n_rows"],
            "n_columns": info["n_columns"],
            "encoding": info["encoding"],
            "columns": info["columns"],
            "error": info.get("error")
        }
    
    json_path = output_dir / "columns_by_file.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(columns_by_file, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {json_path}")
    
    # Create union CSV
    union_path = output_dir / "columns_union.csv"
    create_union_csv(file_infos, union_path)
    print(f"Saved: {union_path}")
    
    # Create intersection CSV
    intersection_path = output_dir / "columns_intersection.csv"
    create_intersection_csv(file_infos, intersection_path)
    print(f"Saved: {intersection_path}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    # File-by-file column counts
    print("\nFile-by-file column counts:")
    for info in file_infos:
        if info.get("error") is None:
            file_name = Path(info["file"]).name
            print(f"  {file_name}: {info['n_columns']} columns")
    
    # Common columns (intersection)
    column_sets = []
    for info in file_infos:
        if info.get("error") is None:
            column_sets.append(set(info["columns"]))
    
    if column_sets:
        common_columns = set.intersection(*column_sets) if len(column_sets) > 1 else column_sets[0]
        print(f"\nCommon columns (intersection): {len(common_columns)}")
        if common_columns:
            common_list = sorted(list(common_columns))
            print("  Top 20:")
            for col in common_list[:20]:
                print(f"    - {col}")
            if len(common_list) > 20:
                print(f"    ... and {len(common_list) - 20} more")
    
    # 8th_3d unique columns (for underbust candidate search)
    info_8th_3d = None
    info_others = []
    for info in file_infos:
        if info.get("error") is None:
            file_name = Path(info["file"]).name
            if "8th_data_3d" in file_name:
                info_8th_3d = info
            else:
                info_others.append(info)
    
    if info_8th_3d and info_others:
        cols_8th_3d = set(info_8th_3d["columns"])
        cols_others = set()
        for other_info in info_others:
            cols_others.update(other_info["columns"])
        
        unique_to_8th_3d = cols_8th_3d - cols_others
        print(f"\n8th_data_3d unique columns (not in other files): {len(unique_to_8th_3d)}")
        if unique_to_8th_3d:
            unique_list = sorted(list(unique_to_8th_3d))
            print("  Top 20:")
            for col in unique_list[:20]:
                print(f"    - {col}")
            if len(unique_list) > 20:
                print(f"    ... and {len(unique_list) - 20} more")
    
    print("\n" + "=" * 80)
    print(f"Output directory: {output_dir.absolute()}")
    print("=" * 80)


if __name__ == "__main__":
    main()
