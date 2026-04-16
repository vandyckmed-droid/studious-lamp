"""
MDY Universe — Step 4: Momentum + Fundamentals + Z-Scores

Signals:
  1. Mom 12-1   — 12-1 log momentum
  2. ResMom     — residual momentum (MDY beta removed)
  3. GPA        — gross profit / total assets
  4. Leverage   — -(net debt / total assets)
  5. EBIT/EV    — EBIT / enterprise value

All signals are cross-sectionally z-scored.

Run in Pythonista — no extra packages needed.
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


# ── Price fetching ───────────────────────────────

def fetch_prices(ticker):
    """Fetch ~13 months of daily closes."""
    now = int(time.time())
    start = now - (400 * 86400)

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"period1": start, "period2": now, "interval": "1d"}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        result = data["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        timestamps = result["timestamp"]
        return [(ts, c) for ts, c in zip(timestamps, closes) if c is not None]
    except Exception:
        return None


# ── Yahoo Finance session (auth) ─────────────────

_yahoo_session = None
_yahoo_crumb = None


def get_yahoo_auth():
    """Get authenticated session + crumb for Yahoo Finance API."""
    global _yahoo_session, _yahoo_crumb

    if _yahoo_session and _yahoo_crumb:
        return _yahoo_session, _yahoo_crumb

    print("  Authenticating with Yahoo Finance...")
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    # Get cookie
    session.get("https://fc.yahoo.com", timeout=10)

    # Get crumb
    r = session.get(
        "https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=10
    )
    crumb = r.text

    _yahoo_session = session
    _yahoo_crumb = crumb
    print(f"  Auth OK (crumb={crumb[:8]}...)\n")
    return session, crumb


# ── Fundamentals fetching ────────────────────────

def fetch_fundamentals(ticker):
    """Fetch GPA, leverage, EBIT/EV from Yahoo Finance."""
    session, crumb = get_yahoo_auth()

    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
    params = {
        "modules": "incomeStatementHistory,balanceSheetHistory,defaultKeyStatistics",
        "crumb": crumb,
    }

    try:
        r = session.get(url, params=params, timeout=10)
        data = r.json()
        result = data["quoteSummary"]["result"][0]

        # Most recent annual income statement
        income = result["incomeStatementHistory"]["incomeStatementHistory"][0]
        gross_profit = income.get("grossProfit", {}).get("raw")
        ebit = income.get("ebit", {}).get("raw")

        # Most recent balance sheet
        balance = result["balanceSheetHistory"]["balanceSheetStatements"][0]
        total_assets = balance.get("totalAssets", {}).get("raw")

        long_debt = balance.get("longTermDebt", {}).get("raw", 0) or 0
        short_debt = balance.get("shortLongTermDebt", {}).get("raw", 0) or 0
        cash = balance.get("cash", {}).get("raw", 0) or 0

        # Enterprise value
        ev = result["defaultKeyStatistics"].get("enterpriseValue", {}).get("raw")

        # Calculate metrics
        net_debt = long_debt + short_debt - cash

        out = {}

        if gross_profit is not None and total_assets and total_assets > 0:
            out["gpa"] = gross_profit / total_assets

        if total_assets and total_assets > 0:
            out["leverage"] = -(net_debt / total_assets)

        if ebit is not None and ev and ev > 0:
            out["ebit_ev"] = ebit / ev

        return out if out else None

    except Exception:
        return None


# ── Math helpers ─────────────────────────────────

def ts_to_date(ts):
    """Unix timestamp to YYYY-MM-DD."""
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def daily_log_returns(daily):
    """Daily (ts, close) pairs -> (date_str, log_return) pairs."""
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
    """OLS: y = alpha + beta * x. Returns (alpha, beta)."""
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)

    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return 0, 0

    beta = (n * sum_xy - sum_x * sum_y) / denom
    alpha = (sum_y - beta * sum_x) / n
    return alpha, beta


def z_score_all(data, fields):
    """Cross-sectional z-score for each field across all stocks."""
    for field in fields:
        values = [d[field] for d in data.values() if field in d]
        if len(values) < 2:
            continue
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance) if variance > 0 else 0
        if std == 0:
            continue
        for d in data.values():
            if field in d:
                d[field + "_z"] = (d[field] - mean) / std


# ── Signal calculation ───────────────────────────

def calc_momentum(daily, mdy_returns_by_date):
    """Calculate 12-1 momentum and residual momentum."""
    if not daily or len(daily) < 200:
        return None

    last_ts = daily[-1][0]
    last_close = daily[-1][1]

    target_1m = last_ts - (30 * 86400)
    target_12m = last_ts - (365 * 86400)

    p_1m = closest_price(daily, target_1m)
    p_12m = closest_price(daily, target_12m)

    if not p_1m or not p_12m or p_12m <= 0 or p_1m <= 0:
        return None

    mom_12_1 = math.log(p_1m) - math.log(p_12m)

    # Residual momentum over 12-1 window
    stock_rets = daily_log_returns(daily)
    date_1m = ts_to_date(target_1m)
    date_12m = ts_to_date(target_12m)

    stock_x = []
    stock_y = []
    for date, ret in stock_rets:
        if date_12m <= date <= date_1m:
            mdy_ret = mdy_returns_by_date.get(date)
            if mdy_ret is not None:
                stock_x.append(mdy_ret)
                stock_y.append(ret)

    if len(stock_x) < 100:
        return None

    alpha, beta = ols(stock_x, stock_y)
    resid_mom = sum(yi - beta * xi for xi, yi in zip(stock_x, stock_y))

    return {
        "mom_12_1": mom_12_1,
        "resid_mom": resid_mom,
        "beta": round(beta, 3),
        "last_close": round(last_close, 2),
    }


# ── Main fetch loop ──────────────────────────────

def fetch_all(tickers, mdy_returns_by_date):
    """Fetch prices + fundamentals and calculate all signals."""
    data = {}
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        pct = int((i + 1) / total * 100)
        print(f"  [{pct:3d}%] {ticker}...", end="")

        # Prices + momentum
        daily = fetch_prices(ticker)
        mom = calc_momentum(daily, mdy_returns_by_date) if daily else None

        # Fundamentals
        fundies = fetch_fundamentals(ticker)

        if mom or fundies:
            entry = {}
            if mom:
                entry.update(mom)
            if fundies:
                entry.update(fundies)
            if "last_close" in entry:
                data[ticker] = entry
                parts = []
                if "mom_12_1" in entry:
                    parts.append(f"mom={entry['mom_12_1']:+.3f}")
                if "gpa" in entry:
                    parts.append(f"gpa={entry['gpa']:.3f}")
                print(f" {' '.join(parts)}")
            else:
                print(" partial data")
        else:
            print(" failed")

        if (i + 1) % 5 == 0:
            time.sleep(0.5)

    return data


# ── Display ──────────────────────────────────────

def display(tickers, data):
    """Print ranked table with z-scores."""
    # Z-score the five signals
    signal_fields = ["mom_12_1", "resid_mom", "gpa", "leverage", "ebit_ev"]
    z_score_all(data, signal_fields)

    rows = []
    for t in tickers:
        d = data.get(t)
        if not d:
            continue
        # Need at least momentum z-scores to rank
        if "mom_12_1_z" not in d:
            continue
        rows.append({
            "ticker": t,
            "price": d.get("last_close", 0),
            "mom_z": d.get("mom_12_1_z", 0),
            "res_z": d.get("resid_mom_z", 0),
            "gpa_z": d.get("gpa_z"),
            "lev_z": d.get("leverage_z"),
            "val_z": d.get("ebit_ev_z"),
        })

    # Sort by average z-score (preview of composite — Step 5 will refine)
    for r in rows:
        scores = [r["mom_z"], r["res_z"]]
        if r["gpa_z"] is not None:
            scores.append(r["gpa_z"])
        if r["lev_z"] is not None:
            scores.append(r["lev_z"])
        if r["val_z"] is not None:
            scores.append(r["val_z"])
        r["avg_z"] = sum(scores) / len(scores)

    rows.sort(key=lambda x: x["avg_z"], reverse=True)

    print()
    print("=" * 72)
    print("  MDY UNIVERSE — ALL SIGNALS (Z-SCORED)")
    print(f"  {len(rows)} stocks | sorted by avg z-score")
    print("=" * 72)
    print()
    print(f"  {'#':>4} {'Tkr':<6} {'Price':>7} {'MomZ':>6} {'ResZ':>6} {'GpaZ':>6} {'LevZ':>6} {'ValZ':>6} {'AvgZ':>6}")
    print(f"  {'—'*4} {'—'*6} {'—'*7} {'—'*6} {'—'*6} {'—'*6} {'—'*6} {'—'*6} {'—'*6}")

    for i, r in enumerate(rows, 1):
        def fmt(v):
            return f"{v:>+5.2f}" if v is not None else "   --"

        print(
            f"  {i:4d} {r['ticker']:<6} {r['price']:>7.2f}"
            f" {fmt(r['mom_z'])} {fmt(r['res_z'])}"
            f" {fmt(r['gpa_z'])} {fmt(r['lev_z'])}"
            f" {fmt(r['val_z'])} {fmt(r['avg_z'])}"
        )

    print()
    print(f"  {len(rows)} of {len(tickers)} tickers loaded.")
    print()


# ── Run ──────────────────────────────────────────

if __name__ == "__main__":
    tickers = load_tickers()
    print(f"Loaded {len(tickers)} tickers from tickers.txt\n")

    # Fetch MDY benchmark
    print("Fetching MDY benchmark...")
    mdy_daily = fetch_prices("MDY")
    if not mdy_daily:
        print("ERROR: Could not fetch MDY prices.")
        raise SystemExit(1)

    mdy_rets = daily_log_returns(mdy_daily)
    mdy_returns_by_date = {date: ret for date, ret in mdy_rets}
    print(f"MDY: {len(mdy_rets)} daily returns loaded.\n")

    # Fetch all stocks
    print("Fetching stock prices + fundamentals...\n")
    data = fetch_all(tickers, mdy_returns_by_date)
    display(tickers, data)
