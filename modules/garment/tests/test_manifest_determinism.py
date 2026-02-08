import unittest
import json
import os
import sys
import tempfile
import time
import shutil
import subprocess
from pathlib import Path

# Paths to tools
TOOLS_DIR = Path(__file__).parent.parent / "tools"
GENERATOR_SCRIPT = TOOLS_DIR / "garment_manifest.py"
VALIDATOR_SCRIPT = TOOLS_DIR / "validate_geometry_manifest.py"
CONTRACTS_DIR = Path(__file__).parent.parent.parent / "fitting_lab" / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "geometry_manifest.schema.json"

class TestGarmentManifest(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.manifest_path = Path(self.test_dir) / "manifest.json"
        self.mesh_path = Path(self.test_dir) / "test.obj"
        self.mesh_path.write_text("dummy mesh content")
        self.input_file = Path(self.test_dir) / "input.txt"
        self.input_file.write_text("dummy input content")
        
        # Verify schema exists (if environment is set up as expected)
        # If not, we might need to skip validation tests or mock schema
        self.schema_available = SCHEMA_PATH.exists()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def run_generator(self, extra_args=[]):
        cmd = [
            sys.executable, str(GENERATOR_SCRIPT),
            "--out", str(self.manifest_path),
            "--mesh_path", str(self.mesh_path),
            "--input_file", str(self.input_file)
        ] + extra_args
        
        # We need to handle validation step in generator. 
        # If schema is not in CWD, generator might fail validation if we don't handle it.
        # But wait, generator calls validator. Validator needs schema.
        # Validator default is CWD/geometry_manifest.schema.json.
        # So we should copy schema to CWD or self.test_dir?
        # Or we can just hope validator manual check passes if schema not found? 
        # No, validator errors if schema not found.
        # So we MUST provide schema path to the generator if it supported it, but it doesn't.
        # OR we copy schema to where we run it.
        
        # Trick: generator calls validator. Arguments passed to generator don't include schema.
        # Generator source: `cmd = [sys.executable, str(validator_script), "--manifest", str(out_path)]`
        # It relies on default.
        # We should create a dummy schema in the output directory or CWD?
        # The generator runs validator as subprocess.
        # The validator defaults schema to "geometry_manifest.schema.json".
        # So providing a dummy schema in CWD of the test runner is needed.
        pass

    def test_fingerprint_stable_across_time(self):
        """Test that fingerprint is identical even if run at different times."""
        # We need to make sure validation doesn't fail so we can check the file.
        # Let's create a partial dummy schema in the current directory so validator passes/runs.
        dummy_schema = {
            "required": ["schema_version", "module", "inputs_fingerprint", "artifacts"],
            "properties": {
                "artifacts": {"required": ["mesh_path"]}
            }
        }
        with open("geometry_manifest.schema.json", "w") as f:
            json.dump(dummy_schema, f)

        try:
            # Run 1
            cmd1 = [
                sys.executable, str(GENERATOR_SCRIPT),
                "--out", str(self.manifest_path),
                "--mesh_path", str(self.mesh_path),
                "--input_file", str(self.input_file),
                "--warnings_created_at" # Add timestamp to warnings
            ]
            subprocess.check_call(cmd1)
            
            with open(self.manifest_path) as f:
                data1 = json.load(f)
                
            # Wait a bit to ensure time changes
            time.sleep(1.1)
            
            # Run 2
            manifest2 = Path(self.test_dir) / "manifest2.json"
            cmd2 = [
                sys.executable, str(GENERATOR_SCRIPT),
                "--out", str(manifest2),
                "--mesh_path", str(self.mesh_path),
                "--input_file", str(self.input_file),
                "--warnings_created_at"
            ]
            subprocess.check_call(cmd2)
            
            with open(manifest2) as f:
                data2 = json.load(f)
                
            # Assert fingerprints match
            self.assertEqual(data1['inputs_fingerprint'], data2['inputs_fingerprint'],
                             "Fingerprint should be stable across time")
            
            # Assert warnings differ (because of timestamp)
            # Assuming format "CREATED_AT:..."
            # Wait, if logic is correct, warnings don't affect fingerprint calculation.
            self.assertNotEqual(data1.get('warnings'), data2.get('warnings'),
                                "Warnings should differ due to timestamp")
            
        finally:
            if os.path.exists("geometry_manifest.schema.json"):
                os.remove("geometry_manifest.schema.json")

    def test_fingerprint_changes_on_input(self):
        """Test that fingerprint changes when input file content changes."""
        dummy_schema = {
             "required": ["schema_version", "module", "inputs_fingerprint", "artifacts"],
             "properties": {
                 "artifacts": {"required": ["mesh_path"]}
             }
        }
        with open("geometry_manifest.schema.json", "w") as f:
            json.dump(dummy_schema, f)
            
        try:
            # Run 1
            cmd1 = [
                sys.executable, str(GENERATOR_SCRIPT),
                "--out", str(self.manifest_path),
                "--mesh_path", str(self.mesh_path),
                "--input_file", str(self.input_file)
            ]
            subprocess.check_call(cmd1)
            with open(self.manifest_path) as f:
                data1 = json.load(f)

            # Change input
            self.input_file.write_text("NEW CONTENT")
            
            # Run 2
            manifest2 = Path(self.test_dir) / "manifest2.json"
            cmd2 = [
                sys.executable, str(GENERATOR_SCRIPT),
                "--out", str(manifest2),
                "--mesh_path", str(self.mesh_path),
                "--input_file", str(self.input_file)
            ]
            subprocess.check_call(cmd2)
            with open(manifest2) as f:
                data2 = json.load(f)
                
            # Assert fingerprints differ
            self.assertNotEqual(data1['inputs_fingerprint'], data2['inputs_fingerprint'],
                                "Fingerprint should change when input content changes")
                                
        finally:
             if os.path.exists("geometry_manifest.schema.json"):
                os.remove("geometry_manifest.schema.json")

if __name__ == "__main__":
    unittest.main()
