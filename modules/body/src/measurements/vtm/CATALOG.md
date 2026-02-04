# CATALOG — modules/body/src/measurements/vtm

## Rules
- Before adding a new file, read this CATALOG and avoid duplicates.
- After changing/adding code, update this CATALOG entry.

## Entries
- core_measurements_v0.py — Core VTM: circumferences, widths, heights, arm. In: verts, faces. Out: MeasurementResult. Status: active.
- metadata_v0.py — Metadata schema v0 helpers. In: params. Out: metadata dict. Status: active.
- circumference_v0.py — Bust/waist/hip circumference. In: verts, faces. Out: CircumferenceResult. Status: active.
- bust_underbust_v0.py — Bust/underbust measurement. In: verts, faces. Out: BustUnderbustResult. Status: active.
- shoulder_width_v12.py — Shoulder width v1.2 prototype. In: verts, joints. Out: width_m. Status: deprecated.
- shoulder_width_v112.py — Shoulder width v1.1.2. In: verts, joints. Out: width_m. Status: deprecated.

## Misc
- __init__.py — Package marker.
