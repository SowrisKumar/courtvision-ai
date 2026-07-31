"""API tests against the ingested database."""

import pytest
from fastapi.testclient import TestClient

from courtvision.config import DB_PATH

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="database not ingested yet")


@pytest.fixture(scope="module")
def client():
    from courtvision.api.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "2025-26" in body["seasons"]


def test_list_teams_season(client):
    teams = client.get("/teams", params={"season": "2025-26"}).json()
    assert len(teams) == 30
    assert teams[0]["win_pct"] >= teams[-1]["win_pct"]
    assert {"off_rating", "def_rating", "pace", "team_name"} <= set(teams[0])


def test_team_detail_and_splits(client):
    all_seasons = client.get("/health").json()["seasons"]
    teams = client.get("/teams", params={"season": "2025-26"}).json()
    team_id = teams[0]["team_id"]
    body = client.get(f"/teams/{team_id}").json()
    assert [s["season"] for s in body["seasons"]] == all_seasons
    splits = body["home_away_splits"]
    assert {(s["season"], s["venue"]) for s in splits} >= {("2025-26", "home"), ("2025-26", "away")}
    for s in splits:
        assert s["gp"] == 41  # 82-game season, half home half away


def test_team_404(client):
    assert client.get("/teams/999999").status_code == 404


def test_player_index(client):
    players = client.get("/players").json()
    assert len(players) > 20
    assert {"player_id", "player_name", "team"} <= set(players[0])
    latest = client.get("/health").json()["seasons"][-1]
    assert players == client.get("/players", params={"season": latest}).json()


def test_player_search_and_detail(client):
    hits = client.get("/players/search", params={"q": "jokic"}).json()
    assert hits and hits[0]["player_name"] == "Nikola Jokić"
    detail = client.get(f"/players/{hits[0]['player_id']}").json()
    assert detail["player_name"] == "Nikola Jokić"
    assert all(s["ts_pct"] > 0.5 for s in detail["seasons"])


def test_leaderboard(client):
    top = client.get(
        "/leaderboards/pts_pg", params={"season": "2023-24", "limit": 5}
    ).json()
    assert len(top) == 5
    assert top[0]["pts_pg"] >= top[1]["pts_pg"]
    assert top[0]["player_name"] == "Luka Dončić"  # 2023-24 scoring champ


def test_leaderboard_rejects_unknown_stat(client):
    assert client.get("/leaderboards/evil; DROP TABLE", params={"season": "2025-26"}).status_code in (400, 404)
    assert client.get("/leaderboards/plus_minus", params={"season": "2025-26"}).status_code == 400
