"""Overnight participation (day shift 2026-10-26, fixed before results).
ONR = overnight volume (18:00-09:30) / mean RTH volume of the previous 20
sessions (H rows of the 5-min panels). Overnight move = 09:30 open / prior
RTH close (15:55 bar close) - 1.
O1: on high-ONR days (top tercile, cut fixed on 2018-21) trade the overnight
    direction from the 10:00 close to 15:55 (overnight news with heavy
    participation keeps going in the day session?); also low-ONR days.
O2: |RTH return 10:00-15:55| (range day vs trend day) by ONR tercile - does
    heavy overnight participation predict a trending day (for the legs)?
Gross bp, day-clustered, four eras + 2026.
v2 (after v1: overnight volume grew over the years, so absolute ONR terciles
do not transfer between eras): ONR relative to its own 60-day median.
Usage: on_volume.py DATA_DIR
"""
from __future__ import annotations

import os
import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import level_lab as L  # noqa: E402


def onvol(data):
    m = {}
    for nm in ("B2_0A", "B2_0B", "BARS5A", "BARS5B", "B2_26"):
        p = os.path.join(data, f"{nm}_tags.txt")
        for raw in open(p):
            f = raw.split(",")
            if f[0] == "H" and len(f) >= 12:
                m[f"{f[1][:4]}-{f[1][4:6]}-{f[1][6:]}"] = (float(f[6]), float(f[10]))
    return m


def main():
    data = sys.argv[1]
    days = B.load(data)
    ov = onvol(data)
    rows = []
    for i in range(21, len(days)):
        d, b = days[i]
        if d not in ov:
            continue
        rth = [ov[days[j][0]][1] for j in range(i - 20, i) if days[j][0] in ov]
        if len(rth) < 15 or st.mean(rth) <= 0:
            continue
        onr = ov[d][0] / st.mean(rth)
        prev_close = days[i - 1][1][L.EOD][3]
        onmove = b[0][0] / prev_close - 1
        r = (b[L.EOD][3] / b[5][3] - 1) * 1e4
        rows.append([d, onr, onmove, r])
    if os.environ.get("ONV2"):
        raw = [x[1] for x in rows]
        rows = [[x[0], x[1] / st.median(raw[max(0, i - 60):i]), x[2], x[3]] for i, x in enumerate(rows) if i >= 60]
    tune = sorted(x[1] for x in rows if "2018" <= x[0] < "2022")
    q1, q2 = tune[len(tune) // 3], tune[2 * len(tune) // 3]
    print(f"ONR terciles (2018-21): {q1:.3f} / {q2:.3f}")
    for lab, lo, hi in B.ERAS:
        sel = [x for x in rows if lo <= x[0] < hi]
        cells = []
        for name, a, c in (("low", 0, q1), ("mid", q1, q2), ("high", q2, 99)):
            g = [x for x in sel if a <= x[1] < c and x[2] != 0]
            o1 = [(x[0], x[3] * (1 if x[2] > 0 else -1)) for x in g]
            o2 = [abs(x[3]) for x in g]
            cells.append(f"{name}: follow ON {B.stat(o1)} |move| {st.mean(o2) if o2 else 0:5.1f} n{len(g)}")
        print(f"{lab:<8} " + " || ".join(cells))


if __name__ == "__main__":
    main()
