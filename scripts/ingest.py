"""Run the ingestion pipeline: fetch from stats.nba.com and load into DuckDB.

Usage:
    python scripts/ingest.py                 # default seasons from config
    python scripts/ingest.py 2025-26         # specific season(s)
"""

import logging
import sys

import pandas as pd

from courtvision.config import DEFAULT_SEASONS
from courtvision.db.connection import get_connection, load_dataframe
from courtvision.ingestion import nba

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ingest")


def main(seasons: list[str]) -> None:
    con = get_connection()

    n = load_dataframe(con, "teams", nba.fetch_teams())
    log.info("teams: %d rows", n)
    n = load_dataframe(con, "players", nba.fetch_players())
    log.info("players: %d rows", n)

    loads: dict[str, list[pd.DataFrame]] = {
        "team_season_base": [], "team_season_advanced": [],
        "player_season_base": [], "player_season_advanced": [],
        "game_logs": [],
    }
    for season in seasons:
        log.info("fetching season %s ...", season)
        loads["team_season_base"].append(nba.fetch_team_season_stats(season, "Base"))
        loads["team_season_advanced"].append(nba.fetch_team_season_stats(season, "Advanced"))
        loads["player_season_base"].append(nba.fetch_player_season_stats(season, "Base"))
        loads["player_season_advanced"].append(nba.fetch_player_season_stats(season, "Advanced"))
        loads["game_logs"].append(nba.fetch_game_log(season))

    for table, frames in loads.items():
        n = load_dataframe(con, table, pd.concat(frames, ignore_index=True))
        log.info("%s: %d rows", table, n)

    con.close()
    log.info("done")


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT_SEASONS)
