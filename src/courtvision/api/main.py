"""CourtVision API.

Run locally:
    uvicorn courtvision.api.main:app --reload
Interactive docs at http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager

import duckdb
from fastapi import Depends, FastAPI, HTTPException, Query

from courtvision.api.deps import db, rows_to_dicts
from courtvision.db.connection import get_connection
from courtvision.metrics.views import build_views


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
def health(con: duckdb.DuckDBPyConnection = Depends(db)) -> dict:
    seasons = [r[0] for r in con.execute("SELECT DISTINCT season FROM v_team_season ORDER BY season").fetchall()]
    return {"status": "ok", "seasons": seasons}


@app.get("/teams")
def list_teams(
    season: str | None = Query(None, description="e.g. 2025-26; omit for all seasons"),
    con: duckdb.DuckDBPyConnection = Depends(db),
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
    con: duckdb.DuckDBPyConnection = Depends(db),
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


@app.get("/players/search")
def search_players(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    con: duckdb.DuckDBPyConnection = Depends(db),
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
    con: duckdb.DuckDBPyConnection = Depends(db),
) -> dict:
    seasons = rows_to_dicts(
        con.execute(
            "SELECT * FROM v_player_season WHERE player_id = ? ORDER BY season", [player_id]
        )
    )
    if not seasons:
        raise HTTPException(404, f"player {player_id} not found in ingested seasons")
    return {"player_id": player_id, "player_name": seasons[-1]["player_name"], "seasons": seasons}


# Whitelist of sortable leaderboard stats -> minimum-minutes filter applied.
LEADERBOARD_STATS = {
    "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg",
    "ts_pct", "efg_pct", "usg_pct", "net_rating", "pie", "fg3a_pg",
}


@app.get("/leaderboards/{stat}")
def leaderboard(
    stat: str,
    season: str = Query(..., description="e.g. 2025-26"),
    limit: int = Query(10, ge=1, le=100),
    min_gp: int = Query(40, ge=0, description="minimum games played"),
    con: duckdb.DuckDBPyConnection = Depends(db),
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
