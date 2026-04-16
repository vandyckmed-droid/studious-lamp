"""Snapshot mom_12_1 and vol_63 for every tracked ticker into the signals table."""

import db
import signals


def main():
    conn = db.connect()
    tickers = db.all_tracked_tickers(conn)
    if not tickers:
        print("No tickers in DB. Run refresh_groups.py first.")
        return

    print(f"Computing signals for {len(tickers)} tickers...")
    written, as_of = signals.compute_for(conn, tickers)
    print(f"Wrote {written} rows as_of={as_of}.")


if __name__ == "__main__":
    main()
