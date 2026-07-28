"""DuckDB connection helpers."""

import duckdb

from courtvision.config import DATA_DIR, DB_PATH


def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def load_dataframe(con: duckdb.DuckDBPyConnection, table: str, df) -> int:
    """Replace `table` with the contents of `df`. Returns the row count."""
    con.register("_incoming", df)
    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM _incoming")
    con.unregister("_incoming")
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
