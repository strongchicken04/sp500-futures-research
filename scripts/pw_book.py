"""Prior-week high/low break (stop 0.15%, flat 15:55, vol gate) as a funded
book leg: time-aware sim at flat 3 MNQ per leg (as level_book.py).
Usage: pw_book.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
import ict_lab as I  # noqa: E402
from level_book import corr  # noqa: E402
from timed_book import legs, days_for, outcomes, life  # noqa: E402
from rescore_all import rvol  # noqa: E402
from collections import defaultdict  # noqa: E402


def main():
    data = sys.argv[1]
    days = I.load(data)
    reg = rvol()
    pw = [(t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, "PW") for t in L.trades(days, I.pwbrk)
          if reg.get(t["date"], 9.0) < 0.30]
    tr = legs(f"{data}/fixed", data) + pw
    by = defaultdict(lambda: defaultdict(float))
    for d, _, _, usd, leg in tr:
        by[leg][d] += usd
    cal = sorted({t[0] for t in tr})
    print("corr PW vs " + ", ".join(f"{n} {corr([by['PW'][d] for d in cal], [by[n][d] for d in cal]):.2f}" for n in ("ORB", "VG", "Z", "RS")))
    for bn, use in {"ORB+VG+Z+RS (now)": ("ORB", "VG", "Z", "RS"), "+ PW": ("ORB", "VG", "Z", "RS", "PW")}.items():
        res = []
        for lo, hi in (("0", "2022"), ("2022", "9")):
            c = [d for d in cal if lo <= d < hi]
            dd = days_for(tr, c, 3, 10 ** 9, use)
            sz = lambda room: (3.0, 10 ** 9)
            f1 = outcomes(dd, sz, window=300, start_pnl=0.0, target=4000.0, consistency=False)
            rp = outcomes(dd, sz, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
            res.append(life(f1, rp))
        print(f"   {bn:<20} ${res[0]:8,.0f} | ${res[1]:8,.0f}")


if __name__ == "__main__":
    main()
