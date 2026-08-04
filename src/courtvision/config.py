"""Central configuration: paths, seasons, and API settings."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


def _env_path(name: str, default: Path) -> Path:
    """Path from `name`, treating blank/whitespace as unset.

    `.env.example` ships these keys with empty values as documentation, so a
    plain `os.environ.get(name, default)` would return "" and resolve to Path(".")
    — a directory that exists, which then defeats every `DB_PATH.exists()` guard
    instead of failing loudly.
    """
    value = (os.environ.get(name) or "").strip()
    return Path(value) if value else default


# COURTVISION_DB overrides the warehouse location (used by CI's synthetic DB).
DB_PATH = _env_path("COURTVISION_DB", DATA_DIR / "courtvision.duckdb")
MODELS_DIR = _env_path("COURTVISION_MODELS", DATA_DIR / "models")

# Seasons ingested by default (nba_api season format). 2022-23 is included so the
# earliest reported season still has a prior season for the roster-carryover
# feature, and so a fresh ingest matches what the UI and docs describe.
DEFAULT_SEASONS = ["2022-23", "2023-24", "2024-25", "2025-26"]

# stats.nba.com is unofficial and rate-limited; be a polite client.
API_TIMEOUT_SECONDS = 30
API_SLEEP_SECONDS = 1.0
API_MAX_RETRIES = 3
