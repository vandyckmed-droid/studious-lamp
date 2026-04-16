# pythonista-quant

Long-term trend-following quality quantitative ranking model. Runs in
[Pythonista](http://omz-software.com/pythonista/) on iPhone/iPad.

## What it does

Maintains a persistent SQLite store of:

- **Groups** — S&P 500 and S&P 400 tickers bucketed by GICS sector
  (11 sectors × 2 indices = up to 22 named groups). Refreshed monthly
  from Wikipedia.
- **Prices** — daily closes from Yahoo Finance, fetched incrementally.
- **Fundamentals** — gross profit / total assets, leverage, EBIT/EV
  from Financial Modeling Prep (free tier, monthly cache).
- **Signals** — 12-1 log momentum, 63-day realised volatility, per
  ticker per as-of date.

Once the data is loaded, you can rank any group (or industry slice of a
group) without refetching anything.

## One-time setup

1. Get a free FMP API key at
   https://site.financialmodelingprep.com/developer/docs (free tier =
   250 calls/day, plenty with monthly caching).
2. Copy `config.txt.example` to `config.txt` and paste your key on the
   first line. `config.txt` is gitignored.
3. In Pythonista: tap the `+` button, **Import from URL**, paste the
   repo zip, and unpack — or use the Working Copy app to clone.

## Usage

Routine schedule (all from Pythonista's **Run** button):

```
# once a month
python refresh_groups.py
python update_fundamentals.py

# weekly
python update_prices.py
python compute_signals.py

# ad-hoc
python rank_group.py sp500_information_technology
python rank_group.py sp500_information_technology --industry Semiconductors
python rank_group.py sp400_industrials
```

## Design

See `db.py` for the schema. Everything lives in `data/quant.db` —
delete it to start fresh. No external dependencies beyond `requests`,
`beautifulsoup4`, and `numpy` (all bundled with Pythonista).

## Data sources & cost

| Source | Purpose | Cost |
| --- | --- | --- |
| Wikipedia | S&P 500 / S&P 400 constituents + GICS classification | free |
| Yahoo Finance (chart API) | Daily closes | free |
| Financial Modeling Prep | Income statement, balance sheet, enterprise value | free tier (250 calls/day) |

Total: $0/month.

## Signals

- **mom_12_1** — `log(P[t-21]) - log(P[t-252])`. 12-1 log momentum with
  the standard 1-month skip.
- **vol_63** — standard deviation of the last 63 daily log returns.
- **gpa** — `gross_profit / total_assets` (gross profitability,
  Novy-Marx).
- **leverage** — `-(total_debt - cash) / total_assets` (sign-flipped so
  less levered = better).
- **ebit_ev** — `EBIT / enterprise_value` (cheapness).

At rank time, each signal is cross-sectionally z-scored within the
group, then averaged into an `AvgZ`.
