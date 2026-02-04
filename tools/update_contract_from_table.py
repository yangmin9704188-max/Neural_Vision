#!/usr/bin/env python3
"""
Update sizekorea_v2.json from Reference Data.csv (exact match only).

Rules:
- Row 7 (secondary header): HUMAN_ID, SEX, AGE
- Row 5 (primary header): All other measurements
- No fuzzy matching, exact match only
"""

import json
import pandas as pd
from pathlib import Path

# Read Reference Data.csv
ref_data_path = Path("data/processed/Reference Data.csv")
ref_df = pd.read_csv(ref_data_path, encoding='utf-8-sig')

# Read current sizekorea_v2.json
mapping_path = Path("data/column_map/sizekorea_v2.json")
with open(mapping_path, 'r', encoding='utf-8') as f:
    mapping = json.load(f)

# Create lookup from standard_key to headers
ref_lookup = {}
for _, row in ref_df.iterrows():
    standard_key = row['standard_key']
    ref_lookup[standard_key] = {
        '7th': row['source_7th_header'],
        '8th_direct': row['source_8th_direct_header'],
        '8th_3d': row['source_8th_3d_header'],
        'row': row['참조 행']
    }

# Safety fixes
# 1) UNDERBUST_CIRC_M: 8th_direct/8th_3d to '젖가슴아래둘레(여)'
if 'UNDERBUST_CIRC_M' in ref_lookup:
    ref_lookup['UNDERBUST_CIRC_M']['8th_direct'] = '젖가슴아래둘레(여)'
    ref_lookup['UNDERBUST_CIRC_M']['8th_3d'] = '젖가슴아래둘레(여)'

# 2) KNEE_HEIGHT_M: 7th to '앉은무릎높이' (already in table, but ensure)
if 'KNEE_HEIGHT_M' in ref_lookup:
    ref_lookup['KNEE_HEIGHT_M']['7th'] = '앉은무릎높이'

# 3) HUMAN_ID: 7th secondary header exact token - confirmed as "HUMAN ID" (with space)
if 'HUMAN_ID' in ref_lookup:
    ref_lookup['HUMAN_ID']['7th'] = 'HUMAN ID'

# Update mapping
for key_info in mapping['keys']:
    standard_key = key_info['standard_key']
    
    if standard_key not in ref_lookup:
        continue
    
    ref_info = ref_lookup[standard_key]
    
    # Update each source
    for source_key in ['7th', '8th_direct', '8th_3d']:
        if source_key not in key_info['sources']:
            key_info['sources'][source_key] = {}
        
        header_value = ref_info[source_key]
        
        if pd.isna(header_value) or header_value == '':
            key_info['sources'][source_key]['column'] = None
            key_info['sources'][source_key]['present'] = False
        else:
            key_info['sources'][source_key]['column'] = str(header_value).strip()
            key_info['sources'][source_key]['present'] = True

# Save updated mapping
with open(mapping_path, 'w', encoding='utf-8') as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)

print(f"Updated {mapping_path}")
print(f"Processed {len(ref_lookup)} standard keys from Reference Data.csv")
