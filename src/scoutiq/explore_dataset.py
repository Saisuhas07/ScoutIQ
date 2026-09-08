"""Read-only deep-dive exploration of the Day 2 historical dataset.

Answers the specific Day 2 questions that a schema listing alone cannot:

1.  What is the temporal coverage of each key table?
2.  How much Premier League (GB1) data do we have?
3.  Can appearances be joined to games and players?
4.  Is the temporal join (performance BEFORE valuation) feasible?
5.  What does the market-value target look like?
6.  Where is data missing?

This script NEVER cleans, joins into a training set, or models. It only
inspects. Queries are intentionally simple and readable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

DB_PATH = (
    r"C:\Users\HP\OneDrive - vit.ac.in\Desktop\ScoutIQ"
    r"\data\raw\transfermarkt_datasets\transfermarkt-datasets.duckdb"
)

PREMIER_LEAGUE_CODE = "GB1"


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Open the raw DuckDB artifact read-only so it can never be modified."""
    return duckdb.connect(str(db_path), read_only=True)


def section(connection: duckdb.DuckDBPyConnection, sql: str) -> None:
    """Run a query and print it with a simple line separator."""
    print("-" * 60)
    print(connection.execute(sql).fetchdf().to_string(index=False))


def question_1_temporal_coverage(connection: duckdb.DuckDBPyConnection) -> None:
    print("Q1. TEMPORAL COVERAGE OF KEY TABLES")

    section(connection, """
        SELECT
            'player_valuations' AS table_name,
            CAST(MIN(date) AS VARCHAR) AS earliest,
            CAST(MAX(date) AS VARCHAR) AS latest,
            COUNT(*) AS rows,
            COUNT(DISTINCT player_id) AS distinct_players
        FROM player_valuations
        UNION ALL
        SELECT
            'appearances' AS table_name,
            CAST(MIN(date) AS VARCHAR),
            CAST(MAX(date) AS VARCHAR),
            COUNT(*),
            COUNT(DISTINCT player_id)
        FROM appearances
        UNION ALL
        SELECT
            'games' AS table_name,
            CAST(MIN(date) AS VARCHAR),
            CAST(MAX(date) AS VARCHAR),
            COUNT(*),
            0
        FROM games
        ORDER BY table_name
    """)


def question_2_premier_league_coverage(connection: duckdb.DuckDBPyConnection) -> None:
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
            EXTRACT(YEAR FROM date) AS year,
            COUNT(*) AS n_valuations
        FROM player_valuations
        WHERE player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
        GROUP BY EXTRACT(YEAR FROM date)
        ORDER BY year
    """)


def question_3_join_relationships(connection: duckdb.DuckDBPyConnection) -> None:
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
            COUNT(g.competition_id) AS matched_to_players,
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


def question_4_temporal_join_feasibility(connection: duckdb.DuckDBPyConnection) -> None:
    print("Q4. TEMPORAL JOIN: performance BEFORE valuation")

    print("""\n  For a prediction problem we can only use appearances that happened
  BEFORE the valuation date. This query counts how many appearance-valuation
  pairs fall on the correct side of the timeline for every PL player:""")
    section(connection, f"""
        SELECT
            COUNT(*) AS total_pairs,
            COUNT(*) FILTER (WHERE a.date < pv.date) AS before_valuation,
            COUNT(*) FILTER (WHERE a.date > pv.date) AS after_valuation
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

    print("\n  Same player comparison: ages observed in valuations")
    section(connection, """
        SELECT
            MIN(DATEDIFF('year', p.date_of_birth, pv.date)) AS min_age,
            MAX(DATEDIFF('year', p.date_of_birth, pv.date)) AS max_age,
            AVG(DATEDIFF('year', p.date_of_birth, pv.date)) AS avg_age
        FROM player_valuations AS pv
        JOIN players AS p USING (player_id)
        WHERE p.date_of_birth IS NOT NULL
    """)


def question_5_market_value_target(connection: duckdb.DuckDBPyConnection) -> None:
    print("Q5. MARKET VALUE TARGET DISTRIBUTION")

    print("\n  Global distribution:")
    section(connection, """
        SELECT
            COUNT(*) AS n,
            MIN(market_value_in_eur) AS min_value,
            MAX(market_value_in_eur) AS max_value,
            ROUND(AVG(market_value_in_eur)) AS avg_value,
            MEDIAN(market_value_in_eur) AS median_value
        FROM player_valuations
        WHERE market_value_in_eur > 0
    """)

    print("\n  Premier League distribution:")
    section(connection, f"""
        SELECT
            COUNT(*) AS n,
            MIN(market_value_in_eur) AS min_value,
            MAX(market_value_in_eur) AS max_value,
            ROUND(AVG(market_value_in_eur)) AS avg_value,
            MEDIAN(market_value_in_eur) AS median_value
        FROM player_valuations
        WHERE market_value_in_eur > 0
          AND player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
    """)

    print("\n  How often do players get re-valued per year (panel density)?")
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


def question_6_missing_data(connection: duckdb.DuckDBPyConnection) -> None:
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

    print("\n  valuations (target):")
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
            COUNT(*) FILTER (WHERE transfer_fee IS NULL) AS null_fee,
            COUNT(*) FILTER (WHERE transfer_fee = 0) AS zero_fee,
            COUNT(*) FILTER (WHERE transfer_fee > 0) AS positive_fee,
            COUNT(*) - COUNT(market_value_in_eur) AS missing_market_value
        FROM transfers
    """)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=DB_PATH,
        help="Path to the raw DuckDB artifact",
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