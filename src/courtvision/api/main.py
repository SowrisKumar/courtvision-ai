"""CourtVision API.

Run locally:
    uvicorn courtvision.api.main:app --reload
Interactive docs at http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager
from typing import Annotated

import duckdb
from fastapi import Depends, FastAPI, HTTPException, Query

from courtvision.api.deps import db, rows_to_dicts
from courtvision.config import MODELS_DIR
from courtvision.db.connection import get_connection
from courtvision.metrics.views import build_views
from courtvision.ml import win_probability
from courtvision.ml.similarity import similar_players

DB = Annotated[duckdb.DuckDBPyConnection, Depends(db)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    con = get_connection()
    build_views(con)
    con.close()
    yield


app = FastAPI(
    title="CourtVision AI",
    description="NBA analytics & decision intelligence API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health(con: DB) -> dict:
    seasons = [r[0] for r in con.execute("SELECT DISTINCT season FROM v_team_season ORDER BY season").fetchall()]
    return {"status": "ok", "seasons": seasons}


@app.get("/teams")
def list_teams(
    con: DB,
    season: str | None = Query(None, description="e.g. 2025-26; omit for all seasons"),
) -> list[dict]:
    if season:
        res = con.execute(
            "SELECT * FROM v_team_season WHERE season = ? ORDER BY win_pct DESC", [season]
        )
    else:
        res = con.execute("SELECT * FROM v_team_season ORDER BY season, win_pct DESC")
    return rows_to_dicts(res)


@app.get("/teams/{team_id}")
def team_detail(
    team_id: int,
    con: DB,
) -> dict:
    seasons = rows_to_dicts(
        con.execute("SELECT * FROM v_team_season WHERE team_id = ? ORDER BY season", [team_id])
    )
    if not seasons:
        raise HTTPException(404, f"team {team_id} not found")
    splits = rows_to_dicts(con.execute(
        """
        SELECT season,
               CASE WHEN is_home THEN 'home' ELSE 'away' END AS venue,
               count(*)                                      AS gp,
               sum(CASE WHEN is_win THEN 1 ELSE 0 END)       AS w,
               round(avg(pts), 1)                            AS pts_pg,
               round(avg(plus_minus), 1)                     AS avg_margin
        FROM v_team_game WHERE team_id = ?
        GROUP BY season, is_home ORDER BY season, venue
        """,
        [team_id],
    ))
    return {"seasons": seasons, "home_away_splits": splits}


@app.get("/players")
def list_players(
    con: DB,
    season: str | None = Query(None, description="defaults to the latest ingested season"),
) -> list[dict]:
    """All players with stats in a season: id, name, team. For browse/index UIs."""
    if season is None:
        season = con.execute("SELECT max(season) FROM v_player_season").fetchone()[0]
    res = con.execute(
        "SELECT player_id, player_name, team FROM v_player_season WHERE season = ?",
        [season],
    )
    return rows_to_dicts(res)


@app.get("/players/search")
def search_players(
    con: DB,
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
) -> list[dict]:
    res = con.execute(
        """
        SELECT DISTINCT player_id, player_name,
               max(season) OVER (PARTITION BY player_id) AS latest_season
        FROM v_player_season
        WHERE strip_accents(lower(player_name)) LIKE '%' || strip_accents(lower(?)) || '%'
        ORDER BY latest_season DESC, player_name
        LIMIT ?
        """,
        [q, limit],
    )
    return rows_to_dicts(res)


@app.get("/players/{player_id}")
def player_detail(
    player_id: int,
    con: DB,
) -> dict:
    seasons = rows_to_dicts(
        con.execute(
            "SELECT * FROM v_player_season WHERE player_id = ? ORDER BY season", [player_id]
        )
    )
    if not seasons:
        raise HTTPException(404, f"player {player_id} not found in ingested seasons")
    return {"player_id": player_id, "player_name": seasons[-1]["player_name"], "seasons": seasons}


@app.get("/players/{player_id}/similar")
def player_similar(
    player_id: int,
    con: DB,
    season: str | None = Query(None, description="defaults to the player's latest season"),
    limit: int = Query(5, ge=1, le=20),
) -> dict:
    if season is None:
        row = con.execute(
            "SELECT max(season) FROM v_player_season WHERE player_id = ?", [player_id]
        ).fetchone()
        if row[0] is None:
            raise HTTPException(404, f"player {player_id} not found in ingested seasons")
        season = row[0]
    similar = similar_players(con, player_id, season, limit)
    if similar is None:
        raise HTTPException(
            404,
            f"player {player_id} has no qualified {season} profile "
            "(needs 20+ games and 15+ minutes per game)",
        )
    return {"player_id": player_id, "season": season, "similar": similar}


@app.get("/predict/game")
def predict_game(
    con: DB,
    home_team_id: int = Query(...),
    away_team_id: int = Query(...),
) -> dict:
    loaded = win_probability.load(MODELS_DIR)
    if loaded is None:
        raise HTTPException(503, "win probability model not trained; run scripts/train_win_model.py")
    model, meta = loaded
    home = win_probability.current_form(con, home_team_id)
    away = win_probability.current_form(con, away_team_id)
    if home is None or away is None:
        missing = home_team_id if home is None else away_team_id
        raise HTTPException(404, f"team {missing} has no game logs")
    p = win_probability.predict_matchup(model, home, away)
    return {
        "home": home,
        "away": away,
        "home_win_probability": round(p, 3),
        "model": meta["best_model"],
        "as_of_season": home["season"],
    }


# Whitelist of sortable leaderboard stats -> minimum-minutes filter applied.
LEADERBOARD_STATS = {
    "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg",
    "ts_pct", "efg_pct", "usg_pct", "net_rating", "pie", "fg3a_pg",
}


@app.get("/leaderboards/{stat}")
def leaderboard(
    stat: str,
    con: DB,
    season: str = Query(..., description="e.g. 2025-26"),
    limit: int = Query(10, ge=1, le=100),
    min_gp: int = Query(40, ge=0, description="minimum games played"),
) -> list[dict]:
    if stat not in LEADERBOARD_STATS:
        raise HTTPException(400, f"stat must be one of {sorted(LEADERBOARD_STATS)}")
    res = con.execute(
        f"""
        SELECT player_id, player_name, team, season, gp, min_pg, {stat}
        FROM v_player_season
        WHERE season = ? AND gp >= ?
        ORDER BY {stat} DESC
        LIMIT ?
        """,
        [season, min_gp, limit],
    )
    return rows_to_dicts(res)
