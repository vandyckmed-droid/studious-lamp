"""
MDY Universe — Step 2: 12-1 Log Momentum

Run this in Pythonista on your iPhone/iPad.
No extra packages needed — uses only built-in modules.

Setup:
  1. Copy app.py and tickers.txt into Pythonista
  2. Edit tickers.txt with your stocks (one per line)
  3. Tap Run
"""

import os
import math
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


def fetch_prices(ticker):
    """Fetch ~13 months of daily closes for a single ticker."""
    now = int(time.time())
    start = now - (400 * 86400)  # ~13 months back

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
        timestamps = result["timestamp"]

        # Pair timestamps with closes, filter out nulls
        daily = [
            (ts, c) for ts, c in zip(timestamps, closes)
            if c is not None
        ]
        return daily
    except Exception:
        return None


def calc_momentum(daily):
    """Calculate 12-1 log momentum from daily price series.

    Returns dict with:
      - mom_12_1: ln(P_1m_ago) - ln(P_12m_ago)
      - last_close: most recent price
      - p_1m: price ~1 month ago
      - p_12m: price ~12 months ago
    """
    if not daily or len(daily) < 200:
        return None

    last_ts = daily[-1][0]
    last_close = daily[-1][1]

    # Find price closest to 1 month ago (~21 trading days)
    target_1m = last_ts - (30 * 86400)
    # Find price closest to 12 months ago (~252 trading days)
    target_12m = last_ts - (365 * 86400)

    def closest_price(daily, target_ts):
        best = None
        best_diff = float("inf")
        for ts, c in daily:
            diff = abs(ts - target_ts)
            if diff < best_diff:
                best_diff = diff
                best = c
        return best

    p_1m = closest_price(daily, target_1m)
    p_12m = closest_price(daily, target_12m)

    if not p_1m or not p_12m or p_12m <= 0 or p_1m <= 0:
        return None

    mom = math.log(p_1m) - math.log(p_12m)

    return {
        "mom_12_1": round(mom, 4),
        "last_close": round(last_close, 2),
        "p_1m": round(p_1m, 2),
        "p_12m": round(p_12m, 2),
    }


def fetch_all(tickers):
    """Fetch data and calculate momentum for all tickers."""
    results = {}
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        pct = int((i + 1) / total * 100)
        print(f"  [{pct:3d}%] {ticker}...", end="")

        daily = fetch_prices(ticker)
        if daily:
            mom = calc_momentum(daily)
            if mom:
                results[ticker] = mom
                sign = "+" if mom["mom_12_1"] >= 0 else ""
                print(f" {sign}{mom['mom_12_1']:.4f}")
            else:
                print(" not enough data")
        else:
            print(" failed")

        # Small delay to avoid rate-limiting
        if (i + 1) % 5 == 0:
            time.sleep(0.5)

    return results


def display(tickers, data):
    """Print a ranked table sorted by 12-1 momentum."""
    rows = []
    for t in tickers:
        d = data.get(t)
        if d:
            rows.append((t, d["last_close"], d["p_1m"], d["p_12m"], d["mom_12_1"]))

    # Sort by 12-1 momentum, best first
    rows.sort(key=lambda x: x[4], reverse=True)

    print()
    print("=" * 62)
    print("  MDY UNIVERSE — 12-1 LOG MOMENTUM")
    print(f"  {len(rows)} stocks | sorted by momentum (high = strong)")
    print("=" * 62)
    print()
    print(f"  {'#':>4}  {'Ticker':<7} {'Price':>8} {'P(1m)':>8} {'P(12m)':>8} {'Mom 12-1':>9}")
    print(f"  {'—'*4}  {'—'*7} {'—'*8} {'—'*8} {'—'*8} {'—'*9}")

    for i, (ticker, close, p1m, p12m, mom) in enumerate(rows, 1):
        sign = "+" if mom >= 0 else ""
        print(f"  {i:4d}  {ticker:<7} {close:>8.2f} {p1m:>8.2f} {p12m:>8.2f} {sign}{mom:>8.4f}")

    print()
    print(f"  {len(rows)} of {len(tickers)} tickers loaded.")
    print()


# ── Run ──────────────────────────────────────────

if __name__ == "__main__":
    tickers = load_tickers()
    print(f"Loaded {len(tickers)} tickers from tickers.txt")
    print(f"Fetching 13 months of prices (this takes a few minutes)...\n")

    data = fetch_all(tickers)
    display(tickers, data)
