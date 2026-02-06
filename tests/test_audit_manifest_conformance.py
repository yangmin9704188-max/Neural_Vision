"""
Audit geometry_manifest conformance tool tests.
- Temp dirs with minimal valid manifests (body, fitting, garment) -> audit exits 0.
- One invalid manifest -> audit exits 1.
Run: python tests/test_audit_manifest_conformance.py
     or: pytest tests/test_audit_manifest_conformance.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _valid_manifest(module: str) -> dict:
    return {
        "schema_version": "geometry_manifest.v1",
        "module_name": module,
        "contract_version": "v0",
        "created_at": "2026-02-05T12:00:00Z",
        "inputs_fingerprint": "sha256:abc123",
        "version_keys": {
            "snapshot_version": "unknown",
            "semantic_version": "unknown",
            "geometry_impl_version": "unknown",
            "dataset_version": "unknown",
        },
        "artifacts": ["out.json"],
    }


def _write_manifest(dir_path: Path, manifest: dict, artifact_name: str = "out.json") -> None:
    (dir_path / "geometry_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (dir_path / artifact_name).write_text("{}", encoding="utf-8")


def test_audit_passes_when_all_valid() -> None:
    """Three valid manifests (body, fitting, garment) -> exit 0."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        body_dir = root / "body"
        fitting_dir = root / "fitting"
        garment_dir = root / "garment"
        body_dir.mkdir()
        fitting_dir.mkdir()
        garment_dir.mkdir()
        _write_manifest(body_dir, _valid_manifest("body"))
        _write_manifest(fitting_dir, _valid_manifest("fitting"))
        _write_manifest(garment_dir, _valid_manifest("garment"))

        result = subprocess.run(
            [
                sys.executable,
                str(_repo_root() / "tools" / "audit_manifest_conformance.py"),
                "--run_dir_body", str(body_dir),
                "--run_dir_fitting", str(fitting_dir),
                "--run_dir_garment", str(garment_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stdout: {result.stdout} stderr: {result.stderr}"


def test_audit_fails_when_one_invalid() -> None:
    """One invalid manifest (wrong schema_version) -> exit 1."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        body_dir = root / "body"
        fitting_dir = root / "fitting"
        body_dir.mkdir()
        fitting_dir.mkdir()
        _write_manifest(body_dir, _valid_manifest("body"))
        invalid = _valid_manifest("fitting")
        invalid["schema_version"] = "geometry_manifest.v0"
        _write_manifest(fitting_dir, invalid)

        result = subprocess.run(
            [
                sys.executable,
                str(_repo_root() / "tools" / "audit_manifest_conformance.py"),
                "--run_dir_body", str(body_dir),
                "--run_dir_fitting", str(fitting_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stdout: {result.stdout}"


def test_audit_fails_on_path_traversal() -> None:
    """Manifest with '../escape.txt' must exit 1 and report ESCAPES_RUN_DIR."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        body_dir = root / "body"
        body_dir.mkdir()
        manifest = _valid_manifest("body")
        manifest["artifacts"] = ["out.json", "../escape.txt"]
        _write_manifest(body_dir, manifest)

        result = subprocess.run(
            [
                sys.executable,
                str(_repo_root() / "tools" / "audit_manifest_conformance.py"),
                "--run_dir_body", str(body_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stdout: {result.stdout}"
        assert "ESCAPES_RUN_DIR" in result.stdout, f"Expected ESCAPES_RUN_DIR in output. stdout: {result.stdout}"


def test_strict_files_fails_when_artifact_missing() -> None:
    """--strict_files must exit 1 when artifact file does not exist."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        body_dir = root / "body"
        body_dir.mkdir()
        manifest = _valid_manifest("body")
        manifest["artifacts"] = ["nonexistent.json"]
        (body_dir / "geometry_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(_repo_root() / "tools" / "audit_manifest_conformance.py"),
                "--run_dir_body", str(body_dir),
                "--strict_files",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stdout: {result.stdout}"


if __name__ == "__main__":
    test_audit_passes_when_all_valid()
    test_audit_fails_when_one_invalid()
    test_audit_fails_on_path_traversal()
    test_strict_files_fails_when_artifact_missing()
    print("All tests passed.")
