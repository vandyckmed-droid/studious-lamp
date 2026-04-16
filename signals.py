"""Signal computation on top of the prices table.

- `log_returns`        : daily log returns for a ticker.
- `mom_12_1`           : log(P[t-21]) - log(P[t-252]).
- `vol_63`             : stdev of the last 63 daily log returns.
- `covariance_matrix`  : sample covariance of daily log returns across
                         a set of tickers on their common dates.
- `compute_for`        : snapshot mom_12_1 and vol_63 into `signals`.

Uses `adj_close` when present (handles splits + dividends correctly),
falls back to raw `close` otherwise.
"""

import math
import time

import numpy as np


MOM_SKIP_DAYS = 21       # 1-month skip
MOM_LOOKBACK_DAYS = 252  # 12 months total
VOL_WINDOW = 63


def _prices(conn, ticker):
    """[(date, price)] using adj_close where available."""
    rows = conn.execute(
        "SELECT date, close, adj_close FROM prices WHERE ticker = ? ORDER BY date",
        (ticker,),
    ).fetchall()
    return [(d, a if a is not None else c) for (d, c, a) in rows]


def log_returns(conn, ticker):
    """[(date, log_return)] starting from the 2nd price row."""
    ps = _prices(conn, ticker)
    out = []
    for i in range(1, len(ps)):
        prev = ps[i - 1][1]
        cur = ps[i][1]
        if prev > 0 and cur > 0:
            out.append((ps[i][0], math.log(cur) - math.log(prev)))
    return out


def mom_12_1(conn, ticker):
    """12-1 log momentum; None if not enough history."""
    ps = _prices(conn, ticker)
    if len(ps) < MOM_LOOKBACK_DAYS + 1:
        return None
    p_skip = ps[-1 - MOM_SKIP_DAYS][1]
    p_start = ps[-1 - MOM_LOOKBACK_DAYS][1]
    if p_skip <= 0 or p_start <= 0:
        return None
    return math.log(p_skip) - math.log(p_start)


def vol_63(conn, ticker):
    """Sample stdev of the last 63 daily log returns. None if insufficient data."""
    rets = log_returns(conn, ticker)
    if len(rets) < VOL_WINDOW:
        return None
    window = [r for _, r in rets[-VOL_WINDOW:]]
    mean = sum(window) / len(window)
    var = sum((x - mean) ** 2 for x in window) / (len(window) - 1)
    return math.sqrt(var)


def covariance_matrix(conn, tickers, window=VOL_WINDOW):
    """Sample covariance of daily log returns across tickers over the last `window`
    *common* trading days. Returns (ordered_tickers, numpy 2D array)."""
    series_by_ticker = {}
    for t in tickers:
        rets = log_returns(conn, t)
        if len(rets) >= window:
            series_by_ticker[t] = dict(rets)

    if len(series_by_ticker) < 2:
        return [], np.zeros((0, 0))

    common = set.intersection(*(set(s.keys()) for s in series_by_ticker.values()))
    common = sorted(common)[-window:]
    if len(common) < window:
        return [], np.zeros((0, 0))

    ordered = sorted(series_by_ticker.keys())
    mat = np.array([[series_by_ticker[t][d] for d in common] for t in ordered])
    return ordered, np.cov(mat)


def compute_for(conn, tickers):
    """Recompute mom_12_1 + vol_63 for each ticker and upsert into `signals`."""
    today = time.strftime("%Y-%m-%d", time.gmtime())
    written = 0
    for t in tickers:
        m = mom_12_1(conn, t)
        v = vol_63(conn, t)
        if m is None and v is None:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO signals(ticker, as_of, mom_12_1, vol_63) "
            "VALUES (?, ?, ?, ?)",
            (t, today, m, v),
        )
        written += 1
    conn.commit()
    return written, today


def latest(conn, ticker):
    """Most recent signals row for a ticker as {'as_of', 'mom_12_1', 'vol_63'}."""
    row = conn.execute(
        "SELECT as_of, mom_12_1, vol_63 FROM signals WHERE ticker = ? "
        "ORDER BY as_of DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if not row:
        return {}
    return {"as_of": row[0], "mom_12_1": row[1], "vol_63": row[2]}
