import yaml
import sys
import argparse
import json
import subprocess
from pathlib import Path

# Allow import of path_shim from repo root
_repo = Path(__file__).resolve().parents[1]
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))
from modules.body.src.utils.path_shim import rewrite_legacy_path

def check_if_changed(base_sha, head_sha, file_path):
    """
    Check if file_path is changed between base and head.
    Returns True if changed, False if not changed or diff fails.
    """
    if not base_sha or not head_sha:
        return False
    
    try:
        # Verify SHAs exist
        subprocess.run(
            ['git', 'rev-parse', '--verify', base_sha],
            capture_output=True,
            check=True
        )
        subprocess.run(
            ['git', 'rev-parse', '--verify', head_sha],
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError:
        return False
    
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', f'{base_sha}...{head_sha}'],
            capture_output=True,
            text=True,
            check=True
        )
        changed_files = result.stdout.strip().split('\n')
        return file_path in changed_files
    except subprocess.CalledProcessError:
        return False

def validate(require_manifest=False, base_sha=None, head_sha=None):
    obs_path = Path("logs/observation.md")
    if not obs_path.exists():
        print("[FAIL] logs/observation.md 파일이 없습니다.")
        sys.exit(1)

    content = obs_path.read_text(encoding="utf-8")
    
    # YAML 블록 추출 (```yaml ... ``` 사이의 내용)
    try:
        if "```yaml" not in content:
            raise ValueError("YAML 블록(```yaml)을 찾을 수 없습니다.")
        
        yaml_part = content.split("```yaml")[1].split("```")[0]
        data = yaml.safe_load(yaml_part)
        
        # 필수 필드 체크
        required_fields = ["policy_name", "run_id", "state_intent"]
        for field in required_fields:
            if not data.get(field):
                print(f"[FAIL] 필수 항목이 비어있습니다: {field}")
                sys.exit(1)
        
        # manifest.json 체크 (--require-manifest 옵션)
        if require_manifest:
            artifacts = data.get("artifacts", {})
            run_dir = artifacts.get("run_dir", "")
            if not run_dir:
                print("[FAIL] artifacts.run_dir이 비어있습니다.")
                sys.exit(1)
            run_dir = rewrite_legacy_path(run_dir)

            # Check if observation.md or run_dir was changed in this PR
            # If not changed, skip manifest validation (legacy path protection)
            should_skip = False
            skip_reason = None
            
            if base_sha and head_sha:
                obs_changed = check_if_changed(base_sha, head_sha, "logs/observation.md")
                run_dir_changed = check_if_changed(base_sha, head_sha, run_dir)
                
                # Check if any file under run_dir was changed
                run_dir_any_changed = False
                try:
                    result = subprocess.run(
                        ['git', 'diff', '--name-only', f'{base_sha}...{head_sha}'],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    changed_files = result.stdout.strip().split('\n')
                    for file in changed_files:
                        if file and file.startswith(run_dir):
                            run_dir_any_changed = True
                            break
                except subprocess.CalledProcessError:
                    pass
                
                if not obs_changed and not run_dir_changed and not run_dir_any_changed:
                    should_skip = True
                    skip_reason = f"SKIP: observation.md and run_dir ({run_dir}) not changed in this PR (legacy path)"
            else:
                # No base/head provided -> safe skip
                should_skip = True
                skip_reason = "SKIP: base/head SHA not provided (safe skip for legacy paths)"
            
            if should_skip:
                print(skip_reason)
                print("[PASS] observation.md 형식이 올바릅니다! (manifest check skipped)")
                return
            
            # Changed in this PR -> strict validation
            manifest_path = Path(run_dir) / "manifest.json"
            if not manifest_path.exists():
                print(f"[FAIL] manifest.json 파일이 없습니다: {manifest_path}")
                sys.exit(1)
            
            # manifest.json 내용 검증
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                
                if "run_id" not in manifest:
                    print("[FAIL] manifest.json에 run_id 필드가 없습니다.")
                    sys.exit(1)
                
                manifest_run_id = manifest.get("run_id", "")
                yaml_run_id = data.get("run_id", "")
                
                if manifest_run_id != yaml_run_id:
                    print(f"[FAIL] observation.md의 run_id({yaml_run_id})와 manifest.json의 run_id({manifest_run_id})가 일치하지 않습니다.")
                    sys.exit(1)
                
                if "artifacts" not in manifest:
                    print("[FAIL] manifest.json에 artifacts 필드가 없습니다.")
                    sys.exit(1)
                
                print(f"[PASS] manifest.json 검증 통과: {manifest_path}")
            except json.JSONDecodeError as e:
                print(f"[FAIL] manifest.json 파싱 오류: {e}")
                sys.exit(1)
                
        print("[PASS] observation.md 형식이 올바릅니다!")
        
    except Exception as e:
        print(f"[FAIL] 검증 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate observation.md format")
    parser.add_argument("--require-manifest", action="store_true", 
                        help="Also validate that manifest.json exists and matches")
    parser.add_argument("--base", help="Base SHA for git diff (optional, for change detection)")
    parser.add_argument("--head", help="Head SHA for git diff (optional, for change detection)")
    args = parser.parse_args()
    validate(require_manifest=args.require_manifest, base_sha=args.base, head_sha=args.head)
