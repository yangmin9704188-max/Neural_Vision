"""Atomic file I/O utilities. Ensures no partial final file on disk."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def atomic_save_json(path: Path, obj: Any, *, indent: int = 2) -> None:
    """
    Write JSON atomically: temp file -> flush+fsync -> os.replace.
    Never produces partial final file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f"{path.name}.tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)
