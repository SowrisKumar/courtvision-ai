"""CourtVision AI — NBA analytics & decision intelligence platform."""

from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root before any module reads os.environ, so a
# single file configures API keys and path overrides for every entry point
# (API, scripts, notebook). Real environment variables always win, leaving CI,
# tests, and Docker in control of their own settings. See .env.example.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
