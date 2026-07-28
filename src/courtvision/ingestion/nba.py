"""Fetchers for stats.nba.com via nba_api.

Every live-endpoint call goes through `_fetch`, which applies the timeout,
retry, and politeness-sleep settings from config. stats.nba.com is unofficial:
expect occasional timeouts, and never hammer it in a tight loop.
"""

import logging
import time

import pandas as pd
from nba_api.stats.endpoints import (
    commonteamroster,
    leaguedashplayerstats,
    leaguedashteamstats,
    leaguegamelog,
)
from nba_api.stats.static import players as static_players
from nba_api.stats.static import teams as static_teams

from courtvision.config import API_MAX_RETRIES, API_SLEEP_SECONDS, API_TIMEOUT_SECONDS

log = logging.getLogger(__name__)


def _fetch(endpoint_cls, **kwargs) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            result = endpoint_cls(timeout=API_TIMEOUT_SECONDS, **kwargs)
            df = result.get_data_frames()[0]
            time.sleep(API_SLEEP_SECONDS)
            return df
        except Exception as exc:  # nba_api raises bare Exception subclasses on HTTP issues
            last_error = exc
            log.warning(
                "%s attempt %d/%d failed: %s",
                endpoint_cls.__name__, attempt, API_MAX_RETRIES, exc,
            )
            time.sleep(API_SLEEP_SECONDS * attempt * 2)
    raise RuntimeError(f"{endpoint_cls.__name__} failed after {API_MAX_RETRIES} attempts") from last_error


def fetch_teams() -> pd.DataFrame:
    return pd.DataFrame(static_teams.get_teams())


def fetch_players() -> pd.DataFrame:
    return pd.DataFrame(static_players.get_players())


def fetch_team_season_stats(season: str, measure_type: str = "Base") -> pd.DataFrame:
    """League-wide per-team stats. measure_type: 'Base' or 'Advanced'."""
    df = _fetch(
        leaguedashteamstats.LeagueDashTeamStats,
        season=season,
        measure_type_detailed_defense=measure_type,
    )
    df["SEASON"] = season
    return df


def fetch_player_season_stats(season: str, measure_type: str = "Base") -> pd.DataFrame:
    """League-wide per-player stats. measure_type: 'Base' or 'Advanced'."""
    df = _fetch(
        leaguedashplayerstats.LeagueDashPlayerStats,
        season=season,
        measure_type_detailed_defense=measure_type,
    )
    df["SEASON"] = season
    return df


def fetch_game_log(season: str) -> pd.DataFrame:
    """One row per team per game for the season (team box scores)."""
    df = _fetch(leaguegamelog.LeagueGameLog, season=season)
    df["SEASON"] = season
    return df


def fetch_team_roster(team_id: int, season: str) -> pd.DataFrame:
    df = _fetch(commonteamroster.CommonTeamRoster, team_id=team_id, season=season)
    df["SEASON"] = season
    return df
