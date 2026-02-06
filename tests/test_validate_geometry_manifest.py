"""
Validate geometry_manifest.json against v1 schema.
- Temp run_dir with minimal valid manifest -> validate passes.
- Mutate one required field -> validate fails.
Run: python tests/test_validate_geometry_manifest.py
     or: pytest tests/test_validate_geometry_manifest.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _valid_manifest() -> dict:
    return {
        "schema_version": "geometry_manifest.v1",
        "module_name": "body",
        "contract_version": "v0",
        "created_at": "2026-02-05T12:00:00Z",
        "inputs_fingerprint": "sha256:abc123",
        "version_keys": {
            "snapshot_version": "unknown",
            "semantic_version": "unknown",
            "geometry_impl_version": "unknown",
            "dataset_version": "unknown",
        },
        "artifacts": ["facts_summary.json", "body_measurements_subset.json"],
    }


def test_validate_passes_on_valid_manifest() -> None:
    """Temp run_dir with minimal valid manifest -> validate passes (exit 0)."""
    with tempfile.TemporaryDirectory() as d:
        tmp_path = Path(d)
        (tmp_path / "geometry_manifest.json").write_text(
            json.dumps(_valid_manifest(), indent=2), encoding="utf-8"
        )
        (tmp_path / "facts_summary.json").write_text("{}", encoding="utf-8")
        (tmp_path / "body_measurements_subset.json").write_text("{}", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(_repo_root() / "tools" / "validate_geometry_manifest.py"), "--run_dir", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}"


def test_validate_fails_when_required_field_mutated() -> None:
    """Mutate one required field (schema_version) -> validate fails (exit 1)."""
    with tempfile.TemporaryDirectory() as d:
        tmp_path = Path(d)
        manifest = _valid_manifest()
        manifest["schema_version"] = "geometry_manifest.v0"
        (tmp_path / "geometry_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        result = subprocess.run(
            [sys.executable, str(_repo_root() / "tools" / "validate_geometry_manifest.py"), "--run_dir", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stderr: {result.stderr}"


if __name__ == "__main__":
    test_validate_passes_on_valid_manifest()
    test_validate_fails_when_required_field_mutated()
    print("All tests passed.")
