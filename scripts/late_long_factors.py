"""Late-day long ingredients (night 2026-10-27/28): strong days at 15:00
(close > open, range position > 0.77) split by trend (prev close below /
above SMA50) x opening gap (< -0.6%, -0.6..+0.6%, > +0.6%); long 15:00 ->
16:00 close, stop 1%, gross bp, four eras + 2026. Shows which ingredient
carries the published rule (gap up in a downtrend).
Usage: late_long_factors.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import qqq_late_long as Q  # noqa: E402


def main():
    days = B.load(sys.argv[1])
    cl = [b[77][3] for _, b in days]
    cells = {}
    for i in range(50, len(days)):
        d, b = days[i]
        pc = cl[i - 1]
        c = b[65][3]
        hi = max(x[1] for x in b[:66]); lo = min(x[2] for x in b[:66])
        if not (c > b[0][0] and hi > lo and (c - lo) / (hi - lo) > 0.77):
            continue
        tr = "below" if pc < sum(cl[i - 50:i]) / 50 else "above"
        g = b[0][0] / pc - 1
        gp = "gap<-0.6" if g < -0.006 else ("gap>+0.6" if g > 0.006 else "gap flat")
        cells.setdefault((tr, gp), []).append((d, Q.trade(b)))
    print("eras:", " | ".join(e[0] for e in B.ERAS), "  (strong days at 15:00, long -> 16:00, gross bp)")
    for k in sorted(cells):
        print(f"{k[0]:5s} {k[1]:9s}", " ".join(Q.cell(v) for v in Q.by_era(cells[k])))


if __name__ == "__main__":
    main()
