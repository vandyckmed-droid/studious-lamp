"""Financial Modeling Prep fundamentals, cached in SQLite.

Three API calls per ticker (income statement, balance sheet,
enterprise value). Free tier = 250 calls/day so the budget caps us at
~80 fresh tickers per run; anything older than 30 days falls back to
its last cached value until budget allows a refresh.
"""

import os
import time

import requests


FMP_BASE = "https://financialmodelingprep.com/api/v3"
FMP_BUDGET = 240
CACHE_MAX_DAYS = 30

UA = {"User-Agent": "Mozilla/5.0"}


def load_api_key(path="config.txt"):
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    try:
        with open(fp, "r") as f:
            key = f.read().strip()
        if not key or key.startswith("PASTE"):
            raise ValueError
        return key
    except (FileNotFoundError, ValueError):
        print("ERROR: Missing or empty config.txt")
        print("  Copy config.txt.example to config.txt and paste your FMP key.")
        raise SystemExit(1)


def _cache_is_fresh(fetched):
    if not fetched:
        return False
    try:
        y, m, d = int(fetched[:4]), int(fetched[5:7]), int(fetched[8:10])
        now = time.gmtime()
        days_stored = y * 365 + m * 30 + d
        days_now = now.tm_year * 365 + now.tm_mon * 30 + now.tm_mday
        return (days_now - days_stored) < CACHE_MAX_DAYS
    except (ValueError, IndexError):
        return False


def _fetch_fmp(ticker, api_key):
    """Three API calls, returns dict of raw fields or None if nothing usable."""
    out = {}

    try:
        r = requests.get(
            f"{FMP_BASE}/income-statement/{ticker}",
            params={"period": "annual", "limit": 1, "apikey": api_key},
            headers=UA, timeout=10,
        )
        rows = r.json()
        if isinstance(rows, list) and rows:
            out["gross_profit"] = rows[0].get("grossProfit")
            out["ebit"] = rows[0].get("operatingIncome")
    except Exception:
        pass

    try:
        r = requests.get(
            f"{FMP_BASE}/balance-sheet-statement/{ticker}",
            params={"period": "annual", "limit": 1, "apikey": api_key},
            headers=UA, timeout=10,
        )
        rows = r.json()
        if isinstance(rows, list) and rows:
            out["total_assets"] = rows[0].get("totalAssets")
            out["total_debt"] = rows[0].get("totalDebt") or 0
            out["cash"] = rows[0].get("cashAndCashEquivalents") or 0
    except Exception:
        pass

    try:
        r = requests.get(
            f"{FMP_BASE}/enterprise-values/{ticker}",
            params={"period": "annual", "limit": 1, "apikey": api_key},
            headers=UA, timeout=10,
        )
        rows = r.json()
        if isinstance(rows, list) and rows:
            out["enterprise_value"] = rows[0].get("enterpriseValue")
    except Exception:
        pass

    if not out.get("total_assets"):
        return None
    return out


def _fresh_count(conn, tickers):
    marks = ",".join("?" * len(tickers))
    rows = conn.execute(
        f"SELECT fetched FROM fundamentals WHERE ticker IN ({marks})", tickers
    ).fetchall()
    fresh = sum(1 for (f,) in rows if _cache_is_fresh(f))
    return fresh, len(rows) - fresh


def update(conn, tickers, api_key, budget=FMP_BUDGET):
    """Refresh fundamentals older than 30 days, respecting call budget.

    Returns (refreshed, api_calls).
    """
    fresh, stale = _fresh_count(conn, tickers)
    missing = len(tickers) - fresh - stale
    print(f"  Cache: {fresh} fresh, {stale} stale, {missing} missing")
    print(f"  Budget: {budget} API calls")

    refreshed = 0
    api_calls = 0
    today = time.strftime("%Y-%m-%d", time.gmtime())

    for i, ticker in enumerate(tickers):
        row = conn.execute(
            "SELECT fetched FROM fundamentals WHERE ticker = ?", (ticker,)
        ).fetchone()
        if row and _cache_is_fresh(row[0]):
            continue

        if api_calls + 3 > budget:
            print(f"  [{i+1}/{len(tickers)}] {ticker}: budget exhausted")
            break

        raw = _fetch_fmp(ticker, api_key)
        api_calls += 3

        if not raw:
            print(f"  [{i+1}/{len(tickers)}] {ticker}: fetch failed")
            continue

        conn.execute(
            """
            INSERT OR REPLACE INTO fundamentals
            (ticker, fetched, gross_profit, total_assets, total_debt,
             cash, ebit, enterprise_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker, today,
                raw.get("gross_profit"),
                raw.get("total_assets"),
                raw.get("total_debt"),
                raw.get("cash"),
                raw.get("ebit"),
                raw.get("enterprise_value"),
            ),
        )
        conn.commit()
        refreshed += 1
        print(f"  [{i+1}/{len(tickers)}] {ticker}: refreshed")

        if (i + 1) % 5 == 0:
            time.sleep(0.5)

    return refreshed, api_calls


def ratios(conn, ticker):
    """Return {gpa, leverage, ebit_ev} or {} when data missing."""
    row = conn.execute(
        "SELECT gross_profit, total_assets, total_debt, cash, ebit, enterprise_value "
        "FROM fundamentals WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    if not row:
        return {}
    gp, ta, td, cash, ebit, ev = row

    out = {}
    if gp is not None and ta and ta > 0:
        out["gpa"] = gp / ta
    if ta and ta > 0:
        net_debt = (td or 0) - (cash or 0)
        out["leverage"] = -(net_debt / ta)
    if ebit is not None and ev and ev > 0:
        out["ebit_ev"] = ebit / ev
    return out
