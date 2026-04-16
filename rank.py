"""Cross-sectional ranking within a group.

Pulls the latest `signals` row and fundamentals `ratios` for every
member of the group (optionally filtered to a single GICS industry),
z-scores each signal within the slice, averages into an `AvgZ`, and
prints a ranked table.
"""

import math

import fundamentals
import groups
import signals


SIGNAL_FIELDS = ["mom_12_1", "vol_neg", "gpa", "leverage", "ebit_ev"]


def _collect(conn, group_name, industry=None):
    """Build the per-ticker metric dict."""
    rows = groups.members(conn, group_name, industry=industry)
    data = {}
    for ticker, sub in rows:
        sig = signals.latest(conn, ticker)
        rat = fundamentals.ratios(conn, ticker)
        entry = {"industry": sub}
        if "mom_12_1" in sig and sig["mom_12_1"] is not None:
            entry["mom_12_1"] = sig["mom_12_1"]
        # Lower vol = better, so negate it before z-scoring.
        if "vol_63" in sig and sig["vol_63"] is not None:
            entry["vol_neg"] = -sig["vol_63"]
            entry["vol_63"] = sig["vol_63"]
        entry.update(rat)
        data[ticker] = entry
    return data


def _z_score(data, fields):
    for field in fields:
        values = [d[field] for d in data.values() if field in d]
        if len(values) < 2:
            continue
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(var) if var > 0 else 0
        if std == 0:
            continue
        for d in data.values():
            if field in d:
                d[field + "_z"] = (d[field] - mean) / std


def rank(conn, group_name, industry=None):
    data = _collect(conn, group_name, industry=industry)
    if not data:
        print(f"No members in group '{group_name}'"
              + (f" industry='{industry}'" if industry else ""))
        return

    _z_score(data, SIGNAL_FIELDS)

    rows = []
    for ticker, d in data.items():
        zs = [d[f + "_z"] for f in SIGNAL_FIELDS if f + "_z" in d]
        if not zs or "mom_12_1_z" not in d:
            continue
        rows.append({
            "ticker": ticker,
            "industry": d.get("industry") or "",
            "mom_z": d.get("mom_12_1_z"),
            "vol_z": d.get("vol_neg_z"),
            "gpa_z": d.get("gpa_z"),
            "lev_z": d.get("leverage_z"),
            "val_z": d.get("ebit_ev_z"),
            "avg_z": sum(zs) / len(zs),
            "vol_63": d.get("vol_63"),
        })

    rows.sort(key=lambda r: r["avg_z"], reverse=True)

    header = f"  {group_name}"
    if industry:
        header += f"  /  {industry}"
    print()
    print("=" * 80)
    print(header)
    print(f"  {len(rows)} ranked / {len(data)} members")
    print("=" * 80)
    print()
    print(f"  {'#':>3} {'Tkr':<6} {'MomZ':>6} {'VolZ':>6} {'GpaZ':>6} "
          f"{'LevZ':>6} {'ValZ':>6} {'AvgZ':>6}  {'Industry'}")

    def fmt(v):
        return f"{v:>+5.2f}" if v is not None else "   --"

    for i, r in enumerate(rows, 1):
        print(
            f"  {i:3d} {r['ticker']:<6} {fmt(r['mom_z'])} {fmt(r['vol_z'])} "
            f"{fmt(r['gpa_z'])} {fmt(r['lev_z'])} {fmt(r['val_z'])} "
            f"{fmt(r['avg_z'])}  {r['industry']}"
        )
    print()
