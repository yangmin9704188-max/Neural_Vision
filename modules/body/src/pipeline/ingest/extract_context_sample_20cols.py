#!/usr/bin/env python3
"""
Purpose: Extract ~20 key columns from SizeKorea raw for context.
Inputs: raw CSV paths
Outputs: sample JSON/CSV (not committed)
Status: diagnostic

This script extracts approximately 20 key columns from each source file
for context understanding purposes. Output files are NOT committed.
"""

import argparse
import pandas as pd
import json
from pathlib import Path
from typing import List, Dict, Set, Optional
from datetime import datetime


def extract_ko_term_from_column(column_name: str) -> str:
    """
    Extract Korean term from column name.
    Handles patterns like "S-STa-...-DM_목둘레" -> "목둘레"
    
    Args:
        column_name: Column name from SizeKorea data
    
    Returns:
        Extracted Korean term
    """
    if '_' in column_name:
        parts = column_name.split('_')
        # Take the last part that contains Korean characters
        for part in reversed(parts):
            if any(ord(c) >= 0xAC00 and ord(c) <= 0xD7A3 for c in str(part)):
                return part.strip()
        # If no Korean found, return last part
        return parts[-1].strip()
    return column_name.strip()


def load_column_mapping(columns_by_file_path: Path) -> Dict[str, List[str]]:
    """
    Load column mapping from columns_by_file.json.
    
    Args:
        columns_by_file_path: Path to columns_by_file.json
    
    Returns:
        Dictionary mapping source key to list of column names
    """
    with open(columns_by_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    result = {}
    for key, info in data.items():
        result[key] = info.get('columns', [])
    
    return result


def find_matching_column(target_term: str, available_columns: List[str]) -> Optional[str]:
    """
    Find matching column for a target Korean term.
    
    Args:
        target_term: Target Korean term to find
        available_columns: List of available column names
    
    Returns:
        Matching column name or None
    """
    for col in available_columns:
        extracted = extract_ko_term_from_column(col)
        if extracted == target_term or target_term in extracted or extracted in target_term:
            return col
    return None


def select_context_columns(available_columns: List[str], 
                          target_terms: List[str]) -> List[str]:
    """
    Select context columns based on target terms.
    
    Args:
        available_columns: List of available column names
        target_terms: List of target Korean terms to find
    
    Returns:
        List of selected column names
    """
    selected = []
    
    for term in target_terms:
        matched = find_matching_column(term, available_columns)
        if matched and matched not in selected:
            selected.append(matched)
    
    return selected


def extract_sample(input_path: Path, 
                  selected_columns: List[str],
                  n_rows: int = 50,
                  header_row: int = 6) -> pd.DataFrame:
    """
    Extract sample rows with selected columns.
    
    Args:
        input_path: Path to input CSV file
        selected_columns: List of column names to extract
        n_rows: Number of rows to extract
        header_row: Row index to use as header (0-indexed)
    
    Returns:
        DataFrame with sample data
    """
    # Try different encodings
    encodings = ['utf-8-sig', 'cp949', 'utf-8']
    
    for encoding in encodings:
        try:
            # Read with header row
            df = pd.read_csv(input_path, encoding=encoding, header=header_row, nrows=n_rows, low_memory=False)
            
            # Filter to selected columns (only those that exist)
            existing_cols = [col for col in selected_columns if col in df.columns]
            
            if not existing_cols:
                print(f"  Warning: No matching columns found. Available columns: {list(df.columns[:10])}")
                return pd.DataFrame()
            
            return df[existing_cols]
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"  Warning: Error reading with {encoding}: {e}")
            continue
    
    return pd.DataFrame()


def calculate_missing_stats(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate missing value statistics.
    
    Args:
        df: DataFrame
    
    Returns:
        Dictionary mapping column name to missing ratio
    """
    stats = {}
    for col in df.columns:
        missing_count = df[col].isna().sum()
        stats[col] = missing_count / len(df) if len(df) > 0 else 0.0
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Extract context sample (20 columns) from SizeKorea raw CSV files"
    )
    parser.add_argument(
        '--raw_dir',
        type=str,
        default='data/raw/sizekorea_raw',
        help='Directory containing raw SizeKorea CSV files'
    )
    parser.add_argument(
        '--out_dir',
        type=str,
        default=None,
        help='Output directory (default: exports/runs/_tools/ingest/extract_context_sample_20cols/<run_id>)'
    )
    parser.add_argument(
        '--n_rows',
        type=int,
        default=50,
        help='Number of rows to extract from each file'
    )
    parser.add_argument(
        '--columns_by_file',
        type=str,
        default='verification/runs/column_inventory/20260123_010549/columns_by_file.json',
        help='Path to columns_by_file.json'
    )
    
    args = parser.parse_args()
    
    raw_dir = Path(args.raw_dir)
    
    # Determine output directory
    from .paths import default_tool_out
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = default_tool_out("extract_context_sample_20cols")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Load column mapping
    columns_by_file_path = Path(args.columns_by_file)
    if not columns_by_file_path.exists():
        print(f"Warning: columns_by_file.json not found: {columns_by_file_path}")
        print("  Will attempt to detect columns from CSV files directly.")
        column_mapping = {}
    else:
        column_mapping = load_column_mapping(columns_by_file_path)
    
    # Define target terms for context columns
    target_terms = [
        # Meta
        'HUMAN ID', 'HUMAN_ID', '인체 데이터 ID', '인체데이터ID',
        '성별', '나이', 'ISO나이', '키', '몸무게',
        # BUST/UNDERBUST
        '젖가슴둘레', '젖가슴아래둘레', '가슴둘레',
        # Core measurements
        '허리둘레', '배꼽수준허리둘레', '엉덩이둘레', 
        '넙다리둘레', '종아리최소둘레', '발목최대둘레',
        '가슴너비', '가슴두께', '허리너비', '허리두께',
        # Length/Height
        '등길이', '팔길이', '샅높이'
    ]
    
    # File mapping
    file_configs = [
        {
            'key': '7th',
            'path': raw_dir / '7th_data.csv',
            'output_name': '7th_context_sample.csv'
        },
        {
            'key': '8th_direct',
            'path': raw_dir / '8th_data_direct.csv',
            'output_name': '8th_direct_context_sample.csv'
        },
        {
            'key': '8th_3d',
            'path': raw_dir / '8th_data_3d.csv',
            'output_name': '8th_3d_context_sample.csv'
        }
    ]
    
    manifest = {
        'timestamp': datetime.now().isoformat(),
        'n_rows_per_file': args.n_rows,
        'files': []
    }
    
    print("=" * 80)
    print("Context Sample Extraction (20 columns)")
    print("=" * 80)
    
    for config in file_configs:
        file_path = config['path']
        file_key = config['key']
        output_name = config['output_name']
        
        if not file_path.exists():
            print(f"\nSkipping {file_key}: File not found: {file_path}")
            continue
        
        print(f"\nProcessing: {file_key} ({file_path.name})")
        
        # Get available columns
        if file_key in column_mapping:
            available_columns = column_mapping[file_key]
        else:
            # Fallback: read header from CSV
            try:
                df_header = pd.read_csv(file_path, nrows=0, encoding='utf-8-sig')
                available_columns = list(df_header.columns)
            except:
                print(f"  Error: Could not read columns from {file_path}")
                continue
        
        # Select context columns
        selected_columns = select_context_columns(available_columns, target_terms)
        
        print(f"  Selected {len(selected_columns)} columns:")
        for col in selected_columns[:10]:
            print(f"    - {col}")
        if len(selected_columns) > 10:
            print(f"    ... and {len(selected_columns) - 10} more")
        
        # Determine header row based on file
        header_row = 6  # Default for most files
        if '7th' in file_key:
            header_row = 6
        elif '8th' in file_key:
            header_row = 6
        
        # Extract sample
        df_sample = extract_sample(file_path, selected_columns, args.n_rows, header_row)
        
        if df_sample.empty:
            print(f"  Warning: No data extracted")
            continue
        
        # Calculate statistics
        missing_stats = calculate_missing_stats(df_sample)
        top_missing = sorted(missing_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Check for human ID
        human_id_col = None
        human_id_unique = None
        for col in df_sample.columns:
            col_upper = str(col).upper()
            if 'HUMAN' in col_upper and 'ID' in col_upper:
                human_id_col = col
                human_id_unique = df_sample[col].nunique()
                break
        
        # Save sample
        output_path = out_dir / output_name
        df_sample.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"  Saved: {output_path}")
        print(f"  Rows: {len(df_sample)}, Columns: {len(df_sample.columns)}")
        
        if human_id_col:
            print(f"  Human ID column: {human_id_col}, Unique values: {human_id_unique}")
        
        print(f"  Top 5 missing rates:")
        for col, rate in top_missing:
            print(f"    {col}: {rate:.1%}")
        
        # Add to manifest
        manifest['files'].append({
            'source': file_key,
            'file_path': str(file_path),
            'output_file': output_name,
            'selected_columns': selected_columns,
            'n_rows': len(df_sample),
            'n_columns': len(df_sample.columns),
            'human_id_column': human_id_col,
            'human_id_unique_count': human_id_unique,
            'top_missing_rates': {col: float(rate) for col, rate in top_missing}
        })
    
    # Save manifest
    manifest_path = out_dir / 'context_sample_manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved manifest: {manifest_path}")
    print(f"\nOutput directory: {out_dir.absolute()}")
    print("=" * 80)


if __name__ == '__main__':
    main()
