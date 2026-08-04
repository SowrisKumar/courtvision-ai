"""Smoke tests for the ingested database. Requires `scripts/ingest.py` to have run."""

import importlib
import tempfile
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from courtvision.config import DATA_DIR, DB_PATH
from courtvision.db.connection import get_connection, upsert_seasons

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


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_path_env_falls_back_to_default(monkeypatch, blank):
    """`.env.example` ships these keys empty; empty must mean "unset", not Path(".").

    Regression: os.environ.get(name, default) returns "" for a key set to "",
    which resolved DB_PATH to the project directory. That directory *exists*, so
    every `DB_PATH.exists()` guard silently passed and DuckDB failed with
    "Is a directory" instead of falling back to the default warehouse.
    """
    monkeypatch.setenv("COURTVISION_DB", blank)
    monkeypatch.setenv("COURTVISION_MODELS", blank)
    config = importlib.reload(importlib.import_module("courtvision.config"))
    try:
        assert config.DB_PATH == DATA_DIR / "courtvision.duckdb"
        assert config.MODELS_DIR == DATA_DIR / "models"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_upsert_is_column_name_matched():
    """A reordered source frame must not shift values into neighbouring columns."""
    path = Path(tempfile.mkdtemp(prefix="courtvision-upsert-")) / "t.duckdb"
    con = duckdb.connect(str(path))
    try:
        upsert_seasons(con, "t", pd.DataFrame({"SEASON": ["2023-24"], "A": [1], "B": [2]}))
        # same columns, different order: BY NAME must still land A=8, B=9
        upsert_seasons(con, "t", pd.DataFrame({"SEASON": ["2024-25"], "B": [9], "A": [8]}))
        assert con.execute("SELECT SEASON, A, B FROM t ORDER BY SEASON").fetchall() == [
            ("2023-24", 1, 2),
            ("2024-25", 8, 9),
        ]
    finally:
        con.close()
