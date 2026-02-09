import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PUBLISH_TOOL = REPO_ROOT / "modules" / "garment" / "tools" / "publish_m1.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_manifest() -> dict:
    return {
        "schema_version": "geometry_manifest.v1",
        "module_name": "garment",
        "contract_version": "garment.contract.m0.v1",
        "created_at": "2026-01-01T00:00:00Z",
        "inputs_fingerprint": "f" * 64,
        "version_keys": {
            "snapshot_version": "m0-snapshot-v1",
            "semantic_version": "m0-semantic-v1",
            "geometry_impl_version": "m0-fixture-gen-v1",
            "dataset_version": "m0-dataset-v1",
        },
        "artifacts": ["geometry_manifest.json", "garment_proxy_meta.json"],
    }


class TestPublishM1Tracks(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="publish_m1_tracks_"))
        self.source_dir = self.temp_dir / "source"
        self.shared_root = self.temp_dir / "shared"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        _write_json(self.source_dir / "geometry_manifest.json", _source_manifest())

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_publish(self, run_id: str) -> Path:
        env = os.environ.copy()
        env["NV_SHARED_M1_ROOT"] = str(self.shared_root)
        cmd = [
            sys.executable,
            str(PUBLISH_TOOL),
            "--source-run-dir",
            str(self.source_dir),
            "--run-id",
            run_id,
            "--overwrite",
            "--no-signal-update",
            "--no-progress-event",
        ]
        subprocess.check_call(cmd, cwd=str(REPO_ROOT), env=env)
        return self.shared_root / "garment" / run_id

    def test_g40_g41_outputs_default_thickness_policy(self) -> None:
        _write_json(
            self.source_dir / "garment_proxy_meta.json",
            {
                "schema_version": "garment_proxy_meta.v1",
                "invalid_face_flag": False,
                "negative_face_area_flag": False,
                "self_intersection_flag": False,
                "warnings": [],
            },
        )

        run_dir = self._run_publish("test_run_default")

        self.assertTrue((run_dir / "intake_gatekeeper_metrics.json").is_file())
        self.assertTrue((run_dir / "fit_hint.json").is_file())
        self.assertTrue((run_dir / "latent_meta.json").is_file())

        meta = json.loads((run_dir / "garment_proxy_meta.json").read_text(encoding="utf-8"))
        fit_hint = json.loads((run_dir / "fit_hint.json").read_text(encoding="utf-8"))
        metrics = json.loads((run_dir / "intake_gatekeeper_metrics.json").read_text(encoding="utf-8"))
        manifest = json.loads((run_dir / "geometry_manifest.json").read_text(encoding="utf-8"))

        self.assertIn("foreign_object_result", meta)
        self.assertEqual(meta["foreign_object_result"]["status"], "clear")
        self.assertEqual(fit_hint["thickness_policy"]["default_applied"], True)
        self.assertIn("THICKNESS_DEFAULTED", fit_hint["warnings"])
        self.assertTrue(metrics["required_presence"]["geometry_manifest.json"])
        self.assertIn("fit_hint.json", manifest["artifacts"])
        self.assertIn("latent_meta.json", manifest["artifacts"])
        self.assertIn("intake_gatekeeper_metrics.json", manifest["artifacts"])

    def test_material_policy_applied_without_default_warning(self) -> None:
        _write_json(
            self.source_dir / "garment_proxy_meta.json",
            {
                "schema_version": "garment_proxy_meta.v1",
                "invalid_face_flag": False,
                "negative_face_area_flag": False,
                "self_intersection_flag": False,
                "material_token": "cotton",
                "warnings": [],
            },
        )

        run_dir = self._run_publish("test_run_cotton")
        fit_hint = json.loads((run_dir / "fit_hint.json").read_text(encoding="utf-8"))

        self.assertEqual(fit_hint["stretch_class"], "low")
        self.assertAlmostEqual(fit_hint["thickness_garment_m"], 0.0012, places=7)
        self.assertEqual(fit_hint["thickness_policy"]["default_applied"], False)
        self.assertEqual(fit_hint["warnings"], [])


if __name__ == "__main__":
    unittest.main()
