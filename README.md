# CourtVision AI

[![CI](https://github.com/SowrisKumar/courtvision-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/SowrisKumar/courtvision-ai/actions/workflows/ci.yml)

## What is this?

CourtVision AI is a basketball analytics website, built from scratch as a complete,
working product. It collects real NBA statistics every day from the league's public
stats site, organizes them into a fast local database, and turns them into things a
coach, analyst, or fan can actually use:

- **Explore any team.** See how every team ranks on offense and defense, its full
  standings record, and how it performs at home versus on the road.
- **Explore any player.** Search or browse all current players, view their career
  trends, shooting efficiency, and role, and instantly get a list of the players
  whose style of play is most similar, found by a machine learning model.
- **Check the leaderboards.** Top players in scoring, rebounding, assists, efficiency,
  and more, for any of the last four seasons.
- **Predict any matchup.** Pick two teams and get the home team's win probability,
  estimated by a model trained on thousands of past games and tested honestly on a
  season it had never seen, where it called about two out of three games correctly.

Under the hood it is a full modern data product: an automated data pipeline, an
analytics database, a machine learning layer, a web API, and an interactive dashboard,
each built the way a real engineering team would build them, with automated tests
running on every change. A companion notebook documents the evidence behind every
modeling decision, including the experiments that failed. Planned next: an AI assistant
that answers basketball questions in plain English, backed by this same data.

## Status

**Milestone 5 complete — AI analytics assistant.** The pipeline pulls league-wide team
and player stats (Base + Advanced measure types) and full game logs from stats.nba.com
via [`nba_api`](https://github.com/swar/nba_api) into a local DuckDB warehouse; SQL views
normalize them into clean per-game analytics tables, served by a FastAPI backend.

| Table | Contents |
|---|---|
| `teams`, `players` | Static reference data (30 teams, ~5,100 players) |
| `team_season_base` / `team_season_advanced` | Per-team season stats (ORtg, DRtg, pace, …) |
| `player_season_base` / `player_season_advanced` | Per-player season stats (TS%, usage, …) |
| `game_logs` | Team box score per game (2 rows per game) |

Full table-by-table notes and an entity-relationship diagram: [`data/README.md`](data/README.md).
Default seasons: 2023-24 through 2025-26 (see `src/courtvision/config.py`); 2022-23 is
also ingested for prior-season features.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
python scripts/ingest.py            # ingest default seasons into data/courtvision.duckdb
python scripts/ingest.py 2022-23    # add/refresh specific season(s); others are preserved
python scripts/build_metrics.py     # (re)create the analytics views
python scripts/train_win_model.py   # train the win probability model
pytest                              # test the warehouse + API (uses a synthetic DB if none ingested)
uvicorn courtvision.api.main:app --reload   # serve the API → http://127.0.0.1:8000/docs
```

### Model evidence notebook

[`notebooks/model_evaluation.ipynb`](notebooks/model_evaluation.ipynb) is the executed
evidence file for every ML decision: baselines, 4 candidate model families on a held-out
season, grid-search tuning, calibration, coefficient analysis, and the similarity-metric
comparison (cosine vs Euclidean, z-scored vs raw, PCA check). All numbers regenerate from
the warehouse by re-running the cells.

### Dashboard (frontend/)

React + TypeScript + Tailwind + Recharts, talking to the API through a dev proxy:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (needs the API running on :8000)
```

Pages: **League** (efficiency scatter + standings) · **Players** (search, career
trends, ML-similar players) · **Leaderboards** (any whitelisted stat) · **Predict**
(win probability for any matchup).

### API endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Status + ingested seasons |
| `GET /teams?season=2025-26` | All teams' season profile (record, ratings, pace, four-factor stats) |
| `GET /teams/{team_id}` | Season history + home/away splits |
| `GET /players/search?q=jokic` | Accent-insensitive player name search |
| `GET /players/{player_id}` | Per-season stats: per-game, shooting efficiency, usage, ratings |
| `GET /leaderboards/{stat}?season=&min_gp=` | Top players by any whitelisted stat (`pts_pg`, `ts_pct`, `pie`, …) |
| `GET /players/{id}/similar?season=` | ML similarity engine: statistically closest players (z-scored profile, cosine) |
| `GET /predict/game?home_team_id=&away_team_id=` | Pregame win probability from current team form (test AUC 0.74) |
| `POST /ask` | Natural-language analytics: an LLM agent writes SQL, reads results, answers with sources |
| `GET /players/{id}/scouting-report` | AI scouting report grounded strictly in warehouse data |

### AI assistant setup

The AI endpoints use whichever LLM API key is present (checked in this order):

```bash
export ANTHROPIC_API_KEY=...   # Claude (claude-opus-5)
export GEMINI_API_KEY=...      # Gemini (gemini-2.5-flash)
export OPENAI_API_KEY=...      # OpenAI (gpt-5-mini)
```

Optional: `COURTVISION_LLM=gemini` forces a provider, `COURTVISION_LLM_MODEL=...`
overrides the model. Install the SDKs with `pip install -e ".[llm]"`. With no key
set, the AI endpoints return 503 and everything else works normally.

Query the warehouse with any DuckDB client:

```python
from courtvision.db.connection import get_connection
con = get_connection(read_only=True)
con.execute("SELECT TEAM_NAME, NET_RATING FROM team_season_advanced ORDER BY NET_RATING DESC LIMIT 5").df()
```

## Notes on data sourcing

stats.nba.com is an unofficial API: it is rate-limited and occasionally blocks
datacenter IPs. All calls go through a retry/backoff wrapper with a politeness delay
(`src/courtvision/ingestion/nba.py`). Ingest from a residential connection.

## Roadmap

1. ✅ Ingestion pipeline + DuckDB warehouse
2. ✅ Computed metrics layer + FastAPI backend
3. ✅ ML models: player similarity, win probability (salary value deferred — needs a licensed data source)
4. ✅ React dashboards
5. ✅ LLM layer: natural-language analytics + AI scouting reports (SQL-agent, grounded in the warehouse)
6. Dockerized deployment + CI/CD
