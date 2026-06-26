"""
Adds trailing_4q_beat_rate to earnings_history.csv and joins sector from
earnings_screener_results.csv.

For each row: fraction of "beat" outcomes across the up-to-4 most recent
quarters for that same ticker BEFORE this earnings_date. Strictly no
look-ahead: shift(1) ensures the current event is never in its own window.

min_periods=2: rows with fewer than 2 prior quarters are dropped, since a
single data point is too noisy to be a reliable feature.
"""

import pandas as pd

HISTORY_CSV  = "earnings_history.csv"
SCREENER_CSV = "earnings_screener_results.csv"
OUTPUT_CSV   = "earnings_history.csv"
MIN_PERIODS  = 2


def main():
    df = pd.read_csv(HISTORY_CSV, parse_dates=["earnings_date"])
    df = df.sort_values(["ticker", "earnings_date"]).reset_index(drop=True)

    rows_before = len(df)

    # Join sector
    sector_map = (
        pd.read_csv(SCREENER_CSV)[["ticker", "sector"]]
        .drop_duplicates(subset="ticker")
    )
    df = df.merge(sector_map, on="ticker", how="left")

    # Recompute trailing beat rate with min_periods=2
    df["is_beat"] = (df["beat_miss_meet"] == "beat").astype(float)
    df["trailing_4q_beat_rate"] = (
        df.groupby("ticker")["is_beat"]
        .transform(lambda s: s.shift(1).rolling(4, min_periods=MIN_PERIODS).mean())
        .round(2)
    )
    df = df.drop(columns=["is_beat"])

    # Count drops per ticker before filtering
    dropped_per_ticker = (
        df[df["trailing_4q_beat_rate"].isna()]
        .groupby("ticker").size()
        .rename("dropped_rows")
    )

    df = df.dropna(subset=["trailing_4q_beat_rate"]).reset_index(drop=True)
    rows_after = len(df)

    df = df[["ticker", "sector", "earnings_date", "eps_estimate", "eps_actual",
             "beat_miss_meet", "trailing_4q_beat_rate"]]
    df["earnings_date"] = df["earnings_date"].dt.strftime("%Y-%m-%d")
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"Rows before filter : {rows_before}")
    print(f"Rows dropped       : {rows_before - rows_after}  (< {MIN_PERIODS} prior quarters)")
    print(f"Rows after filter  : {rows_after}")
    print(f"\nDropped per ticker:")
    print(dropped_per_ticker.to_string())
    print(f"\nWritten {rows_after} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
