"""Re-check today's funded-book questions with the paired block bootstrap
(mc_book.py), separately on 2018-21 and 2022-25 histories.
Usage: mc_runs.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
import ict_lab as I  # noqa: E402
import gate_check as G  # noqa: E402
from mc_book import compare, summary  # noqa: E402
from rescore_all import rvol  # noqa: E402
from fomc_skip import FOMC  # noqa: E402


def sized(tr, mix):
    return [(d, e, x, usd * mix[leg], leg) for d, e, x, usd, leg in tr if leg in mix]


def main():
    data = sys.argv[1]
    base = G.build(data, set())
    zfree = G.build(data, {"Z"})
    days = I.load(data)
    reg = rvol()
    extra = []
    for leg, fn in (("OD", lambda d, p: L.odrive(d, p, 0.0005, 0.0015)), ("PW", I.pwbrk)):
        extra += [(t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, leg) for t in L.trades(days, fn)
                  if reg.get(t["date"], 9.0) < 0.30]
    four = {"ORB": 3, "VG": 3, "Z": 3, "RS": 3}
    cal_all = sorted({t[0] for t in base + zfree + extra})
    for lo, hi in (("0", "2022"), ("2022", "9")):
        cal = [d for d in cal_all if lo <= d < hi]
        V = {
            "now: ORB+VG+Z+RS flat 3": sized(base, four),
            "flat 2": sized(base, {k: 2 for k in four}),
            "flat 4": sized(base, {k: 4 for k in four}),
            "Z without vol gate": sized(zfree, four),
            "+ OD 1": sized(base + extra, dict(four, OD=1)),
            "+ OD 1 + PW 1": sized(base + extra, dict(four, OD=1, PW=1)),
            "+ OD 3": sized(base + extra, dict(four, OD=3)),
            "skip FOMC days": [t for t in sized(base, four) if t[0] not in FOMC],
            "no RS leg": sized(base, {"ORB": 3, "VG": 3, "Z": 3}),
            "no ORB leg": sized(base, {"VG": 3, "Z": 3, "RS": 3}),
        }
        print(f"--- {'2018-2021' if lo == '0' else '2022-2025'} ({len(cal)} days), mean 24-month cash per account")
        for line in summary(compare(V, cal, trials=3000), "now: ORB+VG+Z+RS flat 3"):
            print("   " + line)


if __name__ == "__main__":
    main()
