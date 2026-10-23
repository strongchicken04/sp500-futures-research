"""Group 8, afternoon rules (fixed 2026-10-23 before results), four eras on the
BARS5 panel (B2_0A/B 2010-17, BARS5A/B 2018-25). Reported in bp of price,
gross and net (0.75 pt + 0.25 pt on stops at the trade's price).
  MRB    morning range 09:30-12:00; from 12:00 to 15:00 the first 5-min close
         beyond it -> go with it; stop at the range middle; flat 15:55.
  PMFADE at 13:00, if 09:30 open -> 13:00 moved >= 0.5%, fade it; stop 0.5%;
         flat 15:55.
  PMTREND the same but follow the move (control).
  LHB    range 14:00-15:00; first close beyond it 15:00-15:45 -> go with it;
         stop at the other side; flat 15:55.
Usage: pm_lab.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402

ERAS = (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"), ("2022-25", "2022", "2026"))


def brk(b, lo_i, hi_i, start, last, stop_mid):
    h = max(x[1] for x in b[lo_i:hi_i])
    lo = min(x[2] for x in b[lo_i:hi_i])
    for i in range(start, last + 1):
        c = b[i][3]
        if c > h or c < lo:
            s = 1 if c > h else -1
            stop = (h + lo) / 2 if stop_mid else (lo if s == 1 else h)
            return s, L.run(b, i, s, c, stop), c
    return None


def pm(b, follow):
    o, c = b[0][0], b[41][3]                 # bar 41 ends 13:00
    m = c / o - 1
    if abs(m) < 0.005:
        return None
    s = (1 if m > 0 else -1) * (1 if follow else -1)
    return s, L.run(b, 41, s, c, c * (1 - s * 0.005)), c


RULES = {"MRB": lambda b: brk(b, 0, 30, 30, 65, True), "PMFADE": lambda b: pm(b, False),
         "PMTREND": lambda b: pm(b, True), "LHB": lambda b: brk(b, 54, 66, 66, 74, False)}


def main():
    L.NAMES = ("B2_0A", "B2_0B", "BARS5A", "BARS5B")
    L.COST, L.STOP_COST = 0.0, 0.0
    days = L.load(sys.argv[1])
    for name, fn in RULES.items():
        cells = []
        for lab, lo, hi in ERAS:
            g, n = [], []
            for d in days:
                if not (lo <= d["date"] < hi):
                    continue
                r = fn(d["bars"])
                if not r:
                    continue
                s, (pts, why, i, k), e = r
                gb = pts / e * 1e4
                cost = (0.75 + (0.25 if why == "SL" else 0.0)) / e * 1e4
                g.append(gb)
                n.append(gb - cost)
            t = st.mean(g) / st.pstdev(g) * math.sqrt(len(g)) if len(g) > 2 else 0
            cells.append(f"{lab} {st.mean(g):+5.1f} (net {st.mean(n):+5.1f}) t{t:+4.1f} n{len(g)}")
        print(f"{name:<8} " + " | ".join(cells))


if __name__ == "__main__":
    main()
