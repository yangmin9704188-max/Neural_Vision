# CATALOG — modules/body/src/runners

## Rules
- Before adding a new file, read this CATALOG and avoid duplicates.
- After changing/adding code, update this CATALOG entry.

## Entries
- run_geo_v0_s1_facts.py — U1 runner: S1 manifest mesh/verts → facts. In: --manifest, --out_dir. Out: exports/runs/geo_v0_s1/*. Status: active.
- run_geo_v0_facts_round1.py — geo v0 facts round1. In: manifest, out_dir. Out: facts_summary. Status: active.
- run_curated_v0_facts_round1.py — curated v0 npz → facts. In: npz path. Out: facts_summary.json, md. Status: active.

## Misc
- __init__.py — Package marker.
