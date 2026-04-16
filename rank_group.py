"""Rank the members of a named group.

Usage:
    python rank_group.py <group_name> [--industry "GICS Sub-Industry"]

Examples:
    python rank_group.py sp500_information_technology
    python rank_group.py sp500_information_technology --industry Semiconductors
    python rank_group.py sp400_industrials
"""

import sys

import db
import rank


def _parse_args(argv):
    if len(argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    group_name = argv[1]
    industry = None
    if "--industry" in argv:
        idx = argv.index("--industry")
        if idx + 1 >= len(argv):
            print("--industry needs a value")
            raise SystemExit(1)
        industry = argv[idx + 1]
    return group_name, industry


def main():
    group_name, industry = _parse_args(sys.argv)
    conn = db.connect()
    rank.rank(conn, group_name, industry=industry)


if __name__ == "__main__":
    main()
