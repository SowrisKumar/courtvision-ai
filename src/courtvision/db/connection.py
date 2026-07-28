"""DuckDB connection helpers."""

import duckdb

from courtvision.config import DATA_DIR, DB_PATH


def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=read_only)


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
    con.execute(f"INSERT INTO {table} SELECT * FROM _incoming")
    con.unregister("_incoming")
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
