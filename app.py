"""
MDY Universe — Step 1: Tickers + Closing Prices

Run this in Pythonista on your iPhone/iPad.

Setup (one time):
  1. Open Pythonista
  2. Tap the wrench icon > install StaSh:
     import requests as r; exec(r.get('https://bit.ly/get-stash').text)
  3. Restart Pythonista, open StaSh (launch_stash.py)
  4. In StaSh type:  pip install yfinance
  5. Open this file and tap Run
"""

import os
import sys
import pandas as pd
import numpy as np

try:
    import yfinance as yf
except ImportError:
    print("=" * 50)
    print("  yfinance not installed!")
    print()
    print("  In StaSh run:  pip install yfinance")
    print("  Then restart Pythonista and try again.")
    print("=" * 50)
    sys.exit(1)


def load_tickers(path="tickers.txt"):
    """Read tickers from tickers.txt (one per line, # = comment)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, path)

    tickers = []
    with open(full_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                tickers.append(line.upper())

    return sorted(set(tickers))


def get_prices(tickers):
    """Pull 1 month of closing prices via yfinance."""
    print(f"Downloading prices for {len(tickers)} stocks...")
    print("(this may take 30-60 seconds)\n")
    data = yf.download(tickers, period="1mo", threads=True, progress=True)
    return data["Close"]


def build_summary(tickers, prices):
    """Build summary with last close and 1-month change."""
    last_close = prices.iloc[-1]
    first_close = prices.iloc[0]
    change_pct = ((last_close - first_close) / first_close * 100)

    rows = []
    for t in tickers:
        lc = last_close.get(t)
        cp = change_pct.get(t)
        rows.append({
            "Ticker": t,
            "Last Close": round(float(lc), 2) if pd.notna(lc) else None,
            "1M Chg %": round(float(cp), 2) if pd.notna(cp) else None,
        })

    df = pd.DataFrame(rows)
    return df


def display(df):
    """Print a ranked table to the console."""
    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 100)
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")

    ranked = df.dropna(subset=["1M Chg %"]).sort_values(
        "1M Chg %", ascending=False
    ).reset_index(drop=True)
    ranked.index = ranked.index + 1
    ranked.index.name = "#"

    print()
    print("=" * 55)
    print("  MDY UNIVERSE — CLOSING PRICES")
    print(f"  {len(ranked)} stocks | sorted by 1-month change")
    print("=" * 55)
    print()
    print(ranked.to_string())
    print()
    print(f"  {len(ranked)} of {len(df)} tickers loaded.")
    print()


# ── Run ──────────────────────────────────────────

if __name__ == "__main__":
    tickers = load_tickers()
    print(f"Loaded {len(tickers)} tickers from tickers.txt\n")

    prices = get_prices(tickers)
    summary = build_summary(tickers, prices)
    display(summary)
