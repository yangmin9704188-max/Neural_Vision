"""
Purpose: Centralized path constants for ingest pipeline.
Inputs: N/A
Outputs: N/A
Status: active
"""
from pathlib import Path
from datetime import datetime

# Repo root (ingest -> pipeline -> src -> body -> modules -> repo)
_PROJECT_ROOT = Path(__file__).resolve().parents[5]
PROJECT_ROOT = _PROJECT_ROOT

# External raw data (junction: data/external/sizekorea_raw)
EXTERNAL_RAW_DIR = PROJECT_ROOT / "data" / "external" / "sizekorea_raw"
EXTERNAL_7TH_CSV = EXTERNAL_RAW_DIR / "7th_data.csv"
EXTERNAL_8TH_3D_CSV = EXTERNAL_RAW_DIR / "8th_data_3d.csv"
EXTERNAL_8TH_DIRECT_CSV = EXTERNAL_RAW_DIR / "8th_data_direct.csv"

# Derived outputs
DERIVED_CURATED_DIR = PROJECT_ROOT / "data" / "derived" / "curated_v0"

# Mapping (canonical in contracts)
DEFAULT_MAPPING = PROJECT_ROOT / "contracts" / "measurement" / "coverage" / "sizekorea_v2.json"


def ensure_dir(p: Path) -> Path:
    """Ensure directory exists, return path."""
    p.mkdir(parents=True, exist_ok=True)
    return p


def now_run_id() -> str:
    """Return RUN_ID: YYYYMMDD_HHMMSS."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")
