"""Do the level-lab survivors add to the funded book? (day shift 2026-10-23)

New legs from scripts/level_lab.py on the BARS5 panel, pre-registered settings:
  OD   open drive, tolerance 0.05%, threshold 0.15% (10:00 entry, flat 15:55)
  IB   initial balance break, target IB edge + 1.0 x IB range
Both with the book's vol gate (prior-day 20d realised vol < 0.30). Prints the
daily P&L correlation with the existing legs and the time-aware account
result (timed_book.days_for / outcomes / life), flat 3 MNQ per leg.

Usage: level_book.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
from timed_book import legs, days_for, outcomes, life  # noqa: E402
from rescore_all import rvol  # noqa: E402


def new_legs(data):
    days = L.load(data)
    L.annotate(days)
    reg = rvol()
    out = []
    for leg, fn in (("OD", lambda d, p: L.odrive(d, p, 0.0005, 0.0015)), ("IB", lambda d, p: L.ib(d, p, 1.0))):
        for t in L.trades(days, fn):
            if reg.get(t["date"], 9.0) >= 0.30:
                continue
            out.append((t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, leg))
    return out


def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 0.0


def main():
    data = sys.argv[1]
    tr = legs(f"{data}/fixed", data) + new_legs(data)
    by = defaultdict(lambda: defaultdict(float))
    for d, _, _, usd, leg in tr:
        by[leg][d] += usd
    cal = sorted({t[0] for t in tr})
    names = ["ORB", "VG", "Z", "RS", "OD", "IB"]
    print("daily P&L correlation (all days, 0 when flat)")
    print("      " + "".join(f"{n:>6}" for n in names))
    for a in names:
        print(f"{a:>6}" + "".join(f"{corr([by[a][d] for d in cal], [by[b][d] for d in cal]):6.2f}" for b in names))
    for leg in ("OD", "IB"):
        for lo, hi in (("0", "2022"), ("2022", "9")):
            v = [t[3] for t in tr if t[4] == leg and lo <= t[0] < hi]
            print(f"{leg} {lo}-{hi}: n {len(v)}  ${st.mean(v):+.1f} per MNQ per trade (gated)")
    books = {"ORB+VG+Z+RS (now)": ("ORB", "VG", "Z", "RS"), "+ OD": ("ORB", "VG", "Z", "RS", "OD"),
             "+ IB": ("ORB", "VG", "Z", "RS", "IB"), "+ OD + IB": ("ORB", "VG", "Z", "RS", "OD", "IB"),
             "OD instead of ORB": ("VG", "Z", "RS", "OD"), "ORB+VG+Z (no RS)": ("ORB", "VG", "Z"),
             "ORB+VG+Z + OD": ("ORB", "VG", "Z", "OD")}
    print("\ntime-aware sim, flat 3 MNQ per leg, no day stop; mean 24-month cash per account, 2018-21 | 2022-25")
    for bn, use in books.items():
        res = []
        for lo, hi in (("0", "2022"), ("2022", "9")):
            c = [d for d in cal if lo <= d < hi]
            days = days_for(tr, c, 3, 10 ** 9, use)
            sz = lambda room: (3.0, 10 ** 9)
            f1 = outcomes(days, sz, window=300, start_pnl=0.0, target=4000.0, consistency=False)
            rp = outcomes(days, sz, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
            res.append(life(f1, rp))
        print(f"   {bn:<20} ${res[0]:8,.0f} | ${res[1]:8,.0f}")


if __name__ == "__main__":
    main()
