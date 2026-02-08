import json
import os
import sys
from pathlib import Path
from datetime import datetime
import argparse

def update_status_file(lab_root, status_data):
    status_md_path = lab_root / "STATUS.md"
    
    updated_at = status_data.get("updated_at", datetime.now().isoformat())
    s1 = status_data.get("smoke1", {})
    s2 = status_data.get("smoke2", {})
    s3 = status_data.get("smoke3", {})
    overall = status_data.get("overall", "UNKNOWN")
    
    lab_name = lab_root.name.upper().replace("_LAB", "")
    brief_path = f"exports/brief/{lab_name}_WORK_BRIEF.md"

    # Evidence block for Smoke-2
    s2_evidence_str = ""
    if s2.get("evidence"):
        s2_evidence_str = "  <br> **Evidence**:"
        for k, v in s2["evidence"].items():
             # Make path relative to lab root if possible for cleaner display
             try:
                 rel_path = Path(v).relative_to(lab_root)
                 s2_evidence_str += f"<br> - {k}: `{rel_path}`"
             except:
                 s2_evidence_str += f"<br> - {k}: `{v}`"

    block_content = f"""<!-- GENERATED_SMOKE_STATUS_START -->
## U2 Smoke Status
- **Updated**: {updated_at}
- **Overall**: **{overall}**
- **Brief**: [{brief_path}]({brief_path})

| Task | Status | Output Directory |
|------|--------|------------------|
| Smoke-1 | {s1.get('status')} | `{s1.get('out_dir')}` |
| Smoke-2 | {s2.get('status')} | `{s2.get('out_dir')}`{s2_evidence_str} |
| Smoke-3 | {s3.get('status')} | `{s3.get('out_dir')}` |
<!-- GENERATED_SMOKE_STATUS_END -->"""

    if status_md_path.exists():
        with open(status_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = f"# {lab_name} LAB STATUS\n\n<!-- GENERATED_SMOKE_STATUS_START -->\n<!-- GENERATED_SMOKE_STATUS_END -->\n"

    start_marker = "<!-- GENERATED_SMOKE_STATUS_START -->"
    end_marker = "<!-- GENERATED_SMOKE_STATUS_END -->"
    
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    
    if start_idx != -1 and end_idx != -1:
        new_content = content[:start_idx] + block_content + content[end_idx + len(end_marker):]
    else:
        new_content = content + "\n\n" + block_content

    with open(status_md_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"[STATUS] updated: {status_md_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab_root", default=None, help="Specific lab root to update")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    summary_path = repo_root / "exports" / "brief" / "SMOKE_STATUS_SUMMARY.json"
    
    if not summary_path.exists():
        print(f"[STATUS] Error: Summary not found at {summary_path}")
        sys.exit(1)
        
    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    if args.lab_root:
        target_root = Path(args.lab_root)
        if target_root.exists():
             update_status_file(target_root, data)
        else:
             print(f"Error: {target_root} does not exist")
    else:
        # Default behavior: update both known locations
        update_status_file(repo_root, data) # Garment Lab
        
        fitting_lab_path = repo_root.parent / "fitting_lab"
        if fitting_lab_path.exists():
            update_status_file(fitting_lab_path, data)

    # Print Summary
    s1 = data.get("smoke1", {}).get("status")
    s2 = data.get("smoke2", {}).get("status")
    s3 = data.get("smoke3", {}).get("status")
    overall = data.get("overall")
    print(f"smoke1={s1} smoke2={s2} smoke3={s3} overall={overall}")

if __name__ == "__main__":
    main()
