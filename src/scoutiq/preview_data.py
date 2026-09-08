"""Show real data rows so the dataset can be eyeballed, not just trusted.

Prints sample rows from the main tables, plus an optional player
lookup with their full valuation history.

Usage:
    python src/scoutiq/preview_data.py
    python src/scoutiq/preview_data.py "Bruno Fernandes"
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "interim"
    / "transfermarkt_datasets"
    / "transfermarkt.sqlite"
)

PREMIER_LEAGUE_CODE = "GB1"


def connect(db_path: Path) -> sqlite3.Connection:
    """Open the SQLite copy read-only so nothing can be modified."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def query_df(connection: sqlite3.Connection, sql: str, params=()) -> pd.DataFrame:
    """Run a query and return the result as a pandas DataFrame."""
    cursor = connection.execute(sql, params)
    columns = [desc[0] for desc in cursor.description]
    return pd.DataFrame(cursor.fetchall(), columns=columns)


def print_df(title: str, frame: pd.DataFrame) -> None:
    """Print a titled block of rows."""
    print(f"\n### {title}")
    print("-" * 70)
    print(frame.to_string(index=False))


def show_table_previews(connection: sqlite3.Connection) -> None:
    """One small sample from each important table."""
    print_df(
        "players (player profiles) - first 5",
        query_df(connection, """
            SELECT player_id, name, position, date_of_birth, height_in_cm
            FROM players LIMIT 5
        """),
    )

    print_df(
        "player_valuations (market value history) - first 5",
        query_df(connection, """
            SELECT player_id, date, market_value_in_eur, current_club_name,
                   player_club_domestic_competition_id
            FROM player_valuations LIMIT 5
        """),
    )

    print_df(
        "appearances (player performance per game) - first 5",
        query_df(connection, """
            SELECT game_id, player_id, date, competition_id,
                   goals, assists, minutes_played
            FROM appearances LIMIT 5
        """),
    )

    print_df(
        "transfers (movements and fees) - first 5",
        query_df(connection, """
            SELECT player_id, transfer_date, from_club_name, to_club_name,
                   transfer_fee, market_value_in_eur
            FROM transfers LIMIT 5
        """),
    )

    print_df(
        "games (match results) - PL only, first 5",
        query_df(connection, f"""
            SELECT game_id, date, season, home_club_name, away_club_name,
                   home_club_goals, away_club_goals
            FROM games
            WHERE competition_id = '{PREMIER_LEAGUE_CODE}'
            LIMIT 5
        """),
    )


def player_lookup(connection: sqlite3.Connection, name: str) -> None:
    """Show one player's profile and valuation history."""
    players = query_df(
        connection,
        """
        SELECT player_id, name, date_of_birth, position, height_in_cm
        FROM players
        WHERE LOWER(name) LIKE LOWER(?)
        """,
        (f"%{name}%",),
    ).head(5)

    if players.empty:
        print(f"\nNo player found matching '{name}'.")
        return

    print_df(f"player match for '{name}'", players)

    for player_id, display_name in players[["player_id", "name"]].values[:1]:
        history = query_df(connection, f"""
            SELECT date, market_value_in_eur, current_club_name
            FROM player_valuations
            WHERE player_id = {player_id}
            ORDER BY date
        """)
        print_df(f"valuation history of {display_name} (player_id={player_id})",
                 history)
        print(f"  -> {len(history)} valuation records")


def validation_checks(connection: sqlite3.Connection) -> None:
    """Quick sanity numbers to confirm the data is coherent."""
    checks = {
        "total valuations": "SELECT COUNT(*) FROM player_valuations",
        "distinct players": "SELECT COUNT(DISTINCT player_id) FROM players",
        "PL valuations": f"""
            SELECT COUNT(*) FROM player_valuations
            WHERE player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
        """,
        "valuations missing a value": """
            SELECT COUNT(*) FROM player_valuations
            WHERE market_value_in_eur IS NULL
        """,
        "appearances missing minutes": """
            SELECT COUNT(*) FROM appearances
            WHERE minutes_played IS NULL
        """,
    }
    print("\n### Validation checks")
    print("-" * 70)
    for label, sql in checks.items():
        value = connection.execute(sql).fetchone()[0]
        print(f"  {label:<35} {value:,}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DB_PATH)
    parser.add_argument("player_name", nargs="?", default=None,
                        help="optional: a player name to look up")
    args = parser.parse_args()

    with connect(args.database) as connection:
        show_table_previews(connection)
        validation_checks(connection)
        if args.player_name:
            player_lookup(connection, args.player_name)


if __name__ == "__main__":
    main()