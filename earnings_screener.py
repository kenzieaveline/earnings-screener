"""
Earnings Run-Up Screener
=========================
Finds stocks that:
  1. Have upcoming earnings within a configurable window (default 30-180 days)
  2. Have NOT already had a big price run-up (YTD or trailing N-day change below threshold)
  3. Are pulled from a combined universe: S&P 500 + Russell 2000 (sample) + a curated AI/Tech list

This is a SCREENER, not a recommendation engine. It narrows hundreds of tickers down to
a shortlist worth manually researching (news, fundamentals, analyst sentiment) before
considering any trade.

RUN THIS LOCALLY (e.g. via Claude Code on your own machine) — it needs real internet
access to pull live data, which a sandboxed environment may not have.

Usage:
    python earnings_screener.py

Requires:
    pip install yfinance pandas requests
"""

import io
import time
import warnings
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — tweak these to change what counts as "unnoticed" and the time window
# ─────────────────────────────────────────────────────────────────────────────
MIN_DAYS_TO_EARNINGS = 30      # Don't bother with anything reporting sooner than this
MAX_DAYS_TO_EARNINGS = 180     # Don't look further out than this (~6 months)
MAX_YTD_CHANGE_PCT   = 30.0    # "Hasn't run up" threshold — YTD % change must be below this
MAX_30D_CHANGE_PCT   = 15.0    # Also exclude anything that's spiked hard in the last 30 days
MIN_MARKET_CAP       = 300_000_000   # Skip illiquid micro caps below $300M
REQUEST_DELAY_SEC    = 0.3     # Be polite to Yahoo Finance — avoid getting rate limited

OUTPUT_CSV = "earnings_screener_results.csv"


# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSE — combined S&P 500 (sample) + Russell 2000 (sample) + AI/Tech focus
# ─────────────────────────────────────────────────────────────────────────────
# NOTE: Full S&P 500 and Russell 2000 lists are long. For a complete S&P 500 list,
# this script pulls live from Wikipedia. For Russell 2000, true full constituent
# lists are paywalled/licensed — we use a representative small/mid-cap sample
# focused on tech/AI-adjacent names instead, which fits your stated interest.
# You can freely edit AI_TECH_FOCUS_LIST below to add any tickers you want covered.

AI_TECH_FOCUS_LIST = [
    # AI / Semiconductors / Infrastructure (mix of large, mid, small cap)
    "SMCI", "ARM", "MRVL", "CRDO", "LITE", "ANET", "VRT", "MPWR",
    "ONTO", "LRCX", "KLAC", "ENTG", "COHR", "POWI", "ALAB", "ASTS",
    "RKLB", "IONQ", "QBTS", "RGTI", "SOUN", "BBAI", "AI", "PATH",
    "GTLB", "MNDY", "DDOG", "ESTC", "S", "CRWD", "ZS", "OKTA",
    "NET", "FSLY", "CFLT", "MDB", "TEAM", "HUBS", "BILL", "PCTY",
    "SMAR", "PD", "DOCN", "FROG", "APPN", "BRZE", "AMPL", "GTLS",
    "FN", "NPO", "BE", "PLUG", "FCEL", "CEG", "VST", "NRG",
    "TSEM", "DIOD", "SLAB", "SYNA", "QRVO", "SWKS", "MTSI", "AOSL",
]

def get_sp500_tickers() -> list[str]:
    """Pull live S&P 500 constituent list from Wikipedia."""
    try:
        resp = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15,
        )
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
        df = tables[0]
        return df["Symbol"].str.replace(".", "-", regex=False).tolist()
    except Exception as e:
        print(f"⚠️  Could not fetch S&P 500 list live ({e}). Falling back to empty list.")
        return []


def get_universe() -> list[str]:
    """Combine S&P 500 (live) + curated AI/Tech/small-cap focus list, deduplicated."""
    sp500 = get_sp500_tickers()
    combined = sorted(set(sp500) | set(AI_TECH_FOCUS_LIST))
    print(f"📋 Universe size: {len(combined)} tickers "
          f"({len(sp500)} from S&P 500 + {len(AI_TECH_FOCUS_LIST)} AI/Tech focus list, deduped)")
    return combined


# ─────────────────────────────────────────────────────────────────────────────
# CORE SCREENING LOGIC
# ─────────────────────────────────────────────────────────────────────────────
def days_until(date_obj) -> int | None:
    if date_obj is None:
        return None
    if isinstance(date_obj, (int, float)):
        date_obj = datetime.fromtimestamp(date_obj)
    today = datetime.now().date()
    target = date_obj.date() if hasattr(date_obj, "date") else date_obj
    return (target - today).days


def screen_ticker(ticker: str) -> dict | None:
    """Fetch data for one ticker and return a result row if it passes all filters."""
    try:
        tk = yf.Ticker(ticker)
        info = tk.info

        market_cap = info.get("marketCap")
        if not market_cap or market_cap < MIN_MARKET_CAP:
            return None

        # Earnings date
        try:
            cal = tk.get_earnings_dates(limit=4)
            future_dates = [d for d in cal.index if d.to_pydatetime() > datetime.now()] if cal is not None and not cal.empty else []
            next_earnings = future_dates[0].to_pydatetime() if future_dates else None
        except Exception:
            next_earnings = None

        if next_earnings is None:
            return None

        days_to_earn = days_until(next_earnings)
        if days_to_earn is None or not (MIN_DAYS_TO_EARNINGS <= days_to_earn <= MAX_DAYS_TO_EARNINGS):
            return None

        # Price history for YTD and 30-day change
        hist = tk.history(period="1y")
        if hist.empty or len(hist) < 30:
            return None

        current_price = hist["Close"].iloc[-1]
        year_start_price = hist["Close"].iloc[0]
        thirty_day_price = hist["Close"].iloc[-30]

        ytd_change_pct = ((current_price - year_start_price) / year_start_price) * 100
        thirty_day_change_pct = ((current_price - thirty_day_price) / thirty_day_price) * 100

        if ytd_change_pct > MAX_YTD_CHANGE_PCT:
            return None
        if thirty_day_change_pct > MAX_30D_CHANGE_PCT:
            return None

        return {
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "sector": info.get("sector", "Unknown"),
            "current_price": round(current_price, 2),
            "market_cap_b": round(market_cap / 1e9, 2),
            "next_earnings_date": next_earnings.strftime("%Y-%m-%d"),
            "days_to_earnings": days_to_earn,
            "ytd_change_pct": round(ytd_change_pct, 1),
            "30d_change_pct": round(thirty_day_change_pct, 1),
            "analyst_target": info.get("targetMeanPrice"),
            "analyst_recommendation": info.get("recommendationKey", "n/a"),
            "pe_ratio": info.get("trailingPE"),
        }

    except Exception:
        return None


def run_screener():
    universe = get_universe()
    results = []

    print(f"\n🔍 Screening {len(universe)} tickers — this will take a while "
          f"(~{round(len(universe) * REQUEST_DELAY_SEC / 60, 1)} min minimum)...\n")

    for i, ticker in enumerate(universe, 1):
        if i % 25 == 0:
            print(f"   ...{i}/{len(universe)} checked, {len(results)} matches so far")
        row = screen_ticker(ticker)
        if row:
            results.append(row)
            print(f"   ✅ MATCH: {ticker} — earnings in {row['days_to_earnings']}d, "
                  f"YTD {row['ytd_change_pct']}%, 30d {row['30d_change_pct']}%")
        time.sleep(REQUEST_DELAY_SEC)

    if not results:
        print("\n😕 No matches found. Try loosening MAX_YTD_CHANGE_PCT or widening the earnings window.")
        return

    df = pd.DataFrame(results)
    df = df.sort_values("days_to_earnings")
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"\n✅ Done! {len(df)} candidates saved to {OUTPUT_CSV}\n")
    print(df.to_string(index=False))
    print(
        "\n⚠️  REMINDER: This is a screener, not a recommendation. Each candidate still "
        "needs manual research — read recent news, check why it's quiet, check the "
        "actual earnings estimate trend, before considering any position."
    )


if __name__ == "__main__":
    run_screener()
