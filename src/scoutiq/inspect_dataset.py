"""Read-only schema inspection for the historical dataset.

This tool deliberately does not clean, join, transform, or model the data.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


KEY_COLUMNS = {
    "players": ["player_id", "current_club_id"],
    "player_valuations": ["player_id", "date", "market_value_in_eur"],
    "appearances": ["appearance_id", "player_id", "game_id"],
    "games": ["game_id", "date", "competition_id"],
    "transfers": ["player_id", "transfer_date", "from_club_id", "to_club_id"],
    "clubs": ["club_id", "domestic_competition_id"],
}


def quote(identifier: str) -> str:
    """Quote a schema identifier after taking it from database metadata."""
    return '"' + identifier.replace('"', '""') + '"'


def scalar(connection: duckdb.DuckDBPyConnection, sql: str) -> object:
    return connection.execute(sql).fetchone()[0]


def inspect_table(connection: duckdb.DuckDBPyConnection, table: str) -> None:
    table_sql = quote(table)
    columns = connection.execute(f"PRAGMA table_info({table_sql})").fetchall()
    print(f"\n## {table}")
    print(f"rows: {scalar(connection, f'SELECT count(*) FROM {table_sql}'):,}")
    print("columns:")
    for _, name, data_type, not_null, default, is_primary_key in columns:
        tags = []
        if is_primary_key:
            tags.append("primary key")
        if not_null:
            tags.append("not null")
        suffix = f" ({', '.join(tags)})" if tags else ""
        print(f"  - {name}: {data_type}{suffix}")

    for column in KEY_COLUMNS.get(table, []):
        names = {row[1] for row in columns}
        if column not in names:
            continue
        col_sql = quote(column)
        nulls = scalar(
            connection,
            f"SELECT count(*) - count({col_sql}) FROM {table_sql}",
        )
        distinct = scalar(connection, f"SELECT count(DISTINCT {col_sql}) FROM {table_sql}")
        print(f"  {column}: {nulls:,} nulls; {distinct:,} distinct values")

    date_columns = [name for _, name, data_type, *_ in columns if "DATE" in data_type.upper()]
    for column in date_columns:
        col_sql = quote(column)
        earliest, latest = connection.execute(
            f"SELECT min({col_sql}), max({col_sql}) FROM {table_sql}"
        ).fetchone()
        print(f"  {column} range: {earliest} to {latest}")

    sample = connection.execute(f"SELECT * FROM {table_sql} LIMIT 2").fetchdf()
    print("sample:")
    print(sample.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="Path to the raw DuckDB artifact")
    args = parser.parse_args()

    with duckdb.connect(str(args.database), read_only=True) as connection:
        tables = [row[0] for row in connection.execute("SHOW TABLES").fetchall()]
        print("Read-only dataset inspection")
        print(f"tables ({len(tables)}): {', '.join(tables)}")
        for table in tables:
            inspect_table(connection, table)


if __name__ == "__main__":
    main()
