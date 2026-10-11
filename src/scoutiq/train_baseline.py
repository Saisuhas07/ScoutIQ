"""Linear Regression baseline on the temporal ML dataset.

Reads the CSV built by `build_temporal_dataset.py`, creates a log-target,
splits temporally (train on earlier valuations, test on later ones),
trains a plain LinearRegression and reports MAE / RMSE / R^2.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

CSV_PATH = "data/processed/pl_valuation_features_v1.csv"
# Cut-off date: train on valuations up to this date, test on later ones.
TRAIN_CUTOFF = pd.Timestamp("2023-06-30")


def main() -> None:
    df = pd.read_csv(CSV_PATH, dtype={"player_id": str, "date": str})
    # parse dates
    df["date"] = pd.to_datetime(df["date"])
    # log-transform the target (keeps original column for reference)
    df["log_market_value"] = np.log(df["market_value_in_eur"])

    # Simple feature set – expand later
    features = [
        "age",
        "st_games",
        "st_goals",
        "st_assists",
        "r10_minutes",
        "height_in_cm",
    ]
    # Encode position as integer codes (tree models can handle later)
    df["position_code"] = df["position"].astype("category").cat.codes

    X = df[features + ["position_code"]].copy()
    y_raw = df["market_value_in_eur"]
    y_log = df["log_market_value"]

    # Drop rows with any missing feature / target values so LinearRegression can fit
    subset = features + ["position_code", "market_value_in_eur"]
    df_clean = df.dropna(subset=subset)

    # Re-index clean data to preserve original index alignment later
    X = df_clean[features + ["position_code"]].copy()
    y_raw = df_clean["market_value_in_eur"]
    y_log = df_clean["log_market_value"]

    # Temporal split: train on earlier dates, test on later dates
    train = df_clean[df_clean["date"] <= TRAIN_CUTOFF]
    test = df_clean[df_clean["date"] > TRAIN_CUTOFF]

    X_train = X.loc[train.index]
    X_test = X.loc[test.index]
    y_train_raw = y_raw.loc[train.index]
    y_test_raw = y_raw.loc[test.index]
    y_train_log = y_log.loc[train.index]
    y_test_log = y_log.loc[test.index]

    # ----- baseline on raw market value -----
    model_raw = LinearRegression()
    model_raw.fit(X_train, y_train_raw)
    pred_raw = model_raw.predict(X_test)
    mae_raw = mean_absolute_error(y_test_raw, pred_raw)
    rmse_raw = np.sqrt(mean_squared_error(y_test_raw, pred_raw))
    r2_raw = r2_score(y_test_raw, pred_raw)

    # ----- baseline on log-transformed target, back-transformed to EUR -----
    model_log = LinearRegression()
    model_log.fit(X_train, y_train_log)
    pred_log_exp = np.exp(model_log.predict(X_test))  # back-transform to euros
    mae_log = mean_absolute_error(y_test_raw, pred_log_exp)
    rmse_log = np.sqrt(mean_squared_error(y_test_raw, pred_log_exp))
    r2_log = r2_score(y_test_raw, pred_log_exp)

    print("=== Linear Regression baseline (raw target) ===")
    print(f"Train rows: {len(train):,} | Test rows: {len(test):,}")
    print(f"Features used: {features + ['position_code']}")
    print(f"MAE (EUR): {mae_raw:,.0f}")
    print(f"RMSE (EUR): {rmse_raw:,.0f}")
    print(f"R^2 (raw): {r2_raw:.4f}\n")

    print("=== Linear Regression baseline (log-target, back-transformed) ===")
    print(f"MAE (EUR, log-back): {mae_log:,.0f}")
    print(f"RMSE (EUR, log-back): {rmse_log:,.0f}")
    print(f"R^2 (log-back): {r2_log:.4f}")


if __name__ == "__main__":
    main()