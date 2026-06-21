# Earnings Run-Up Screener

A screener that finds stocks with upcoming earnings (30–180 days out by default)
that have NOT yet had a big price run-up — i.e. candidates that might still be
"unnoticed" before their pre-earnings momentum potentially kicks in.

**This must be run on your own machine via Claude Code (or any local Python setup) —
it needs real internet access to pull live stock data, which this sandboxed chat
environment does not have.**

---

## Setup

1. Install Claude Code if you haven't already (ask Claude in chat for the link,
   or see https://docs.claude.com).
2. Open this folder in Claude Code, or just copy `earnings_screener.py` to a
   folder on your computer.
3. Install dependencies:

   ```bash
   pip install yfinance pandas requests
   ```

4. Run it:

   ```bash
   python earnings_screener.py
   ```

It will take a few minutes (intentionally rate-limited so Yahoo Finance doesn't
block the requests). Results are printed to the terminal and saved to
`earnings_screener_results.csv`.

---

## What it actually does

1. Builds a universe of tickers: the live S&P 500 list (pulled from Wikipedia)
   combined with a curated list of ~70 AI/semiconductor/small-mid cap tech names
   (since true Russell 2000 full constituent data is generally paywalled).
2. For each ticker, pulls:
   - Next earnings date
   - Current price, YTD % change, trailing 30-day % change
   - Market cap, sector, analyst target price, P/E ratio
3. Filters down to only tickers where:
   - Earnings are 30–180 days away (configurable)
   - YTD change is below 30% (configurable) — i.e. hasn't already run hard
   - 30-day change is below 15% (configurable) — i.e. no recent spike either
   - Market cap is above $300M (avoids illiquid micro-caps)

## Tuning it

All the thresholds are constants at the top of `earnings_screener.py`:

```python
MIN_DAYS_TO_EARNINGS = 30
MAX_DAYS_TO_EARNINGS = 180
MAX_YTD_CHANGE_PCT   = 30.0
MAX_30D_CHANGE_PCT   = 15.0
MIN_MARKET_CAP       = 300_000_000
```

Loosen `MAX_YTD_CHANGE_PCT` if you get zero results — quiet stocks are quiet
precisely because the market doesn't always cooperate with finding many of them
at once.

To add specific tickers you want covered (e.g. something a friend mentioned, or
something from NTU Quant Finance Academy chat), just add the ticker string to
the `AI_TECH_FOCUS_LIST` list near the top of the script.

---

## Important honest limitations

- **This is a screener, not a signal.** It narrows hundreds of tickers down to a
  shortlist worth manually researching — it does NOT tell you a stock will go up.
- **"Hasn't run up" ≠ "will run up."** Plenty of quiet stocks stay quiet, or drop
  further. The filter just removes names that have *already* made their move.
- **Russell 2000 isn't fully covered.** True full small-cap universe data is
  usually behind a paid data feed (e.g. Polygon.io, IEX Cloud). The curated
  AI/Tech list is a reasonable proxy for your stated interest, not a full
  small-cap sweep.
- **yfinance can be flaky.** It's an unofficial wrapper around Yahoo Finance, not
  a paid guaranteed API. If you get a lot of errors, try re-running, or add
  retry logic.
- **Always verify the top candidates manually** — re-check price and earnings
  date on Moomoo or directly with Claude in chat before doing anything with
  real money, the same way we cross-checked AVGO and MU.

---

## Suggested workflow going forward

1. Run this screener locally every 1–2 weeks (or set up a scheduled run).
2. Take the top 3–5 candidates from the CSV.
3. Bring those specific tickers back to Claude in chat — Claude can then verify
   live prices via web search, dig into recent news/catalysts, and help assess
   whether the setup is genuinely interesting or just statistically quiet.
4. Decide entry/exit/stop-loss together, same as the DELL/AVGO playbook.
