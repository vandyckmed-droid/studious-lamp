"""Scrape S&P 500 and S&P 400 constituents from Wikipedia into groups.

Each Wikipedia table has Symbol, GICS Sector, and GICS Sub-Industry
columns. We write one `groups` row per (index, sector) pair and fan
members out into `group_members`, keeping the sub-industry so you can
filter a sector group down to e.g. Semiconductors at rank time.
"""

import time

import requests
from bs4 import BeautifulSoup


SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SP400_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"

UA = {"User-Agent": "studious-lamp-quant/0.1"}


def _slug(s):
    return s.strip().lower().replace("&", "and").replace(" ", "_").replace("/", "_")


def _scrape_wikipedia_constituents(url):
    """Return list of (ticker, sector, sub_industry) from a Wikipedia list page."""
    r = requests.get(url, headers=UA, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table", {"class": "wikitable"})
    if table is None:
        raise RuntimeError(f"No wikitable found at {url}")

    # Find column indexes from the header row.
    header_cells = [c.get_text(strip=True).lower() for c in table.find("tr").find_all(["th", "td"])]

    def col(*candidates):
        for cand in candidates:
            for i, h in enumerate(header_cells):
                if cand in h:
                    return i
        return None

    i_symbol = col("symbol", "ticker")
    i_sector = col("gics sector", "sector")
    i_sub    = col("gics sub", "sub-industry", "sub industry", "industry")

    if i_symbol is None or i_sector is None:
        raise RuntimeError(f"Expected columns not found at {url}: {header_cells}")

    out = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) <= max(i_symbol, i_sector, i_sub or 0):
            continue
        ticker = cells[i_symbol].get_text(strip=True).replace(".", "-")
        sector = cells[i_sector].get_text(strip=True)
        sub    = cells[i_sub].get_text(strip=True) if i_sub is not None else ""
        if ticker and sector:
            out.append((ticker, sector, sub))
    return out


def _write_groups(conn, index_src, rows):
    """Replace all groups + members for this index."""
    today = time.strftime("%Y-%m-%d", time.gmtime())

    # Remove prior groups for this index (and their members).
    existing = conn.execute(
        "SELECT name FROM groups WHERE index_src = ?", (index_src,)
    ).fetchall()
    for (name,) in existing:
        conn.execute("DELETE FROM group_members WHERE group_name = ?", (name,))
    conn.execute("DELETE FROM groups WHERE index_src = ?", (index_src,))

    # Build new groups.
    sectors = sorted({sector for _, sector, _ in rows})
    for sector in sectors:
        name = f"{index_src}_{_slug(sector)}"
        conn.execute(
            "INSERT INTO groups(name, index_src, sector, updated) VALUES (?, ?, ?, ?)",
            (name, index_src, sector, today),
        )

    for ticker, sector, sub in rows:
        name = f"{index_src}_{_slug(sector)}"
        conn.execute(
            "INSERT OR REPLACE INTO group_members(group_name, ticker, industry) "
            "VALUES (?, ?, ?)",
            (name, ticker, sub),
        )
    conn.commit()


def refresh_sp500(conn):
    rows = _scrape_wikipedia_constituents(SP500_URL)
    _write_groups(conn, "sp500", rows)
    return len(rows)


def refresh_sp400(conn):
    rows = _scrape_wikipedia_constituents(SP400_URL)
    _write_groups(conn, "sp400", rows)
    return len(rows)


def list_groups(conn):
    """Return [(name, sector, member_count)] for printing."""
    return conn.execute(
        """
        SELECT g.name, g.sector, COUNT(m.ticker) AS n
        FROM groups g
        LEFT JOIN group_members m ON m.group_name = g.name
        GROUP BY g.name
        ORDER BY g.index_src, g.sector
        """
    ).fetchall()


def members(conn, group_name, industry=None):
    """Return [(ticker, industry)] for a group, optionally filtered by industry."""
    if industry:
        return conn.execute(
            "SELECT ticker, industry FROM group_members "
            "WHERE group_name = ? AND industry = ? ORDER BY ticker",
            (group_name, industry),
        ).fetchall()
    return conn.execute(
        "SELECT ticker, industry FROM group_members "
        "WHERE group_name = ? ORDER BY ticker",
        (group_name,),
    ).fetchall()
