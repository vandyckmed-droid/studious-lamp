"""
MDY Universe — Momentum + Fundamentals + Z-Scores

Signals:
  1. Mom 12-1   — 12-1 log momentum
  2. ResMom     — residual momentum (MDY beta removed)
  3. GPA        — gross profit / total assets
  4. Leverage   — -(net debt / total assets)
  5. EBIT/EV    — EBIT / enterprise value

All signals are cross-sectionally z-scored.
Prices from Yahoo Finance, fundamentals from FMP (cached).

Run in Pythonista — no extra packages needed.
"""

import json
import os
import math
import time
import requests

FMP_BASE = "https://financialmodelingprep.com/api/v3"
FMP_BUDGET = 240  # max API calls per run (free tier = 250/day, keep buffer)
CACHE_MAX_DAYS = 30


def _script_path(filename):
    """Resolve a file path relative to the script directory."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def load_tickers(path="tickers.txt"):
    """Read tickers from tickers.txt (one per line, # = comment)."""
    tickers = []
    with open(_script_path(path), "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                tickers.append(line.upper())
    return sorted(set(tickers))


def load_config(path="config.txt"):
    """Read FMP API key from config.txt."""
    fp = _script_path(path)
    try:
        with open(fp, "r") as f:
            key = f.read().strip()
        if not key:
            raise ValueError
        return key
    except (FileNotFoundError, ValueError):
        print("ERROR: Missing or empty config.txt")
        print("  Create config.txt with your FMP API key (one line).")
        print("  Sign up free at https://financialmodelingprep.com")
        raise SystemExit(1)


# ── FMP cache ───────────────────────────────────

def load_cache(path="fmp_cache.json"):
    """Load cached fundamentals from JSON file."""
    fp = _script_path(path)
    try:
        with open(fp, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache, path="fmp_cache.json"):
    """Save fundamentals cache to JSON file."""
    fp = _script_path(path)
    with open(fp, "w") as f:
        json.dump(cache, f, indent=1)


def _cache_is_fresh(entry):
    """Check if a cache entry is less than CACHE_MAX_DAYS old."""
    fetched = entry.get("fetched", "")
    if not fetched:
        return False
    try:
        y, m, d = int(fetched[:4]), int(fetched[5:7]), int(fetched[8:10])
        now = time.gmtime()
        # Approximate days difference
        fetched_days = y * 365 + m * 30 + d
        now_days = now.tm_year * 365 + now.tm_mon * 30 + now.tm_mday
        return (now_days - fetched_days) < CACHE_MAX_DAYS
    except (ValueError, IndexError):
        return False


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


# ── FMP fundamentals fetching ───────────────────

def fetch_fundamentals_fmp(ticker, api_key):
    """Fetch raw fundamental data from FMP (3 API calls). Returns dict or None."""
    out = {}

    # 1. Income statement
    try:
        url = f"{FMP_BASE}/income-statement/{ticker}"
        r = requests.get(url, params={"period": "annual", "limit": 1, "apikey": api_key}, timeout=10)
        rows = r.json()
        if rows and isinstance(rows, list):
            out["grossProfit"] = rows[0].get("grossProfit")
            out["ebit"] = rows[0].get("operatingIncome")
    except Exception:
        pass

    # 2. Balance sheet
    try:
        url = f"{FMP_BASE}/balance-sheet-statement/{ticker}"
        r = requests.get(url, params={"period": "annual", "limit": 1, "apikey": api_key}, timeout=10)
        rows = r.json()
        if rows and isinstance(rows, list):
            out["totalAssets"] = rows[0].get("totalAssets")
            out["totalDebt"] = rows[0].get("totalDebt", 0) or 0
            out["cash"] = rows[0].get("cashAndCashEquivalents", 0) or 0
    except Exception:
        pass

    # 3. Enterprise value
    try:
        url = f"{FMP_BASE}/enterprise-values/{ticker}"
        r = requests.get(url, params={"period": "annual", "limit": 1, "apikey": api_key}, timeout=10)
        rows = r.json()
        if rows and isinstance(rows, list):
            out["enterpriseValue"] = rows[0].get("enterpriseValue")
    except Exception:
        pass

    if not out.get("totalAssets"):
        return None

    out["fetched"] = time.strftime("%Y-%m-%d", time.gmtime())
    return out


def get_fundamentals(ticker, api_key, cache, api_calls):
    """Get fundamentals from cache or FMP. Returns (ratios_dict, api_calls_used)."""
    # Use cache if fresh
    if ticker in cache and _cache_is_fresh(cache[ticker]):
        ratios = _calc_ratios(cache[ticker])
        return ratios, 0

    # Budget check (3 calls per ticker)
    if api_calls + 3 > FMP_BUDGET:
        # Over budget — fall back to stale cache if available
        if ticker in cache:
            return _calc_ratios(cache[ticker]), 0
        return None, 0

    raw = fetch_fundamentals_fmp(ticker, api_key)
    if raw:
        cache[ticker] = raw
        return _calc_ratios(raw), 3
    return None, 3


def _calc_ratios(raw):
    """Calculate GPA, leverage, EBIT/EV from raw cached data."""
    out = {}
    gross_profit = raw.get("grossProfit")
    total_assets = raw.get("totalAssets")
    total_debt = raw.get("totalDebt", 0) or 0
    cash = raw.get("cash", 0) or 0
    ebit = raw.get("ebit")
    ev = raw.get("enterpriseValue")

    if gross_profit is not None and total_assets and total_assets > 0:
        out["gpa"] = gross_profit / total_assets

    if total_assets and total_assets > 0:
        net_debt = total_debt - cash
        out["leverage"] = -(net_debt / total_assets)

    if ebit is not None and ev and ev > 0:
        out["ebit_ev"] = ebit / ev

    return out if out else None


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

def fetch_all(tickers, mdy_returns_by_date, api_key):
    """Fetch prices + fundamentals and calculate all signals."""
    cache = load_cache()
    api_calls = 0

    # Count cache status
    fresh = sum(1 for t in tickers if t in cache and _cache_is_fresh(cache[t]))
    stale = sum(1 for t in tickers if t in cache and not _cache_is_fresh(cache[t]))
    missing = len(tickers) - fresh - stale
    print(f"  Cache: {fresh} fresh, {stale} stale, {missing} missing")
    print(f"  Budget: {FMP_BUDGET} API calls this run\n")

    data = {}
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        pct = int((i + 1) / total * 100)
        print(f"  [{pct:3d}%] {ticker}...", end="")

        # Prices + momentum (Yahoo — no daily limit)
        daily = fetch_prices(ticker)
        mom = calc_momentum(daily, mdy_returns_by_date) if daily else None

        # Fundamentals (FMP with cache)
        fundies, calls_used = get_fundamentals(ticker, api_key, cache, api_calls)
        api_calls += calls_used

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
                src = "cache" if calls_used == 0 and fundies else "fmp" if fundies else ""
                if src:
                    parts.append(f"[{src}]")
                print(f" {' '.join(parts)}")
            else:
                print(" partial data")
        else:
            print(" failed")

        if (i + 1) % 5 == 0:
            time.sleep(0.5)

    # Persist cache after all fetches
    save_cache(cache)
    print(f"\n  FMP API calls used: {api_calls} / {FMP_BUDGET}")
    cached_count = sum(1 for t in tickers if t in cache)
    print(f"  Cache now has {cached_count} / {total} tickers\n")

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
    api_key = load_config()
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
    print("Fetching stock data...\n")
    data = fetch_all(tickers, mdy_returns_by_date, api_key)
    display(tickers, data)
