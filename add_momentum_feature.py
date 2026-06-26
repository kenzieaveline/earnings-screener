"""
Adds pre_earnings_30d_momentum to earnings_history.csv.

For each row: closing price % change from the nearest trading day on or before
(earnings_date - 30 calendar days) to the last trading day BEFORE earnings_date.
No look-ahead: the earnings date itself is never included in the window.

Price history is fetched once per ticker (start="2013-01-01") for efficiency,
then sliced per earnings event in-memory.
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


def fetch_history(ticker: str) -> pd.DataFrame | None:
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(start="2013-01-01")[["Close"]].dropna()
        if hist.empty:
            return None
        # Strip timezone so comparisons against naive CSV dates work
        hist.index = hist.index.tz_convert(None).normalize()
        return hist
    except Exception:
        return None


def compute_momentum(hist: pd.DataFrame, earnings_date: str) -> tuple[float | None, dict]:
    earnings_ts  = pd.Timestamp(earnings_date)
    start_target = earnings_ts - timedelta(days=30)

    before = hist[hist.index < earnings_ts]
    if before.empty:
        return None, {}

    at_start = before[before.index <= start_target]
    if at_start.empty:
        return None, {}

    price_end   = float(before["Close"].iloc[-1])
    price_start = float(at_start["Close"].iloc[-1])
    end_date    = before.index[-1]
    start_date  = at_start.index[-1]

    momentum = round((price_end - price_start) / price_start * 100, 2)
    return momentum, {
        "start_date":  start_date.strftime("%Y-%m-%d"),
        "end_date":    end_date.strftime("%Y-%m-%d"),
        "price_start": round(price_start, 2),
        "price_end":   round(price_end, 2),
    }


def main():
    df = pd.read_csv(INPUT_CSV)
    tickers = df["ticker"].unique()

    print(f"[*] Fetching price history for {len(tickers)} tickers (one request each)...")
    histories = {}
    for i, ticker in enumerate(tickers, 1):
        hist = fetch_history(ticker)
        histories[ticker] = hist
        n = len(hist) if hist is not None else 0
        print(f"  [{i:>2}/{len(tickers)}] {ticker:<8}  {n} trading days")
        time.sleep(REQUEST_DELAY_SEC)

    print(f"\n[*] Computing pre_earnings_30d_momentum for {len(df)} rows...")
    momentums = []
    for _, row in df.iterrows():
        hist = histories.get(row["ticker"])
        if hist is None:
            momentums.append(None)
            continue
        mom, _ = compute_momentum(hist, row["earnings_date"])
        momentums.append(mom)

    df["pre_earnings_30d_momentum"] = momentums
    n_missing = df["pre_earnings_30d_momentum"].isna().sum()
    print(f"  Computed: {len(df) - n_missing}/{len(df)}  ({n_missing} returned None)")

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"  Written to {OUTPUT_CSV}\n")

    # Verification: recompute 4 examples and show the full date window explicitly
    print("=== Verification ===")
    print("  start_date : nearest trading day ON OR BEFORE (earnings_date - 30 cal days)")
    print("  end_date   : last trading day BEFORE earnings_date (earnings date excluded)\n")

    examples = [("AMZN", 3), ("KO", 5), ("BA", 2), ("TSLA", 4)]
    for ticker, nth in examples:
        hist = histories.get(ticker)
        sub  = df[df["ticker"] == ticker].reset_index(drop=True)
        if hist is None or nth >= len(sub):
            continue
        row = sub.iloc[nth]
        _, dbg = compute_momentum(hist, row["earnings_date"])
        if not dbg:
            continue

        target_start  = (pd.Timestamp(row["earnings_date"]) - timedelta(days=30)).strftime("%Y-%m-%d")
        days_gap      = (pd.Timestamp(row["earnings_date"]) - pd.Timestamp(dbg["end_date"])).days
        window_span   = (pd.Timestamp(dbg["end_date"]) - pd.Timestamp(dbg["start_date"])).days

        print(f"  {ticker}  earnings_date={row['earnings_date']}")
        print(f"    target start (earnings - 30d) = {target_start}")
        print(f"    actual start_date             = {dbg['start_date']}  price=${dbg['price_start']:.2f}")
        print(f"    actual end_date               = {dbg['end_date']}  price=${dbg['price_end']:.2f}  ({days_gap} cal day(s) before earnings)")
        print(f"    window span                   = {window_span} calendar days")
        print(f"    pre_earnings_30d_momentum     = {row['pre_earnings_30d_momentum']}%")
        print()


if __name__ == "__main__":
    main()
