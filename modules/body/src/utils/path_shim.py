"""
Legacy verification path shim. Do not resurrect verification/ tree.
Canonical: data/golden, exports/runs. Legacy verification/* supported via rewrite only.
"""
from pathlib import Path

LEGACY_VERIFICATION_PREFIX = "verification"
CANON_GOLDEN_PREFIX = "data/golden"
CANON_EXPORTS_RUNS_PREFIX = "exports/runs"


def rewrite_legacy_path(p: str) -> str:
    """
    Rewrite legacy verification/* paths to canonical paths.
    - verification/datasets/golden/... -> data/golden/...
    - verification/runs/... -> exports/runs/...
    Input normalized to forward slashes; output uses forward slashes.
    """
    if not p or not str(p).strip():
        return p
    normalized = Path(p).as_posix()
    if normalized.startswith("verification/datasets/golden/"):
        suffix = normalized[len("verification/datasets/golden/"):]
        return CANON_GOLDEN_PREFIX + ("/" if suffix else "") + suffix
    if normalized.startswith("verification/runs/"):
        suffix = normalized[len("verification/runs/"):]
        return CANON_EXPORTS_RUNS_PREFIX + ("/" if suffix else "") + suffix
    return normalized
