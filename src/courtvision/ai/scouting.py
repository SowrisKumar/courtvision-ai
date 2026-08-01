"""AI scouting reports, grounded in structured warehouse data.

The report prompt receives ONLY data we retrieved ourselves (season stats,
trends, league percentiles, similar players) and instructs the model to write
from that data alone -- the opposite of asking an LLM what it remembers about
a player.
"""

import json

import duckdb

from courtvision.ai.assistant import strip_em_dashes
from courtvision.ai.llm import LLMClient
from courtvision.ml.similarity import similar_players

SYSTEM_PROMPT = """
You are an NBA scout writing an internal scouting report. Use ONLY the JSON
data provided by the user. Do not add facts, injuries, draft history, or any
information not present in the data. If something cannot be concluded from the
data, leave it out.

Write in plain text (no markdown headers or tables). Structure, using these
exact section labels on their own lines:
PROFILE: two sentences summarizing role and level.
OFFENSE: scoring volume, efficiency (ts_pct vs league average of 0.57),
shooting profile, playmaking.
REBOUNDING AND DEFENSE: what the data supports, including net/def rating
context; be cautious, box stats capture defense poorly.
TRAJECTORY: how the last seasons trend.
COMPARABLE PLAYERS: one sentence on the statistically similar players listed.
Keep it under 300 words. Do not use em dashes.
""".strip()


def gather_player_data(con: duckdb.DuckDBPyConnection, player_id: int) -> dict | None:
    seasons = con.execute(
        "SELECT * FROM v_player_season WHERE player_id = ? ORDER BY season", [player_id]
    ).df()
    if seasons.empty:
        return None
    latest_season = seasons["season"].iloc[-1]
    league = con.execute(
        """
        SELECT round(avg(pts_pg), 1) AS avg_pts_pg, round(avg(ts_pct), 3) AS avg_ts_pct,
               round(avg(usg_pct), 3) AS avg_usg_pct
        FROM v_player_season WHERE season = ? AND gp >= 40
        """,
        [latest_season],
    ).df()
    similar = similar_players(con, player_id, latest_season, limit=4) or []
    return {
        "player_name": seasons["player_name"].iloc[-1],
        "seasons": json.loads(seasons.to_json(orient="records")),
        "league_averages_latest_season": json.loads(league.to_json(orient="records"))[0],
        "similar_players": [
            {k: s[k] for k in ("player_name", "team", "similarity")} for s in similar
        ],
    }


def scouting_report(con: duckdb.DuckDBPyConnection, llm: LLMClient, player_id: int) -> dict | None:
    data = gather_player_data(con, player_id)
    if data is None:
        return None
    report = llm.complete(
        SYSTEM_PROMPT,
        [{"role": "user", "content": json.dumps(data)}],
    )
    return {
        "player_id": player_id,
        "player_name": data["player_name"],
        "report": strip_em_dashes(report.strip()),
        "grounded_on": {
            "seasons": [s["season"] for s in data["seasons"]],
            "similar_players": [s["player_name"] for s in data["similar_players"]],
        },
    }
