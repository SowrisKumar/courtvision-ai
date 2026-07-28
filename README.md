# CourtVision AI

An end-to-end NBA analytics & decision intelligence platform: automated data ingestion,
an analytics warehouse, advanced metrics, ML models (player similarity, win probability,
salary value), interactive dashboards, and an LLM-powered analytics assistant.

## Status

**Milestone 1 — data ingestion (in progress).** The pipeline pulls league-wide team and
player stats (Base + Advanced measure types) and full game logs from stats.nba.com via
[`nba_api`](https://github.com/swar/nba_api) into a local DuckDB warehouse.

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
python scripts/ingest.py 2022-23    # ingest specific season(s)
pytest                              # smoke-test the ingested database
```

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
2. Computed metrics layer + FastAPI backend
3. ML models: player similarity, win probability, salary value
4. React dashboards
5. LLM layer: natural-language analytics + AI scouting reports (RAG, grounded in the warehouse)
6. Dockerized deployment + CI/CD
