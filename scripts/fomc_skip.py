"""Funded book on FOMC days (day shift 2026-10-23): (a) as now, (b) no entries
on FOMC days, (c) no entries from 13:55 on FOMC days (statement 14:00). Time-
aware sim, flat 3 MNQ, ORB+VG+Z+RS; plus the legs' P&L on FOMC days.
FOMC dates as in strategy/quantconnect/news_fade_exporter.py.
Usage: fomc_skip.py DATA_DIR
"""
from __future__ import annotations

import re
import sys

sys.path.insert(0, "scripts")
from timed_book import legs, days_for, outcomes, life  # noqa: E402

src = open("strategy/quantconnect/news_fade_exporter.py").read()
FOMC = {f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in re.search(r'FOMC = set\("""(.*?)"""', src, re.S).group(1).split()}


def main():
    data = sys.argv[1]
    tr = legs(f"{data}/fixed", data)
    cal = sorted({t[0] for t in tr})
    use = ("ORB", "VG", "Z", "RS")
    for leg in use:
        v = [t[3] * 3 for t in tr if t[4] == leg and t[0] in FOMC]
        w = [t[3] * 3 for t in tr if t[4] == leg and t[0] not in FOMC]
        print(f"{leg:<4} FOMC days n {len(v):3d} mean ${sum(v) / max(1, len(v)):+7.1f} per trade (3 MNQ) | other days ${sum(w) / max(1, len(w)):+7.1f}")
    variants = {"as now": lambda t: True, "skip FOMC days": lambda t: t[0] not in FOMC,
                "no entries from 13:55 on FOMC days": lambda t: not (t[0] in FOMC and t[1] >= 835)}
    print("\nflat 3, mean 24-month cash per account, 2018-21 | 2022-25")
    for name, keep in variants.items():
        tt = [t for t in tr if keep(t)]
        res = []
        for lo, hi in (("0", "2022"), ("2022", "9")):
            c = [d for d in cal if lo <= d < hi]
            dd = days_for(tt, c, 3, 10 ** 9, use)
            sz = lambda room: (3.0, 10 ** 9)
            f1 = outcomes(dd, sz, window=300, start_pnl=0.0, target=4000.0, consistency=False)
            rp = outcomes(dd, sz, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
            res.append(life(f1, rp))
        print(f"   {name:<36} ${res[0]:8,.0f} | ${res[1]:8,.0f}")


if __name__ == "__main__":
    main()
