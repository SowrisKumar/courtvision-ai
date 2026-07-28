# CourtVision AI — Project Report

A running log of everything built in this project: what was done, why, how it works,
how to troubleshoot it, and what alternatives were considered. Each milestone gets a
section with a non-technical summary first, then the technical detail.

---

## Milestone 1 — Project Scaffold & Data Ingestion Pipeline

*Completed: July 28, 2026*

### Non-technical summary

Before any analytics, dashboards, or AI features can exist, the platform needs data.
This milestone built the foundation: a program that automatically downloads NBA
statistics from the NBA's own stats website and stores them in a local database,
organized so that later features can query them quickly.

Think of it as stocking the warehouse before opening the store. We now have three full
seasons (2023-24 through 2025-26) of:

- Every team's season statistics — both traditional (points, rebounds) and advanced
  (offensive/defensive efficiency, pace)
- Every player's season statistics, same two flavors (~1,700 player-seasons)
- Every game played (~3,690 games, stored as one row per team per game)
- Reference lists of all 30 teams and ~5,100 historical players

We verified correctness by checking known facts against the data: the 2023-24 Celtics
show 64 wins, Oklahoma City has the best net rating in 2024-25 and 2025-26, and the
scoring leaders are Luka Dončić and Shai Gilgeous-Alexander — all correct.

### What was done (technical)

1. **Repository scaffold** — a `src/`-layout Python package (`courtvision`) with
   `pyproject.toml`, installable via `pip install -e .`; git initialized and pushed to
   [github.com/SowrisKumar/courtvision-ai](https://github.com/SowrisKumar/courtvision-ai).
2. **Configuration module** (`src/courtvision/config.py`) — single source of truth for
   paths, default seasons, and API politeness settings (timeout, retry count, sleep).
3. **Ingestion layer** (`src/courtvision/ingestion/nba.py`) — typed fetch functions
   wrapping `nba_api` endpoints. All live calls route through one `_fetch()` helper
   that applies a 30s timeout, 3 retries with exponential backoff, and a 1s sleep
   after every successful call.
4. **Database layer** (`src/courtvision/db/connection.py`) — DuckDB connection helper
   and a `load_dataframe()` that registers a pandas DataFrame and does
   `CREATE OR REPLACE TABLE ... AS SELECT`, i.e., full-refresh loads.
5. **Pipeline entry point** (`scripts/ingest.py`) — fetches static reference data plus,
   per season: team stats (Base + Advanced), player stats (Base + Advanced), and the
   league game log; concatenates across seasons and loads 7 tables into
   `data/courtvision.duckdb`.
6. **Smoke tests** (`tests/test_db.py`) — 5 pytest checks: expected tables exist,
   exactly 30 teams, 30 team-rows per season, exactly 2 game-log rows per `GAME_ID`
   (home + away), no null offensive/defensive ratings. All pass.

### Why

- **Data first:** every downstream feature (metrics, ML, dashboards, the LLM layer)
  reads from this warehouse. Building it first also validated the project's riskiest
  external dependency before we invested in anything else.
- **Season-level Base + Advanced tables** give immediate material for the analytics
  features; **game logs** are the raw material for the win-probability model and
  trend/form features later.
- **Full-refresh loads** (not incremental) because the data volume is tiny (thousands
  of rows) — re-downloading everything is simpler and self-healing. Incremental
  loading is an optimization we can add when we ingest play-by-play data, which is
  orders of magnitude larger.

### How it works

```
stats.nba.com  ──nba_api──▶  ingestion/nba.py (_fetch: timeout/retry/sleep)
                                   │  pandas DataFrames (+ SEASON column added)
                                   ▼
                             scripts/ingest.py (concat seasons)
                                   │
                                   ▼
                             db/connection.py  ──▶  data/courtvision.duckdb (7 tables)
```

Run it:

```bash
python scripts/ingest.py            # default seasons from config.py
python scripts/ingest.py 2022-23    # add/refresh a specific season
pytest                              # verify the result
```

Key detail: `nba_api`'s `LeagueDash*` endpoints take
`measure_type_detailed_defense="Base"|"Advanced"` — the same endpoint returns
completely different stat columns depending on this parameter, which is why each
entity has two tables rather than one wide one.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ReadTimeout` / hangs on fetch | stats.nba.com throttling or blocking your IP | Wait and re-run (retries are built in). Datacenter/cloud IPs and VPNs are frequently blocked — ingest from a residential connection. |
| `RuntimeError: ... failed after 3 attempts` | Persistent block or NBA changed the endpoint | Try a browser visit to stats.nba.com first (sometimes "warms" the block); check for an `nba_api` package update — the community patches header/endpoint changes quickly. |
| Empty DataFrame for a season | Wrong season string | Format must be `YYYY-YY`, e.g. `2025-26`. |
| `duckdb.IOException: ... lock` | Another process (or a stale notebook) holds the DB file | Close other connections; DuckDB allows one writer at a time. Delete `data/courtvision.duckdb.wal` only if no process is running. |
| Tests skipped | Database not ingested yet | Run `python scripts/ingest.py` first — tests are gated on the DB file existing. |
| Import errors after clone | Package not installed | `pip install -e ".[dev]"` inside the venv. |

### Alternatives considered

| Decision | Chosen | Alternatives & why rejected |
|---|---|---|
| Data source | `nba_api` (stats.nba.com) | **Basketball-Reference scraping**: richer historical data but scraping violates their ToS for automated bulk use and breaks on HTML changes. **Paid APIs (Sportradar, SportsDataIO)**: production-grade but cost money — wrong trade-off for a portfolio project. **Kaggle dumps**: static, go stale immediately; we want a live pipeline. |
| Database | DuckDB | **PostgreSQL**: the spec names it, and we may still adopt it when the FastAPI backend needs concurrent writers — but for a single-writer analytics workload DuckDB is zero-setup, file-based, and much faster for OLAP scans. **SQLite**: same convenience but row-oriented and weak analytics SQL (no `QUALIFY`, weaker window functions). |
| DataFrame library | pandas only | **Polars**: faster, but `nba_api` returns pandas natively and our volumes are tiny — using both adds conversion friction for zero benefit at this scale. Revisit if play-by-play ingestion (millions of rows) lands. |
| Orchestration | Plain script | **Airflow**: heavy infrastructure (scheduler, metadata DB) for what is currently one command; **dbt**: valuable later for the metrics/transform layer, premature while there are no transforms. A cron entry or GitHub Action can schedule `ingest.py` when needed. |
| Load strategy | Full refresh (`CREATE OR REPLACE`) | **Incremental upserts**: more code, more edge cases (late stat corrections by the NBA are common), no payoff at this volume. |
| Package layout | `src/` layout + editable install | **Flat scripts/notebooks**: faster to start but doesn't demonstrate production engineering, and imports break as the project grows. |
