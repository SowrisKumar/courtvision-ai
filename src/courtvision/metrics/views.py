"""Analytics views over the raw ingested tables.

Raw tables mirror the nba_api responses (totals + rank noise). These views are
the clean interface the API and ML layers read: per-game normalization, joined
Base + Advanced stats, and derived flags. Views are cheap in DuckDB — they are
recomputed on read, so re-running ingestion never invalidates them.
"""

import duckdb

VIEWS: dict[str, str] = {
    # One row per player-team-season, per-game stats + advanced metrics.
    "v_player_season": """
        SELECT
            b.PLAYER_ID                        AS player_id,
            b.PLAYER_NAME                      AS player_name,
            b.TEAM_ID                          AS team_id,
            b.TEAM_ABBREVIATION                AS team,
            b.SEASON                           AS season,
            b.AGE                              AS age,
            b.GP                               AS gp,
            b.W_PCT                            AS win_pct,
            round(b.MIN / b.GP, 1)             AS min_pg,
            round(b.PTS / b.GP, 1)             AS pts_pg,
            round(b.REB / b.GP, 1)             AS reb_pg,
            round(b.AST / b.GP, 1)             AS ast_pg,
            round(b.STL / b.GP, 1)             AS stl_pg,
            round(b.BLK / b.GP, 1)             AS blk_pg,
            round(b.TOV / b.GP, 1)             AS tov_pg,
            b.FG_PCT                           AS fg_pct,
            b.FG3_PCT                          AS fg3_pct,
            b.FT_PCT                           AS ft_pct,
            round(b.FG3A / b.GP, 1)            AS fg3a_pg,
            a.TS_PCT                           AS ts_pct,
            a.EFG_PCT                          AS efg_pct,
            a.USG_PCT                          AS usg_pct,
            a.OFF_RATING                       AS off_rating,
            a.DEF_RATING                       AS def_rating,
            a.NET_RATING                       AS net_rating,
            a.AST_PCT                          AS ast_pct,
            a.REB_PCT                          AS reb_pct,
            a.PIE                              AS pie,
            b.TEAM_COUNT                       AS team_count
        FROM player_season_base b
        JOIN player_season_advanced a
          USING (PLAYER_ID, TEAM_ID, SEASON)
        WHERE b.GP > 0
    """,
    # One row per team-season: record, per-game scoring, efficiency profile.
    "v_team_season": """
        SELECT
            b.TEAM_ID                          AS team_id,
            b.TEAM_NAME                        AS team_name,
            t.abbreviation                     AS team,
            b.SEASON                           AS season,
            b.GP                               AS gp,
            b.W                                AS w,
            b.L                                AS l,
            b.W_PCT                            AS win_pct,
            round(b.PTS / b.GP, 1)             AS pts_pg,
            round(b.REB / b.GP, 1)             AS reb_pg,
            round(b.AST / b.GP, 1)             AS ast_pg,
            round(b.TOV / b.GP, 1)             AS tov_pg,
            a.OFF_RATING                       AS off_rating,
            a.DEF_RATING                       AS def_rating,
            a.NET_RATING                       AS net_rating,
            a.PACE                             AS pace,
            a.EFG_PCT                          AS efg_pct,
            a.TS_PCT                           AS ts_pct,
            a.OREB_PCT                         AS oreb_pct,
            a.DREB_PCT                         AS dreb_pct,
            a.REB_PCT                          AS reb_pct,
            a.TM_TOV_PCT                       AS tov_pct,
            a.AST_PCT                          AS ast_pct,
            a.PIE                              AS pie
        FROM team_season_base b
        JOIN team_season_advanced a USING (TEAM_ID, SEASON)
        JOIN teams t ON t.id = b.TEAM_ID
    """,
    # One row per team per game, with home/away and win flags derived from MATCHUP.
    "v_team_game": """
        SELECT
            GAME_ID                            AS game_id,
            SEASON                             AS season,
            CAST(GAME_DATE AS DATE)            AS game_date,
            TEAM_ID                            AS team_id,
            TEAM_ABBREVIATION                  AS team,
            MATCHUP                            AS matchup,
            contains(MATCHUP, ' vs. ')         AS is_home,
            (WL = 'W')                         AS is_win,
            PTS                                AS pts,
            PLUS_MINUS                         AS plus_minus,
            FG_PCT                             AS fg_pct,
            FG3M                               AS fg3m,
            REB                                AS reb,
            AST                                AS ast,
            TOV                                AS tov
        FROM game_logs
    """,
}


def build_views(con: duckdb.DuckDBPyConnection) -> list[str]:
    """(Re)create all analytics views. Returns the view names."""
    for name, sql in VIEWS.items():
        con.execute(f"CREATE OR REPLACE VIEW {name} AS {sql}")
    return list(VIEWS)
