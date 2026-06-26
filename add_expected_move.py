"""
Standalone pass: reads the existing 239-match CSV, adds expected_move_pct column,
writes the result back. Run this once rather than re-running the full screener.
"""
import time
import warnings
from datetime import datetime

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

INPUT_CSV  = "earnings_screener_results.csv"
OUTPUT_CSV = "earnings_screener_results.csv"
REQUEST_DELAY_SEC = 0.3


def compute_expected_move(ticker: str, earnings_date: str) -> float | None:
    try:
        tk = yf.Ticker(ticker)

        hist = tk.history(period="5d")
        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            return None
        current_price = float(hist["Close"].iloc[-1])
        if current_price <= 0:
            return None

        if isinstance(earnings_date, str):
            earnings_dt = datetime.strptime(earnings_date, "%Y-%m-%d").date()
        else:
            earnings_dt = earnings_date.date() if hasattr(earnings_date, "date") else earnings_date

        expirations = tk.options
        if not expirations:
            return None

        future_expiries = [
            e for e in expirations
            if datetime.strptime(e, "%Y-%m-%d").date() > earnings_dt
        ]
        if not future_expiries:
            return None

        # Walk expiries until we find one with enough overlapping strikes.
        # The nearest expiry is often a stub chain with 1–2 contracts and no puts.
        calls = puts = common_strikes = None
        for expiry in future_expiries:
            chain = tk.option_chain(expiry)
            c = chain.calls
            p = chain.puts
            if c.empty or p.empty:
                continue
            common = sorted(set(c["strike"].values) & set(p["strike"].values))
            if len(common) >= 5:
                calls, puts, common_strikes = c, p, common
                break

        if common_strikes is None:
            return None
        atm_strike = min(common_strikes, key=lambda s: abs(s - current_price))

        call_row = calls[calls["strike"] == atm_strike].iloc[0]
        put_row  = puts[puts["strike"]  == atm_strike].iloc[0]

        def mid_or_last(series):
            try:
                bid, ask = series["bid"], series["ask"]
                if pd.notna(bid) and pd.notna(ask) and float(bid) > 0 and float(ask) > 0:
                    return (float(bid) + float(ask)) / 2
            except (KeyError, TypeError, ValueError):
                pass
            try:
                last = series["lastPrice"]
                if pd.notna(last) and float(last) > 0:
                    return float(last)
            except (KeyError, TypeError, ValueError):
                pass
            return None

        call_premium = mid_or_last(call_row)
        put_premium  = mid_or_last(put_row)
        if call_premium is None or put_premium is None:
            return None

        return round((call_premium + put_premium) / current_price * 100, 1)

    except Exception:
        return None


def main():
    df = pd.read_csv(INPUT_CSV)
    n = len(df)
    print(f"[*] Loaded {n} tickers from {INPUT_CSV}")
    print(f"[>] Computing expected moves (~{round(n * REQUEST_DELAY_SEC / 60, 1)} min minimum)...\n")

    results = []
    for i, row in enumerate(df.itertuples(index=False), 1):
        if i % 25 == 0:
            filled = sum(1 for r in results if r is not None)
            print(f"   ...{i}/{n} done  ({filled} with data, {i - filled} None so far)")
        em = compute_expected_move(row.ticker, row.next_earnings_date)
        results.append(em)
        time.sleep(REQUEST_DELAY_SEC)

    df["expected_move_pct"] = results
    df.to_csv(OUTPUT_CSV, index=False)

    filled  = df["expected_move_pct"].notna().sum()
    missing = df["expected_move_pct"].isna().sum()
    print(f"\n[DONE] {filled} tickers with expected_move_pct, {missing} returned None")
    print(f"       Written to {OUTPUT_CSV}\n")
    print(df.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
