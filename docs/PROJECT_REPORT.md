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

---

## Incident report — venv broken by iCloud Desktop sync

*July 28, 2026 — resolved*

### Non-technical summary

Midway through milestone 2, `import courtvision` suddenly stopped working — sometimes.
The same command would succeed one minute and fail the next, which is the most confusing
class of bug. The cause turned out to be macOS itself: this project lives on the
Desktop, and the Mac's iCloud "Desktop & Documents" sync was interfering with the
Python environment.

### Technical detail

**Symptom:** `ModuleNotFoundError: No module named 'courtvision'` — intermittently.
The editable-install `.pth` file existed in `site-packages` with the correct contents,
the target path existed, yet the path never appeared on `sys.path`.

**Diagnosis path (useful as a template for "impossible" bugs):**
1. Verified the `.pth` file's exact bytes (`xxd`) — clean, newline-terminated.
2. Verified `os.path.exists()` on the target from inside Python — true.
3. Probed whether `.pth` processing runs at all — it did, sometimes even twice.
4. A byte-identical copy of the file under a different name worked while the original
   didn't — then later both failed. Intermittency ⇒ environment, not code.
5. `ls -lO@` showed every file in the venv carried the macOS **`hidden` chflag** and
   `com.apple.fileprovider` extended attributes — the fingerprint of iCloud's file
   provider managing the directory.
6. `python -v` gave the smoking gun: **`Skipping hidden .pth file`**. Python 3.13
   added a rule to ignore `.pth` files carrying the hidden attribute, and iCloud was
   (asynchronously — hence the intermittency) flagging synced files hidden.

**Fix:**
1. Renamed the venv to `.venv.nosync` — iCloud excludes `*.nosync` paths from sync —
   with a symlink `.venv → .venv.nosync` so every documented command still works.
2. `chflags -R nohidden .venv.nosync` to clear the existing flags.
3. Verified with repeated imports and the full test suite.

### Troubleshooting (if it recurs)

- `python -v -c pass 2>&1 | grep -i pth` — look for "Skipping hidden .pth file".
- `ls -lO` in site-packages — check for the `hidden` flag; clear with `chflags -R nohidden`.
- Long-term recommendation: keep code repositories out of iCloud-synced folders
  (Desktop/Documents) entirely — e.g. `~/Projects/`. Sync also risks corrupting the
  DuckDB file if it syncs mid-write, and uploads tens of thousands of venv files.

### Alternatives considered

| Option | Why not chosen |
|---|---|
| Move the whole project out of Desktop | The right long-term fix, but it's the user's file organization to decide; `.nosync` solves the immediate problem without moving anything. |
| Abandon editable install (plain `pip install .`) | Would require reinstalling after every source edit during development. |
| `PYTHONPATH` in shell profile | Machine-specific, invisible configuration; breaks for anyone else cloning the repo. |

---

## Milestone 2 — Metrics Layer & REST API

*Completed: July 28, 2026*

### Non-technical summary

Milestone 1 stocked the warehouse; milestone 2 opens the service counter. Two things
were built:

1. **A metrics layer** — the raw downloaded tables are messy (55–80 columns each,
   season *totals* rather than per-game numbers, dozens of "rank" columns we don't
   need). We defined clean, analyst-friendly *views*: one row per player-season and
   per team-season with the numbers people actually reason about — points per game,
   true shooting %, usage rate, offensive/defensive rating, pace — plus a per-game
   view that knows which games were home vs. away.

2. **A REST API** — a web service that any program (our future dashboard, the future
   AI assistant, or a curious developer with a browser) can query: search players by
   name, get a team's season history with home/away splits, pull leaderboards for any
   stat. It ships with self-documenting interactive docs at `/docs`.

Everything is covered by automated tests, including basketball "ground truth" checks
(the API must report Luka Dončić as the 2023-24 scoring champion, every team must have
exactly 41 home and 41 away games).

### What was done (technical)

1. **`src/courtvision/metrics/views.py`** — three DuckDB views defined as SQL constants
   and created idempotently (`CREATE OR REPLACE VIEW`):
   - `v_player_season`: Base ⋈ Advanced on `(PLAYER_ID, TEAM_ID, SEASON)`; per-game
     normalization (`PTS/GP` etc.), TS%, eFG%, USG%, ratings, PIE. `GP > 0` guard
     against division by zero.
   - `v_team_season`: team Base ⋈ Advanced ⋈ `teams` (for the abbreviation); record,
     per-game scoring, ratings, pace, four-factor-adjacent metrics.
   - `v_team_game`: game logs with `is_home` derived from the `MATCHUP` string
     (`"vs."` = home, `"@"` = away) and an `is_win` flag.
   `scripts/build_metrics.py` creates them from the CLI; the API also (re)creates them
   at startup so views never go stale after re-ingestion.
2. **FastAPI app** (`src/courtvision/api/`):
   - `deps.py` — per-request **read-only** DuckDB connection as a dependency
     (read-only connections coexist; the out-of-process ingest script is the only writer).
   - `main.py` — endpoints: `/health`, `/teams`, `/teams/{id}` (with home/away splits
     computed by SQL aggregation), `/players/search`, `/players/{id}`,
     `/leaderboards/{stat}`. Lifespan handler builds views on startup.
3. **Security details:** every user value is a bound SQL parameter (`?`); the
   leaderboard stat name — which must be interpolated into `ORDER BY` and can't be a
   bound parameter — is validated against a hard whitelist, tested with an injection
   attempt (`/leaderboards/evil; DROP TABLE`).
4. **Search UX detail:** name search uses `strip_accents(lower(...))` on both sides so
   "jokic" finds "Jokić" and "doncic" finds "Dončić". (Found by a failing test —
   the test suite caught it before any user would have.)
5. **7 new API tests** (`tests/test_api.py`) using FastAPI's `TestClient`, gated to
   skip when the database hasn't been ingested. 12 tests total, all passing.

### Why

- **Views, not materialized tables:** at this data volume DuckDB recomputes a view in
  microseconds; views can never be stale relative to the raw tables; and view SQL
  doubles as living documentation of every metric definition. This is the same
  pattern dbt formalizes — if/when we adopt dbt, these views port directly.
- **Per-request read-only connections:** DuckDB allows exactly one writer but many
  readers. Keeping the API read-only makes it impossible for a web request to corrupt
  the warehouse and sidesteps connection-sharing/threading questions entirely.
- **A REST API now, before dashboards/ML:** every later milestone consumes this layer.
  Building it early means the frontend and the LLM tool-calling layer both get a
  stable, tested contract.

### How it works

```
                    ┌── scripts/build_metrics.py (CLI)
raw tables ──▶ SQL views (v_player_season, v_team_season, v_team_game)
                    └── FastAPI lifespan (auto-refresh on startup)
                              │
                    per-request read-only DuckDB connection (deps.py)
                              │
                    GET /teams /players /leaderboards ... ──▶ JSON
```

Run it:

```bash
python scripts/build_metrics.py
uvicorn courtvision.api.main:app --reload    # http://127.0.0.1:8000/docs
```

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Catalog Error: Table 'v_player_season' does not exist` | Views not built | Run `python scripts/build_metrics.py`, or just start the API (it builds them at startup). |
| API returns empty lists | Wrong `season` format | Use `YYYY-YY`, e.g. `2025-26`; check `/health` for available seasons. |
| `IO Error: ... database is locked` on API start | Ingest running concurrently (it's the writer) | Let ingestion finish; the API only needs read access. |
| 400 on `/leaderboards/...` | Stat not in whitelist | Error message lists valid stats; add new ones to `LEADERBOARD_STATS` *and* `v_player_season`. |
| Search finds nothing for an accented name | — | Search is accent-insensitive by design; if a name is missing, the player may not have played in the ingested seasons. |

### Alternatives considered

| Decision | Chosen | Alternatives & why rejected |
|---|---|---|
| Transform layer | DuckDB SQL views | **dbt**: the industry tool, but adds a whole toolchain for 3 views; planned once the model count grows. **Pandas transforms → new tables**: logic hidden in Python, stale after re-ingest, harder to inspect than `DESCRIBE v_player_season`. |
| API framework | FastAPI | **Flask**: no built-in validation/OpenAPI docs. **Django REST**: ORM-centric and heavyweight — we deliberately query analytics SQL, not ORM models. FastAPI's auto `/docs` is also a portfolio asset. |
| Leaderboard design | One endpoint + stat whitelist | **Endpoint per stat**: 11 near-identical handlers. **Free-form stat parameter**: SQL injection via `ORDER BY` — identifiers can't be bound parameters, so a whitelist is the only safe generic design. |
| Connection strategy | New read-only connection per request | **Shared global connection**: DuckDB connections aren't safely shareable across threads, and FastAPI runs sync handlers in a threadpool. **Connection pool**: solves a throughput problem we don't have; revisit under load. |
| Response models | Plain dicts from SQL rows | **Pydantic models per endpoint**: better OpenAPI schemas and type safety, but duplicates the view schemas by hand today; planned when the API surface stabilizes (and needed anyway for the LLM tool-calling layer). |

---

## Project Audit — full correctness review + CI

*Completed: July 28, 2026*

### Non-technical summary

Before building the machine-learning milestone we paused and audited everything built
so far: the plan, the framework choices, and every line of code. The architecture held
up. The data was re-verified against reality. Five concrete problems were found and
fixed — the most important being a hidden data-loss trap: asking the ingestion script
to refresh *one* season would silently delete all the *other* seasons. We also added
continuous integration: from now on, every change pushed to GitHub is automatically
linted and tested before a human ever reviews it.

### Findings (technical)

**Verified correct, no action needed:**
- Warehouse semantics: exactly one row per player per season (count == distinct across
  all three seasons); traded players carry `TEAM_COUNT > 1` with their last team.
- SQL injection surface: all user values bound; the one interpolated identifier
  (leaderboard stat) is whitelist-guarded and covered by an injection test.
- Ground-truth checks pass against real basketball facts.

**Fixed:**

| # | Issue | Fix |
|---|---|---|
| 1 | `ingest.py 2022-23` **replaced entire tables** with just that season (data loss); README implied additive behavior | New `upsert_seasons()` in `db/connection.py`: creates the table if missing, deletes only the incoming seasons' rows, inserts. Verified empirically: re-ingested 2025-26 alone, 2023-24/2024-25 row counts unchanged. |
| 2 | Test hardcoded `len(seasons) == 3` — breaks on any 4th season | Expected seasons now derived from `/health` at test time. |
| 3 | Dead code: unused `fetch_team_roster` | Removed. |
| 4 | Stray empty `".venv 2"` directory (macOS artifact) | Removed. |
| 5 | ruff declared but never run | Ran it; fixed all findings — migrated API handlers to FastAPI's modern `Annotated` dependency style (B008), added a documented `noqa` for the intentional broad catch in the network retry wrapper (BLE001). |

### CI pipeline

`.github/workflows/ci.yml`: on every push/PR — Python 3.12, `pip install -e ".[dev]"`,
`ruff check`, `pytest -q`.

The interesting problem: **CI has no database.** The real warehouse requires
stats.nba.com, which is unreachable/blockable from GitHub's datacenter IPs, and a test
suite that depends on a third-party API is flaky by construction. Solution: a
**synthetic warehouse** (`tests/synth.py` + `tests/conftest.py`). When
`data/courtvision.duckdb` is absent, conftest builds a fake-but-structurally-faithful
DuckDB before any test imports the app: 30 real teams, 3 seasons, a full 82-game
schedule per team (41 home / 41 away, 2 rows per game — real NBA constraint: 1,230
games per season), and a player pool seeded with real star names whose crafted stats
preserve the ground-truth assertions (Luka leads 2023-24 scoring; Jokić's TS% > .55).
`COURTVISION_DB` env var overrides the DB path (read in `config.py`). Local runs
against a real ingested DB are completely unchanged.

### Troubleshooting

| Symptom | Fix |
|---|---|
| CI red on lint | `ruff check src scripts tests` locally; `--fix` for auto-fixables. |
| CI red on tests but green locally | You're testing real data locally, CI tests synthetic. Reproduce with: `COURTVISION_DB=/tmp/s.duckdb python -c "import sys; sys.path.insert(0,'tests'); from synth import build_synthetic_db; from pathlib import Path; build_synthetic_db(Path('/tmp/s.duckdb'))"` then `COURTVISION_DB=/tmp/s.duckdb pytest -q`. |
| A new test needs a column the synthetic DB lacks | Add it to the relevant frame in `tests/synth.py` — synthetic tables only carry columns the views reference. |
| Old single-season ingest wiped data (pre-audit clone) | Re-run `python scripts/ingest.py` with all seasons; upsert semantics now prevent recurrence. |

### Alternatives considered

| Decision | Chosen | Alternatives & why rejected |
|---|---|---|
| CI database | Synthetic fixture built in-process | **Hit stats.nba.com from CI**: blocked IPs + flaky third-party dependency. **Commit a real DuckDB file**: binary blobs in git, stale data, licensing gray area. **Skip DB tests in CI**: lint-only CI catches almost nothing. |
| Ingest fix | Per-season delete+insert upsert | **Document the destructive behavior instead**: docs don't prevent data loss, they just explain it afterwards. **Full merge/dedup logic**: seasons are the natural refresh unit; finer granularity adds complexity with no use case. |
| B008 lint finding | Adopt `Annotated` dependencies | **Suppress the rule**: `Annotated` is FastAPI's current recommended style anyway — the lint was right. |

---

## Milestone 3 — Machine Learning Layer

*Completed: July 28, 2026*

### Non-technical summary

Two ML features shipped, both live behind API endpoints:

1. **Player similarity engine** — "who plays like this player?" Each player-season is
   summarized as a 15-number statistical fingerprint (scoring volume, efficiency,
   usage, playmaking, rebounding, shot diet); the engine ranks everyone by how closely
   their fingerprint's *shape* matches. The results pass the basketball eye test:
   Jokić's closest 2025-26 matches are Jalen Johnson, LeBron, Giddey, and Sengun —
   all jumbo playmakers; Luka's are Donovan Mitchell and James Harden — high-usage
   shot-creating guards.

2. **Win probability model** — given any two teams, estimates the home team's chance
   of winning from *current form* (recent record, scoring margin, season record,
   rest). Honest evaluation on a season the model never saw (2025-26): **67.6%
   accuracy vs a 55.1% "always pick home team" baseline, AUC 0.738**. Professional
   betting lines land around 68–70%, so a pure team-form model at 67.6% is credible —
   and the gap to Vegas is roughly what player-availability information is worth.

**Deferred: salary value analysis.** There is no clean, legally re-distributable
public source for NBA salary data (Spotrac/HoopsHype are scrape-hostile; the CBA data
isn't published as an API). Rather than build on a shaky source, this feature waits
for a sourcing decision.

### What was done (technical)

1. **`src/courtvision/ml/features.py`** — feature-engineering SQL:
   - `TEAM_FORM_SQL`: per team-game rolling windows over `v_team_game` — last-10 win%
     and average margin, season-to-date win%, rest days. **Every window ends at
     `1 PRECEDING`**, so a game's features never include its own outcome (no leakage).
   - `GAME_DATASET_SQL`: self-join of home and away form rows per `GAME_ID`; drops
     games where either side has played < 6 games (unstable early-season form);
     rest days capped at 7 (an 8-day All-Star break tells you nothing more than a week off).
2. **`ml/similarity.py`** — pulls qualified players (≥20 GP, ≥15 min/game) for a
   season, z-scores the 15-feature matrix, ranks by cosine similarity to the target.
   Pure NumPy (~600×15 matrix; milliseconds), no model artifact needed.
3. **`ml/win_probability.py`** — trains two candidates (standardized logistic
   regression; histogram gradient boosting), evaluates both on the held-out test
   season, saves the better one (by log loss) with a JSON metadata sidecar
   (`data/models/win_probability.{joblib,json}`). Logistic won: log loss 0.601 vs
   0.628, AUC 0.738 vs 0.710 — with 8 features and ~2,300 training games, the extra
   capacity of boosting only finds noise.
4. **API endpoints** — `GET /players/{id}/similar` (season defaults to the player's
   latest) and `GET /predict/game?home_team_id=&away_team_id=` (503 with instructions
   if the model isn't trained; predicts from each team's latest-season form).
5. **`scripts/train_win_model.py`** — CLI training entry point; prints the metrics JSON.
6. **6 new tests** (`tests/test_ml.py`), all running on both real and synthetic data:
   similarity structure (ordering, self-exclusion, score bounds), dataset integrity
   (no NaNs, one row per game), model-beats-chance gate (AUC > 0.55), endpoint
   behavior incl. 404s. 18 tests total.

### How it works

```
v_team_game ──window SQL──▶ rolling form features ──self-join──▶ game dataset
                                                       │
                              train/test split by season (no shuffling!)
                                                       │
                    logistic regression vs hist gradient boosting
                                                       │
                        best by log loss ──▶ data/models/*.joblib
                                                       │
GET /predict/game ──▶ current_form(team) ──▶ model.predict_proba ──▶ P(home win)

v_player_season ──▶ z-scored 15-feature matrix ──▶ cosine vs target ──▶ top-k
```

### Model evaluation detail (2025-26 held out)

| Model | Log loss | AUC | Accuracy |
|---|---|---|---|
| Always pick home team | — | 0.500 | 0.551 |
| Hist gradient boosting | 0.628 | 0.710 | 0.656 |
| **Logistic regression** | **0.601** | **0.738** | **0.676** |

The split is **by season, never shuffled** — shuffling game rows across time would
leak future form into training and inflate every metric.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/predict/game` returns 503 | Model not trained | `python scripts/train_win_model.py` |
| `/players/{id}/similar` returns 404 for a real player | Player below qualification floor | Needs ≥20 games and ≥15 min/game that season (floor set in `ml/similarity.py`). |
| `ConnectionException` about read-only/write configs in tests | A write connection held open while the API opens read-only ones (same process) | Order fixtures: write work (views, training) fully closed *before* `TestClient` starts — see the comment in `tests/test_ml.py`. |
| Metrics look too good after changing the dataset SQL | Leakage | Check every window still ends at `1 PRECEDING` and the split is by season. |
| Retraining gives slightly different boosting numbers | Nondeterminism | `random_state=0` is set; if numbers still drift, check sklearn version. |

### Alternatives considered

| Decision | Chosen | Alternatives & why rejected |
|---|---|---|
| Similarity metric | Cosine on z-scores | **Euclidean/KNN**: dominated by volume stats — every star matches every star. Cosine on standardized features matches on *style*. **PCA first**: adds an unexplainable step; 15 curated features don't need reduction. |
| Similarity serving | Compute per request | **Precomputed FAISS/ChromaDB index**: the spec names them, but they solve million-vector problems; ~600 players is a 1 ms NumPy dot product. Vector DBs enter with the RAG milestone, where they belong. |
| Win-prob algorithms | Logistic + HistGB, keep better | **XGBoost/LightGBM** (named in spec): heavier native deps for marginal gains at this scale; sklearn's HistGB is the same algorithm family, and it *still* lost to logistic — the honest lesson is that small tabular data favors simple models. |
| Win-prob features | Team form only | **Player-level availability/ratings**: the single biggest upgrade (injuries move lines), but requires reliable daily injury data — a sourcing problem, deferred deliberately. |
| Evaluation | Hold out the latest full season | **Random K-fold**: leaks time. **Rolling-origin backtest**: better still, and worth adding when the model gains features; one clean temporal split is honest and simple today. |
| Salary model | Deferred | No legally solid public salary source; building on scraped Spotrac data would undermine the project's "production-grade" claim. |

---

## Milestone 4 — React Dashboard

*Completed: July 31, 2026*

### Non-technical summary

The platform now has a face. A web dashboard (React) with four pages, all fed live by
the API:

- **League** — every team plotted on an offense-vs-defense efficiency map (the classic
  quadrant chart analysts use), plus full sortable standings.
- **Players** — type-ahead search (accent-insensitive, so "jokic" works), a career
  per-game trend chart, headline stat tiles, and the ML similarity engine's picks
  rendered as comparison cards.
- **Leaderboards** — pick any stat and season; horizontal bar chart with exact values
  labeled.
- **Predict** — pick any two teams; the win probability model renders as a
  two-color split bar with each team's current form beneath.

The design follows a validated data-viz token system: light *and* dark mode (follows
the OS setting), colorblind-safe series colors, one accent hue for single-series
charts, muted grids, direct labels where they help.

### What was done (technical)

1. **Toolchain**: installed Node 26 (Homebrew); scaffolded with Vite (`react-ts`
   template) in `frontend/`; added Tailwind CSS v4 (`@tailwindcss/vite` plugin —
   no PostCSS config needed), Recharts, React Router.
2. **Design tokens** (`src/index.css`): CSS custom properties for surfaces, ink
   hierarchy, gridlines, and series colors — the reference palette from the dataviz
   method, both light and dark values behind `prefers-color-scheme`. Charts reference
   roles (`var(--series-1)`), never raw hex.
3. **API client** (`src/lib/api.ts`): typed fetch wrapper with response interfaces
   mirroring the API's JSON; errors surface FastAPI's `detail` message.
4. **Dev/preview proxy** (`vite.config.ts`): `/api/*` → `127.0.0.1:8000` with prefix
   strip — no CORS configuration needed on the backend at all.
5. **Pages** (`src/pages/`): `League` (ScatterChart with reversed DRtg axis so
   "good" is a consistent corner + standings table), `Players` (debounced search,
   3-series LineChart with legend, similarity cards with score bars), `Leaderboards`
   (vertical BarChart, value labels, stat/season filters in one row), `Predict`
   (split probability bar using series-1 vs series-2 with a 2px surface gap, form
   stat tiles). Loading/error/empty states on every page.
6. **CI**: second job (`frontend`) — Node 22, `npm ci`, `npm run build` (which runs
   `tsc -b` first, so type errors fail CI).

### How it works

```
React (5173/4173) ──/api/*──▶ Vite proxy ──▶ FastAPI (8000) ──▶ DuckDB views/models
        │
   App.tsx loads /health once → seasons list → passed to pages as props
   pages fetch on mount/filter-change → Recharts renders with CSS-token colors
```

Run the full stack locally:

```bash
uvicorn courtvision.api.main:app --reload   # terminal 1
cd frontend && npm run dev                  # terminal 2 → http://localhost:5173
```

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "API unreachable" banner | Backend not running | Start uvicorn on port 8000 (the proxy target). |
| `curl 127.0.0.1:4173` refused but browser works | Node ≥ 17 binds `localhost` to IPv6 `::1` | Use `http://localhost:...` (or `--host 127.0.0.1`). Bit us during verification. |
| Charts render with no colors | CSS tokens missing | Series colors come from `index.css` custom properties; check the `--series-*` definitions. |
| Type errors only in CI | Local dev server skips type-checking | `npm run build` runs `tsc -b`; run it locally before pushing. |
| Empty dashboard after re-ingest | View/schema drift | Check `/api/health` first; then browser devtools network tab for the failing endpoint. |

### Alternatives considered

| Decision | Chosen | Alternatives & why rejected |
|---|---|---|
| Build tool | Vite | **Create React App**: deprecated. **Next.js**: SSR/routing framework overhead for what is a pure client-side dashboard against our own API. |
| Charts | Recharts | **Plotly**: heavier bundle, harder to token-theme; **D3 direct**: maximum control, 5× the code for standard chart forms. Recharts is declarative React and styles cleanly from CSS variables. |
| Styling | Tailwind v4 + CSS custom properties | **Plain CSS/modules**: more boilerplate for the same tokens; **component library (MUI etc.)**: fights the design tokens and bloats the bundle for 4 pages. |
| API access | Dev-server proxy | **CORS middleware on FastAPI**: works, but ships a permissive-origins config that must be tightened at deploy; the proxy keeps the backend origin-agnostic until real deployment sets the policy. |
| State management | `useState` + props | **Redux/TanStack Query**: four pages with per-page fetches don't justify a cache layer yet; TanStack Query becomes attractive with the LLM milestone's streaming/chat state. |
| Node version pinning | Node 22 in CI, 26 locally | **Pin 26 everywhere**: 22 is the active LTS; CI on LTS catches "works only on bleeding edge" issues. |

### Post-milestone addition: warehouse schema docs (August 1, 2026)

`data/README.md` documents the warehouse for newcomers: the raw-vs-views two-layer
design, every table's grain and row count, the traded-player convention
(`TEAM_COUNT` > 1, one row per player-season), join keys, a mermaid ER diagram
(GitHub renders it), and a copy-paste DuckDB snippet for exploring. Lives in `data/`
next to the database file it describes; the data files themselves stay gitignored.

### Post-milestone addition: roster-turnover robustness, tested (July 31, 2026)

**The question (from the user):** the model trains on past seasons, but teams trade,
players move, coaches change — how is that addressed?

**The architecture answer:** the win probability model is deliberately **identity-free**.
No team ID, no franchise history, no prior-season record is a feature — every input is
current-season form (last-10 win%/margin, season-to-date win%, rest). Past seasons teach
only the general form→outcome mapping, which transfers across seasons because it doesn't
know who the teams are; a rebuilt roster is read from its own new games after ~6 games.

**The empirical check:** we built `roster_carryover` — the share of a team's
previous-season minutes played by players still on the roster (SQL in
`ml/features.py::ROSTER_CARRYOVER_SQL`; 2022-23 was ingested so 2023-24 has a prior) —
and A/B tested it on the held-out 2025-26 season. Result: log loss 0.6015 → 0.6014,
AUC 0.736 → 0.735. **No measurable improvement, so it was not shipped** — once current
form is known, roster turnover adds nothing, which validates the identity-free design.
The dataset still exposes the carryover columns (`CARRYOVER_FEATURES`) for future
experiments, the notebook documents the negative result in §3.6, and the tests assert
the columns are filled and in [0, 1].

**Honest residual gaps** (documented in the notebook): opening weeks (form needs 6+
games — exactly when summer turnover matters most), the ~10 games after a mid-season
trade or coach change (the form window spans the disruption), and tonight's
injuries/rest (needs external player-availability data; the main gap to betting lines).

Side effect: the warehouse now holds four seasons (2022-23 → 2025-26); training uses
three of them, and the dashboard's season pickers gained 2022-23.

### Post-milestone addition: model evidence notebook (July 31, 2026)

`notebooks/model_evaluation.ipynb` — an executed, committed notebook that serves as the
evidence file for the ML layer, aimed at portfolio reviewers ("prove these choices are
best"). It imports the production modules (never re-implements them) and shows:
similarity results for three stars plus the rejected alternatives (Euclidean on raw and
z-scored features) side by side; a PCA variance check (7 of 15 components for 90% —
no compact latent space, so no reduction step); win-probability baselines (coin flip,
always-home, better-record heuristic), four model families on the held-out 2025-26
season, GridSearchCV tuning evidence (moves the third decimal), a calibration curve, and
standardized coefficients. One notable honest finding: the better-record heuristic
*matches* the model on pick accuracy (67.7% vs 67.6%) but is far worse on probability
quality (AUC 0.680 vs 0.738) — the notebook frames probability quality as the product.
Charts use the project's dataviz palette via `plt.rcParams`. Re-run:
`jupyter nbconvert --to notebook --execute --inplace notebooks/model_evaluation.ipynb`.
Committed with outputs deliberately (the outputs are the proof; GitHub renders them).
Dev deps added: matplotlib, nbformat, nbclient, nbconvert, ipykernel.

### Post-milestone addition: player directory (July 31, 2026)

The Players page's empty state (just a search box) was replaced with a browsable
directory: a new `GET /players?season=` endpoint lists every player with stats in a
season, and the page renders them alphabetically, grouped by accent-stripped first
letter (so Dončić files under D), in a responsive multi-column grid. Every name is
clickable and behaves like a search selection; a "back to all players" button
restores the directory. The full ~580-name flat list was rejected as a wall of text;
letter grouping plus columns keeps it scannable. Directory data loads once per
season and is sorted client-side with `localeCompare` (DuckDB's default collation
would sort accented names after Z).
