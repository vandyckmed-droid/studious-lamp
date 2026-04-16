"""
MDY Universe — Step 3: 12-1 Momentum + Residual Momentum

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

        daily = [
            (ts, c) for ts, c in zip(timestamps, closes)
            if c is not None
        ]
        return daily
    except Exception:
        return None


def ts_to_date(ts):
    """Convert a Unix timestamp to a date string (YYYY-MM-DD)."""
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def daily_log_returns(daily):
    """Convert daily (timestamp, close) pairs to daily log returns.

    Returns list of (date_str, log_return) tuples.
    """
    returns = []
    for i in range(1, len(daily)):
        date = ts_to_date(daily[i][0])
        lr = math.log(daily[i][1]) - math.log(daily[i - 1][1])
        returns.append((date, lr))
    return returns


def closest_price(daily, target_ts):
    """Find price closest to a target timestamp."""
    best = None
    best_diff = float("inf")
    for ts, c in daily:
        diff = abs(ts - target_ts)
        if diff < best_diff:
            best_diff = diff
            best = c
    return best


def ols(x, y):
    """Simple OLS regression: y = alpha + beta * x.

    Returns (alpha, beta, residuals).
    """
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)

    beta = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
    alpha = (sum_y - beta * sum_x) / n

    residuals = [yi - alpha - beta * xi for xi, yi in zip(x, y)]
    return alpha, beta, residuals


def calc_signals(daily, mdy_returns_by_ts):
    """Calculate 12-1 momentum and residual momentum.

    mdy_returns_by_ts: dict of {timestamp: MDY daily log return}
    """
    if not daily or len(daily) < 200:
        return None

    last_ts = daily[-1][0]
    last_close = daily[-1][1]

    # 12-1 momentum: ln(P_1m) - ln(P_12m)
    target_1m = last_ts - (30 * 86400)
    target_12m = last_ts - (365 * 86400)

    p_1m = closest_price(daily, target_1m)
    p_12m = closest_price(daily, target_12m)

    if not p_1m or not p_12m or p_12m <= 0 or p_1m <= 0:
        return None

    mom_12_1 = math.log(p_1m) - math.log(p_12m)

    # Residual momentum: regress stock daily returns on MDY daily returns
    # over the 12-1 window, then sum the residuals
    stock_rets = daily_log_returns(daily)

    # Filter to the 12-1 window (skip most recent month)
    date_1m = ts_to_date(last_ts - (30 * 86400))
    date_12m = ts_to_date(last_ts - (365 * 86400))

    stock_x = []  # MDY returns
    stock_y = []  # stock returns

    for date, ret in stock_rets:
        if date_12m <= date <= date_1m:
            # Match by date string
            mdy_ret = mdy_returns_by_ts.get(date)
            if mdy_ret is not None:
                stock_x.append(mdy_ret)
                stock_y.append(ret)

    if len(stock_x) < 100:
        # Not enough overlapping data points
        return None

    alpha, beta, residuals = ols(stock_x, stock_y)
    resid_mom = sum(residuals)

    return {
        "mom_12_1": round(mom_12_1, 4),
        "resid_mom": round(resid_mom, 4),
        "beta": round(beta, 3),
        "last_close": round(last_close, 2),
    }


def fetch_all(tickers, mdy_returns_by_ts):
    """Fetch data and calculate signals for all tickers."""
    results = {}
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        pct = int((i + 1) / total * 100)
        print(f"  [{pct:3d}%] {ticker}...", end="")

        daily = fetch_prices(ticker)
        if daily:
            signals = calc_signals(daily, mdy_returns_by_ts)
            if signals:
                results[ticker] = signals
                print(f" mom={signals['mom_12_1']:+.4f}  resid={signals['resid_mom']:+.4f}")
            else:
                print(" not enough data")
        else:
            print(" failed")

        if (i + 1) % 5 == 0:
            time.sleep(0.5)

    return results


def display(tickers, data):
    """Print a ranked table sorted by residual momentum."""
    rows = []
    for t in tickers:
        d = data.get(t)
        if d:
            rows.append((t, d["last_close"], d["mom_12_1"], d["resid_mom"], d["beta"]))

    # Sort by residual momentum, best first
    rows.sort(key=lambda x: x[3], reverse=True)

    print()
    print("=" * 68)
    print("  MDY UNIVERSE — 12-1 MOMENTUM + RESIDUAL MOMENTUM")
    print(f"  {len(rows)} stocks | sorted by residual momentum")
    print("=" * 68)
    print()
    print(f"  {'#':>4}  {'Ticker':<7} {'Price':>8} {'Mom12-1':>8} {'ResMom':>8} {'Beta':>6}")
    print(f"  {'—'*4}  {'—'*7} {'—'*8} {'—'*8} {'—'*8} {'—'*6}")

    for i, (ticker, close, mom, resid, beta) in enumerate(rows, 1):
        print(f"  {i:4d}  {ticker:<7} {close:>8.2f} {mom:>+8.4f} {resid:>+8.4f} {beta:>6.2f}")

    print()
    print(f"  {len(rows)} of {len(tickers)} tickers loaded.")
    print()


# ── Run ──────────────────────────────────────────

if __name__ == "__main__":
    tickers = load_tickers()
    print(f"Loaded {len(tickers)} tickers from tickers.txt\n")

    # Step 1: Fetch MDY (the benchmark) first
    print("Fetching MDY benchmark prices...")
    mdy_daily = fetch_prices("MDY")
    if not mdy_daily:
        print("ERROR: Could not fetch MDY prices.")
        raise SystemExit(1)

    mdy_rets = daily_log_returns(mdy_daily)
    mdy_returns_by_ts = {date: ret for date, ret in mdy_rets}
    print(f"MDY: {len(mdy_rets)} daily returns loaded.\n")

    # Step 2: Fetch all stocks and calculate signals
    print("Fetching stock prices...\n")
    data = fetch_all(tickers, mdy_returns_by_ts)
    display(tickers, data)
