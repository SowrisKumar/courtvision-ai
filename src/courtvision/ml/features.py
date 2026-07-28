"""Feature engineering SQL for the ML models.

All features are point-in-time: every window uses only games *before* the one
being predicted (ROWS BETWEEN ... AND 1 PRECEDING), so training never leaks
the outcome of the game itself.
"""

# Per team-game rolling form, computed from v_team_game.
TEAM_FORM_SQL = """
    SELECT
        game_id, season, game_date, team_id, team, is_home, is_win,
        row_number() OVER w                                  AS game_num,
        avg(CASE WHEN is_win THEN 1.0 ELSE 0.0 END)
            OVER (w ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING) AS form_win_pct,
        avg(plus_minus)
            OVER (w ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING) AS form_margin,
        avg(CASE WHEN is_win THEN 1.0 ELSE 0.0 END)
            OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS season_win_pct,
        coalesce(date_diff('day',
            lag(game_date) OVER w, game_date), 3)            AS rest_days
    FROM v_team_game
    WINDOW w AS (PARTITION BY team_id, season ORDER BY game_date, game_id)
"""

# One row per game: home-team features vs away-team features + the label.
# Games where either side has played < 6 games are dropped (unstable form).
GAME_DATASET_SQL = f"""
    WITH form AS ({TEAM_FORM_SQL})
    SELECT
        h.game_id, h.season, h.game_date,
        h.team_id  AS home_team_id, h.team AS home_team,
        a.team_id  AS away_team_id, a.team AS away_team,
        h.form_win_pct   AS home_form_win_pct,
        a.form_win_pct   AS away_form_win_pct,
        h.form_margin    AS home_form_margin,
        a.form_margin    AS away_form_margin,
        h.season_win_pct AS home_season_win_pct,
        a.season_win_pct AS away_season_win_pct,
        least(h.rest_days, 7)  AS home_rest_days,
        least(a.rest_days, 7)  AS away_rest_days,
        CAST(h.is_win AS INT)  AS home_win
    FROM form h
    JOIN form a ON a.game_id = h.game_id AND a.team_id != h.team_id
    WHERE h.is_home AND NOT a.is_home
      AND h.game_num >= 6 AND a.game_num >= 6
    ORDER BY h.game_date, h.game_id
"""

WIN_PROB_FEATURES = [
    "home_form_win_pct", "away_form_win_pct",
    "home_form_margin", "away_form_margin",
    "home_season_win_pct", "away_season_win_pct",
    "home_rest_days", "away_rest_days",
]

# Standardized per-season profile used by the similarity engine.
SIMILARITY_FEATURES = [
    "min_pg", "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg", "tov_pg",
    "fg3a_pg", "fg_pct", "fg3_pct", "ft_pct",
    "ts_pct", "usg_pct", "ast_pct", "reb_pct",
]
