import unittest
import subprocess
import sys
import json
import shutil
import tempfile
from pathlib import Path
import os

# Locate tools and fixtures
PROJECT_ROOT = Path(__file__).parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
INVALID_MESH = FIXTURES_DIR / "invalid_mesh.obj"

class TestHardGateFlags(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def test_invalid_face_determinism(self):
        """Test that invalid_mesh logic is deterministic."""
        meta_1 = self.test_dir / "meta_1.json"
        meta_2 = self.test_dir / "meta_2.json"
        
        cmd = [sys.executable, str(TOOLS_DIR / "garment_proxy_meta.py"), "--mesh", str(INVALID_MESH)]
        
        # Run 1
        subprocess.check_call(cmd + ["--out", str(meta_1)])
        # Run 2
        subprocess.check_call(cmd + ["--out", str(meta_2)])
        
        with open(meta_1, 'r') as f1, open(meta_2, 'r') as f2:
            data1 = json.load(f1)
            data2 = json.load(f2)
            
        # Check Identity
        self.assertEqual(data1, data2, "Meta JSON should be identical deterministically")
        
        # Check Content (expect invalid faces)
        self.assertTrue(data1['flags']['invalid_face_flag'], "Should have invalid_face_flag=True for fixture")
        self.assertGreater(data1['mesh_stats']['invalid_face_count'], 0, "Should have invalid faces count > 0")

    def test_hard_gate_bundle_outputs_exist(self):
        """Test that bundle tool exits with 1 on invalid mesh but produces outputs."""
        out_dir = self.test_dir / "bundle_out"
        out_dir.mkdir()
        
        cmd = [
            sys.executable, str(TOOLS_DIR / "garment_generate_bundle.py"),
            "--mesh", str(INVALID_MESH),
            "--out_dir", str(out_dir),
            "--schema", str(PROJECT_ROOT / "contracts" / "geometry_manifest.schema.json") # Assumption, handled if not found by warning?
            # Actually, we rely on the tool defaults or relative paths. 
            # We assume geometry_manifest.schema.json is effectively found or we need to point to it?
            # The tool `garment_generate_bundle` re-routes to `garment_manifest.py`.
            # Let's just pass a dummy schema path if we only care about existence, 
            # OR better, if validation fails, manifest tool exits 1?
            # Wait, if manifest tool exits 1, bundle tool exits 1.
            # But we want bundle tool to exit 1 DUE TO HARD GATE, not validation failure.
            # So Manifest validation MUST PASS.
        ]
        
        # We need a valid schema for manifest validation to pass.
        # Let's see if we can locate one or mock one?
        # In this env, `contracts/geometry_manifest.schema.json` might not verify cleanly if we don't have it.
        # But previous step 1-min said "Step 1-min complete", implying validation works.
        # Let's hope it defaults correctly or we pass a valid path.
        # If the user env doesn't have the schema file at expected place, validation fails.
        # For this test, let's create a minimal schema to ensure validation passes, 
        # so we can test the HARD GATE exit code specifically.
        
        dummy_schema = self.test_dir / "schema.json"
        with open(dummy_schema, 'w') as f:
            json.dump({"type": "object", "properties": {"module": {"type": "string"}}}, f) # Minimal loose schema
            
        cmd = [
            sys.executable, str(TOOLS_DIR / "garment_generate_bundle.py"),
            "--mesh", str(INVALID_MESH),
            "--out_dir", str(out_dir),
            "--schema", str(dummy_schema)
        ]

        # Expect Exit Code 1
        try:
            subprocess.check_call(cmd)
            self.fail("Bundle should exit with code 1 for invalid mesh")
        except subprocess.CalledProcessError as e:
            self.assertEqual(e.returncode, 1, "Exit code should be 1")
            
        # Check Artifacts Existence
        self.assertTrue((out_dir / "garment_proxy_meta.json").exists(), "Meta should exist despite hard gate")
        self.assertTrue((out_dir / "geometry_manifest.json").exists(), "Manifest should exist despite hard gate")
        
        # Check Meta Content
        with open(out_dir / "garment_proxy_meta.json") as f:
            data = json.load(f)
            self.assertTrue(data['flags']['invalid_face_flag'])

if __name__ == "__main__":
    unittest.main()
