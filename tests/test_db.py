"""Smoke tests for the ingested database. Requires `scripts/ingest.py` to have run."""

import pytest

from courtvision.config import DB_PATH
from courtvision.db.connection import get_connection

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="database not ingested yet")

EXPECTED_TABLES = {
    "teams", "players",
    "team_season_base", "team_season_advanced",
    "player_season_base", "player_season_advanced",
    "game_logs",
}


@pytest.fixture(scope="module")
def con():
    con = get_connection(read_only=True)
    yield con
    con.close()


def test_all_tables_exist(con):
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    assert EXPECTED_TABLES <= tables


def test_thirty_teams(con):
    assert con.execute("SELECT count(*) FROM teams").fetchone()[0] == 30


def test_team_seasons_complete(con):
    rows = con.execute(
        "SELECT SEASON, count(*) FROM team_season_base GROUP BY SEASON"
    ).fetchall()
    assert rows and all(count == 30 for _, count in rows)


def test_game_logs_two_rows_per_game(con):
    bad = con.execute(
        "SELECT GAME_ID FROM game_logs GROUP BY GAME_ID HAVING count(*) != 2"
    ).fetchall()
    assert bad == []


def test_no_null_ratings(con):
    n = con.execute(
        "SELECT count(*) FROM team_season_advanced WHERE OFF_RATING IS NULL OR DEF_RATING IS NULL"
    ).fetchone()[0]
    assert n == 0
