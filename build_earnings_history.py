"""
Build a labelled historical earnings dataset for the beat-probability classifier (FR-6.1).

Takes the 30 largest-cap tickers from earnings_screener_results.csv, pulls full
earnings history via yfinance, and writes earnings_history.csv with one row per
historical quarter that has both an EPS estimate and a reported EPS.
"""

import time
import warnings
from datetime import datetime

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

INPUT_CSV   = "earnings_screener_results.csv"
OUTPUT_CSV  = "earnings_history.csv"
N_TICKERS   = 30
HISTORY_LIMIT = 40   # quarters to request; yfinance will return what it has
REQUEST_DELAY_SEC = 0.4
MIN_QUARTERS_USEFUL = 4


def fetch_earnings_history(ticker: str) -> list[dict]:
    try:
        tk = yf.Ticker(ticker)
        ed = tk.get_earnings_dates(limit=HISTORY_LIMIT)
        if ed is None or ed.empty:
            return []

        now = datetime.now()
        rows = []
        for dt, row in ed.iterrows():
            # Skip future / unconfirmed events (Reported EPS not yet available)
            event_dt = dt.to_pydatetime().replace(tzinfo=None)
            if event_dt >= now:
                continue

            eps_est    = row.get("EPS Estimate")
            eps_actual = row.get("Reported EPS")

            # Skip if either value is missing
            if pd.isna(eps_est) or pd.isna(eps_actual):
                continue

            eps_est    = float(eps_est)
            eps_actual = float(eps_actual)

            if eps_actual > eps_est:
                label = "beat"
            elif eps_actual < eps_est:
                label = "miss"
            else:
                label = "meet"

            rows.append({
                "ticker":         ticker,
                "earnings_date":  event_dt.strftime("%Y-%m-%d"),
                "eps_estimate":   round(eps_est,    4),
                "eps_actual":     round(eps_actual, 4),
                "beat_miss_meet": label,
            })

        return rows

    except Exception:
        return []


def main():
    screener = pd.read_csv(INPUT_CSV)
    top30 = (
        screener.nlargest(N_TICKERS, "market_cap_b")
        [["ticker", "name", "market_cap_b"]]
        .reset_index(drop=True)
    )
    print(f"[*] Top {N_TICKERS} tickers by market cap:")
    for _, r in top30.iterrows():
        print(f"    {r['ticker']:<8}  ${r['market_cap_b']:.1f}B  {r['name']}")

    print(f"\n[>] Fetching earnings history (limit={HISTORY_LIMIT} quarters each)...\n")

    all_rows = []
    counts   = {}

    for i, row in enumerate(top30.itertuples(index=False), 1):
        ticker = row.ticker
        rows = fetch_earnings_history(ticker)
        all_rows.extend(rows)
        counts[ticker] = len(rows)
        print(f"  [{i:>2}/{N_TICKERS}] {ticker:<8}  {len(rows)} quarters collected")
        time.sleep(REQUEST_DELAY_SEC)

    if not all_rows:
        print("\n[!] No data collected.")
        return

    df = pd.DataFrame(all_rows, columns=["ticker", "earnings_date", "eps_estimate", "eps_actual", "beat_miss_meet"])
    df = df.sort_values(["ticker", "earnings_date"])
    df.to_csv(OUTPUT_CSV, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    thin = {t: c for t, c in counts.items() if c < MIN_QUARTERS_USEFUL}

    sep = "-" * 55
    print(f"\n{sep}")
    print(f"  Total rows collected : {len(df)}")
    print(f"  Tickers with data    : {sum(1 for c in counts.values() if c > 0)} / {N_TICKERS}")
    print(f"  Avg quarters/ticker  : {len(df) / N_TICKERS:.1f}")
    print(f"\n  Quarters per ticker:")
    for t, c in sorted(counts.items(), key=lambda x: -x[1]):
        flag = "  <-- thin" if c < MIN_QUARTERS_USEFUL else ""
        print(f"    {t:<8}  {c}{flag}")
    print(f"\n  Tickers with < {MIN_QUARTERS_USEFUL} quarters (thin coverage): {len(thin)}")
    if thin:
        for t, c in thin.items():
            print(f"    {t}: {c} quarters")
    print(f"\n  Beat/miss/meet breakdown:")
    print(df["beat_miss_meet"].value_counts().to_string())
    print(f"\n  Output written to {OUTPUT_CSV}")
    print(sep)


if __name__ == "__main__":
    main()
