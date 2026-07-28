"""ML layer tests: similarity engine, win probability dataset/model, API endpoints."""

import pytest
from fastapi.testclient import TestClient

from courtvision.config import DB_PATH, MODELS_DIR

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="database not ingested yet")

JOKIC = 203999


# DuckDB refuses to open read-only and write connections to the same file
# concurrently in one process, so ordering matters: the write connection
# (views + training) is opened and closed first, then the API client (whose
# lifespan briefly opens a write connection), then the read-only test handle.


@pytest.fixture(scope="module")
def trained_meta():
    from courtvision.db.connection import get_connection
    from courtvision.metrics.views import build_views
    from courtvision.ml.win_probability import train

    con = get_connection()
    build_views(con)
    meta = train(con, MODELS_DIR)
    con.close()
    return meta


@pytest.fixture(scope="module")
def client(trained_meta):
    from courtvision.api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def con(client):
    from courtvision.db.connection import get_connection

    con = get_connection(read_only=True)
    yield con
    con.close()


def test_similarity_structure(con):
    from courtvision.ml.similarity import similar_players

    sims = similar_players(con, JOKIC, "2025-26", limit=5)
    assert sims is not None and len(sims) == 5
    assert all(s["player_id"] != JOKIC for s in sims)
    scores = [s["similarity"] for s in sims]
    assert scores == sorted(scores, reverse=True)
    assert all(-1.001 <= s <= 1.001 for s in scores)


def test_similarity_unknown_player(con):
    from courtvision.ml.similarity import similar_players

    assert similar_players(con, 42, "2025-26") is None


def test_win_prob_dataset_no_leakage_nulls(con):
    from courtvision.ml.features import WIN_PROB_FEATURES
    from courtvision.ml.win_probability import build_dataset

    df = build_dataset(con)
    assert len(df) > 500
    assert not df[WIN_PROB_FEATURES].isna().any().any()
    assert set(df["home_win"].unique()) <= {0, 1}
    # each game appears exactly once
    assert df["game_id"].is_unique


def test_model_beats_chance(trained_meta):
    best = trained_meta["candidates"][trained_meta["best_model"]]
    assert best["auc"] > 0.55
    assert (MODELS_DIR / "win_probability.joblib").exists()


def test_similar_endpoint(client):
    body = client.get(f"/players/{JOKIC}/similar", params={"limit": 3}).json()
    assert len(body["similar"]) == 3
    assert body["season"]  # defaulted to latest
    assert client.get("/players/42/similar").status_code == 404


def test_predict_endpoint(client, con):
    a, b = con.execute(
        "SELECT DISTINCT team_id FROM v_team_game ORDER BY team_id LIMIT 2"
    ).fetchall()
    body = client.get(
        "/predict/game", params={"home_team_id": a[0], "away_team_id": b[0]}
    ).json()
    assert 0.0 <= body["home_win_probability"] <= 1.0
    assert body["home"]["team"] != body["away"]["team"]
    assert client.get(
        "/predict/game", params={"home_team_id": 1, "away_team_id": 2}
    ).status_code == 404
