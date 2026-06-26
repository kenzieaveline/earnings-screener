"""
Adds net_analyst_rating_change_90d to earnings_history.csv.

For each row: (# upgrades - # downgrades) in the 90 calendar days strictly
before earnings_date, using yfinance upgrades_downgrades Action column.
Only 'up' and 'down' are counted; 'main', 'reit', 'init' are skipped.

NaN when the 90-day window start (earnings_date - 90d) predates the earliest
available data for that ticker — no guessing, no partial-window imputation.
Coverage varies per ticker (e.g. AMZN from 2019-10-25, KO from 2012-02-08).

upgrades_downgrades is fetched once per ticker for efficiency.
"""

import time
import warnings
from datetime import timedelta

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

INPUT_CSV         = "earnings_history.csv"
OUTPUT_CSV        = "earnings_history.csv"
REQUEST_DELAY_SEC = 0.4


def fetch_ud(ticker: str) -> pd.DataFrame | None:
    try:
        tk = yf.Ticker(ticker)
        ud = tk.upgrades_downgrades
        if ud is None or ud.empty:
            return None
        ud = ud[["Action"]].copy()
        if ud.index.tz is not None:
            ud.index = ud.index.tz_convert(None)
        return ud
    except Exception:
        return None


def compute_net_rating_change(ud: pd.DataFrame, earnings_date: str) -> int | None:
    earnings_ts  = pd.Timestamp(earnings_date)
    window_start = earnings_ts - timedelta(days=90)

    if window_start < ud.index.min():
        return None

    window     = ud[(ud.index >= window_start) & (ud.index < earnings_ts)]
    upgrades   = (window["Action"] == "up").sum()
    downgrades = (window["Action"] == "down").sum()
    return int(upgrades - downgrades)


def main():
    df      = pd.read_csv(INPUT_CSV)
    tickers = df["ticker"].unique()

    print(f"[*] Fetching upgrades_downgrades for {len(tickers)} tickers...")
    ud_map = {}
    for i, ticker in enumerate(tickers, 1):
        ud = fetch_ud(ticker)
        ud_map[ticker] = ud
        if ud is not None:
            print(f"  [{i:>2}/{len(tickers)}] {ticker:<8}  {len(ud):>4} rows  "
                  f"{ud.index.min().date()} to {ud.index.max().date()}")
        else:
            print(f"  [{i:>2}/{len(tickers)}] {ticker:<8}  no data")
        time.sleep(REQUEST_DELAY_SEC)

    print(f"\n[*] Computing net_analyst_rating_change_90d for {len(df)} rows...")
    values = []
    for _, row in df.iterrows():
        ud = ud_map.get(row["ticker"])
        if ud is None:
            values.append(None)
            continue
        values.append(compute_net_rating_change(ud, row["earnings_date"]))

    df["net_analyst_rating_change_90d"] = values

    n_valid = df["net_analyst_rating_change_90d"].notna().sum()
    n_nan   = df["net_analyst_rating_change_90d"].isna().sum()

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"  Valid (real value) : {n_valid}")
    print(f"  NaN (pre-coverage) : {n_nan}")
    print(f"  Written to {OUTPUT_CSV}\n")

    # ── Verification ─────────────────────────────────────────────────────────
    print("=== Verification ===")
    print("  window = [earnings_date - 90d, earnings_date)  — earnings_date excluded")
    print("  NaN when window_start < ticker's earliest upgrades_downgrades date\n")

    # Deliberately pick: 2 rows with valid coverage, 2 that should be NaN
    examples = [
        ("TSLA", 30, "valid — TSLA coverage from 2019-02-11"),
        ("KO",    3, "valid — KO coverage from 2012, so even early rows are covered"),
        ("AMZN",  1, "NaN  — AMZN coverage only from 2019-10-25; row 1 is ~2014"),
        ("TSLA",  0, "NaN  — TSLA coverage from 2019-02-11; row 0 is ~2014"),
    ]
    for ticker, nth, note in examples:
        ud  = ud_map.get(ticker)
        sub = df[df["ticker"] == ticker].reset_index(drop=True)
        if ud is None or nth >= len(sub):
            continue
        row          = sub.iloc[nth]
        earnings_ts  = pd.Timestamp(row["earnings_date"])
        window_start = earnings_ts - timedelta(days=90)
        window_end   = earnings_ts - timedelta(days=1)

        window     = ud[(ud.index >= window_start) & (ud.index < earnings_ts)]
        upgrades   = int((window["Action"] == "up").sum())
        downgrades = int((window["Action"] == "down").sum())

        val = row["net_analyst_rating_change_90d"]
        val_str = str(int(val)) if pd.notna(val) else "NaN"

        print(f"  {ticker}  earnings_date={row['earnings_date']}  [{note}]")
        print(f"    ticker coverage start  = {ud.index.min().date()}")
        print(f"    window                 = [{window_start.date()} to {window_end.date()}]")
        print(f"    window_start < coverage: {window_start.date() < ud.index.min().date()}")
        print(f"    upgrades={upgrades}  downgrades={downgrades}  net={val_str}")
        print()


if __name__ == "__main__":
    main()
