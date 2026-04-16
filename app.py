"""
MDY Universe — Step 1: Tickers + Closing Prices

Run this in Pythonista on your iPhone/iPad.
No extra packages needed — uses only built-in modules.

Setup:
  1. Copy app.py and tickers.txt into Pythonista
  2. Edit tickers.txt with your stocks (one per line)
  3. Tap Run
"""

import os
import json
import time
import requests


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


def fetch_price(ticker):
    """Fetch 1 month of daily closes for a single ticker from Yahoo Finance."""
    now = int(time.time())
    start = now - (35 * 86400)  # ~35 days back to ensure 1 month of trading days

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "period1": start,
        "period2": now,
        "interval": "1d",
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        result = data["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        # Filter out None values
        valid = [c for c in closes if c is not None]
        if len(valid) >= 2:
            return {
                "last_close": round(valid[-1], 2),
                "first_close": round(valid[0], 2),
            }
    except Exception:
        pass
    return None


def fetch_all_prices(tickers):
    """Fetch prices for all tickers, one at a time."""
    results = {}
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        pct = int((i + 1) / total * 100)
        print(f"  [{pct:3d}%] {ticker}...", end="")

        data = fetch_price(ticker)
        if data:
            results[ticker] = data
            print(f" ${data['last_close']}")
        else:
            print(" failed")

        # Small delay to avoid getting rate-limited
        if (i + 1) % 5 == 0:
            time.sleep(0.5)

    return results


def display(tickers, prices):
    """Print a ranked table to the console."""
    rows = []
    for t in tickers:
        p = prices.get(t)
        if p:
            chg = round((p["last_close"] - p["first_close"]) / p["first_close"] * 100, 2)
            rows.append((t, p["last_close"], chg))

    # Sort by 1-month change, best first
    rows.sort(key=lambda x: x[2], reverse=True)

    print()
    print("=" * 45)
    print("  MDY UNIVERSE — CLOSING PRICES")
    print(f"  {len(rows)} stocks | sorted by 1M change")
    print("=" * 45)
    print()
    print(f"  {'#':>4}  {'Ticker':<8} {'Last Close':>11} {'1M Chg %':>9}")
    print(f"  {'—'*4}  {'—'*8} {'—'*11} {'—'*9}")

    for i, (ticker, close, chg) in enumerate(rows, 1):
        sign = "+" if chg >= 0 else ""
        print(f"  {i:4d}  {ticker:<8} ${close:>10.2f} {sign}{chg:>8.2f}%")

    print()
    print(f"  {len(rows)} of {len(tickers)} tickers loaded.")
    print()


# ── Run ──────────────────────────────────────────

if __name__ == "__main__":
    tickers = load_tickers()
    print(f"Loaded {len(tickers)} tickers from tickers.txt")
    print(f"Fetching prices (this takes a few minutes)...\n")

    prices = fetch_all_prices(tickers)
    display(tickers, prices)
