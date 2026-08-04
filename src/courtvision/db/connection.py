"""DuckDB connection helpers."""

import duckdb

from courtvision.config import DATA_DIR, DB_PATH


def get_connection(
    read_only: bool = False,
    allow_external: bool = True,
) -> duckdb.DuckDBPyConnection:
    """Open the warehouse.

    `allow_external=False` disables DuckDB's filesystem and network access
    (read_csv, read_text, ATTACH, httpfs). Read-only protects the *database*;
    this protects the *host*, and is what the API serves model-written SQL on.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    config = {} if allow_external else {"enable_external_access": False}
    return duckdb.connect(str(DB_PATH), read_only=read_only, config=config)


def load_dataframe(con: duckdb.DuckDBPyConnection, table: str, df) -> int:
    """Replace `table` with the contents of `df`. Returns the row count.

    Full-refresh semantics — use only for reference tables (teams, players).
    """
    con.register("_incoming", df)
    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM _incoming")
    con.unregister("_incoming")
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def upsert_seasons(con: duckdb.DuckDBPyConnection, table: str, df) -> int:
    """Insert `df` into `table`, replacing only the seasons present in `df`.

    Seasons already in the table but absent from `df` are preserved, so
    re-ingesting one season never wipes the others. Returns the table's
    total row count afterwards.
    """
    seasons = sorted(df["SEASON"].unique())
    con.register("_incoming", df)
    con.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM _incoming LIMIT 0")
    placeholders = ", ".join("?" for _ in seasons)
    con.execute(f"DELETE FROM {table} WHERE SEASON IN ({placeholders})", seasons)
    # BY NAME, not positional: the table schema was frozen on the first ingest,
    # so if stats.nba.com ever reorders its columns a positional INSERT would
    # silently write each value into the wrong column.
    con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM _incoming")
    con.unregister("_incoming")
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
