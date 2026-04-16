"""Incrementally fetch daily prices for every tracked ticker."""

import db
import prices


def main():
    conn = db.connect()
    tickers = db.all_tracked_tickers(conn)
    if not tickers:
        print("No tickers in DB. Run refresh_groups.py first.")
        return

    print(f"Updating prices for {len(tickers)} tickers...\n")
    updated, new_rows = prices.update(conn, tickers)
    print(f"\nDone. {updated} tickers touched, {new_rows} new bars inserted.")


if __name__ == "__main__":
    main()
