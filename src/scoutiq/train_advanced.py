"""Advanced baseline: tree models and a richer feature set.

Features (beyond the original baseline):
  - age
  - age**2  (captures the inverted-U age-value relationship)
  - st_games, st_goals, st_assists
  - r10_minutes
  - height_in_cm
  - days_since_last_match  (median-imputed)

Two split strategies are compared:
  1. Calendar cut-off (train <= 2023-06-30, test >)
  2. Player-wise split: each player's most recent valuation goes to test,
     all earlier valuations go to train.

Models: LinearRegression, RandomForestRegressor, HistGradientBoostingRegressor.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

CSV_PATH = "data/processed/pl_valuation_features_v1.csv"
CUTOFF_DATE = pd.Timestamp("2023-06-30")


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add age**2 and median-impute days_since_last_match. Return a copy."""
    df = df.copy()
    df["age_sq"] = df["age"] ** 2
    median_days = df["days_since_last_match"].median()
    df["days_since_last_match"] = df["days_since_last_match"].fillna(median_days)
    return df


def make_player_wise_splits(df: pd.DataFrame):
    """Return (train, test) where each player's last valuation goes to test.

    For each player_id we sort by date descending, take the first row as test,
    the rest as train.
    """
    train_rows = []
    test_rows = []
    for pid, group in df.groupby("player_id"):
        group = group.sort_values("date", ascending=False)
        test_rows.append(group.iloc[0])       # most recent valuation
        train_rows.append(group.iloc[1:])     # older valuations
    train = pd.concat(train_rows).reset_index(drop=True)
    test = pd.concat(test_rows).reset_index(drop=True)
    return train, test


def evaluate(y_true, y_pred, label):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    print(f"  {label:>12s} | MAE: {mae:,.0f} | RMSE: {rmse:,.0f} | R2: {r2:.4f}")


def main():
    # ------------------------------------------------------------------
    # 1) Load data
    # ------------------------------------------------------------------
    df = pd.read_csv(CSV_PATH, dtype={"player_id": str, "date": str})
    df["date"] = pd.to_datetime(df["date"])
    y = df["market_value_in_eur"]               # raw target

    # ------------------------------------------------------------------
    # 2) Engineer a few extra features
    # ------------------------------------------------------------------
    df = add_engineered_features(df)

    # ------------------------------------------------------------------
    # 3) Feature column list (must be present after engineering)
    # ------------------------------------------------------------------
    feat_cols = [
        "age",
        "age_sq",
        "st_games",
        "st_goals",
        "st_assists",
        "r10_minutes",
        "height_in_cm",
        "days_since_last_match",
    ]

    # Keep only rows that have all features (drop NaNs)
    df = df.dropna(subset=feat_cols + ["market_value_in_eur"]).reset_index(drop=True)
    y = y.loc[df.index]
    X = df[feat_cols]

    # ------------------------------------------------------------------
    # 4) Build the two split strategies
    # ------------------------------------------------------------------
    # 4a) Calendar split
    train_cal = df[df["date"] <= CUTOFF_DATE].copy()
    test_cal = df[df["date"] > CUTOFF_DATE].copy()

    # 4b) Player-wise split (last valuation per player -> test)
    train_pw, test_pw = make_player_wise_splits(df)
    # Align columns – both train and test must have exactly the same feature columns
    train_pw = train_pw[feat_cols].reset_index(drop=True)
    test_pw = test_pw.reindex(columns=feat_cols).reset_index(drop=True)  # missing columns become NaN
    y_train_pw = y.loc[train_pw.index]
    y_test_pw = y.loc[test_pw.index]

    # ------------------------------------------------------------------
    # 5) Models
    # ------------------------------------------------------------------
    models = {
        "LinearReg": LinearRegression(),
        "RandomForest": RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1),
        "HistGBM": HistGradientBoostingRegressor(random_state=42),
    }

    # ----- Calendar split -----
    print("=== Calendar split (train <= 2023-06-30, test >) ===")
    X_train_cal = train_cal[feat_cols]
    X_test_cal = test_cal[feat_cols]
    y_train_cal = y.loc[train_cal.index]
    y_test_cal = y.loc[test_cal.index]

    for name, m in models.items():
        m.fit(X_train_cal, y_train_cal)
        pred = m.predict(X_test_cal)
        print("\nModel: %s" % name)
        evaluate(y_test_cal, pred, "test")

    # ----- Player-wise split -----
    print("\n\n=== Player-wise split (each player's last valuation -> test) ===")
    X_train_pw = train_pw[feat_cols]
    X_test_pw = test_pw[feat_cols]
    y_train_pw = y.loc[train_pw.index]
    y_test_pw = y.loc[test_pw.index]

    for name, m in models.items():
        m.fit(X_train_pw, y_train_pw)
        pred = m.predict(X_test_pw)
        print("\nModel: %s" % name)
        evaluate(y_test_pw, pred, "test")


if __name__ == "__main__":
    main()