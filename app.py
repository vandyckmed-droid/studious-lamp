"""
MDY Universe — Step 1: Tickers + Closing Prices

Run this in Pyto on your iPhone/iPad.
It pulls the S&P MidCap 400 universe and shows closing prices.

First time setup in Pyto:
  1. Open Pyto
  2. Go to the PyPI tab (puzzle piece icon)
  3. Install: yfinance, pandas, lxml
  4. Open this file and tap Run
"""

import pandas as pd
import yfinance as yf


def get_universe():
    """Pull S&P MidCap 400 constituents (MDY) from Wikipedia."""
    print("Fetching MDY universe from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
    tables = pd.read_html(url)
    df = tables[0][["Symbol", "Security", "GICS Sector"]].copy()
    df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)
    df = df.sort_values("Symbol").reset_index(drop=True)
    return df


def get_prices(tickers):
    """Pull 1 month of closing prices."""
    print(f"Downloading prices for {len(tickers)} stocks (this takes ~30 sec)...")
    data = yf.download(tickers, period="1mo", threads=True)
    return data["Close"]


def build_summary(universe, prices):
    """Build a summary table with last close and 1-month change."""
    last_close = prices.iloc[-1]
    first_close = prices.iloc[0]
    change_pct = ((last_close - first_close) / first_close * 100).round(2)

    summary = universe.copy()
    summary["Last Close"] = summary["Symbol"].map(
        lambda s: round(float(last_close.get(s, float("nan"))), 2)
        if pd.notna(last_close.get(s))
        else None
    )
    summary["1M Chg %"] = summary["Symbol"].map(
        lambda s: round(float(change_pct.get(s, float("nan"))), 2)
        if pd.notna(change_pct.get(s))
        else None
    )
    return summary


def display(summary):
    """Print a clean table to the Pyto console."""
    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 120)
    pd.set_option("display.max_colwidth", 25)

    print("\n" + "=" * 80)
    print("  MDY UNIVERSE — S&P MidCap 400")
    print(f"  {len(summary)} stocks | sorted by 1-month change")
    print("=" * 80)

    ranked = summary.dropna(subset=["1M Chg %"]).sort_values(
        "1M Chg %", ascending=False
    )
    ranked.index = range(1, len(ranked) + 1)
    ranked.index.name = "#"

    print(ranked.to_string())
    print(f"\n  Loaded {len(ranked)} of {len(summary)} tickers with price data.\n")


# ── Run ──────────────────────────────────────────────────────

if __name__ == "__main__":
    universe = get_universe()
    print(f"Found {len(universe)} tickers.\n")

    prices = get_prices(universe["Symbol"].tolist())
    summary = build_summary(universe, prices)
    display(summary)
