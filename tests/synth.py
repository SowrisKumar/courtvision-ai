"""Build a small synthetic warehouse for running tests without the real database.

Used by CI, where stats.nba.com is unreachable (and shouldn't be a test
dependency anyway). The data is fake but structurally faithful: 30 real teams,
3 seasons, a full 82-game schedule per team (41 home / 41 away, two rows per
game), and a player pool seeded with real star names whose crafted stats keep
the ground-truth API tests meaningful (Luka Dončić leads 2023-24 scoring,
Nikola Jokić posts elite true-shooting every season).
"""

from pathlib import Path

import duckdb
import pandas as pd
from nba_api.stats.static import teams as static_teams

SEASONS = ["2023-24", "2024-25", "2025-26"]

STARS = [
    # (player_id, name, team abbr, pts_pg target)
    (1629029, "Luka Dončić", "LAL", 33.9),
    (203999, "Nikola Jokić", "DEN", 26.4),
    (1628983, "Shai Gilgeous-Alexander", "OKC", 30.1),
]


def _team_tables(teams: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_rows, adv_rows = [], []
    for season in SEASONS:
        for rank, t in enumerate(teams):
            w = 60 - rank  # spread of records, no ties
            base_rows.append({
                "TEAM_ID": t["id"], "TEAM_NAME": t["full_name"], "GP": 82,
                "W": w, "L": 82 - w, "W_PCT": round(w / 82, 3),
                "PTS": 9000 + 20 * rank, "REB": 3600, "AST": 2200, "TOV": 1100,
                "SEASON": season,
            })
            adv_rows.append({
                "TEAM_ID": t["id"], "OFF_RATING": 120.0 - 0.3 * rank,
                "DEF_RATING": 108.0 + 0.2 * rank,
                "NET_RATING": round(12.0 - 0.5 * rank, 1), "PACE": 99.0,
                "EFG_PCT": 0.55, "TS_PCT": 0.58, "OREB_PCT": 0.28,
                "DREB_PCT": 0.72, "REB_PCT": 0.50, "TM_TOV_PCT": 0.13,
                "AST_PCT": 0.62, "PIE": 0.5, "SEASON": season,
            })
    return pd.DataFrame(base_rows), pd.DataFrame(adv_rows)


def _player_tables(teams: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    star_ids = {s[0] for s in STARS}
    abbr_to_id = {t["abbreviation"]: t["id"] for t in teams}
    roster = list(STARS) + [
        (900000 + i, f"Synth Player {i}", teams[i % 30]["abbreviation"], 22.0 - 0.5 * i)
        for i in range(25)
    ]
    base_rows, adv_rows = [], []
    for season in SEASONS:
        for pid, name, abbr, pts_pg in roster:
            gp = 70
            # Luka must lead 2023-24 scoring; give others a small dip that season.
            pts = (pts_pg if (pid == 1629029 or season != "2023-24") else pts_pg - 1.0) * gp
            base_rows.append({
                "PLAYER_ID": pid, "PLAYER_NAME": name,
                "TEAM_ID": abbr_to_id[abbr], "TEAM_ABBREVIATION": abbr,
                "AGE": 27, "GP": gp, "W_PCT": 0.6, "MIN": 34.0 * gp,
                "PTS": pts, "REB": 6.0 * gp, "AST": 5.0 * gp,
                "STL": 1.0 * gp, "BLK": 0.6 * gp, "TOV": 2.5 * gp,
                "FG_PCT": 0.48, "FG3_PCT": 0.37, "FT_PCT": 0.8,
                "FG3A": 6.0 * gp, "TEAM_COUNT": 1, "SEASON": season,
            })
            adv_rows.append({
                "PLAYER_ID": pid, "TEAM_ID": abbr_to_id[abbr], "SEASON": season,
                "TS_PCT": 0.66 if pid in star_ids else 0.56,
                "EFG_PCT": 0.55, "USG_PCT": 0.25, "OFF_RATING": 116.0,
                "DEF_RATING": 112.0, "NET_RATING": 4.0, "AST_PCT": 0.25,
                "REB_PCT": 0.10, "PIE": 0.12,
            })
    return pd.DataFrame(base_rows), pd.DataFrame(adv_rows)


def _game_logs(teams: list[dict]) -> pd.DataFrame:
    """82 games per team per season: 41 home / 41 away, 2 rows per GAME_ID.

    Schedule construction: every ordered pair (home, away) once = 58 games per
    team (29 home, 29 away); then 12 rotation slates where team i hosts team
    (i + offset) % 30, each adding 1 home + 1 away game per team.
    """
    n = len(teams)
    rows = []
    for si, season in enumerate(SEASONS):
        pairs = [(h, a) for h in range(n) for a in range(n) if h != a]
        pairs += [(i, (i + off) % n) for off in range(1, 13) for i in range(n)]
        for g, (h, a) in enumerate(pairs):
            game_id = f"0{si}2{g:05d}"
            date = pd.Timestamp("2023-10-24") + pd.Timedelta(days=si * 365 + g % 170)
            home_wins = h < a  # deterministic, arbitrary
            for team_idx, opp_idx, is_home in ((h, a, True), (a, h, False)):
                t, o = teams[team_idx], teams[opp_idx]
                sep = " vs. " if is_home else " @ "
                win = home_wins == is_home
                rows.append({
                    "GAME_ID": game_id, "SEASON": season,
                    "GAME_DATE": date.strftime("%Y-%m-%d"),
                    "TEAM_ID": t["id"], "TEAM_ABBREVIATION": t["abbreviation"],
                    "MATCHUP": f"{t['abbreviation']}{sep}{o['abbreviation']}",
                    "WL": "W" if win else "L",
                    "PTS": 115 if win else 105, "PLUS_MINUS": 10 if win else -10,
                    "FG_PCT": 0.48, "FG3M": 13, "REB": 44, "AST": 26, "TOV": 13,
                })
    return pd.DataFrame(rows)


def build_synthetic_db(path: Path) -> None:
    teams = sorted(static_teams.get_teams(), key=lambda t: t["id"])
    team_base, team_adv = _team_tables(teams)
    player_base, player_adv = _player_tables(teams)
    frames = {
        "teams": pd.DataFrame(teams),
        "players": pd.DataFrame(
            [{"id": pid, "full_name": name, "is_active": True} for pid, name, *_ in STARS]
        ),
        "team_season_base": team_base,
        "team_season_advanced": team_adv,
        "player_season_base": player_base,
        "player_season_advanced": player_adv,
        "game_logs": _game_logs(teams),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    for name, df in frames.items():
        con.register("_incoming", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _incoming")
        con.unregister("_incoming")
    con.close()
