#!/usr/bin/env python3
"""
Build SizeKorea glossary and v1 mapping table from ergonomics standard terms.

This script:
1. Processes XLS file to create glossary (Semantic layer)
2. Creates measurement coverage v0 (Contract layer)
3. Extends standard_keys.md (Contract layer)
4. Creates sizekorea_v1.json mapping table (Contract layer)
5. Generates mapping report (not committed)
"""

import argparse
import pandas as pd
import json
import csv
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import subprocess
import sys
import re


def convert_xls_to_xlsx(xls_path: Path, xlsx_path: Path) -> bool:
    """
    Convert XLS to XLSX using LibreOffice headless mode.
    
    Args:
        xls_path: Path to input XLS file
        xlsx_path: Path to output XLSX file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Try LibreOffice (Linux/Mac)
        cmd = ['soffice', '--headless', '--convert-to', 'xlsx', '--outdir', 
               str(xlsx_path.parent), str(xls_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            # LibreOffice creates file with same name but .xlsx extension
            converted = xls_path.parent / f"{xls_path.stem}.xlsx"
            if converted.exists():
                converted.rename(xlsx_path)
                return True
    except FileNotFoundError:
        pass
    
    try:
        # Try on Windows with full path
        cmd = ['C:\\Program Files\\LibreOffice\\program\\soffice.exe', 
               '--headless', '--convert-to', 'xlsx', '--outdir',
               str(xlsx_path.parent), str(xls_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            converted = xls_path.parent / f"{xls_path.stem}.xlsx"
            if converted.exists():
                converted.rename(xlsx_path)
                return True
    except FileNotFoundError:
        pass
    
    # Fallback: try xlrd (if available)
    try:
        import xlrd
        wb = xlrd.open_workbook(str(xls_path))
        ws = wb.sheet_by_index(0)
        
        # Create DataFrame from xlrd
        data = []
        for row_idx in range(ws.nrows):
            row = [ws.cell_value(row_idx, col_idx) for col_idx in range(ws.ncols)]
            data.append(row)
        
        df = pd.DataFrame(data)
        df.to_excel(xlsx_path, index=False, header=False, engine='openpyxl')
        return True
    except ImportError:
        pass
    
    return False


def read_glossary_xls(xls_path: Path) -> pd.DataFrame:
    """
    Read glossary from XLS file.
    
    Args:
        xls_path: Path to XLS file
    
    Returns:
        DataFrame with columns: 번호, 표준 용어, 대응 영어
    """
    xlsx_path = xls_path.parent / f"{xls_path.stem}_converted.xlsx"
    
    # Try to read as XLSX first
    if xls_path.suffix.lower() == '.xlsx':
        df = pd.read_excel(xls_path, sheet_name=0, header=None, engine='openpyxl')
    elif xls_path.suffix.lower() == '.xls':
        # Try to convert
        if not convert_xls_to_xlsx(xls_path, xlsx_path):
            # Try direct read with xlrd
            try:
                import xlrd
                wb = xlrd.open_workbook(str(xls_path))
                ws = wb.sheet_by_index(0)
                data = []
                for row_idx in range(ws.nrows):
                    row = [ws.cell_value(row_idx, col_idx) for col_idx in range(ws.ncols)]
                    data.append(row)
                df = pd.DataFrame(data)
            except:
                raise ValueError(f"Could not read XLS file: {xls_path}")
        else:
            df = pd.read_excel(xlsx_path, sheet_name=0, header=None, engine='openpyxl')
    else:
        raise ValueError(f"Unsupported file format: {xls_path}")
    
    # Find header row (look for "번호", "표준 용어", "대응 영어")
    header_row = None
    for i in range(min(10, len(df))):
        row_values = [str(v).strip() for v in df.iloc[i].tolist() if pd.notna(v)]
        if any('번호' in v for v in row_values) and any('표준 용어' in v or '용어' in v for v in row_values):
            header_row = i
            break
    
    if header_row is None:
        # Assume first row is header
        header_row = 0
    
    # Read with header
    df_header = pd.read_excel(xls_path if xls_path.suffix.lower() == '.xlsx' else xlsx_path,
                              sheet_name=0, header=header_row, engine='openpyxl')
    
    # Find columns: 번호, 표준 용어, 대응 영어
    col_map = {}
    for col in df_header.columns:
        col_str = str(col).strip()
        if '번호' in col_str or 'no' in col_str.lower():
            col_map['번호'] = col
        elif '표준 용어' in col_str or ('표준' in col_str and '용어' in col_str):
            col_map['표준 용어'] = col
        elif '대응 영어' in col_str or ('영어' in col_str and '대응' in col_str):
            col_map['대응 영어'] = col
    
    # Extract relevant columns
    if len(col_map) < 2:
        # Fallback: assume first 3 columns
        result = df_header.iloc[:, :3].copy()
        result.columns = ['번호', '표준 용어', '대응 영어']
    else:
        result = df_header[[col_map.get('번호', df_header.columns[0]),
                            col_map.get('표준 용어', df_header.columns[1]),
                            col_map.get('대응 영어', df_header.columns[2])]].copy()
        result.columns = ['번호', '표준 용어', '대응 영어']
    
    # Clean data
    result = result.dropna(subset=['표준 용어'])
    result['표준 용어'] = result['표준 용어'].astype(str).str.strip()
    result['대응 영어'] = result['대응 영어'].astype(str).str.strip().replace('nan', '')
    
    return result


def create_glossary_csv(glossary_df: pd.DataFrame, output_path: Path):
    """
    Create glossary CSV file.
    
    Args:
        glossary_df: DataFrame with 번호, 표준 용어, 대응 영어
        output_path: Path to save CSV
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    result_df = pd.DataFrame({
        'ko_term': glossary_df['표준 용어'],
        'en_term': glossary_df['대응 영어'],
        'source': 'ergonomics_glossary_v0'
    })
    
    result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"Created glossary: {output_path}")


def load_glossary(glossary_path: Path) -> Dict[str, str]:
    """
    Load glossary and create ko_term -> en_term mapping.
    
    Args:
        glossary_path: Path to glossary CSV
    
    Returns:
        Dictionary mapping ko_term to en_term
    """
    df = pd.read_csv(glossary_path, encoding='utf-8-sig')
    return dict(zip(df['ko_term'], df['en_term']))


def extract_ko_term_from_column(column_name: str) -> str:
    """
    Extract Korean term from column name.
    Handles patterns like "S-STa-...-DM_목둘레" -> "목둘레"
    
    Args:
        column_name: Column name from SizeKorea data
    
    Returns:
        Extracted Korean term
    """
    # Pattern: CODE_TERM or just TERM
    if '_' in column_name:
        parts = column_name.split('_')
        # Take the last part that contains Korean characters
        for part in reversed(parts):
            if any(ord(c) >= 0xAC00 and ord(c) <= 0xD7A3 for c in str(part)):
                return part.strip()
        # If no Korean found, return last part
        return parts[-1].strip()
    return column_name.strip()


def create_coverage_v0(glossary: Dict[str, str], output_path: Path, 
                       selected_terms: List[str]) -> pd.DataFrame:
    """
    Create measurement coverage v0 CSV.
    
    Args:
        glossary: Dictionary mapping ko_term to en_term
        output_path: Path to save CSV
        selected_terms: List of selected Korean terms for coverage
    
    Returns:
        DataFrame with coverage data
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    coverage_data = []
    unmatched = []
    
    for ko_term in selected_terms:
        en_term = glossary.get(ko_term, '')
        if not en_term:
            unmatched.append(ko_term)
            en_term = ''
        
        # Determine dimension type from term
        if '둘레' in ko_term or 'circumference' in en_term.lower():
            dim_type = 'circ'
        elif '너비' in ko_term or 'width' in en_term.lower():
            dim_type = 'width'
        elif '두께' in ko_term or 'depth' in en_term.lower() or 'thickness' in en_term.lower():
            dim_type = 'depth'
        elif '길이' in ko_term or 'length' in en_term.lower():
            dim_type = 'length'
        elif '높이' in ko_term or 'height' in en_term.lower():
            dim_type = 'height'
        else:
            dim_type = 'length'  # default
        
        # Determine priority (must for key measurements, optional for others)
        priority = 'must' if ko_term in ['키', '몸무게', '가슴둘레', '허리둘레', '엉덩이둘레'] else 'optional'
        
        # Generate standard_key
        if en_term:
            # Convert en_term to standard_key format
            standard_key = en_term.upper().replace(' ', '_').replace('-', '_')
            # Add suffix based on dimension type
            if dim_type == 'circ':
                standard_key = f"{standard_key}_CIRC_M"
            elif dim_type == 'width':
                standard_key = f"{standard_key}_WIDTH_M"
            elif dim_type == 'depth':
                standard_key = f"{standard_key}_DEPTH_M"
            elif dim_type == 'height':
                standard_key = f"{standard_key}_HEIGHT_M"
            else:
                standard_key = f"{standard_key}_LENGTH_M"
        else:
            standard_key = f"UNMATCHED_{ko_term.upper().replace(' ', '_')}"
        
        coverage_data.append({
            'standard_key': standard_key,
            'ko_term': ko_term,
            'en_term': en_term if en_term else 'unmatched',
            'dimension_type': dim_type,
            'priority': priority
        })
    
    df = pd.DataFrame(coverage_data)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"Created coverage v0: {output_path}")
    
    return df, unmatched


def extend_standard_keys(coverage_df: pd.DataFrame, standard_keys_path: Path):
    """
    Extend standard_keys.md with new keys from coverage.
    
    Args:
        coverage_df: DataFrame with coverage data
        standard_keys_path: Path to standard_keys.md
    """
    # Read existing content
    with open(standard_keys_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract existing table
    lines = content.split('\n')
    table_start = None
    table_end = None
    
    for i, line in enumerate(lines):
        if '| standard_key |' in line:
            table_start = i
        if table_start and line.startswith('##') and i > table_start:
            table_end = i
            break
    
    if table_end is None:
        table_end = len(lines)
    
    # Build new table rows
    new_rows = []
    for _, row in coverage_df.iterrows():
        standard_key = row['standard_key']
        ko_term = row['ko_term']
        en_term = row['en_term'] if row['en_term'] != 'unmatched' else ''
        dim_type = row['dimension_type']
        
        # Determine unit
        if dim_type == 'circ':
            unit = 'meters'
        elif dim_type in ['width', 'depth', 'length', 'height']:
            unit = 'meters'
        else:
            unit = 'meters'
        
        # Create meaning
        if en_term:
            meaning = f"{ko_term} ({en_term})"
        else:
            meaning = ko_term
        
        # Extract related_measurement_key (domain token)
        related_key = standard_key.split('_')[0] if '_' in standard_key else standard_key
        
        new_rows.append(f"| {standard_key} | {meaning} | {unit} | {related_key} |")
    
    # Insert new rows before table end
    new_content = '\n'.join(lines[:table_end]) + '\n' + '\n'.join(new_rows) + '\n' + '\n'.join(lines[table_end:])
    
    with open(standard_keys_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Extended standard_keys.md: {standard_keys_path}")


def create_sizekorea_v1_mapping(coverage_df: pd.DataFrame, 
                                columns_by_file: Dict,
                                columns_union_path: Path,
                                output_path: Path,
                                glossary: Dict[str, str]) -> Dict:
    """
    Create sizekorea_v1.json mapping table.
    
    Args:
        coverage_df: DataFrame with coverage data
        columns_by_file: Dictionary from columns_by_file.json
        columns_union_path: Path to columns_union.csv
        output_path: Path to save JSON
        glossary: Glossary dictionary
    
    Returns:
        Mapping dictionary with statistics
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load columns_union.csv
    union_df = pd.read_csv(columns_union_path, encoding='utf-8-sig')
    
    # Build mapping
    keys_data = []
    unmatched_ko_terms = []
    exact_matched_count = 0
    
    for _, coverage_row in coverage_df.iterrows():
        standard_key = coverage_row['standard_key']
        ko_term = coverage_row['ko_term']
        en_term = coverage_row['en_term'] if coverage_row['en_term'] != 'unmatched' else ''
        
        # Find matching columns in each source
        sources = {}
        for source_key in ['7th', '8th_direct', '8th_3d']:
            source_columns = columns_by_file.get(source_key, {}).get('columns', [])
            matched_column = None
            present = False
            
            # Try exact match first
            for col in source_columns:
                extracted_term = extract_ko_term_from_column(col)
                if extracted_term == ko_term:
                    matched_column = col
                    present = True
                    exact_matched_count += 1
                    break
            
            # If not found, try partial match
            if not matched_column:
                for col in source_columns:
                    extracted_term = extract_ko_term_from_column(col)
                    if ko_term in extracted_term or extracted_term in ko_term:
                        matched_column = col
                        present = True
                        break
            
            sources[source_key] = {
                'column': matched_column if matched_column else None,
                'present': present
            }
        
        if en_term == 'unmatched':
            unmatched_ko_terms.append(ko_term)
        
        keys_data.append({
            'standard_key': standard_key,
            'ko_term': ko_term,
            'en_term': en_term,
            'sources': sources
        })
    
    result = {
        'version': 'v1',
        'keys': keys_data,
        'unmatched_ko_terms': unmatched_ko_terms,
        'notes': 'exact-match only; fuzzy suggestions emitted in report'
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"Created sizekorea_v1.json: {output_path}")
    
    return {
        'exact_matched_count': exact_matched_count,
        'unmatched_ko_terms': unmatched_ko_terms,
        'total_keys': len(keys_data)
    }


def generate_fuzzy_suggestions(ko_term: str, all_columns: List[str], top_n: int = 3) -> List[str]:
    """
    Generate fuzzy match suggestions for a Korean term.
    
    Args:
        ko_term: Korean term to match
        all_columns: List of all column names
        top_n: Number of suggestions to return
    
    Returns:
        List of suggested column names
    """
    suggestions = []
    ko_term_lower = ko_term.lower()
    
    for col in all_columns:
        extracted = extract_ko_term_from_column(col).lower()
        # Simple similarity: check if key characters match
        if any(char in extracted for char in ko_term_lower if len(char) > 1):
            suggestions.append(col)
    
    return suggestions[:top_n]


def create_mapping_report(mapping_stats: Dict,
                         coverage_df: pd.DataFrame,
                         columns_by_file: Dict,
                         output_path: Path):
    """
    Create mapping report (not committed).
    
    Args:
        mapping_stats: Statistics from mapping creation
        coverage_df: Coverage DataFrame
        columns_by_file: Columns by file dictionary
        output_path: Path to save report
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Collect all columns
    all_columns = []
    for source_data in columns_by_file.values():
        all_columns.extend(source_data.get('columns', []))
    
    # Generate fuzzy suggestions for unmatched terms
    fuzzy_suggestions = {}
    for ko_term in mapping_stats['unmatched_ko_terms']:
        suggestions = generate_fuzzy_suggestions(ko_term, all_columns, top_n=3)
        if suggestions:
            fuzzy_suggestions[ko_term] = suggestions
    
    report = {
        'exact_matched_count': mapping_stats['exact_matched_count'],
        'total_keys': mapping_stats['total_keys'],
        'unmatched_ko_terms': mapping_stats['unmatched_ko_terms'],
        'fuzzy_suggestions': fuzzy_suggestions,
        'timestamp': datetime.now().isoformat()
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"Created mapping report: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Build SizeKorea glossary and v1 mapping table"
    )
    parser.add_argument(
        '--xls_path',
        type=str,
        required=True,
        help='Path to XLS file with ergonomics standard terms'
    )
    parser.add_argument(
        '--columns_by_file',
        type=str,
        default='verification/runs/column_inventory/20260123_010549/columns_by_file.json',
        help='Path to columns_by_file.json'
    )
    parser.add_argument(
        '--columns_union',
        type=str,
        default='verification/runs/column_inventory/20260123_010549/columns_union.csv',
        help='Path to columns_union.csv'
    )
    
    args = parser.parse_args()
    
    xls_path = Path(args.xls_path)
    if not xls_path.exists():
        print(f"Error: XLS file not found: {xls_path}")
        print("Please provide the path to the ergonomics standard terms XLS file.")
        sys.exit(1)
    
    # 1. Process XLS and create glossary
    print("Step 1: Processing XLS file and creating glossary...")
    glossary_df = read_glossary_xls(xls_path)
    glossary_path = Path('docs/semantic/sizekorea_term_glossary_v0.csv')
    create_glossary_csv(glossary_df, glossary_path)
    
    # 2. Load glossary
    glossary = load_glossary(glossary_path)
    
    # 3. Load columns_by_file for term extraction
    columns_by_file_path = Path(args.columns_by_file)
    with open(columns_by_file_path, 'r', encoding='utf-8') as f:
        columns_by_file = json.load(f)
    
    # Extract unique Korean terms from columns
    all_columns = []
    for source_data in columns_by_file.values():
        all_columns.extend(source_data.get('columns', []))
    
    # Extract terms and prioritize key measurements
    extracted_terms = {}
    for col in all_columns:
        term = extract_ko_term_from_column(col)
        if term and any(ord(c) >= 0xAC00 and ord(c) <= 0xD7A3 for c in term):
            # Count frequency across sources
            if term not in extracted_terms:
                extracted_terms[term] = 0
            extracted_terms[term] += 1
    
    # Priority terms (must-have measurements)
    priority_terms = [
        '키', '몸무게', '가슴둘레', '젖가슴둘레', '젖가슴아래둘레', '허리둘레', 
        '배꼽수준허리둘레', '엉덩이둘레', '목둘레', '겨드랑둘레', '어깨너비', 
        '가슴너비', '젖가슴너비', '허리너비', '엉덩이너비', '어깨높이', '목뒤높이', 
        '겨드랑높이', '허리높이', '엉덩이높이', '무릎높이', '가슴두께', '젖가슴두께', 
        '허리두께', '엉덩이두께', '팔길이', '어깨길이', '등길이', '앉은키', 'BMI'
    ]
    
    # Build selected_terms: priority first, then by frequency
    selected_terms = []
    for term in priority_terms:
        if term in extracted_terms:
            selected_terms.append(term)
    
    # Add remaining terms by frequency (up to 50 total)
    remaining_terms = [(term, count) for term, count in extracted_terms.items() 
                       if term not in selected_terms]
    remaining_terms.sort(key=lambda x: x[1], reverse=True)
    
    for term, _ in remaining_terms:
        if len(selected_terms) >= 50:
            break
        selected_terms.append(term)
    
    print(f"Selected {len(selected_terms)} terms for coverage")
    
    # 4. Create coverage v0
    print("Step 2: Creating measurement coverage v0...")
    coverage_path = Path('docs/contract/measurement_coverage_v0.csv')
    coverage_df, unmatched = create_coverage_v0(glossary, coverage_path, selected_terms)
    
    # 5. Extend standard_keys.md
    print("Step 3: Extending standard_keys.md...")
    standard_keys_path = Path('docs/contract/standard_keys.md')
    extend_standard_keys(coverage_df, standard_keys_path)
    
    # 6. Create sizekorea_v1.json
    print("Step 4: Creating sizekorea_v1.json mapping table...")
    columns_union_path = Path(args.columns_union)
    mapping_path = Path('data/column_map/sizekorea_v1.json')
    mapping_stats = create_sizekorea_v1_mapping(
        coverage_df, columns_by_file, columns_union_path, mapping_path, glossary
    )
    
    # 7. Create mapping report
    print("Step 5: Creating mapping report...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(f'verification/runs/mapping_build/{timestamp}/mapping_report.json')
    create_mapping_report(mapping_stats, coverage_df, columns_by_file, report_path)
    
    print("\n" + "=" * 80)
    print("Summary of generated files:")
    print(f"  Glossary: {glossary_path}")
    print(f"  Coverage v0: {coverage_path}")
    print(f"  Standard keys: {standard_keys_path}")
    print(f"  SizeKorea v1 mapping: {mapping_path}")
    print(f"  Mapping report: {report_path}")
    print("=" * 80)


if __name__ == '__main__':
    main()
