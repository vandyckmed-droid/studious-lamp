"""Refresh FMP fundamentals older than 30 days, up to the daily call budget."""

import db
import fundamentals


def main():
    conn = db.connect()
    tickers = db.all_tracked_tickers(conn)
    if not tickers:
        print("No tickers in DB. Run refresh_groups.py first.")
        return

    api_key = fundamentals.load_api_key()
    print(f"Refreshing fundamentals for {len(tickers)} tickers...\n")
    refreshed, calls = fundamentals.update(conn, tickers, api_key)
    print(f"\nDone. {refreshed} tickers refreshed, {calls} FMP calls used.")


if __name__ == "__main__":
    main()
