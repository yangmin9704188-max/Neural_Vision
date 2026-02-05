#!/usr/bin/env python3
"""
Generate COMMANDS.md from Makefile

Makefile의 help 타겟 실행 결과를 파싱하여 docs/ops/COMMANDS.md를 자동 생성합니다.
Source of truth = Makefile help output
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional

# Add project root to path
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))


def normalize_output(text: str) -> str:
    """Normalize output: convert \\r\\n to \\n, remove trailing whitespace."""
    # Convert \r\n to \n
    text = text.replace('\r\n', '\n')
    # Remove trailing whitespace from each line
    lines = [line.rstrip() for line in text.split('\n')]
    return '\n'.join(lines)


def run_make_help() -> Optional[str]:
    """Run `make help` with fixed environment and return normalized stdout.
    
    Returns None if make is not available (fallback for local dev without make).
    """
    env = os.environ.copy()
    # Fix locale for deterministic output
    env['LANG'] = 'C'
    env['LC_ALL'] = 'C'
    
    try:
        result = subprocess.run(
            ['make', 'help'],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding='utf-8',
            env=env,
            check=True
        )
        # Normalize output
        return normalize_output(result.stdout)
    except FileNotFoundError:
        # make not available - return None for fallback
        return None
    except subprocess.CalledProcessError as e:
        # make help failed - return None for fallback
        return None


def parse_makefile_variables(makefile_path: Path) -> dict:
    """Parse Makefile to extract variable defaults."""
    if not makefile_path.exists():
        return {}
    
    content = makefile_path.read_text(encoding='utf-8')
    variables = {}
    var_pattern = r'^([A-Z_]+)\s*\?=\s*(.+)$'
    for line in content.split('\n'):
        match = re.match(var_pattern, line)
        if match:
            var_name = match.group(1)
            var_value = match.group(2).strip()
            variables[var_name] = var_value
    
    return variables


def parse_help_output(help_output: str) -> Tuple[List[str], List[str], List[str]]:
    """Parse make help output to extract sections."""
    available_targets = []
    round_ops_shortcuts = []
    examples = []
    
    lines = help_output.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Detect section headers
        if 'Available targets:' in line:
            current_section = 'available'
            continue
        elif 'Round Ops Shortcuts:' in line:
            current_section = 'round_ops'
            continue
        elif 'Examples:' in line:
            current_section = 'examples'
            continue
        
        # Add to appropriate section
        if current_section == 'available':
            if line.startswith('make '):
                available_targets.append(line)
        elif current_section == 'round_ops':
            if line.startswith('make '):
                round_ops_shortcuts.append(line)
        elif current_section == 'examples':
            if line.startswith('make '):
                examples.append(line)
    
    return available_targets, round_ops_shortcuts, examples


def parse_target_info(target_line: str) -> Tuple[str, str, str]:
    """Parse a target line to extract target name, usage, and description."""
    # Remove "make " prefix
    if not target_line.startswith('make '):
        return None, None, None
    
    target_line = target_line[5:].strip()
    
    # Extract target name (first word)
    parts = target_line.split(None, 1)
    if not parts:
        return None, None, None
    
    target_name = parts[0]
    
    # Extract usage (everything after target name)
    usage = parts[1] if len(parts) > 1 else ""
    
    # Try to infer description from target name
    description = ""
    if target_name == 'sync-dry':
        description = "Sync state를 dry-run 모드로 실행하여 변경 사항을 미리 확인"
    elif target_name == 'sync':
        description = "Sync state를 실행하여 상태를 업데이트"
    elif target_name == 'ai-prompt':
        description = "AI 프롬프트를 렌더링하여 출력"
    elif target_name == 'ai-prompt-json':
        description = "AI 프롬프트를 JSON 형식으로 렌더링하여 출력"
    elif target_name == 'curated_v0_round':
        description = "Curated v0 라운드를 실행 (runner + postprocess)"
    elif target_name == 'ops_guard':
        description = "Ops lock 경고 센서 실행"
    elif target_name == 'postprocess':
        description = "라운드 실행 결과에 대한 후처리 실행 (KPI/DIFF/CHARTER 생성)"
    elif target_name == 'postprocess-baseline':
        description = "Baseline run directory에 대한 후처리 실행 (BASELINE_RUN_DIR 사용)"
    elif target_name == 'curated_v0_baseline':
        description = "Baseline에 대한 curated_v0 라운드 실행 (runner 스킵, postprocess만)"
    elif target_name == 'golden-apply':
        description = "Golden registry에 패치 적용"
    elif target_name == 'judgment':
        description = "라운드 실행 결과에서 judgment 문서 생성 (스캐폴딩)"
    elif target_name == 'commands-update':
        description = "COMMANDS.md를 Makefile에서 자동 생성"
    
    return target_name, usage, description


def generate_commands_md(
    available_targets: List[str],
    round_ops_shortcuts: List[str],
    examples: List[str],
    variables: dict,
    make_help_available: bool = True
) -> str:
    """Generate COMMANDS.md content."""
    
    lines = []
    lines.append("# 공식 단축 명령 목록")
    lines.append("")
    lines.append("이 문서는 AI Fitting Engine 프로젝트에서 사용 가능한 공식 단축 명령들을 정리합니다.")
    lines.append("이 문서는 `make commands-update` 명령으로 자동 생성됩니다.")
    lines.append("")
    if not make_help_available:
        lines.append("**Note**: make help not available - document not updated.")
        lines.append("")
    lines.append("**Source of truth**: Makefile help output")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append("Makefile을 통해 제공되는 단축 명령들입니다. 각 명령의 목적, 사용법, 예시를 확인할 수 있습니다.")
    lines.append("")
    
    # Basic commands
    if available_targets:
        lines.append("## 기본 명령")
        lines.append("")
        
        for target_line in available_targets:
            target_name, usage, description = parse_target_info(target_line)
            if not target_name:
                continue
            
            lines.append(f"### {target_name}")
            if description:
                lines.append(f"**목적**: {description}")
            lines.append("")
            lines.append("**기본 사용법**:")
            lines.append("```bash")
            lines.append(f"make {target_name}" + (f" {usage}" if usage else ""))
            lines.append("```")
            lines.append("")
            
            # Find examples for this target
            target_examples = [ex for ex in examples if ex.startswith(f"make {target_name}")]
            if target_examples:
                lines.append("**예시**:")
                for ex in target_examples[:2]:  # Limit to 2 examples
                    lines.append("```bash")
                    lines.append(ex[5:])  # Remove "make " prefix
                    lines.append("```")
                lines.append("")
    
    # Round Ops Shortcuts
    if round_ops_shortcuts:
        lines.append("## Round Ops Shortcuts")
        lines.append("")
        
        for target_line in round_ops_shortcuts:
            target_name, usage, description = parse_target_info(target_line)
            if not target_name:
                continue
            
            lines.append(f"### {target_name}")
            if description:
                lines.append(f"**목적**: {description}")
            lines.append("")
            lines.append("**기본 사용법**:")
            lines.append("```bash")
            lines.append(f"make {target_name}" + (f" {usage}" if usage else ""))
            lines.append("```")
            lines.append("")
            
            # Find examples for this target
            target_examples = [ex for ex in examples if ex.startswith(f"make {target_name}")]
            if target_examples:
                lines.append("**예시**:")
                for ex in target_examples[:2]:  # Limit to 2 examples
                    lines.append("```bash")
                    lines.append(ex[5:])  # Remove "make " prefix
                    lines.append("```")
                lines.append("")
    
    # Quick recipes
    lines.append("## Quick Recipes")
    lines.append("")
    lines.append("자주 사용하는 조합 명령들입니다.")
    lines.append("")
    
    # Baseline postprocess
    if 'postprocess-baseline' in [parse_target_info(t)[0] for t in round_ops_shortcuts]:
        lines.append("### Baseline 후처리")
        lines.append("```bash")
        lines.append("make postprocess-baseline")
        lines.append("```")
        lines.append("")
    
    # Curated v0 baseline
    if 'curated_v0_baseline' in [parse_target_info(t)[0] for t in round_ops_shortcuts]:
        lines.append("### Baseline Curated v0 라운드")
        lines.append("```bash")
        lines.append("make curated_v0_baseline")
        lines.append("```")
        lines.append("")
    
    # Golden apply
    if 'golden-apply' in [parse_target_info(t)[0] for t in round_ops_shortcuts]:
        lines.append("### Golden Registry 패치 적용")
        lines.append("```bash")
        lines.append("make golden-apply PATCH=verification/runs/facts/curated_v0/round20_20260125_164801/CANDIDATES/GOLDEN_REGISTRY_PATCH.json")
        lines.append("```")
        lines.append("")
    
    # Judgment
    if 'judgment' in [parse_target_info(t)[0] for t in round_ops_shortcuts]:
        lines.append("### Judgment 문서 생성")
        lines.append("```bash")
        lines.append("make judgment FROM_RUN=verification/runs/facts/curated_v0/round20_20260125_164801")
        lines.append("```")
        lines.append("")
    
    # Variables
    if variables:
        lines.append("## 기본 변수")
        lines.append("")
        lines.append("다음 변수들은 Makefile에서 기본값으로 설정되어 있으며, 필요시 오버라이드할 수 있습니다:")
        lines.append("")
        
        for var_name, var_value in sorted(variables.items()):
            lines.append(f"- `{var_name}`: 기본값 `{var_value}`")
        
        lines.append("")
        lines.append("**예시**:")
        lines.append("```bash")
        if 'BASELINE_RUN_DIR' in variables:
            lines.append(f"make postprocess-baseline BASELINE_RUN_DIR=verification/runs/facts/curated_v0/round21_20260126_120000")
        lines.append("```")
        lines.append("")
    
    return '\n'.join(lines)


def main():
    makefile_path = repo_root / 'Makefile'
    output_path = repo_root / 'docs' / 'ops' / 'COMMANDS.md'
    
    # Run make help with fallback
    help_output = run_make_help()
    
    if help_output is None:
        # make help not available - no-op (don't modify existing file)
        print("Note: make help not available - COMMANDS.md not updated.", file=sys.stderr)
        sys.exit(0)
    
    # Parse help output
    available_targets, round_ops_shortcuts, examples = parse_help_output(help_output)
    
    # Parse Makefile variables
    variables = parse_makefile_variables(makefile_path)
    
    # Generate content
    content = generate_commands_md(available_targets, round_ops_shortcuts, examples, variables, make_help_available=True)
    
    # Write output with \n line endings (normalized)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure content uses \n line endings
    content_normalized = content.replace('\r\n', '\n').replace('\r', '\n')
    output_path.write_text(content_normalized, encoding='utf-8', newline='\n')
    
    print(f"Generated: {output_path.relative_to(repo_root)}")


if __name__ == '__main__':
    main()
