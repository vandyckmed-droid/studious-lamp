"""SQLite connection + schema for the quant store.

Single file at data/quant.db, created relative to this module so it
works the same in Pythonista and from a desktop shell.
"""

import os
import sqlite3

DB_FILENAME = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "quant.db"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    name       TEXT PRIMARY KEY,
    index_src  TEXT NOT NULL,
    sector     TEXT,
    updated    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS group_members (
    group_name TEXT NOT NULL,
    ticker     TEXT NOT NULL,
    industry   TEXT,
    PRIMARY KEY (group_name, ticker)
);
CREATE INDEX IF NOT EXISTS idx_members_ticker ON group_members(ticker);

CREATE TABLE IF NOT EXISTS prices (
    ticker    TEXT NOT NULL,
    date      TEXT NOT NULL,
    close     REAL NOT NULL,
    adj_close REAL,
    PRIMARY KEY (ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date ON prices(ticker, date);

CREATE TABLE IF NOT EXISTS fundamentals (
    ticker           TEXT PRIMARY KEY,
    fetched          TEXT NOT NULL,
    gross_profit     REAL,
    total_assets     REAL,
    total_debt       REAL,
    cash             REAL,
    ebit             REAL,
    enterprise_value REAL
);

CREATE TABLE IF NOT EXISTS signals (
    ticker    TEXT NOT NULL,
    as_of     TEXT NOT NULL,
    mom_12_1  REAL,
    vol_63    REAL,
    PRIMARY KEY (ticker, as_of)
);
CREATE INDEX IF NOT EXISTS idx_signals_asof ON signals(as_of);
"""


def connect():
    """Open the DB (creating parent dir + schema on first call)."""
    os.makedirs(os.path.dirname(DB_FILENAME), exist_ok=True)
    conn = sqlite3.connect(DB_FILENAME)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def all_tracked_tickers(conn):
    """Tickers that appear in any group — the universe to fetch prices for."""
    rows = conn.execute("SELECT DISTINCT ticker FROM group_members").fetchall()
    return sorted(r[0] for r in rows)
