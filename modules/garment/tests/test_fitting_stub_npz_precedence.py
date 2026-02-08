import unittest
import sys
import subprocess
import json
import shutil
import tempfile
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
STUB_TOOL = PROJECT_ROOT / "tools" / "gen_fitting_facts_summary_stub.py"

class TestFittingStubNpzPrecedence(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_npz_precedence(self):
        """
        Verify that if 'garment_proxy.npz' exists, 
        'garment_input_path_used' is set to 'npz', 
        even if 'garment_proxy_mesh.glb' also exists.
        """
        meta_path = self.test_dir / "garment_proxy_meta.json"
        
        # 1. Create Meta (Hard Gate triggered)
        meta_data = {
            "schema_version": "garment_proxy_meta.v1",
            "flags": {
                "invalid_face_flag": True
            }
        }
        with open(meta_path, 'w') as f:
            json.dump(meta_data, f)
            
        # 2. Create Dummy Assets
        # Create BOTH npz and glb to test precedence
        (self.test_dir / "garment_proxy.npz").touch()
        (self.test_dir / "garment_proxy_mesh.glb").touch()
        
        # 3. Run Stub
        out_summary = self.test_dir / "fitting_facts_summary.json"
        
        cmd = [
            sys.executable, str(STUB_TOOL),
            "--garment_out_dir", str(self.test_dir),
            "--out", str(out_summary)
        ]
        
        subprocess.check_call(cmd)
        
        # 4. Verify Output
        with open(out_summary, 'r') as f:
            data = json.load(f)
            
        self.assertEqual(data["garment_input_path_used"], "npz", 
                         "Should select 'npz' when both npz and glb exist")
        self.assertTrue(data["early_exit"], "Should be early exit due to invalid_face_flag")

    def test_glb_fallback(self):
        """
        Verify that if only 'garment_proxy_mesh.glb' exists (no npz),
        'garment_input_path_used' is 'glb_fallback'.
        """
        meta_path = self.test_dir / "garment_proxy_meta.json"
        
        meta_data = {"flags": {"invalid_face_flag": True}}
        with open(meta_path, 'w') as f:
            json.dump(meta_data, f)
            
        # Create ONLY glb
        (self.test_dir / "garment_proxy_mesh.glb").touch()
        if (self.test_dir / "garment_proxy.npz").exists():
             (self.test_dir / "garment_proxy.npz").unlink()
        
        out_summary = self.test_dir / "fitting_facts_summary.json"
        
        cmd = [
            sys.executable, str(STUB_TOOL),
            "--garment_out_dir", str(self.test_dir),
            "--out", str(out_summary)
        ]
        
        subprocess.check_call(cmd)
        
        with open(out_summary, 'r') as f:
            data = json.load(f)
            
        self.assertEqual(data["garment_input_path_used"], "glb_fallback", 
                         "Should select 'glb_fallback' when no npz exists")

if __name__ == "__main__":
    unittest.main()
