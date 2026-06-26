"""
Adds sector_momentum to earnings_history.csv.

For each row (ticker T, earnings_date D): average 30-day price momentum of all
OTHER tickers in T's sector over the same calendar window that ends just before D
(nearest trading day <= D-30d to last trading day before D).

T is excluded from its own sector average. Returns NaN if fewer than MIN_PEERS
other tickers have valid momentum for that window.

Sectors with <= 2 tickers in the 29-ticker set will always be NaN (Technology,
Energy, Basic Materials, Utilities, Communication Services).

Price history is fetched once per ticker; all averaging is in-memory.
"""

import time
import warnings
from collections import defaultdict
from datetime import timedelta

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

INPUT_CSV         = "earnings_history.csv"
OUTPUT_CSV        = "earnings_history.csv"
REQUEST_DELAY_SEC = 0.4
MIN_PEERS         = 3


def fetch_history(ticker: str) -> pd.DataFrame | None:
    try:
        hist = yf.Ticker(ticker).history(start="2013-01-01")[["Close"]].dropna()
        if hist.empty:
            return None
        if hist.index.tz is not None:
            hist.index = hist.index.tz_convert(None)
        hist.index = hist.index.normalize()
        return hist
    except Exception:
        return None


def momentum_at_date(hist: pd.DataFrame, earnings_date: str) -> float | None:
    """30-day price % change ending strictly before earnings_date."""
    earnings_ts  = pd.Timestamp(earnings_date)
    start_target = earnings_ts - timedelta(days=30)

    before = hist[hist.index < earnings_ts]
    if before.empty:
        return None
    at_start = before[before.index <= start_target]
    if at_start.empty:
        return None

    price_end   = float(before["Close"].iloc[-1])
    price_start = float(at_start["Close"].iloc[-1])
    return round((price_end - price_start) / price_start * 100, 2)


def main():
    df = pd.read_csv(INPUT_CSV)

    # Build sector -> [tickers] map from the data itself
    sector_map     = df.groupby("ticker")["sector"].first()
    sector_tickers = defaultdict(list)
    for ticker, sector in sector_map.items():
        sector_tickers[sector].append(ticker)

    # ── Sector distribution ───────────────────────────────────────────────────
    print("Sector distribution (29-ticker set):")
    print(f"  {'Sector':<25} {'N':>3}  {'Max peers':>9}  Verdict")
    for sector, tickers in sorted(sector_tickers.items(), key=lambda x: -len(x[1])):
        max_peers = len(tickers) - 1
        verdict = "valid" if max_peers >= MIN_PEERS else f"always NaN (<{MIN_PEERS} peers)"
        print(f"  {sector:<25} {len(tickers):>3}  {max_peers:>9}  {verdict}  {sorted(tickers)}")
    print()

    # ── Fetch price history once per ticker ───────────────────────────────────
    all_tickers = df["ticker"].unique()
    print(f"[*] Fetching price history for {len(all_tickers)} tickers...")
    histories = {}
    for i, ticker in enumerate(all_tickers, 1):
        hist = fetch_history(ticker)
        histories[ticker] = hist
        n = len(hist) if hist is not None else 0
        print(f"  [{i:>2}/{len(all_tickers)}] {ticker:<8}  {n} trading days")
        time.sleep(REQUEST_DELAY_SEC)

    # ── Compute sector_momentum ───────────────────────────────────────────────
    print(f"\n[*] Computing sector_momentum for {len(df)} rows...")
    values = []
    for _, row in df.iterrows():
        peers = [t for t in sector_tickers.get(row["sector"], []) if t != row["ticker"]]

        peer_moms = []
        for peer in peers:
            hist = histories.get(peer)
            if hist is None:
                continue
            mom = momentum_at_date(hist, row["earnings_date"])
            if mom is not None:
                peer_moms.append(mom)

        values.append(round(sum(peer_moms) / len(peer_moms), 2) if len(peer_moms) >= MIN_PEERS else None)

    df["sector_momentum"] = values
    n_valid = df["sector_momentum"].notna().sum()
    n_nan   = df["sector_momentum"].isna().sum()

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"  Valid : {n_valid}  NaN : {n_nan}")
    print(f"  Written to {OUTPUT_CSV}\n")

    # ── Verification ─────────────────────────────────────────────────────────
    print("=== Verification ===")
    print("  Showing per-peer momentums that feed each average, "
          "and two thin-sector NaN cases.\n")

    examples = [
        ("KO",   8,  "Consumer Defensive — 4 peers"),
        ("ABBV", 10, "Healthcare — 3 peers (at threshold)"),
        ("IBM",  5,  "Technology — 2 peers, always NaN"),
        ("VZ",   3,  "Communication Services — 0 peers, always NaN"),
    ]
    for ticker, nth, note in examples:
        sub = df[df["ticker"] == ticker].reset_index(drop=True)
        nth = min(nth, len(sub) - 1)
        row = sub.iloc[nth]
        peers = [t for t in sector_tickers.get(row["sector"], []) if t != ticker]

        peer_results = {}
        for peer in peers:
            hist = histories.get(peer)
            peer_results[peer] = momentum_at_date(hist, row["earnings_date"]) if hist is not None else None

        valid_moms  = [m for m in peer_results.values() if m is not None]
        val         = row["sector_momentum"]
        val_str     = f"{val:.2f}%" if pd.notna(val) else "NaN"

        print(f"  {ticker}  earnings_date={row['earnings_date']}  sector={row['sector']}  [{note}]")
        if peers:
            for peer, mom in peer_results.items():
                print(f"    {peer}: {f'{mom:.2f}%' if mom is not None else 'None'}")
        else:
            print(f"    (no other tickers in sector)")
        print(f"    valid peers: {len(valid_moms)} / {len(peers)}  -->  sector_momentum = {val_str}")
        print()


if __name__ == "__main__":
    main()
