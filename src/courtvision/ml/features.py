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

# Roster continuity per team-season: the share of the team's previous-season
# minutes played by players still on the roster this season. ~0.95 = same team,
# ~0.5 = rebuilt. NULL when the previous season isn't in the warehouse.
# Approximation: a traded player's TEAM_ID is their last team of that season.
ROSTER_CARRYOVER_SQL = """
    WITH pm AS (
        SELECT PLAYER_ID AS player_id, TEAM_ID AS team_id, SEASON AS season, MIN AS minutes
        FROM player_season_base
    ),
    prev AS (
        SELECT *,
            printf('%d-%02d',
                CAST(substr(season, 1, 4) AS INT) + 1,
                (CAST(substr(season, 1, 4) AS INT) + 2) % 100) AS next_season
        FROM pm
    )
    SELECT
        prev.team_id,
        prev.next_season AS season,
        sum(CASE WHEN cur.player_id IS NOT NULL THEN prev.minutes ELSE 0 END)
            / sum(prev.minutes) AS roster_carryover
    FROM prev
    LEFT JOIN pm cur
      ON cur.player_id = prev.player_id
     AND cur.team_id = prev.team_id
     AND cur.season = prev.next_season
    GROUP BY prev.team_id, prev.next_season
"""

# One row per game: home-team features vs away-team features + the label.
# Games where either side has played < 6 games are dropped (unstable form).
GAME_DATASET_SQL = f"""
    WITH form AS ({TEAM_FORM_SQL}),
    carry AS ({ROSTER_CARRYOVER_SQL})
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
        ch.roster_carryover    AS home_roster_carryover,
        ca.roster_carryover    AS away_roster_carryover,
        CAST(h.is_win AS INT)  AS home_win
    FROM form h
    JOIN form a ON a.game_id = h.game_id AND a.team_id != h.team_id
    LEFT JOIN carry ch ON ch.team_id = h.team_id AND ch.season = h.season
    LEFT JOIN carry ca ON ca.team_id = a.team_id AND ca.season = a.season
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

# Candidate features evaluated in the notebook; added to WIN_PROB_FEATURES only
# if they improve held-out metrics.
CARRYOVER_FEATURES = ["home_roster_carryover", "away_roster_carryover"]

# Standardized per-season profile used by the similarity engine.
SIMILARITY_FEATURES = [
    "min_pg", "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg", "tov_pg",
    "fg3a_pg", "fg_pct", "fg3_pct", "ft_pct",
    "ts_pct", "usg_pct", "ast_pct", "reb_pct",
]
