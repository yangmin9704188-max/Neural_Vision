import unittest
import sys
import subprocess
import json
import shutil
import tempfile
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
INVALID_MESH = FIXTURES_DIR / "invalid_mesh.obj"
BUNDLE_TOOL = TOOLS_DIR / "garment_generate_bundle.py"

class TestSmoke2Reproducible(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def run_bundle(self, out_dir):
        # Resolve schema path (sibling repo)
        schema_path = PROJECT_ROOT.parent / "fitting_lab" / "contracts" / "geometry_manifest.schema.json"
        
        cmd = [
            sys.executable, str(BUNDLE_TOOL),
            "--mesh", str(INVALID_MESH),
            "--out_dir", str(out_dir),
            "--schema", str(schema_path)
        ]
        # Expect failures (exit 1) but capture output
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            return 0
        except subprocess.CalledProcessError as e:
            return e.returncode

    def test_reproducibility(self):
        dir1 = self.test_dir / "run1"
        dir2 = self.test_dir / "run2"
        
        # Run 1
        code1 = self.run_bundle(dir1)
        # Run 2
        code2 = self.run_bundle(dir2)
        
        # Check Exit Codes
        self.assertNotEqual(code1, 0, "Run1 should be Hard Gate (non-zero)")
        self.assertNotEqual(code2, 0, "Run2 should be Hard Gate (non-zero)")
        
        # Check Manifest Fingerprint Identity
        man1 = json.loads((dir1 / "geometry_manifest.json").read_text(encoding='utf-8'))
        man2 = json.loads((dir2 / "geometry_manifest.json").read_text(encoding='utf-8'))
        
        self.assertEqual(man1['inputs_fingerprint'], man2['inputs_fingerprint'], 
                         "Fingerprint must be deterministic regardless of out_dir")
                         
        # Check Meta Identity
        meta1 = json.loads((dir1 / "garment_proxy_meta.json").read_text(encoding='utf-8'))
        meta2 = json.loads((dir2 / "garment_proxy_meta.json").read_text(encoding='utf-8'))
        
        # Exclude 'source_mesh_path' if it contains absolute path that might vary? 
        # In this test, mesh path is constant.
        self.assertEqual(meta1['flags'], meta2['flags'])
        self.assertEqual(meta1['metrics'], meta2['metrics'])
        self.assertEqual(meta1['mesh_stats'], meta2['mesh_stats'])

if __name__ == "__main__":
    unittest.main()
