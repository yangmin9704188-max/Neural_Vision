import pytest
import subprocess
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
E2E_SCRIPT = PROJECT_ROOT / "scripts" / "run_e2e_smoke2.ps1"

def is_powershell_available():
    return shutil.which("powershell") is not None

@pytest.mark.skipif(not is_powershell_available(), reason="PowerShell not found")
def test_e2e_smoke2_pipeline():
    """
    Executes the End-to-End Smoke-2 pipeline script.
    The script itself handles generating the garment output,
    running the fitting stub, and verifying the JSON content.
    We just need to check the exit code.
    """
    if not E2E_SCRIPT.exists():
        pytest.fail(f"E2E script not found at {E2E_SCRIPT}")

    # Use run_command style execution
    cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(E2E_SCRIPT)]
    
    # Run synchronously
    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True
    )
    
    # Print output for debugging if it fails
    if result.returncode != 0:
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        
    assert result.returncode == 0, f"E2E Pipeline failed with exit code {result.returncode}"
