"""Central configuration: paths, seasons, and API settings."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "courtvision.duckdb"

# Seasons ingested by default (nba_api season format).
DEFAULT_SEASONS = ["2023-24", "2024-25", "2025-26"]

# stats.nba.com is unofficial and rate-limited; be a polite client.
API_TIMEOUT_SECONDS = 30
API_SLEEP_SECONDS = 1.0
API_MAX_RETRIES = 3
