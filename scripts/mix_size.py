"""Book with extra momentum legs at smaller size (day shift 2026-10-23).
Legs ORB, VG, Z, RS (now flat 3 each) plus open drive (OD) and prior-week
break (PW); each leg gets its own MNQ count. Time-aware sim, no day stop,
mean 24-month cash per account (as timed_book.py). Grid fixed in advance.
Usage: mix_size.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
import ict_lab as I  # noqa: E402
from timed_book import legs, days_for, outcomes, life  # noqa: E402
from rescore_all import rvol  # noqa: E402

MIXES = [
    {"ORB": 3, "VG": 3, "Z": 3, "RS": 3},
    {"ORB": 3, "VG": 3, "Z": 3, "RS": 3, "OD": 1},
    {"ORB": 3, "VG": 3, "Z": 3, "RS": 3, "PW": 1},
    {"ORB": 3, "VG": 3, "Z": 3, "RS": 3, "OD": 1, "PW": 1},
    {"ORB": 3, "VG": 3, "Z": 3, "RS": 3, "OD": 2},
    {"ORB": 2, "VG": 2, "Z": 2, "RS": 2, "OD": 2, "PW": 2},
    {"ORB": 2, "VG": 3, "Z": 3, "RS": 3, "OD": 1},
    {"ORB": 4, "VG": 4, "Z": 4, "RS": 4},
]


def main():
    data = sys.argv[1]
    days = I.load(data)
    reg = rvol()
    extra = []
    for leg, fn in (("OD", lambda d, p: L.odrive(d, p, 0.0005, 0.0015)), ("PW", I.pwbrk)):
        extra += [(t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, leg) for t in L.trades(days, fn)
                  if reg.get(t["date"], 9.0) < 0.30]
    base = legs(f"{data}/fixed", data) + extra
    cal = sorted({t[0] for t in base})
    print("mean 24-month cash per account, 2018-21 | 2022-25 (MNQ per leg)")
    for mix in MIXES:
        tr = [(d, e, x, usd * mix[leg], leg) for d, e, x, usd, leg in base if leg in mix]
        res = []
        for lo, hi in (("0", "2022"), ("2022", "9")):
            c = [d for d in cal if lo <= d < hi]
            dd = days_for(tr, c, 1, 10 ** 9, tuple(mix))
            sz = lambda room: (1.0, 10 ** 9)
            f1 = outcomes(dd, sz, window=300, start_pnl=0.0, target=4000.0, consistency=False)
            rp = outcomes(dd, sz, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
            res.append(life(f1, rp))
        lab = " ".join(f"{k}{v}" for k, v in mix.items())
        print(f"   {lab:<36} ${res[0]:8,.0f} | ${res[1]:8,.0f}")


if __name__ == "__main__":
    main()
