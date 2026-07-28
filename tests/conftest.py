"""Test bootstrap: fall back to a synthetic warehouse when the real one is absent.

This runs at conftest import time — before any test module imports
`courtvision.config` — so the COURTVISION_DB override is seen everywhere.
Local runs against an ingested data/courtvision.duckdb are unaffected.
"""

import os
import tempfile
from pathlib import Path

_REAL_DB = Path(__file__).resolve().parents[1] / "data" / "courtvision.duckdb"

if not _REAL_DB.exists() and "COURTVISION_DB" not in os.environ:
    _synth_path = Path(tempfile.mkdtemp(prefix="courtvision-test-")) / "synth.duckdb"
    os.environ["COURTVISION_DB"] = str(_synth_path)
    from synth import build_synthetic_db

    build_synthetic_db(_synth_path)
