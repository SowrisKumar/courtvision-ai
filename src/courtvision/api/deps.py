"""FastAPI dependencies."""

from collections.abc import Iterator

import duckdb

from courtvision.db.connection import get_connection


def db() -> Iterator[duckdb.DuckDBPyConnection]:
    """Read-only, filesystem-sandboxed DuckDB connection per request.

    Read-only connections can coexist with each other; the ingest script is the
    only writer and runs out-of-process.

    External access is disabled because /ask executes SQL written by an LLM from
    an untrusted question. Read-only alone would still allow
    `SELECT * FROM read_csv_auto('/etc/passwd')`, whose rows the API hands
    straight back to the browser.
    """
    con = get_connection(read_only=True, allow_external=False)
    try:
        yield con
    finally:
        con.close()


def rows_to_dicts(result) -> list[dict]:
    cols = [d[0] for d in result.description]
    return [dict(zip(cols, row)) for row in result.fetchall()]
