"""Build a candidate ML dataset: one row per Premier League valuation.

Each row is one player at one valuation date. Every performance feature
is computed only from appearances strictly BEFORE that valuation date,
so no information from the future can leak into the row.

The output is a flat CSV in data/processed/ so it can be inspected
directly or loaded into pandas later for modelling.
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
OUT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "processed"
    / "pl_valuation_features_v1.csv"
)

PREMIER_LEAGUE_CODE = "GB1"


def connect(db_path: Path) -> sqlite3.Connection:
    """Open the SQLite copy read-only."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def load_appearances(connection: sqlite3.Connection) -> pd.DataFrame:
    """Load Premier League appearances as rows per player per game."""
    df = pd.read_sql_query(
        f"""
        SELECT player_id, game_id, date, goals, assists, minutes_played
        FROM appearances
        WHERE competition_id = '{PREMIER_LEAGUE_CODE}'
        """,
        connection,
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_valuations(connection: sqlite3.Connection) -> pd.DataFrame:
    """Load Premier League valuations (the prediction target holder)."""
    df = pd.read_sql_query(
        f"""
        SELECT
            player_id,
            date,
            market_value_in_eur,
            current_club_id
        FROM player_valuations
        WHERE player_club_domestic_competition_id = '{PREMIER_LEAGUE_CODE}'
        """,
        connection,
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_players(connection: sqlite3.Connection) -> pd.DataFrame:
    """Load the fixed player profile fields we trust as always-known."""
    df = pd.read_sql_query(
        """
        SELECT player_id, date_of_birth, position, height_in_cm
        FROM players
        """,
        connection,
    )
    df["date_of_birth"] = pd.to_datetime(df["date_of_birth"])
    return df


def season_year(dates: pd.Series) -> pd.Series:
    """Map a date to its football season start year.

    We treat a season as starting in July: anything from July onwards
    belongs to the season that begins that year; anything before July
    belongs to the previous season. So 2024-03 is season 2023 and
    2024-09 is season 2024.
    """
    year = dates.dt.year
    month = dates.dt.month
    return year.where(month >= 7, year - 1)


def summarize(pairs: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Aggregate appearance groups into per-valuation totals.

    pairs     : appearances already filtered to one window, with
                date_v being the valuation date for that observation.
    prefix    : short name for the window, e.g. 'st' for season-to-date.
    """
    grouped = (
        pairs.groupby(["player_id", "date_v"])
        .agg(
            games=("game_id", "count"),
            goals=("goals", "sum"),
            assists=("assists", "sum"),
            minutes=("minutes_played", "sum"),
        )
        .reset_index()
        .rename(columns={"date_v": "date"})
    )
    grouped.columns = ["player_id", "date"] + [
        f"{prefix}_{column}" for column in grouped.columns[2:]
    ]
    return grouped


def compute_performance_features(
    appearances: pd.DataFrame, valuations: pd.DataFrame
) -> pd.DataFrame:
    """Build the performance feature block, one row per valuation.

    Approach:
      1. Join every appearance to every future valuation of that player.
      2. Keep only appearances strictly BEFORE the valuation date.
      3. Split by window (current season, prior season, last 10 games)
         and sum each window into one row per valuation.
      4. Also record days since the player's last match.
    """
    pairs = appearances.merge(
        valuations[["player_id", "date"]],
        on="player_id",
        suffixes=("_a", "_v"),
    )
    pairs = pairs[pairs["date_a"] < pairs["date_v"]].copy()
    pairs["season_a"] = season_year(pairs["date_a"])
    pairs["season_v"] = season_year(pairs["date_v"])

    current_season = summarize(
        pairs[pairs["season_a"] == pairs["season_v"]], "st"
    )
    prior_season = summarize(
        pairs[pairs["season_a"] == pairs["season_v"] - 1], "ps"
    )

    recent = pairs.sort_values(
        ["player_id", "date_v", "date_a"], ascending=[True, True, False]
    )
    recent["rank_in_window"] = recent.groupby(["player_id", "date_v"]).cumcount()
    recent_ten = summarize(recent[recent["rank_in_window"] < 10], "r10")

    last_match = (
        pairs.sort_values(["player_id", "date_v", "date_a"])
        .groupby(["player_id", "date_v"])["date_a"]
        .last()
        .reset_index()
        .rename(columns={"date_a": "last_match_date"})
    )
    last_match["days_since_last_match"] = (
        last_match["date_v"] - last_match["last_match_date"]
    ).dt.days

    base = valuations[["player_id", "date"]]
    for block in (current_season, prior_season, recent_ten):
        base = base.merge(block, on=["player_id", "date"], how="left")
    base = base.merge(
        last_match[["player_id", "date_v", "last_match_date", "days_since_last_match"]],
        left_on=["player_id", "date"],
        right_on=["player_id", "date_v"],
        how="left",
    )
    base = base.drop(columns=["date_v"])

    # Windows with no appearances at all are truly zero, not missing.
    for column in [c for c in base.columns if c.startswith(("st_", "ps_", "r10_"))]:
        base[column] = base[column].fillna(0)
    return base


def build_static_features(
    players: pd.DataFrame, valuations: pd.DataFrame
) -> pd.DataFrame:
    """Attach fixed profile fields plus age at the valuation date."""
    static = valuations[["player_id", "date"]].merge(
        players[["player_id", "date_of_birth", "position", "height_in_cm"]],
        on="player_id",
        how="left",
    )
    static["age"] = (
        static["date"] - static["date_of_birth"]
    ).dt.days / 365.25
    return static[["player_id", "date", "age", "position", "height_in_cm"]]


def report_leakage_check(features: pd.DataFrame) -> None:
    """Sanity check that no future performance could be in the rows.

    We prove it by reporting, for each valuation, the single most recent
    appearance date that contributed a feature, and confirming it is
    always before the valuation date.
    """
    print("\nLeakage check (max appearance date used per valuation):")
    print(f"  rows checked      : {len(features):,}")
    after = (features["last_match_date"] > features["date"]).sum()
    print(f"  rows using a future match : {after}")
    print("  => PASS (strictly BEFORE verified by construction)" if after == 0
          else "  => FAIL")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DB_PATH)
    parser.add_argument("--output", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    with connect(args.database) as connection:
        appearances = load_appearances(connection)
        valuations = load_valuations(connection)
        players = load_players(connection)
        print(f"appearances (PL) : {len(appearances):,}")
        print(f"valuations (PL)  : {len(valuations):,}")
        print(f"players          : {len(players):,}")

        performance = compute_performance_features(appearances, valuations)
        static = build_static_features(players, valuations)

        dataset = (
            valuations.merge(static, on=["player_id", "date"])
            .merge(performance, on=["player_id", "date"])
        )
        dataset["season_v"] = season_year(dataset["date"]).astype(int)

    dataset = dataset.sort_values(["player_id", "date"]).reset_index(drop=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(args.output, index=False)

    print(f"\nDataset rows: {len(dataset):,}")
    print(f"Columns: {list(dataset.columns)}")
    print("\nSample (Bruno-ish row, latest valuation per player):")
    latest = dataset.sort_values("date").groupby("player_id").tail(1)
    print(latest[["player_id", "date", "age", "position",
                  "st_games", "st_goals", "st_assists",
                  "r10_minutes", "market_value_in_eur"]]
          .tail(5).to_string(index=False))

    report_leakage_check(dataset)

    no_history = (dataset["st_games"] == 0).mean()
    print(f"\nShare of PL valuations with no prior PL appearance: {no_history:.1%}")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()