#!/usr/bin/env python3
"""
Round Postprocessing Tool (round3)

라운드 마감 단일 엔트리포인트:
- KPI 생성 (KPI.md)
- KPI_DIFF 생성 (KPI_DIFF.md)
- Prev/Baseline 자동 해석
- Round Registry 기록
- Coverage Backlog 갱신
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


def find_facts_summary(run_dir: Path, required: bool = True) -> Optional[Path]:
    """Find facts_summary.json in run_dir with priority."""
    # Priority 1: direct path
    facts_path = run_dir / "facts_summary.json"
    if facts_path.exists():
        return facts_path
    
    # Priority 2: search in subdirectories
    for subdir in run_dir.iterdir():
        if subdir.is_dir():
            candidate = subdir / "facts_summary.json"
            if candidate.exists():
                return candidate
    
    if required:
        print(f"Error: facts_summary.json not found in {run_dir}", file=sys.stderr)
        print(f"  Searched: {run_dir}/facts_summary.json", file=sys.stderr)
        print(f"  And subdirectories", file=sys.stderr)
        sys.exit(2)
    
    return None


def infer_lane_from_path(run_dir: Path) -> str:
    """Infer lane from run_dir path."""
    # Example: verification/runs/facts/curated_v0/round20_... -> curated_v0
    parts = run_dir.parts
    try:
        facts_idx = parts.index("facts")
        if facts_idx + 1 < len(parts):
            return parts[facts_idx + 1]
    except ValueError:
        pass
    
    # Fallback: use parent directory name
    return run_dir.parent.name


def load_baselines() -> Dict[str, Any]:
    """Load baselines.json."""
    baselines_path = project_root / "docs" / "ops" / "baselines.json"
    if not baselines_path.exists():
        return {}
    
    try:
        with open(baselines_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load baselines.json: {e}", file=sys.stderr)
        return {}


def get_baseline_run_dir(lane: str, baselines: Dict[str, Any], explicit_baseline: Optional[str] = None) -> Optional[Path]:
    """Get baseline run directory."""
    if explicit_baseline:
        baseline_path = project_root / explicit_baseline
        if baseline_path.exists():
            return baseline_path.resolve()
        return None
    
    lane_config = baselines.get(lane, {})
    baseline_rel = lane_config.get("baseline_run_dir")
    if baseline_rel:
        baseline_path = project_root / baseline_rel
        if baseline_path.exists():
            return baseline_path.resolve()
    
    return None


def load_round_registry(registry_path: Path) -> List[Dict[str, Any]]:
    """Load round registry."""
    if not registry_path.exists():
        return []
    
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load round registry: {e}", file=sys.stderr)
        return []


def get_prev_run_dir(lane: str, registry: List[Dict[str, Any]], baseline_run_dir: Optional[Path]) -> Optional[Path]:
    """Get previous run directory from registry (old schema)."""
    # Find last entry for same lane
    for entry in reversed(registry):
        if entry.get("lane") == lane:
            prev_rel = entry.get("current_run_dir")
            if prev_rel:
                prev_path = project_root / prev_rel
                if prev_path.exists():
                    return prev_path.resolve()
    
    # Fallback to baseline
    return baseline_run_dir


def get_prev_run_dir_auto(
    lane: str,
    current_run_dir: Path,
    old_registry_path: Path,
    new_registry_path: Path
) -> Tuple[Optional[Path], str]:
    """
    Automatically infer prev_run_dir from registries.
    Returns: (prev_run_dir, status_message)
    """
    # Try old registry first (reports/validation/round_registry.json)
    if old_registry_path.exists():
        try:
            with open(old_registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
            
            if isinstance(registry, list):
                # Find entries for same lane, excluding current
                current_rel = str(current_run_dir.relative_to(project_root))
                prev_entries = [
                    e for e in registry
                    if e.get("lane") == lane and e.get("current_run_dir") != current_rel
                ]
                
                if prev_entries:
                    # Get most recent (last in list)
                    last_entry = prev_entries[-1]
                    prev_run_dir_str = last_entry.get("current_run_dir")
                    if prev_run_dir_str:
                        prev_path = project_root / prev_run_dir_str
                        if prev_path.exists():
                            return prev_path.resolve(), f"auto (old registry: {prev_run_dir_str})"
        except Exception as e:
            print(f"Warning: Failed to read old registry for prev lookup: {e}", file=sys.stderr)
    
    # Try new registry (docs/verification/round_registry.json)
    if new_registry_path.exists():
        try:
            with open(new_registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
            
            lanes = registry.get("lanes", {})
            lane_data = lanes.get(lane, {})
            rounds = lane_data.get("rounds", [])
            
            # Extract current round info
            from tools.round_registry import extract_round_info
            _, current_round_num, _ = extract_round_info(current_run_dir)
            
            # Find previous round (largest round_num < current_round_num)
            prev_round = None
            for round_entry in rounds:
                round_num = round_entry.get("round_num")
                if round_num is not None and round_num < current_round_num:
                    if prev_round is None or round_num > prev_round.get("round_num", -1):
                        prev_round = round_entry
            
            if prev_round:
                prev_run_dir_str = prev_round.get("run_dir")
                if prev_run_dir_str:
                    prev_path = project_root / prev_run_dir_str
                    if prev_path.exists():
                        return prev_path.resolve(), f"auto (new registry: round {prev_round.get('round_num')})"
        except Exception as e:
            print(f"Warning: Failed to read new registry for prev lookup: {e}", file=sys.stderr)
    
    # Fallback: use current as prev (with warning)
    return current_run_dir, "fallback (no prev found, using current)"


def get_baseline_alias_auto(
    lane: str,
    explicit_alias: Optional[str],
    new_registry_path: Path
) -> Tuple[str, str]:
    """
    Automatically infer baseline alias.
    Returns: (baseline_alias, status_message)
    """
    # Priority A: explicit argument
    if explicit_alias:
        return explicit_alias, "explicit"
    
    # Priority B: new registry baseline.alias
    if new_registry_path.exists():
        try:
            with open(new_registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
            
            lanes = registry.get("lanes", {})
            lane_data = lanes.get(lane, {})
            baseline = lane_data.get("baseline", {})
            
            if baseline:
                alias = baseline.get("alias")
                if alias:
                    return alias, f"auto (new registry: {alias})"
        except Exception as e:
            print(f"Warning: Failed to read new registry for baseline alias: {e}", file=sys.stderr)
    
    # Priority C: UNSET_BASELINE + warning
    print(f"Warning: Baseline alias not found for lane '{lane}'. Using 'UNSET_BASELINE'.", file=sys.stderr)
    return "UNSET_BASELINE", "fallback (UNSET_BASELINE)"


def get_prev_and_baseline_from_new_registry(
    lane: str,
    current_round_num: Optional[int],
    new_registry_path: Path
) -> tuple[Optional[Path], Optional[Path]]:
    """Get prev and baseline run directories from new round_registry.json schema."""
    if not new_registry_path.exists():
        return None, None
    
    try:
        with open(new_registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except Exception:
        return None, None
    
    lanes = registry.get("lanes", {})
    lane_data = lanes.get(lane, {})
    
    # Get baseline
    baseline_info = lane_data.get("baseline")
    baseline_run_dir = None
    if baseline_info and baseline_info.get("run_dir"):
        baseline_path = project_root / baseline_info["run_dir"]
        if baseline_path.exists():
            baseline_run_dir = baseline_path.resolve()
    
    # Get prev (current round_num보다 작은 round 중 가장 큰 round)
    prev_run_dir = None
    if current_round_num is not None:
        rounds = lane_data.get("rounds", [])
        prev_candidates = [
            r for r in rounds
            if r.get("round_num") is not None and r.get("round_num") < current_round_num
        ]
        if prev_candidates:
            # Sort by round_num descending and take the largest
            prev_candidates.sort(key=lambda x: x.get("round_num", 0), reverse=True)
            prev_entry = prev_candidates[0]
            prev_run_dir_str = prev_entry.get("run_dir")
            if prev_run_dir_str:
                prev_path = project_root / prev_run_dir_str
                if prev_path.exists():
                    prev_run_dir = prev_path.resolve()
    
    return prev_run_dir, baseline_run_dir


def generate_kpi(run_dir: Path, facts_summary_path: Path) -> Path:
    """Generate KPI.md using summarize_facts_kpi.py."""
    kpi_md_path = run_dir / "KPI.md"
    
    # Call summarize_facts_kpi.py
    cmd = [
        sys.executable,
        str(project_root / "tools" / "summarize_facts_kpi.py"),
        str(facts_summary_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))
    if result.returncode != 0:
        print(f"Error: Failed to generate KPI: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    
    # Save KPI.md
    with open(kpi_md_path, "w", encoding="utf-8") as f:
        f.write(result.stdout)
    
    print(f"Generated: {kpi_md_path}")
    return kpi_md_path


def generate_kpi_diff(
    current_run_dir: Path,
    current_facts_path: Path,
    prev_run_dir: Optional[Path],
    baseline_run_dir: Optional[Path]
) -> None:
    """Generate KPI_DIFF.md using kpi_diff.py."""
    from tools.kpi_diff import generate_kpi_diff as gen_diff
    
    # Find prev and baseline facts_summary.json
    prev_facts_path = find_facts_summary(prev_run_dir, required=False) if prev_run_dir else None
    baseline_facts_path = find_facts_summary(baseline_run_dir, required=False) if baseline_run_dir else None
    
    if not prev_facts_path and prev_run_dir:
        print(f"Warning: prev facts_summary.json not found in {prev_run_dir}", file=sys.stderr)
    
    if not baseline_facts_path and baseline_run_dir:
        print(f"Warning: baseline facts_summary.json not found in {baseline_run_dir}", file=sys.stderr)
    
    # Generate diff
    diff_md = gen_diff(
        current_path=current_facts_path,
        prev_path=prev_facts_path,
        baseline_path=baseline_facts_path,
        current_run_dir=str(current_run_dir.relative_to(project_root)),
        prev_run_dir=str(prev_run_dir.relative_to(project_root)) if prev_run_dir else None,
        baseline_run_dir=str(baseline_run_dir.relative_to(project_root)) if baseline_run_dir else None
    )
    
    # Save KPI_DIFF.md
    diff_path = current_run_dir / "KPI_DIFF.md"
    with open(diff_path, "w", encoding="utf-8") as f:
        f.write(diff_md)
    
    print(f"Generated: {diff_path}")


def update_coverage_backlog(
    facts_summary_path: Path,
    run_dir: Path,
    registry_path: Path
) -> None:
    """Update coverage backlog using coverage_backlog.py."""
    from tools.coverage_backlog import update_coverage_backlog as update_backlog
    
    update_backlog(
        facts_summary_path=facts_summary_path,
        run_dir=run_dir,
        registry_path=registry_path
    )


def update_new_round_registry(
    current_run_dir: Path,
    facts_summary_path: Optional[Path],
    lane: str,
    baselines: Dict[str, Any],
    coverage_backlog_touched: bool,
    baseline_alias: Optional[str] = None
) -> tuple[Optional[int], str, Optional[str]]:
    """Update new round registry schema using round_registry.py.
    
    Returns:
        (round_num, round_id, round_md_relpath)
        round_md_relpath is project_root-relative path (str) or None if cannot compute.
    """
    from tools.round_registry import update_registry, extract_round_info
    
    # Extract round info
    _, round_num, round_id = extract_round_info(current_run_dir)
    
    # New registry path
    new_registry_path = project_root / "docs" / "verification" / "round_registry.json"
    
    # Update registry (baseline_alias is handled by baselines.json and new registry baseline.alias)
    update_registry(
        registry_path=new_registry_path,
        current_run_dir=current_run_dir,
        facts_summary_path=facts_summary_path,
        lane=lane,
        round_num=round_num,
        round_id=round_id,
        baselines=baselines,
        coverage_backlog_touched=coverage_backlog_touched
    )
    
    # T2) Compute folder-split canonical round md path and ensure stub
    round_md_relpath: Optional[str] = None
    if round_num is not None:
        milestone_id = "M01_baseline"  # Fixed for now
        lane_slug = lane.replace("/", "_")
        round_md_dir = project_root / "docs" / "ops" / "rounds" / lane_slug / milestone_id
        round_md_filename = f"round_{round_num:02d}.md"
        round_md_path = round_md_dir / round_md_filename
        round_md_relpath = f"docs/ops/rounds/{lane_slug}/{milestone_id}/{round_md_filename}"
        
        # Idempotent stub generation: create only if file does not exist
        if not round_md_path.exists():
            try:
                round_md_dir.mkdir(parents=True, exist_ok=True)
                
                # Try to load template
                stub_content: Optional[str] = None
                template_candidates = [
                    project_root / "docs" / "ops" / "rounds" / "ROUND_TEMPLATE.md",
                    project_root / "docs" / "ops" / "rounds" / "ROUND_TEMPLATE_v1.md",
                ]
                for tpl_path in template_candidates:
                    if tpl_path.exists():
                        try:
                            stub_content = tpl_path.read_text(encoding="utf-8")
                            break
                        except Exception:
                            continue
                
                # Fallback minimal stub
                if not stub_content:
                    stub_content = f"""# Round {round_num}

## Goal
[라운드 목표를 간단히 기술]

## Changes
[주요 변경사항을 나열]

## Artifacts
- **run_dir**: `{str(current_run_dir.relative_to(project_root)).replace(chr(92), '/')}`

## Progress Events (dashboard)

```jsonl
# (optional) one event per line
```

## Notes
[추가 메모]
"""
                
                round_md_path.write_text(stub_content, encoding="utf-8")
                print(f"Generated round stub: {round_md_relpath}")
            except Exception as e:
                print(f"Warning: Failed to create round md stub: {e}", file=sys.stderr)
                # round_md_relpath remains set; ingest will warn if file missing
    
    return round_num, round_id, round_md_relpath


def generate_lineage_manifest(
    current_run_dir: Path,
    facts_summary_path: Path,
    lane: str,
    round_id: str,
    round_num: Optional[int]
) -> None:
    """Generate LINEAGE.md using lineage.py."""
    from tools.lineage import generate_lineage_manifest as gen_lineage
    
    lineage_md = gen_lineage(
        current_run_dir=current_run_dir,
        facts_summary_path=facts_summary_path,
        lane=lane,
        round_id=round_id,
        round_num=round_num
    )
    
    # Save LINEAGE.md
    lineage_path = current_run_dir / "LINEAGE.md"
    with open(lineage_path, "w", encoding="utf-8") as f:
        f.write(lineage_md)
    
    print(f"Generated: {lineage_path}")


def generate_visual_provenance(
    current_run_dir: Path,
    facts_summary_path: Path,
    lane: str
) -> Dict[str, Any]:
    """Generate visual provenance images."""
    from tools.visual_provenance import generate_visual_provenance as gen_visual
    
    try:
        visual_metadata = gen_visual(
            current_run_dir=current_run_dir,
            facts_summary_path=facts_summary_path,
            npz_path=None,  # Will be extracted from facts_summary
            lane=lane
        )
        
        if visual_metadata["visual_status"] == "success":
            print(f"Generated: artifacts/visual/front_xy.png, side_zy.png")
        elif visual_metadata["visual_status"] == "partial":
            print(f"Warning: Partial visual generation (one view failed)")
        elif visual_metadata["visual_status"] == "failed":
            print(f"Warning: Visual generation failed: {visual_metadata.get('warnings', [])}")
        elif visual_metadata["visual_status"] == "skipped":
            # Check if it's a measurement-only NPZ (expected case)
            reason = visual_metadata.get("visual_reason", "")
            npz_has_verts = visual_metadata.get("npz_has_verts", True)
            
            if not npz_has_verts and "measurement-only" in reason:
                # Determine if this is expected for this lane
                is_expected = False
                expected_hint = ""
                
                # Check if lane is curated_v0 or schema suggests realdata
                if lane == "curated_v0":
                    is_expected = True
                    expected_hint = f" This is expected for {lane} realdata lane."
                else:
                    # Try to infer from facts_summary schema_version
                    try:
                        with open(facts_summary_path, "r", encoding="utf-8") as f:
                            facts_data = json.load(f)
                        schema_version = facts_data.get("schema_version", "")
                        if "realdata" in schema_version.lower() or "real_data" in schema_version.lower():
                            is_expected = True
                            expected_hint = f" This is expected for realdata datasets."
                    except Exception:
                        pass
                
                print(f"Visual provenance unavailable: measurement-only NPZ (no 'verts' key).{expected_hint}")
            else:
                print(f"Warning: Visual generation skipped: {visual_metadata.get('warnings', [])}")
        
        return visual_metadata
    except Exception as e:
        print(f"Warning: Visual provenance generation failed: {e}", file=sys.stderr)
        return {
            "visual_status": "skipped",
            "visual_reason": f"exception: {str(e)}",
            "warnings": [f"EXCEPTION: {str(e)}"]
        }


def update_lineage_with_visual(
    current_run_dir: Path,
    visual_metadata: Dict[str, Any]
) -> None:
    """Update LINEAGE.md with visual provenance metadata."""
    lineage_path = current_run_dir / "LINEAGE.md"
    if not lineage_path.exists():
        return  # LINEAGE.md not generated yet
    
    try:
        with open(lineage_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Find Outputs section and add visual info
        if "## Outputs" in content:
            # Add visual provenance section before NPZ Metadata
            visual_section = "\n## Visual Provenance\n\n"
            visual_section += f"- **status**: `{visual_metadata.get('visual_status', 'unknown')}`\n"
            
            if visual_metadata.get("visual_reason"):
                visual_section += f"- **reason**: `{visual_metadata['visual_reason']}`\n"
            
            visual_section += f"- **npz_has_verts**: `{visual_metadata.get('npz_has_verts', False)}`\n"
            
            if visual_metadata.get("npz_keys"):
                npz_keys_str = ", ".join([f"`{k}`" for k in visual_metadata["npz_keys"][:10]])
                if len(visual_metadata["npz_keys"]) > 10:
                    npz_keys_str += f", ... ({len(visual_metadata['npz_keys'])} total)"
                visual_section += f"- **npz_keys**: {npz_keys_str}\n"
            
            if visual_metadata.get("visual_case_id"):
                visual_section += f"- **case_id**: `{visual_metadata['visual_case_id']}`\n"
                visual_section += f"- **case_class**: `{visual_metadata.get('visual_case_class', 'unknown')}`\n"
                visual_section += f"- **is_valid**: `{visual_metadata.get('visual_case_is_valid', 'unknown')}`\n"
                visual_section += f"- **selection_reason**: `{visual_metadata.get('selection_reason', 'unknown')}`\n"
            
            if visual_metadata.get("downsample_n"):
                visual_section += f"- **downsample_n**: `{visual_metadata['downsample_n']}` ({visual_metadata.get('downsample_method', 'unknown')})\n"
            
            if visual_metadata.get("front_xy_path"):
                visual_section += f"- **front_xy**: `{visual_metadata['front_xy_path']}`\n"
            if visual_metadata.get("side_zy_path"):
                visual_section += f"- **side_zy**: `{visual_metadata['side_zy_path']}`\n"
            
            if visual_metadata.get("warnings"):
                visual_section += f"- **warnings**: {len(visual_metadata['warnings'])} warning(s)\n"
            
            visual_section += "\n"
            
            # Insert before NPZ Metadata section
            if "## NPZ Metadata" in content:
                content = content.replace("## NPZ Metadata", visual_section + "## NPZ Metadata")
            else:
                # Append at end if no NPZ Metadata section
                content = content.rstrip() + "\n" + visual_section
        
        with open(lineage_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"Warning: Failed to update LINEAGE.md with visual metadata: {e}", file=sys.stderr)


def update_kpi_with_visual(
    kpi_path: Path,
    visual_metadata: Dict[str, Any]
) -> None:
    """Update KPI.md with visual provenance section."""
    if not kpi_path.exists():
        return
    
    try:
        with open(kpi_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Add Visual Provenance section at the end
        visual_section = "\n## Visual Provenance\n\n"
        
        if visual_metadata.get("visual_status") == "success":
            if visual_metadata.get("front_xy_path"):
                front_rel = visual_metadata["front_xy_path"]
                visual_section += f"- [Front View (X-Y)]({front_rel})\n"
            if visual_metadata.get("side_zy_path"):
                side_rel = visual_metadata["side_zy_path"]
                visual_section += f"- [Side View (Z-Y)]({side_rel})\n"
            
            if visual_metadata.get("visual_case_id"):
                visual_section += f"\n*Case: {visual_metadata['visual_case_id']} ({visual_metadata.get('visual_case_class', 'unknown')})*\n"
        elif visual_metadata.get("visual_status") == "skipped":
            visual_section += "*Visual provenance generation skipped.\n"
            if visual_metadata.get("warnings"):
                visual_section += f"Warnings: {', '.join(visual_metadata['warnings'][:3])}\n"
            visual_section += "*\n"
        else:
            visual_section += f"*Visual provenance status: {visual_metadata.get('visual_status', 'unknown')}*\n"
        
        visual_section += "\n"
        
        content = content.rstrip() + "\n" + visual_section
        
        with open(kpi_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"Warning: Failed to update KPI.md with visual provenance: {e}", file=sys.stderr)


def update_golden_registry(
    facts_summary_path: Path
) -> None:
    """Update golden registry from facts_summary.json."""
    try:
        with open(facts_summary_path, "r", encoding="utf-8") as f:
            facts_data = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load facts_summary.json for golden registry: {e}", file=sys.stderr)
        return
    
    # Round33: Extract npz_path (multiple keys for compatibility)
    npz_path_str = (
        facts_data.get("npz_path") or
        facts_data.get("verts_npz_path") or
        facts_data.get("dataset_path") or
        facts_data.get("npz_path_abs")
    )
    if not npz_path_str:
        return  # No NPZ path, skip
    
    npz_path = Path(npz_path_str)
    if npz_path.is_absolute():
        npz_path_obj = npz_path
    else:
        npz_path_obj = project_root / npz_path
    
    if not npz_path_obj.exists():
        print(f"Warning: NPZ file not found: {npz_path_obj}", file=sys.stderr)
        return
    
    # Extract source_path_abs
    source_path_abs = facts_data.get("source_path_abs")
    if source_path_abs:
        source_path_abs = str(Path(source_path_abs).resolve())
    
    # Update golden registry
    from tools.golden_registry import upsert_golden_entry
    
    registry_path = project_root / "docs" / "verification" / "golden_registry.json"
    
    try:
        upsert_golden_entry(
            registry_path=registry_path,
            npz_path=npz_path_obj,
            source_path_abs=source_path_abs
        )
    except Exception as e:
        print(f"Warning: Failed to update golden registry: {e}", file=sys.stderr)


def get_git_commit() -> Optional[str]:
    """Get current git commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(project_root)
        )
        return result.stdout.strip()
    except Exception:
        return None


def ensure_round_charter(
    current_run_dir: Path,
    charter_template_path: Path
) -> Path:
    """
    Ensure ROUND_CHARTER.md exists (idempotent: do not overwrite if exists).
    Returns: Path to ROUND_CHARTER.md
    """
    charter_path = current_run_dir / "ROUND_CHARTER.md"
    
    # If charter already exists, do not touch it (idempotency)
    if charter_path.exists():
        print(f"Charter exists (preserved): {charter_path.relative_to(project_root)}")
        return charter_path
    
    # Load template
    if not charter_template_path.exists():
        print(f"Warning: Charter template not found: {charter_template_path}", file=sys.stderr)
        # Create minimal stub
        stub_content = "# Round Charter\n\n**Round**: [round_id]\n**Date**: [YYYY-MM-DD]\n\n## Single Objective\n\n## DOD\n\n## Forbidden Actions\n\n## Success Signals\n\n## Next Decision Gate\n"
    else:
        with open(charter_template_path, "r", encoding="utf-8") as f:
            stub_content = f.read()
    
    # Write stub
    with open(charter_path, "w", encoding="utf-8") as f:
        f.write(stub_content)
    
    print(f"Generated (stub): {charter_path.relative_to(project_root)}")
    return charter_path


def generate_prompt_snapshot(
    current_run_dir: Path,
    lane: str,
    baseline_alias: str,
    baseline_run_dir: Optional[Path],
    baseline_report: Optional[str],
    charter_path: Path,
    prev_run_dir: Optional[Path]
) -> Path:
    """
    Generate PROMPT_SNAPSHOT.md (always overwrite, facts-only, stable).
    Returns: Path to PROMPT_SNAPSHOT.md
    """
    snapshot_path = current_run_dir / "PROMPT_SNAPSHOT.md"
    
    lines = []
    lines.append("# Prompt Snapshot")
    lines.append("")
    lines.append("**Facts-only, stable across re-runs**")
    lines.append("")
    lines.append("## Lane")
    lines.append(f"- lane: `{lane}`")
    lines.append("")
    lines.append("## Current Run")
    lines.append(f"- current_run_dir: `{current_run_dir.relative_to(project_root)}`")
    lines.append("")
    lines.append("## Baseline")
    lines.append(f"- baseline_tag(alias): `{baseline_alias}`")
    if baseline_run_dir:
        lines.append(f"- baseline_run_dir: `{baseline_run_dir.relative_to(project_root)}`")
    else:
        lines.append("- baseline_run_dir: `unknown`")
    if baseline_report:
        lines.append(f"- baseline_report: `{baseline_report}`")
    else:
        lines.append("- baseline_report: `unknown`")
    lines.append("")
    lines.append("## Charter")
    lines.append(f"- charter_path: `{charter_path.relative_to(project_root)}`")
    lines.append("")
    lines.append("## Previous Run")
    if prev_run_dir:
        lines.append(f"- prev_run_dir: `{prev_run_dir.relative_to(project_root)}`")
    else:
        lines.append("- prev_run_dir: `unknown`")
    lines.append("")
    
    content = "\n".join(lines)
    
    # Always overwrite
    with open(snapshot_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"Generated (overwrite): {snapshot_path.relative_to(project_root)}")
    return snapshot_path


def ensure_visual_skip_evidence(
    current_run_dir: Path,
    facts_summary_path: Path,
    visual_metadata: Dict[str, Any],
    lane: str
) -> None:
    """
    Ensure visual skip evidence is recorded (DoD: artifacts/visual/ + SKIPPED.txt with fixed phrase + reason line).
    """
    visual_dir = current_run_dir / "artifacts" / "visual"
    
    # Always create visual_dir
    visual_dir.mkdir(parents=True, exist_ok=True)
    
    # Only write SKIPPED.txt if visual was skipped
    if visual_metadata.get("visual_status") != "skipped":
        return  # Visual succeeded or failed (not skipped), no skip evidence needed
    
    # Load facts_summary for additional context
    facts_data = {}
    try:
        with open(facts_summary_path, "r", encoding="utf-8") as f:
            facts_data = json.load(f)
    except Exception:
        pass
    
    # Extract facts from facts_summary
    meta_unit = facts_data.get("meta_unit", "unknown")
    npz_has_verts = visual_metadata.get("npz_has_verts", False)
    schema_version = facts_data.get("schema_version", "unknown")
    dataset_path = facts_data.get("dataset_path") or facts_data.get("npz_path_abs", "unknown")
    
    # Build reason line (facts-only, from facts_summary)
    reason_parts = []
    reason_parts.append(f"meta_unit={meta_unit}")
    reason_parts.append(f"npz_has_verts={npz_has_verts}")
    if not npz_has_verts:
        reason_parts.append("missing_key=verts")
    if schema_version != "unknown":
        reason_parts.append(f"schema_version={schema_version}")
    reason_line = ", ".join(reason_parts)
    
    # Write SKIPPED.txt with fixed phrase + reason line
    skipped_path = visual_dir / "SKIPPED.txt"
    with open(skipped_path, "w", encoding="utf-8") as f:
        f.write("visual unavailable: measurement-only npz\n")
        f.write(f"reason: {reason_line}\n")
        f.write(f"lane: {lane}\n")
        f.write(f"run_dir: {current_run_dir.relative_to(project_root)}\n")
        if dataset_path != "unknown":
            f.write(f"dataset_path: {dataset_path}\n")
    
    print(f"Recorded visual skip evidence: {skipped_path.relative_to(project_root)}")


def compute_relative_path_from_candidates(target_path: Path, candidates_dir: Path) -> str:
    """
    Compute relative path from CANDIDATES directory to target path.
    Returns path with forward slashes (for markdown links).
    """
    try:
        # Use os.path.relpath for reliable relative path calculation
        rel = os.path.relpath(str(target_path.resolve()), str(candidates_dir.resolve()))
        # Normalize to forward slashes for markdown
        rel = rel.replace("\\", "/")
        return rel
    except Exception:
        # Fallback: try pathlib relative_to
        try:
            rel = str(target_path.resolve().relative_to(candidates_dir.resolve()))
            rel = rel.replace("\\", "/")
            return rel
        except Exception:
            # If all else fails, return a safe relative path
            return f"../{target_path.name}"


def generate_candidate_stubs(
    current_run_dir: Path,
    lane: str,
    round_id: str,
    facts_summary_path: Path,
    kpi_path: Optional[Path],
    kpi_diff_path: Optional[Path],
    lineage_path: Optional[Path],
    charter_path: Optional[Path],
    snapshot_path: Optional[Path]
) -> None:
    """
    Generate candidate stub documents (GOLDEN_CANDIDATE.md, BASELINE_CANDIDATE.md).
    Always overwrite (not idempotent for content, but stable relative links).
    """
    candidates_dir = current_run_dir / "CANDIDATES"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    
    # Load templates
    golden_template_path = project_root / "docs" / "ops" / "templates" / "golden_candidate_stub.md"
    baseline_template_path = project_root / "docs" / "ops" / "templates" / "baseline_candidate_stub.md"
    
    # Load template content
    golden_template = ""
    baseline_template = ""
    
    if golden_template_path.exists():
        with open(golden_template_path, "r", encoding="utf-8") as f:
            golden_template = f.read()
    else:
        # Fallback stub
        golden_template = "# Golden Candidate: [Round ID]\n\n**NOTE: 이 문서는 참고용 후보 스텁입니다. 확정 시 별도 보관(예: docs/judgments/)을 권장합니다.**\n\n## Metadata\n- **lane**: [lane]\n- **run_dir**: [run_dir]\n- **generated_by**: `tools/postprocess_round.py`\n\n## Evidence Links\n\n## KPI_DIFF Summary\n\n## Warning Summary\n\n## Next Actions (권고/체크리스트)\n"
    
    if baseline_template_path.exists():
        with open(baseline_template_path, "r", encoding="utf-8") as f:
            baseline_template = f.read()
    else:
        # Fallback stub
        baseline_template = "# Baseline Candidate: [Round ID]\n\n**NOTE: 이 문서는 참고용 후보 스텁입니다. 확정 시 별도 보관(예: docs/judgments/)을 권장합니다.**\n\n## Metadata\n- **lane**: [lane]\n- **run_dir**: [run_dir]\n- **generated_by**: `tools/postprocess_round.py`\n\n## Evidence Links\n\n## KPI_DIFF Summary\n\n## Warning Summary\n\n## Next Actions (권고/체크리스트)\n"
    
    # Compute relative paths from CANDIDATES directory
    evidence_links = []
    
    if kpi_diff_path and kpi_diff_path.exists():
        rel_kpi_diff = compute_relative_path_from_candidates(kpi_diff_path, candidates_dir)
        evidence_links.append(f"- [KPI_DIFF.md]({rel_kpi_diff})")
    
    if lineage_path and lineage_path.exists():
        rel_lineage = compute_relative_path_from_candidates(lineage_path, candidates_dir)
        evidence_links.append(f"- [LINEAGE.md]({rel_lineage})")
    
    if kpi_path and kpi_path.exists():
        rel_kpi = compute_relative_path_from_candidates(kpi_path, candidates_dir)
        evidence_links.append(f"- [KPI.md]({rel_kpi})")
    
    if charter_path and charter_path.exists():
        rel_charter = compute_relative_path_from_candidates(charter_path, candidates_dir)
        evidence_links.append(f"- [ROUND_CHARTER.md]({rel_charter})")
    
    if snapshot_path and snapshot_path.exists():
        rel_snapshot = compute_relative_path_from_candidates(snapshot_path, candidates_dir)
        evidence_links.append(f"- [PROMPT_SNAPSHOT.md]({rel_snapshot})")
    
    evidence_links_section = "\n".join(evidence_links) if evidence_links else "- (No evidence files found)"
    
    # Replace template placeholders
    run_dir_rel = str(current_run_dir.relative_to(project_root))
    timestamp = datetime.now().isoformat()
    
    # Generate GOLDEN_CANDIDATE.md
    golden_content = golden_template
    golden_content = golden_content.replace("[Round ID]", round_id)
    golden_content = golden_content.replace("[lane]", lane)
    golden_content = golden_content.replace("[run_dir]", run_dir_rel)
    golden_content = golden_content.replace("[timestamp]", timestamp)
    
    # Replace Evidence Links section
    if "## Evidence Links" in golden_content:
        # Find the section and replace content until next ##
        lines = golden_content.split("\n")
        new_lines = []
        in_evidence_section = False
        for line in lines:
            if line.strip() == "## Evidence Links":
                in_evidence_section = True
                new_lines.append(line)
                new_lines.append("")
                new_lines.append("다음 증거 파일을 확인하세요 (CANDIDATES 기준 상대경로):")
                new_lines.append("")
                new_lines.append(evidence_links_section)
                new_lines.append("")
            elif in_evidence_section and line.startswith("##"):
                in_evidence_section = False
                new_lines.append(line)
            elif not in_evidence_section:
                new_lines.append(line)
        golden_content = "\n".join(new_lines)
    
    golden_path = candidates_dir / "GOLDEN_CANDIDATE.md"
    with open(golden_path, "w", encoding="utf-8") as f:
        f.write(golden_content)
    
    # Generate BASELINE_CANDIDATE.md
    baseline_content = baseline_template
    baseline_content = baseline_content.replace("[Round ID]", round_id)
    baseline_content = baseline_content.replace("[lane]", lane)
    baseline_content = baseline_content.replace("[run_dir]", run_dir_rel)
    baseline_content = baseline_content.replace("[timestamp]", timestamp)
    
    # Replace Evidence Links section
    if "## Evidence Links" in baseline_content:
        lines = baseline_content.split("\n")
        new_lines = []
        in_evidence_section = False
        for line in lines:
            if line.strip() == "## Evidence Links":
                in_evidence_section = True
                new_lines.append(line)
                new_lines.append("")
                new_lines.append("다음 증거 파일을 확인하세요 (CANDIDATES 기준 상대경로):")
                new_lines.append("")
                new_lines.append(evidence_links_section)
                new_lines.append("")
            elif in_evidence_section and line.startswith("##"):
                in_evidence_section = False
                new_lines.append(line)
            elif not in_evidence_section:
                new_lines.append(line)
        baseline_content = "\n".join(new_lines)
    
    baseline_path = candidates_dir / "BASELINE_CANDIDATE.md"
    with open(baseline_path, "w", encoding="utf-8") as f:
        f.write(baseline_content)
    
    print(f"Generated: {golden_path.relative_to(project_root)}")
    print(f"Generated: {baseline_path.relative_to(project_root)}")


def detect_golden_registry_conflicts(
    proposed_entry: Dict[str, Any],
    registry_path: Path
) -> List[Dict[str, Any]]:
    """
    Detect conflicts between proposed_entry and existing golden registry.
    Returns list of conflict objects (facts-only).
    """
    conflicts = []
    
    if not registry_path.exists():
        return conflicts
    
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except Exception:
        return conflicts
    
    entries = registry.get("entries", [])
    
    # Check for duplicate run_dir
    proposed_run_dir = proposed_entry.get("run_dir")
    if proposed_run_dir:
        existing_ids = []
        for i, entry in enumerate(entries):
            # Check if entry has run_dir field (may not exist in old entries)
            if entry.get("run_dir") == proposed_run_dir:
                existing_ids.append(i)
        
        if existing_ids:
            conflicts.append({
                "type": "duplicate_run_dir",
                "existing_ids": existing_ids,
                "value": proposed_run_dir
            })
    
    # Check for duplicate npz_sha256
    proposed_sha256 = proposed_entry.get("npz_sha256")
    if proposed_sha256:
        existing_ids = []
        for i, entry in enumerate(entries):
            if entry.get("npz_sha256") == proposed_sha256:
                existing_ids.append(i)
        
        if existing_ids:
            conflicts.append({
                "type": "duplicate_npz_sha256",
                "existing_ids": existing_ids,
                "value": proposed_sha256
            })
    
    return conflicts


def generate_golden_registry_patch(
    current_run_dir: Path,
    lane: str,
    baseline_alias: Optional[str],
    facts_summary_path: Path,
    kpi_path: Optional[Path],
    kpi_diff_path: Optional[Path],
    lineage_path: Optional[Path],
    charter_path: Optional[Path],
    snapshot_path: Optional[Path]
) -> None:
    """
    Generate GOLDEN_REGISTRY_PATCH.json and README.
    Always overwrite (not idempotent for content).
    """
    candidates_dir = current_run_dir / "CANDIDATES"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    
    # Load facts_summary for npz_sha256 extraction
    facts_data = {}
    npz_sha256 = None
    try:
        with open(facts_summary_path, "r", encoding="utf-8") as f:
            facts_data = json.load(f)
        
        # Try to extract npz_sha256 from facts_summary or compute from NPZ
        npz_path_str = facts_data.get("dataset_path") or facts_data.get("npz_path_abs")
        if npz_path_str:
            npz_path = Path(npz_path_str)
            if npz_path.is_absolute():
                npz_path_obj = npz_path
            else:
                npz_path_obj = project_root / npz_path
            
            if npz_path_obj.exists():
                # Try to compute hash (only for small files)
                from tools.golden_registry import compute_file_hash
                npz_sha256 = compute_file_hash(npz_path_obj, max_size_mb=50)
    except Exception:
        pass
    
    # Build evidence_paths (repo-relative)
    evidence_paths = {}
    
    if charter_path and charter_path.exists():
        try:
            rel_charter = str(charter_path.relative_to(project_root))
            evidence_paths["round_charter"] = rel_charter
        except Exception:
            evidence_paths["round_charter"] = None
    else:
        evidence_paths["round_charter"] = None
    
    if snapshot_path and snapshot_path.exists():
        try:
            rel_snapshot = str(snapshot_path.relative_to(project_root))
            evidence_paths["prompt_snapshot"] = rel_snapshot
        except Exception:
            evidence_paths["prompt_snapshot"] = None
    else:
        evidence_paths["prompt_snapshot"] = None
    
    if kpi_diff_path and kpi_diff_path.exists():
        try:
            rel_kpi_diff = str(kpi_diff_path.relative_to(project_root))
            evidence_paths["kpi_diff"] = rel_kpi_diff
        except Exception:
            evidence_paths["kpi_diff"] = None
    else:
        evidence_paths["kpi_diff"] = None
    
    if lineage_path and lineage_path.exists():
        try:
            rel_lineage = str(lineage_path.relative_to(project_root))
            evidence_paths["lineage"] = rel_lineage
        except Exception:
            evidence_paths["lineage"] = None
    else:
        evidence_paths["lineage"] = None
    
    if kpi_path and kpi_path.exists():
        try:
            rel_kpi = str(kpi_path.relative_to(project_root))
            evidence_paths["kpi"] = rel_kpi
        except Exception:
            evidence_paths["kpi"] = None
    else:
        evidence_paths["kpi"] = None
    
    # Build proposed_entry
    run_dir_rel = str(current_run_dir.relative_to(project_root))
    
    proposed_entry = {
        "lane": lane,
        "run_dir": run_dir_rel,
        "baseline_tag_alias": baseline_alias if baseline_alias else None,
        "npz_sha256": npz_sha256,
        "evidence_paths": evidence_paths
    }
    
    # Detect conflicts
    registry_path = project_root / "docs" / "verification" / "golden_registry.json"
    conflicts = detect_golden_registry_conflicts(proposed_entry, registry_path)
    
    # Build patch JSON
    patch_data = {
        "schema_version": "golden_registry_patch@1",
        "generated_at": datetime.now().isoformat(),
        "generated_by": "tools/postprocess_round.py",
        "proposed_entry": proposed_entry,
        "conflicts": conflicts
    }
    
    # Write patch JSON
    patch_json_path = candidates_dir / "GOLDEN_REGISTRY_PATCH.json"
    with open(patch_json_path, "w", encoding="utf-8") as f:
        json.dump(patch_data, f, indent=2, ensure_ascii=False)
    
    # Generate README
    readme_content = f"""# Golden Registry Patch

**Generated at**: {patch_data['generated_at']}
**Generated by**: {patch_data['generated_by']}

## Proposed Entry

- **lane**: {lane}
- **run_dir**: {run_dir_rel}
- **baseline_tag_alias**: {baseline_alias if baseline_alias else 'null'}
- **npz_sha256**: {npz_sha256 if npz_sha256 else 'null'}

### Evidence Paths

- **round_charter**: {evidence_paths['round_charter'] or 'null'}
- **prompt_snapshot**: {evidence_paths['prompt_snapshot'] or 'null'}
- **kpi_diff**: {evidence_paths['kpi_diff'] or 'null'}
- **lineage**: {evidence_paths['lineage'] or 'null'}
- **kpi**: {evidence_paths['kpi'] or 'null'}

## Conflicts

"""
    
    if conflicts:
        readme_content += f"**Warning**: {len(conflicts)} conflict(s) detected:\n\n"
        for conflict in conflicts:
            readme_content += f"- **{conflict['type']}**: value=`{conflict['value']}`, existing_ids={conflict['existing_ids']}\n"
        readme_content += "\n"
    else:
        readme_content += "No conflicts detected.\n\n"
    
    # Add apply command example
    patch_json_rel = str(patch_json_path.relative_to(project_root))
    readme_content += f"""## Apply Command

To apply this patch to the golden registry:

```bash
py tools/golden_registry.py --add-entry {patch_json_rel} --registry docs/verification/golden_registry.json
```

If conflicts are detected and you want to force apply:

```bash
py tools/golden_registry.py --add-entry {patch_json_rel} --registry docs/verification/golden_registry.json --force
```

**Note**: This patch is a proposal only. The golden registry is not automatically modified.
"""
    
    readme_path = candidates_dir / "GOLDEN_REGISTRY_PATCH_README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print(f"Generated: {patch_json_path.relative_to(project_root)}")
    print(f"Generated: {readme_path.relative_to(project_root)}")


def extract_kpi_diff_summary(kpi_diff_path: Optional[Path]) -> str:
    """
    Extract change summary from KPI_DIFF.md (facts-only, no judgment).
    Returns markdown-formatted summary.
    """
    if not kpi_diff_path or not kpi_diff_path.exists():
        return "KPI_DIFF.md not found."
    
    try:
        with open(kpi_diff_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return "Failed to read KPI_DIFF.md."
    
    # Extract "Diff vs Baseline" section (more relevant for baseline update)
    lines = content.split("\n")
    summary_lines = []
    in_baseline_section = False
    in_table = False
    table_row_count = 0
    
    for i, line in enumerate(lines):
        if line.strip() == "## Diff vs Baseline":
            in_baseline_section = True
            summary_lines.append("### Diff vs Baseline")
            summary_lines.append("")
            continue
        
        if in_baseline_section and line.startswith("##") and not line.strip().startswith("###"):
            # End of baseline section (new top-level section)
            break
        
        if in_baseline_section:
            # Extract key metrics (Total Cases, HEIGHT_M, BUST/WAIST/HIP, NaN Rate, Failure Reason)
            if line.strip().startswith("###"):
                if summary_lines and summary_lines[-1] != "":
                    summary_lines.append("")
                summary_lines.append(line)
            elif line.strip().startswith("- **"):
                # Metric line like "- **Current**: 200"
                summary_lines.append(line)
            elif "|" in line and ("Key" in line or "Reason" in line or "Current" in line):
                # Table header
                in_table = True
                table_row_count = 0
                if summary_lines and summary_lines[-1] != "":
                    summary_lines.append("")
                summary_lines.append(line)
            elif "|" in line and in_table and line.strip().startswith("|"):
                # Table row (limit to top 5)
                table_row_count += 1
                if table_row_count <= 6:  # Header + 5 rows
                    summary_lines.append(line)
                else:
                    in_table = False
            elif line.strip().startswith("**Summary:**"):
                # Summary line
                in_table = False
                if summary_lines and summary_lines[-1] != "":
                    summary_lines.append("")
                summary_lines.append(line)
            elif not in_table and line.strip() and not line.strip().startswith("*"):
                # Other content lines (but skip note lines starting with *)
                pass
    
    if not summary_lines or len(summary_lines) <= 1:
        return "No baseline diff section found in KPI_DIFF.md."
    
    return "\n".join(summary_lines)


def generate_baseline_update_proposal(
    current_run_dir: Path,
    lane: str,
    baseline_alias: Optional[str],
    baseline_run_dir: Optional[Path],
    kpi_diff_path: Optional[Path],
    kpi_path: Optional[Path],
    lineage_path: Optional[Path],
    charter_path: Optional[Path],
    snapshot_path: Optional[Path]
) -> None:
    """
    Generate BASELINE_UPDATE_PROPOSAL.md.
    Always overwrite (not idempotent for content).
    """
    candidates_dir = current_run_dir / "CANDIDATES"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    
    # Load template
    template_path = project_root / "docs" / "ops" / "templates" / "baseline_update_proposal.md"
    
    template_content = ""
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()
    else:
        # Fallback template
        template_content = """# Baseline Update Proposal: [Round ID]

**NOTE: 이 문서는 참고용 후보 제안서입니다. baseline 갱신은 별도 PR로만 수행합니다.**

## Current Context

- **lane**: [lane]
- **run_dir**: [run_dir]
- **current_baseline_alias**: [baseline_alias]
- **current_baseline_run_dir**: [baseline_run_dir]

## Evidence Links

## KPI_DIFF Change Summary

## Risks & Rollback

## SYNC_HUB Checklist

## Next Actions (권고/체크리스트)
"""
    
    # Replace placeholders
    run_dir_rel = str(current_run_dir.relative_to(project_root))
    round_id = current_run_dir.name
    timestamp = datetime.now().isoformat()
    
    baseline_run_dir_str = str(baseline_run_dir.relative_to(project_root)) if baseline_run_dir else "None"
    
    template_content = template_content.replace("[Round ID]", round_id)
    template_content = template_content.replace("[lane]", lane)
    template_content = template_content.replace("[run_dir]", run_dir_rel)
    template_content = template_content.replace("[baseline_alias]", baseline_alias if baseline_alias else "None")
    template_content = template_content.replace("[baseline_run_dir]", baseline_run_dir_str)
    template_content = template_content.replace("[timestamp]", timestamp)
    
    # Extract KPI_DIFF summary
    kpi_diff_summary = extract_kpi_diff_summary(kpi_diff_path)
    
    # Replace KPI_DIFF Change Summary section
    if "## KPI_DIFF Change Summary" in template_content:
        lines = template_content.split("\n")
        new_lines = []
        in_summary_section = False
        for line in lines:
            if line.strip() == "## KPI_DIFF Change Summary":
                in_summary_section = True
                new_lines.append(line)
                new_lines.append("")
                new_lines.append("다음은 KPI_DIFF.md에서 추출한 변화 요약입니다 (facts-only, 판정 없음):")
                new_lines.append("")
                # Add extracted summary
                for summary_line in kpi_diff_summary.split("\n"):
                    new_lines.append(summary_line)
                new_lines.append("")
            elif in_summary_section and line.startswith("##"):
                in_summary_section = False
                new_lines.append(line)
            elif not in_summary_section:
                new_lines.append(line)
        template_content = "\n".join(new_lines)
    
    # Write proposal
    proposal_path = candidates_dir / "BASELINE_UPDATE_PROPOSAL.md"
    with open(proposal_path, "w", encoding="utf-8") as f:
        f.write(template_content)
    
    print(f"Generated: {proposal_path.relative_to(project_root)}")


def update_round_registry(
    registry_path: Path,
    current_run_dir: Path,
    facts_summary_path: Path,
    kpi_path: Path,
    lane: str,
    baseline_run_dir: Optional[Path],
    prev_run_dir: Optional[Path],
    baselines: Dict[str, Any],
    baseline_alias: Optional[str] = None
) -> None:
    """Update round registry with new entry."""
    registry = load_round_registry(registry_path)
    
    # Get baseline tag alias (use provided or fallback to baselines.json)
    baseline_tag_alias = baseline_alias
    if not baseline_tag_alias:
        lane_config = baselines.get(lane, {})
        if lane_config:
            baseline_tag_alias = lane_config.get("baseline_tag_alias")
    
    entry = {
        "created_at": datetime.now().isoformat(),
        "lane": lane,
        "current_run_dir": str(current_run_dir.relative_to(project_root)),
        "current_run_dir_abs": str(current_run_dir.resolve()),
        "facts_summary_path": str(facts_summary_path.resolve()),
        "kpi_path": str(kpi_path.resolve()),
        "baseline_run_dir": str(baseline_run_dir.relative_to(project_root)) if baseline_run_dir else None,
        "baseline_run_dir_abs": str(baseline_run_dir.resolve()) if baseline_run_dir else None,
        "prev_run_dir": str(prev_run_dir.relative_to(project_root)) if prev_run_dir else None,
        "prev_run_dir_abs": str(prev_run_dir.resolve()) if prev_run_dir else None,
        "git_commit": get_git_commit(),
        "baseline_tag_alias": baseline_tag_alias
    }
    
    registry.append(entry)
    
    # Ensure parent directory exists
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save registry
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"Updated: {registry_path} ({len(registry)} entries)")


def main():
    parser = argparse.ArgumentParser(
        description="Round postprocessing tool (round5)"
    )
    parser.add_argument(
        "--current_run_dir",
        type=str,
        required=True,
        help="Current run directory path"
    )
    parser.add_argument(
        "--lane",
        type=str,
        default=None,
        help="Lane name (default: inferred from current_run_dir path)"
    )
    parser.add_argument(
        "--baseline_run_dir",
        type=str,
        default=None,
        help="Baseline run directory (default: loaded from baselines.json)"
    )
    parser.add_argument(
        "--registry_path",
        type=str,
        default="reports/validation/round_registry.json",
        help="Round registry path (default: reports/validation/round_registry.json)"
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    current_run_dir = (project_root / args.current_run_dir).resolve()
    if not current_run_dir.exists():
        print(f"Error: Current run directory not found: {current_run_dir}", file=sys.stderr)
        sys.exit(1)
    
    registry_path = project_root / args.registry_path
    
    # Infer lane if not provided
    lane = args.lane or infer_lane_from_path(current_run_dir)
    print(f"Lane: {lane}")
    
    # Load baselines
    baselines = load_baselines()
    
    # Get baseline run directory
    baseline_run_dir = get_baseline_run_dir(lane, baselines, args.baseline_run_dir)
    if baseline_run_dir:
        print(f"Baseline: {baseline_run_dir.relative_to(project_root)}")
    else:
        print("Baseline: None")
    
    # Load new registry path
    new_registry_path = project_root / "docs" / "verification" / "round_registry.json"
    
    # Auto-infer prev_run_dir
    prev_run_dir, prev_status = get_prev_run_dir_auto(
        lane=lane,
        current_run_dir=current_run_dir,
        old_registry_path=registry_path,
        new_registry_path=new_registry_path
    )
    
    # Warn if prev == current (fallback case)
    if prev_run_dir == current_run_dir and prev_status.startswith("fallback"):
        print(f"Warning: No previous run found for lane '{lane}'. Using current as prev.", file=sys.stderr)
    
    # Get baseline alias (auto-infer)
    baseline_alias, alias_status = get_baseline_alias_auto(
        lane=lane,
        explicit_alias=None,  # Could add --baseline_alias arg if needed
        new_registry_path=new_registry_path
    )
    
    # Get baseline_run_dir from new registry if available
    if new_registry_path.exists():
        try:
            with open(new_registry_path, "r", encoding="utf-8") as f:
                new_registry = json.load(f)
            lanes = new_registry.get("lanes", {})
            lane_data = lanes.get(lane, {})
            baseline = lane_data.get("baseline", {})
            if baseline:
                baseline_run_dir_str = baseline.get("run_dir")
                if baseline_run_dir_str:
                    baseline_path = project_root / baseline_run_dir_str
                    if baseline_path.exists():
                        baseline_run_dir = baseline_path.resolve()
        except Exception:
            pass  # Keep baseline_run_dir from baselines.json
    
    # Console output (enhanced)
    print(f"Prev: {prev_run_dir.relative_to(project_root) if prev_run_dir else 'None'} ({prev_status})")
    print(f"Baseline: {baseline_run_dir.relative_to(project_root) if baseline_run_dir else 'None'}")
    print(f"Baseline alias: {baseline_alias} ({alias_status})")
    
    # Find facts_summary.json
    facts_summary_path = find_facts_summary(current_run_dir, required=True)
    if not facts_summary_path:
        sys.exit(2)
    print(f"Facts summary: {facts_summary_path.relative_to(project_root)}")
    
    # Generate KPI
    kpi_path = generate_kpi(current_run_dir, facts_summary_path)
    
    # Generate KPI_DIFF
    generate_kpi_diff(
        current_run_dir=current_run_dir,
        current_facts_path=facts_summary_path,
        prev_run_dir=prev_run_dir,
        baseline_run_dir=baseline_run_dir
    )
    
    # Update old registry (for backward compatibility, keep existing logic)
    update_round_registry(
        registry_path=registry_path,
        current_run_dir=current_run_dir,
        facts_summary_path=facts_summary_path,
        kpi_path=kpi_path,
        lane=lane,
        baseline_run_dir=baseline_run_dir,
        prev_run_dir=prev_run_dir,
        baselines=baselines,
        baseline_alias=baseline_alias
    )
    
    # Update coverage backlog
    coverage_backlog_touched = False
    try:
        update_coverage_backlog(
            facts_summary_path=facts_summary_path,
            run_dir=current_run_dir,
            registry_path=registry_path
        )
        coverage_backlog_touched = True
    except Exception as e:
        print(f"Warning: Failed to update coverage backlog: {e}", file=sys.stderr)
    
    # Update round registry (new schema) and get round info + round md path
    round_num, round_id, round_md_rel = update_new_round_registry(
        current_run_dir=current_run_dir,
        facts_summary_path=facts_summary_path,
        lane=lane,
        baselines=baselines,
        coverage_backlog_touched=coverage_backlog_touched,
        baseline_alias=baseline_alias
    )
    
    # Generate lineage manifest
    generate_lineage_manifest(
        current_run_dir=current_run_dir,
        facts_summary_path=facts_summary_path,
        lane=lane,
        round_id=round_id,
        round_num=round_num
    )
    
    # Update golden registry
    update_golden_registry(
        facts_summary_path=facts_summary_path
    )
    
    # Generate visual provenance
    visual_metadata = generate_visual_provenance(
        current_run_dir=current_run_dir,
        facts_summary_path=facts_summary_path,
        lane=lane
    )
    
    # Update LINEAGE.md with visual metadata
    update_lineage_with_visual(
        current_run_dir=current_run_dir,
        visual_metadata=visual_metadata
    )
    
    # Update KPI.md with visual provenance section
    update_kpi_with_visual(
        kpi_path=kpi_path,
        visual_metadata=visual_metadata
    )
    
    # Ensure ROUND_CHARTER.md (idempotent: do not overwrite if exists)
    charter_template_path = project_root / "docs" / "verification" / "round_charter_template.md"
    charter_path = ensure_round_charter(
        current_run_dir=current_run_dir,
        charter_template_path=charter_template_path
    )
    
    # Get baseline_report from baselines or new registry
    baseline_report = None
    lane_config = baselines.get(lane, {})
    if lane_config:
        baseline_report = lane_config.get("baseline_report")
    if not baseline_report and new_registry_path.exists():
        try:
            with open(new_registry_path, "r", encoding="utf-8") as f:
                new_registry = json.load(f)
            lanes = new_registry.get("lanes", {})
            lane_data = lanes.get(lane, {})
            baseline = lane_data.get("baseline", {})
            if baseline:
                baseline_report = baseline.get("report")
        except Exception:
            pass
    
    # Generate PROMPT_SNAPSHOT.md (always overwrite)
    generate_prompt_snapshot(
        current_run_dir=current_run_dir,
        lane=lane,
        baseline_alias=baseline_alias,
        baseline_run_dir=baseline_run_dir,
        baseline_report=baseline_report,
        charter_path=charter_path,
        prev_run_dir=prev_run_dir
    )
    
    # Ensure visual skip evidence (DoD: artifacts/visual/ + SKIPPED.txt)
    ensure_visual_skip_evidence(
        current_run_dir=current_run_dir,
        facts_summary_path=facts_summary_path,
        visual_metadata=visual_metadata,
        lane=lane
    )
    
    # Generate candidate stubs (always overwrite)
    lineage_path_obj = current_run_dir / "LINEAGE.md"
    kpi_diff_path_obj = current_run_dir / "KPI_DIFF.md"
    snapshot_path_obj = current_run_dir / "PROMPT_SNAPSHOT.md"
    
    generate_candidate_stubs(
        current_run_dir=current_run_dir,
        lane=lane,
        round_id=round_id,
        facts_summary_path=facts_summary_path,
        kpi_path=kpi_path,
        kpi_diff_path=kpi_diff_path_obj if kpi_diff_path_obj.exists() else None,
        lineage_path=lineage_path_obj if lineage_path_obj.exists() else None,
        charter_path=charter_path,
        snapshot_path=snapshot_path_obj if snapshot_path_obj.exists() else None
    )
    
    # Generate golden registry patch (always overwrite)
    generate_golden_registry_patch(
        current_run_dir=current_run_dir,
        lane=lane,
        baseline_alias=baseline_alias,
        facts_summary_path=facts_summary_path,
        kpi_path=kpi_path,
        kpi_diff_path=kpi_diff_path_obj if kpi_diff_path_obj.exists() else None,
        lineage_path=lineage_path_obj if lineage_path_obj.exists() else None,
        charter_path=charter_path,
        snapshot_path=snapshot_path_obj if snapshot_path_obj.exists() else None
    )
    
    # Generate baseline update proposal (always overwrite)
    generate_baseline_update_proposal(
        current_run_dir=current_run_dir,
        lane=lane,
        baseline_alias=baseline_alias,
        baseline_run_dir=baseline_run_dir,
        kpi_diff_path=kpi_diff_path_obj if kpi_diff_path_obj.exists() else None,
        kpi_path=kpi_path,
        lineage_path=lineage_path_obj if lineage_path_obj.exists() else None,
        charter_path=charter_path,
        snapshot_path=snapshot_path_obj if snapshot_path_obj.exists() else None
    )
    
    if round_md_rel:
        subprocess.run([sys.executable, str(project_root / "tools" / "ingest_round_progress_events_v0.py"), "--round-path", str(project_root / round_md_rel), "--hub-root", str(project_root)], check=False)
    else:
        print("Warning: round_md_rel not available (round_num not detected from run_dir name). Ingest skipped.", file=sys.stderr)
    subprocess.run([sys.executable, str(project_root / "tools" / "render_dashboard_v0.py"), "--hub-root", str(project_root)], check=False)
    subprocess.run([sys.executable, str(project_root / "tools" / "publish_work_briefs_v0.py"), "--hub-root", str(project_root)], check=False)
    subprocess.run([sys.executable, str(project_root / "tools" / "ops" / "run_end_ops_hook.py")], check=False)

    print("\nPostprocessing complete!")


if __name__ == "__main__":
    main()
