"""Yu, Rentzler & Wolf (Nasdaq-100 futures): opening momentum or reversal depends
on the signs of yesterday's and last night's returns. Rule (fixed 2026-10-23):
regime = (sign of yesterday's RTH return open->16:00, sign of the overnight
return 16:00 close -> 09:30 open); signal = sign of the first 30 minutes
(09:30 open -> 10:00 close). For each of the 4 regimes, 2018-2021 picks
'follow' or 'fade' (the sign of the mean 10:00 -> 15:55 return times the
signal); 2022-2025 is traded unchanged. Entry 10:00 close, flat 15:55,
stop 0.40% (and none). Costs as level_lab.py.

Usage: yrw_lab.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402


def main():
    days = L.load(sys.argv[1])
    rows = []
    for prev, d in zip(days, days[1:]):
        if d["exp"] != prev["exp"]:
            continue
        pb, b = prev["bars"], d["bars"]
        if len(pb) < 78:
            continue
        y = 1 if pb[77][3] > pb[0][0] else -1
        n = 1 if b[0][0] > pb[77][3] else -1
        s = 1 if b[5][3] > b[0][0] else -1
        rows.append({"date": d["date"], "reg": (y, n), "s": s, "b": b})
    fit = {}
    print("2018-21 mean 10:00->15:55 return x first-30-min sign (gross pt):")
    for reg in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        v = [r["s"] * (r["b"][L.EOD][3] - r["b"][5][3]) for r in rows if r["reg"] == reg and r["date"] < "2022"]
        fit[reg] = 1 if st.mean(v) > 0 else -1
        w = [r["s"] * (r["b"][L.EOD][3] - r["b"][5][3]) for r in rows if r["reg"] == reg and r["date"] >= "2022"]
        print(f"   yesterday {reg[0]:+d} overnight {reg[1]:+d}: {st.mean(v):+6.2f} (n {len(v)}) -> "
              f"{'follow' if fit[reg] == 1 else 'fade'};  2022-25 same stat {st.mean(w):+6.2f} (n {len(w)})")
    for stop in (0.004, None):
        a, bb = [], []
        for r in rows:
            d = fit[r["reg"]] * r["s"]
            e = r["b"][5][3]
            pts = L.run(r["b"], 5, d, e, e * (1 - d * stop) if stop else -1e9 * d)[0]
            (a if r["date"] < "2022" else bb).append(pts)
        print(f"rule, stop {stop}: 2018-21 {L.stat(a)} | 2022-25 {L.stat(bb)}")


if __name__ == "__main__":
    main()
