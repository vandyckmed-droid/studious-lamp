"""Rebuild group membership from Wikipedia. Run monthly."""

import db
import groups


def main():
    conn = db.connect()

    print("Fetching S&P 500 constituents...")
    n500 = groups.refresh_sp500(conn)
    print(f"  {n500} tickers")

    print("Fetching S&P 400 constituents...")
    n400 = groups.refresh_sp400(conn)
    print(f"  {n400} tickers")

    print()
    print("Groups now in DB:")
    for name, sector, count in groups.list_groups(conn):
        print(f"  {name:<45} {count:>4}  ({sector})")


if __name__ == "__main__":
    main()
