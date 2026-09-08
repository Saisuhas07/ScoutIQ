"""Read-only deep-dive exploration of the historical dataset, on SQLite.

The same questions as explore_dataset.py, but written with sqlite3 and
portable SQL so it runs on a familiar engine. It is a read-only copy;
the data still comes straight from the raw artifact, never modified.

Small SQL dialect notes versus DuckDB:
  - year: strftime('%Y', date) instead of EXTRACT(YEAR FROM date)
  - age:  julianday arithmetic instead of DATEDIFF
  - median: SQLite has no MEDIAN, so it is computed with pandas
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
    """Open the SQLite copy read-only."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def query_df(connection: sqlite3.Connection, sql: str) -> pd.DataFrame:
    """Run a query and return the result as a pandas DataFrame."""
    cursor = connection.execute(sql)
    columns = [desc[0] for desc in cursor.description]
    return pd.DataFrame(cursor.fetchall(), columns=columns)


def section(connection: sqlite3.Connection, sql: str) -> None:
    """Run a query and print it with a simple separator."""
    print("-" * 60)
    print(query_df(connection, sql).to_string(index=False))


def question_1_temporal_coverage(connection: sqlite3.Connection) -> None:
    print("Q1. TEMPORAL COVERAGE OF KEY TABLES")

    section(connection, """
        SELECT
            'player_valuations' AS table_name,
            MIN(date) AS earliest,
            MAX(date) AS latest,
            COUNT(*) AS rows,
            COUNT(DISTINCT player_id) AS distinct_players
        FROM player_valuations
        UNION ALL
        SELECT
            'appearances' AS table_name,
            MIN(date),
            MAX(date),
            COUNT(*),
            COUNT(DISTINCT player_id)
        FROM appearances
        UNION ALL
        SELECT
            'games' AS table_name,
            MIN(date),
            MAX(date),
            COUNT(*),
            0
        FROM games
        ORDER BY table_name
    """)


def question_2_premier_league_coverage(connection: sqlite3.Connection) -> None:
    print("Q2. PREMIER LEAGUE (GB1) COVERAGE")

    section(connection, f"""
        SELECT
            'valuations' AS data,
            COUNT(*) AS rows,
            COUNT(DISTINCT player_id) AS distinct_players
        FROM player_valuations
        WHERE player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
        UNION ALL
        SELECT
            'appearances' AS data,
            COUNT(*),
            COUNT(DISTINCT player_id)
        FROM appearances
        WHERE competition_id = '{PREMIER_LEAGUE_CODE}'
        UNION ALL
        SELECT
            'games' AS data,
            COUNT(*),
            0
        FROM games
        WHERE competition_id = '{PREMIER_LEAGUE_CODE}'
    """)

    print("\n  valuations per season (year):")
    section(connection, f"""
        SELECT
            strftime('%Y', date) AS year,
            COUNT(*) AS n_valuations
        FROM player_valuations
        WHERE player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
        GROUP BY 1
        ORDER BY 1
    """)


def question_3_join_relationships(connection: sqlite3.Connection) -> None:
    print("Q3. JOIN RELATIONSHIPS")

    print("\n  valuations -> players (every valuation must resolve to a profile):")
    section(connection, """
        SELECT
            COUNT(*) AS total_valuations,
            COUNT(p.player_id) AS matched_to_players,
            COUNT(*) - COUNT(p.player_id) AS unmatched
        FROM player_valuations AS pv
        LEFT JOIN players AS p USING (player_id)
    """)

    print("\n  games -> competitions (how many games have no competition metadata):")
    section(connection, """
        SELECT
            COUNT(*) AS total_games,
            COUNT(g.competition_id) AS matched_to_games,
            COUNT(*) - COUNT(g.competition_id) AS unmatched
        FROM games AS g
        LEFT JOIN competitions AS c USING (competition_id)
    """)

    print("\n  PL clubs (are there distinct club IDs?):")
    section(connection, f"""
        SELECT COUNT(*) AS n_club_rows,
               COUNT(DISTINCT club_id) AS n_distinct_clubs
        FROM clubs
        WHERE domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
    """)


def question_4_temporal_join_feasibility(connection: sqlite3.Connection) -> None:
    print("Q4. TEMPORAL JOIN: performance BEFORE valuation")

    print("""\n  For a prediction problem we can only use appearances that happened
  BEFORE the valuation date. This counts how many appearance-valuation
  pairs fall on the correct side of the timeline for every PL player:""")
    section(connection, f"""
        SELECT
            COUNT(*) AS total_pairs,
            SUM(CASE WHEN a.date < pv.date THEN 1 ELSE 0 END) AS before_valuation,
            SUM(CASE WHEN a.date > pv.date THEN 1 ELSE 0 END) AS after_valuation
        FROM appearances AS a
        JOIN player_valuations AS pv USING (player_id)
        WHERE a.competition_id = '{PREMIER_LEAGUE_CODE}'
          AND pv.player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
    """)

    print("\n  Distinct PL players with at least one prior performance row:")
    section(connection, f"""
        SELECT COUNT(DISTINCT a.player_id) AS pl_players_with_prior_performance
        FROM appearances AS a
        JOIN player_valuations AS pv USING (player_id)
        WHERE a.competition_id = '{PREMIER_LEAGUE_CODE}'
          AND pv.player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
          AND a.date < pv.date
    """)

    print("\n  Distinct PL players with a valuation record (the pool we can score):")
    section(connection, f"""
        SELECT COUNT(DISTINCT player_id) AS pl_players_with_valuation
        FROM player_valuations
        WHERE player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
    """)

    print("\n  Ages observed across all valuations:")
    section(connection, """
        SELECT
            CAST(MIN((julianday(pv.date) - julianday(p.date_of_birth)) / 365.25) AS INTEGER) AS min_age,
            CAST(MAX((julianday(pv.date) - julianday(p.date_of_birth)) / 365.25) AS INTEGER) AS max_age,
            CAST(AVG((julianday(pv.date) - julianday(p.date_of_birth)) / 365.25) AS INTEGER) AS avg_age
        FROM player_valuations AS pv
        JOIN players AS p USING (player_id)
        WHERE p.date_of_birth IS NOT NULL
    """)


def question_5_market_value_target(connection: sqlite3.Connection) -> None:
    print("Q5. MARKET VALUE TARGET DISTRIBUTION")

    print("\n  Global distribution:")
    section(connection, """
        SELECT
            COUNT(*) AS n,
            MIN(market_value_in_eur) AS min_value,
            MAX(market_value_in_eur) AS max_value,
            CAST(AVG(market_value_in_eur) AS INTEGER) AS avg_value
        FROM player_valuations
        WHERE market_value_in_eur > 0
    """)

    print("\n  Premier League distribution:")
    section(connection, f"""
        SELECT
            COUNT(*) AS n,
            MIN(market_value_in_eur) AS min_value,
            MAX(market_value_in_eur) AS max_value,
            CAST(AVG(market_value_in_eur) AS INTEGER) AS avg_value
        FROM player_valuations
        WHERE market_value_in_eur > 0
          AND player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
    """)

    # SQLite has no MEDIAN() function, so we compute it with pandas.
    global_values = query_df(
        connection,
        "SELECT market_value_in_eur FROM player_valuations WHERE market_value_in_eur > 0",
    )
    pl_values = query_df(
        connection,
        f"""SELECT market_value_in_eur FROM player_valuations
            WHERE market_value_in_eur > 0
              AND player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'""",
    )
    print(f"  median (global)   : {global_values['market_value_in_eur'].median():,.0f}")
    print(f"  median (Premier L.): {pl_values['market_value_in_eur'].median():,.0f}")

    print("\n  How often do players get re-valued (panel density)?")
    section(connection, f"""
        SELECT
            CASE
                WHEN n <= 1 THEN '1'
                WHEN n <= 5 THEN '2-5'
                WHEN n <= 10 THEN '6-10'
                WHEN n <= 20 THEN '11-20'
                ELSE '21+'
            END AS valuations_per_player,
            COUNT(*) AS n_players,
            SUM(n) AS total_valuations
        FROM (
            SELECT player_id, COUNT(*) AS n
            FROM player_valuations
            WHERE player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
            GROUP BY player_id
        )
        GROUP BY 1
        ORDER BY MIN(n)
    """)


def question_6_missing_data(connection: sqlite3.Connection) -> None:
    print("Q6. MISSING DATA")

    print("\n  players:")
    section(connection, """
        SELECT
            COUNT(*) AS total,
            COUNT(*) - COUNT(date_of_birth) AS missing_dob,
            COUNT(*) - COUNT(position) AS missing_position,
            COUNT(*) - COUNT(height_in_cm) AS missing_height,
            COUNT(*) - COUNT(foot) AS missing_foot
        FROM players
    """)

    print("\n  appearances:")
    section(connection, """
        SELECT
            COUNT(*) AS total,
            COUNT(*) - COUNT(minutes_played) AS missing_minutes,
            COUNT(*) - COUNT(goals) AS missing_goals,
            COUNT(*) - COUNT(assists) AS missing_assists
        FROM appearances
    """)

    print("\n  valuations (the target):")
    section(connection, f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) - COUNT(market_value_in_eur) AS missing_value,
            COUNT(*) - COUNT(date) AS missing_date,
            COUNT(*) - COUNT(current_club_id) AS missing_club
        FROM player_valuations
        WHERE player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
    """)

    print("\n  transfers:")
    section(connection, """
        SELECT
            COUNT(*) AS total_transfers,
            SUM(CASE WHEN transfer_fee IS NULL THEN 1 ELSE 0 END) AS null_fee,
            SUM(CASE WHEN transfer_fee = 0 THEN 1 ELSE 0 END) AS zero_fee,
            SUM(CASE WHEN transfer_fee > 0 THEN 1 ELSE 0 END) AS positive_fee,
            COUNT(*) - COUNT(market_value_in_eur) AS missing_market_value
        FROM transfers
    """)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=DB_PATH,
        help="Path to the SQLite copy",
    )
    args = parser.parse_args()

    with connect(args.database) as connection:
        question_1_temporal_coverage(connection)
        question_2_premier_league_coverage(connection)
        question_3_join_relationships(connection)
        question_4_temporal_join_feasibility(connection)
        question_5_market_value_target(connection)
        question_6_missing_data(connection)


if __name__ == "__main__":
    main()