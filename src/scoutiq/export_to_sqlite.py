"""Copy the raw DuckDB artifact into a SQLite database.

The DuckDB file is the raw source and stays untouched (opened read-only).
The SQLite copy goes into data/interim because it is a derived copy,
not a raw source. Types are mapped explicitly so the schema still reads
like the source.
"""

from __future__ import annotations

import argparse
import sqlite3
from decimal import Decimal
from pathlib import Path

import duckdb

DEFAULT_DUCKDB = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "raw"
    / "transfermarkt_datasets"
    / "transfermarkt-datasets.duckdb"
)
DEFAULT_SQLITE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "interim"
    / "transfermarkt_datasets"
    / "transfermarkt.sqlite"
)


def connect_duckdb(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Open the source DuckDB read-only."""
    return duckdb.connect(str(db_path), read_only=True)


def list_tables(connection: duckdb.DuckDBPyConnection) -> list[str]:
    """Return the names of all tables in the source database."""
    return [row[0] for row in connection.execute("SHOW TABLES").fetchall()]


def duckdb_type_to_sqlite(duckdb_type: str) -> str:
    """Translate a DuckDB type into a SQLite column type.

    SQLite does not enforce types; the declared name mostly matters for
    readability. We keep it close to the source so the schema reads the same.
    """
    base = duckdb_type.split("(")[0].upper()
    mapping = {
        "INTEGER": "INTEGER",
        "BIGINT": "INTEGER",
        "DOUBLE": "REAL",
        "FLOAT": "REAL",
        "DECIMAL": "REAL",
        "NUMERIC": "REAL",
        "VARCHAR": "TEXT",
        "DATE": "DATE",
        "TIMESTAMP": "TIMESTAMP",
        "BOOLEAN": "INTEGER",
    }
    return mapping.get(base, "TEXT")


def create_table_schema(
    duckdb_connection: duckdb.DuckDBPyConnection,
    sqlite_connection: sqlite3.Connection,
    table: str,
) -> None:
    """Recreate one table's schema in SQLite from DuckDB metadata."""
    columns = duckdb_connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    column_defs = ", ".join(
        f'"{name}" {duckdb_type_to_sqlite(data_type)}'
        for _, name, data_type, *_ in columns
    )
    sqlite_connection.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({column_defs})')


def adapt_value(value):
    """Convert one DuckDB cell into a value SQLite can store.

    DuckDB returns date/datetime/Decimal objects for DATE, TIMESTAMP and
    DECIMAL columns, which SQLite does not understand, so we convert them:
      date/datetime -> ISO strings (readable, still sort correctly)
      Decimal       -> float (SQLite has no DECIMAL storage class)
    """
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def copy_rows(
    duckdb_connection: duckdb.DuckDBPyConnection,
    sqlite_connection: sqlite3.Connection,
    table: str,
    batch_size: int = 100_000,
) -> int:
    """Copy a table in batches; returns the number of rows copied."""
    column_count = len(duckdb_connection.execute(f'PRAGMA table_info("{table}")').fetchall())
    placeholders = ", ".join(["?"] * column_count)
    insert_sql = f'INSERT INTO "{table}" VALUES ({placeholders})'
    rows = duckdb_connection.execute(f'SELECT * FROM "{table}"').fetchall()
    total = 0
    for start in range(0, len(rows), batch_size):
        batch = [tuple(adapt_value(v) for v in row) for row in rows[start:start + batch_size]]
        with sqlite_connection:  # one transaction per batch -> much faster
            sqlite_connection.executemany(insert_sql, batch)
        total += len(batch)
    return total


def verify_counts(
    duckdb_connection: duckdb.DuckDBPyConnection,
    sqlite_connection: sqlite3.Connection,
    tables: list[str],
) -> bool:
    """Compare row counts between the source and the copy."""
    ok = True
    for table in tables:
        duck_count = duckdb_connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        sqlite_count = sqlite_connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        status = "OK" if duck_count == sqlite_count else "MISMATCH"
        if duck_count != sqlite_count:
            ok = False
        print(f"  {table:<22} duckdb={duck_count:>10,}  sqlite={sqlite_count:>10,}  {status}")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE)
    args = parser.parse_args()

    args.sqlite.parent.mkdir(parents=True, exist_ok=True)

    with connect_duckdb(args.duckdb) as duck_conn, sqlite3.connect(str(args.sqlite)) as sqlite_conn:
        tables = list_tables(duck_conn)
        print(f"Exporting {len(tables)} tables from {args.duckdb.name}")
        print(f"Into: {args.sqlite}")
        for table in tables:
            create_table_schema(duck_conn, sqlite_conn, table)
            copied = copy_rows(duck_conn, sqlite_conn, table)
            print(f"  copied {table}: {copied:,} rows")

        print("\nRow-count verification:")
        ok = verify_counts(duck_conn, sqlite_conn, tables)
        print("All tables match." if ok else "WARNING: row counts differ.")

    print(f"\nDone. SQLite database at: {args.sqlite}")


if __name__ == "__main__":
    main()