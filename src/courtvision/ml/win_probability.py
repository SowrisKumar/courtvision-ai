"""Pregame win probability model.

Predicts P(home team wins) from point-in-time form features (rolling last-10
win% and margin, season-to-date win%, rest days). Two candidates are trained —
logistic regression and histogram gradient boosting — and the one with the
better held-out log loss is saved.
"""

import json
import logging
from pathlib import Path

import duckdb
import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from courtvision.ml.features import CARRYOVER_FEATURES, GAME_DATASET_SQL, WIN_PROB_FEATURES

log = logging.getLogger(__name__)

MODEL_FILE = "win_probability.joblib"
META_FILE = "win_probability.json"


def build_dataset(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute(GAME_DATASET_SQL).df()
    # Seasons with no prior season in the warehouse have NULL carryover; fill
    # with the mean so the columns are always usable as features.
    for col in CARRYOVER_FEATURES:
        df[col] = df[col].fillna(df[col].mean())
    return df


def train(
    con: duckdb.DuckDBPyConnection,
    model_dir: Path,
    test_season: str | None = None,
) -> dict:
    """Train, evaluate on `test_season` (default: latest), save best model.

    Returns the evaluation metrics dict (also written next to the model).
    """
    df = build_dataset(con)
    seasons = sorted(df["season"].unique())
    if len(seasons) < 2:
        raise ValueError(
            "training needs at least 2 ingested seasons (one to train on, one held "
            f"out to evaluate); the warehouse has {len(seasons)}: {seasons}. "
            "Run scripts/ingest.py for more seasons."
        )
    test_season = test_season or seasons[-1]
    if test_season not in seasons:
        raise ValueError(f"test season {test_season!r} is not in the warehouse; have {seasons}")

    train_df = df[df["season"] != test_season]
    test_df = df[df["season"] == test_season]

    X_tr, y_tr = train_df[WIN_PROB_FEATURES], train_df["home_win"]
    X_te, y_te = test_df[WIN_PROB_FEATURES], test_df["home_win"]
    if y_te.nunique() < 2:
        raise ValueError(
            f"test season {test_season} has only one outcome class; "
            "AUC and log loss are undefined. Pick a different test season."
        )

    candidates = {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_depth=3, learning_rate=0.05, max_iter=300, random_state=0
        ),
    }

    results = {}
    for name, model in candidates.items():
        model.fit(X_tr, y_tr)
        proba = model.predict_proba(X_te)[:, 1]
        results[name] = {
            "model": model,
            "log_loss": log_loss(y_te, proba),
            "auc": roc_auc_score(y_te, proba),
            "accuracy": accuracy_score(y_te, proba >= 0.5),
        }

    best_name = min(results, key=lambda n: results[n]["log_loss"])
    best = results[best_name]

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(best["model"], model_dir / MODEL_FILE)
    meta = {
        "best_model": best_name,
        "test_season": test_season,
        "n_train": len(train_df),
        "n_test": len(test_df),
        "home_win_baseline_accuracy": float(y_te.mean()),
        "features": WIN_PROB_FEATURES,
        "candidates": {
            n: {k: round(float(v), 4) for k, v in r.items() if k != "model"}
            for n, r in results.items()
        },
    }
    (model_dir / META_FILE).write_text(json.dumps(meta, indent=2))
    log.info("saved %s (log_loss=%.4f auc=%.4f)", best_name, best["log_loss"], best["auc"])
    return meta


def load(model_dir: Path):
    """(model, metadata) or None if not trained yet."""
    model_path = model_dir / MODEL_FILE
    if not model_path.exists():
        return None
    model = joblib.load(model_path)
    meta = json.loads((model_dir / META_FILE).read_text())
    return model, meta


def current_form(con: duckdb.DuckDBPyConnection, team_id: int) -> dict | None:
    """A team's latest form features (from its most recent ingested season)."""
    row = con.execute(
        """
        SELECT
            team, season,
            avg(CASE WHEN is_win THEN 1.0 ELSE 0.0 END)
                FILTER (WHERE recency <= 10)          AS form_win_pct,
            avg(plus_minus) FILTER (WHERE recency <= 10) AS form_margin,
            avg(CASE WHEN is_win THEN 1.0 ELSE 0.0 END)  AS season_win_pct
        FROM (
            SELECT *, row_number() OVER (ORDER BY game_date DESC, game_id DESC) AS recency
            FROM v_team_game
            WHERE team_id = ?
              AND season = (SELECT max(season) FROM v_team_game WHERE team_id = ?)
        )
        GROUP BY team, season
        """,
        [team_id, team_id],
    ).fetchone()
    if row is None:
        return None
    team, season, form_win_pct, form_margin, season_win_pct = row
    return {
        "team": team,
        "season": season,
        "form_win_pct": round(float(form_win_pct), 3),
        "form_margin": round(float(form_margin), 2),
        "season_win_pct": round(float(season_win_pct), 3),
    }


def predict_matchup(
    model,
    home: dict,
    away: dict,
    home_rest_days: int = 2,
    away_rest_days: int = 2,
) -> float:
    X = pd.DataFrame([{
        "home_form_win_pct": home["form_win_pct"],
        "away_form_win_pct": away["form_win_pct"],
        "home_form_margin": home["form_margin"],
        "away_form_margin": away["form_margin"],
        "home_season_win_pct": home["season_win_pct"],
        "away_season_win_pct": away["season_win_pct"],
        "home_rest_days": min(home_rest_days, 7),
        "away_rest_days": min(away_rest_days, 7),
    }])[WIN_PROB_FEATURES]
    return float(model.predict_proba(X)[0, 1])
