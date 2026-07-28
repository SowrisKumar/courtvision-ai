# CourtVision AI

[![CI](https://github.com/SowrisKumar/courtvision-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/SowrisKumar/courtvision-ai/actions/workflows/ci.yml)

An end-to-end NBA analytics & decision intelligence platform: automated data ingestion,
an analytics warehouse, advanced metrics, ML models (player similarity, win probability,
salary value), interactive dashboards, and an LLM-powered analytics assistant.

## Status

**Milestone 3 complete — ML layer (similarity + win probability).** The pipeline pulls league-wide team
and player stats (Base + Advanced measure types) and full game logs from stats.nba.com
via [`nba_api`](https://github.com/swar/nba_api) into a local DuckDB warehouse; SQL views
normalize them into clean per-game analytics tables, served by a FastAPI backend.

| Table | Contents |
|---|---|
| `teams`, `players` | Static reference data (30 teams, ~5,100 players) |
| `team_season_base` / `team_season_advanced` | Per-team season stats (ORtg, DRtg, pace, …) |
| `player_season_base` / `player_season_advanced` | Per-player season stats (TS%, usage, …) |
| `game_logs` | Team box score per game (2 rows per game) |

Default seasons: 2023-24 through 2025-26 (see `src/courtvision/config.py`).

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
4. React dashboards
5. LLM layer: natural-language analytics + AI scouting reports (RAG, grounded in the warehouse)
6. Dockerized deployment + CI/CD
