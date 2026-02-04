# CATALOG — modules/body/src/pipeline/ingest

## Rules
- Before adding a new file, read this CATALOG and avoid duplicates.
- After changing/adding code, update this CATALOG entry.

## Path convention
- External raw: data/external/sizekorea_raw (single junction). All 7th/8th CSVs here.

## Entries
- paths.py — Centralized path constants (EXTERNAL_*, DERIVED_CURATED_DIR, now_run_id). Status: active.
- build_curated_v0.py — SizeKorea raw → curated_v0 parquet/csv. In: data/external/sizekorea_raw 7th/8th CSV|XLSX, sizekorea_v2.json. Out: data/derived/curated_v0/<RUN_ID>/curated_v0.parquet. Status: active.
- ingestion_units.py — Unit canonicalization mm/cm/m → m. In: values, source_unit. Out: meters array. Status: active.
- build_glossary_and_mapping.py — Build glossary and v1 mapping from ergonomics terms. In: XLS, config. Out: sizekorea_v1.json, glossary. Status: one-off.
- convert_7th_xlsx_to_csv.py — Convert 7th XLSX to CSV, human_id as string. In: 7th XLSX. Out: CSV. Status: active.
- convert_scan_xlsx_to_csv.py — Convert scan XLSX to CSV, mm→m. In: scan XLSX. Out: normalized CSV. Status: one-off.
- extract_context_sample_20cols.py — Extract ~20 key columns for context. In: raw CSV. Out: sample JSON/CSV. Status: diagnostic.
- inspect_raw_columns.py — Column headers inventory (union/intersection). In: raw CSV. Out: column_inventory. Status: diagnostic.
- observe_normalized_columns.py — Observe bust/underbust column existence. In: normalized CSV. Out: observation log. Status: diagnostic.
- observe_sizekorea_columns.py — Observe raw CSV column names. In: raw CSV. Out: column list log. Status: diagnostic.
- reextract_raw_headers.py — Re-extract headers with improved detection. In: raw CSV/XLSX. Out: column_inventory. Status: diagnostic.
- sample_raw_data_units.py — Sample value ranges for unit observation. In: raw CSV. Out: stdout. Status: diagnostic.

## Misc
- __init__.py — Package marker.
