"""Incremental daily-price fetcher using the Yahoo Finance chart API.

For each ticker we look up MAX(date) already stored and only pull bars
from (max+1) to today. First-time fetches go back `lookback_days` so
there is enough history for 12-1 momentum (needs ~252 trading days).
"""

import time

import requests


YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
UA = {"User-Agent": "Mozilla/5.0"}


def _ts_to_date(ts):
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def _date_to_ts(date_str):
    return int(time.mktime(time.strptime(date_str, "%Y-%m-%d")))


def _fetch_yahoo(ticker, period1, period2):
    """Return list of (date_str, close, adj_close) or []."""
    url = YAHOO_URL.format(ticker=ticker)
    params = {
        "period1": period1,
        "period2": period2,
        "interval": "1d",
        "events": "history",
    }
    try:
        r = requests.get(url, params=params, headers=UA, timeout=10)
        payload = r.json()
        result = payload["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        quote = result["indicators"]["quote"][0]
        closes = quote.get("close") or []
        adj = None
        if "adjclose" in result["indicators"]:
            adj = result["indicators"]["adjclose"][0].get("adjclose")
        out = []
        for i, ts in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            a = adj[i] if adj and i < len(adj) else None
            if c is None:
                continue
            out.append((_ts_to_date(ts), float(c), float(a) if a is not None else None))
        return out
    except Exception:
        return []


def _latest_date(conn, ticker):
    row = conn.execute(
        "SELECT MAX(date) FROM prices WHERE ticker = ?", (ticker,)
    ).fetchone()
    return row[0] if row and row[0] else None


def update(conn, tickers, lookback_days=400, sleep_every=5, sleep_seconds=0.5):
    """Incrementally fetch prices for each ticker. Returns (updated, new_rows)."""
    now = int(time.time())
    one_day = 86400
    updated = 0
    total_new = 0

    for i, ticker in enumerate(tickers):
        latest = _latest_date(conn, ticker)
        if latest:
            start_ts = _date_to_ts(latest) + one_day
            if start_ts >= now:
                print(f"  [{i+1}/{len(tickers)}] {ticker}: up to date")
                continue
        else:
            start_ts = now - lookback_days * one_day

        rows = _fetch_yahoo(ticker, start_ts, now)
        if not rows:
            print(f"  [{i+1}/{len(tickers)}] {ticker}: fetch failed")
            continue

        # Filter out anything we already have (Yahoo sometimes returns today twice).
        existing_dates = {
            r[0]
            for r in conn.execute(
                "SELECT date FROM prices WHERE ticker = ? AND date >= ?",
                (ticker, rows[0][0]),
            )
        }
        new = [(ticker, d, c, a) for (d, c, a) in rows if d not in existing_dates]

        conn.executemany(
            "INSERT OR REPLACE INTO prices(ticker, date, close, adj_close) "
            "VALUES (?, ?, ?, ?)",
            new,
        )
        conn.commit()
        updated += 1
        total_new += len(new)
        print(f"  [{i+1}/{len(tickers)}] {ticker}: +{len(new)} bars")

        if (i + 1) % sleep_every == 0:
            time.sleep(sleep_seconds)

    return updated, total_new


def series(conn, ticker):
    """Return [(date, close, adj_close)] ordered by date ascending."""
    return conn.execute(
        "SELECT date, close, adj_close FROM prices WHERE ticker = ? ORDER BY date",
        (ticker,),
    ).fetchall()
