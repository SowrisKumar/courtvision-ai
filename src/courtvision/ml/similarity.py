"""Player similarity engine.

Z-scores each player's per-season statistical profile (volume, efficiency,
usage, playmaking, rebounding) and ranks peers by cosine similarity — i.e.
"who has the most similar *shape* of game", independent of raw magnitude
differences already absorbed by standardization.
"""

import duckdb
import numpy as np

from courtvision.ml.features import SIMILARITY_FEATURES

MIN_GP = 20
MIN_MIN_PG = 15.0


def similar_players(
    con: duckdb.DuckDBPyConnection,
    player_id: int,
    season: str,
    limit: int = 5,
) -> list[dict] | None:
    """Top-`limit` most similar qualified players. None if player not qualified."""
    cols = ", ".join(SIMILARITY_FEATURES)
    df = con.execute(
        f"""
        SELECT player_id, player_name, team, {cols}
        FROM v_player_season
        WHERE season = ? AND gp >= ? AND min_pg >= ?
        """,
        [season, MIN_GP, MIN_MIN_PG],
    ).df()

    ids = df["player_id"].to_numpy()
    if player_id not in ids:
        return None

    X = df[SIMILARITY_FEATURES].to_numpy(dtype=float)
    X = np.nan_to_num(X)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    Z = (X - X.mean(axis=0)) / std

    target = Z[ids == player_id][0]
    norms = np.linalg.norm(Z, axis=1) * np.linalg.norm(target)
    norms[norms == 0] = 1.0
    sims = Z @ target / norms

    order = np.argsort(-sims)
    out = []
    for i in order:
        if ids[i] == player_id:
            continue
        row = df.iloc[i]
        out.append({
            "player_id": int(row["player_id"]),
            "player_name": row["player_name"],
            "team": row["team"],
            "similarity": round(float(sims[i]), 3),
            "pts_pg": float(row["pts_pg"]),
            "reb_pg": float(row["reb_pg"]),
            "ast_pg": float(row["ast_pg"]),
            "ts_pct": float(row["ts_pct"]),
            "usg_pct": float(row["usg_pct"]),
        })
        if len(out) == limit:
            break
    return out
