"""Order-flow ideas on 5-min OHLCV (day shift 2026-10-26, rules fixed before
results; aggressive volume estimated by bulk volume classification as in
big_trades.py - real aggressor data would be better).

ABSORPTION: bar k (ending 10:05 .. 15:30 ET) with volume >= 2.5 x its 20-day
  time-of-day mean, range <= 0.6 x its 20-day mean range (v1; v2 after v1
  gave ~0 events: 2.0 x volume, range <= 1.0 x), and the bar makes a
  new high of the day (high above all earlier RTH bars) -> SHORT at its close;
  new low of the day -> LONG. (Big volume that does not move price at the
  extreme = passive orders absorbing the aggressors.)
DELTA DIVERGENCE: cumulative estimated delta since 09:30 (sum of volume x
  (2 x buy share - 1)). Bar k makes a new high of the day while cum delta is
  BELOW its value at the bar of the previous day high, set >= 6 bars earlier
  -> SHORT; mirror at a new low with cum delta above -> LONG. First per day.
Forward gross bp from the close of bar k: 15 / 30 / 60 min and 15:55,
day-clustered t; four eras + 2026. A strategy check follows only if the
event average is positive in all four eras.
Usage: orderflow_proxy.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import level_lab as L  # noqa: E402


ABS_V, ABS_R = 2.5, 0.6     # v2 (after v1 gave ~0 events): 2.0 / 1.0


def scan(days):
    ab, dv = [], []
    for i in range(20, len(days)):
        d, b = days[i]
        prev = [x[1] for x in days[i - 20:i]]
        rets = [p[k][3] / p[k - 1][3] - 1 for p in prev for k in range(1, 78)]
        sig = st.pstdev(rets)
        if sig <= 0:
            continue
        hi = lo = None
        cum = 0.0
        hi_k = lo_k = None
        hi_cum = lo_cum = None
        div_done = False
        for k in range(0, B.K1 + 1):
            o, h, l, c, v = b[k]
            share = B.phi((c / b[k - 1][3] - 1) / sig) if k else 0.5
            cum += v * (2 * share - 1)
            new_hi = hi is not None and h > hi
            new_lo = lo is not None and l < lo
            if k >= B.K0:
                av = sum(p[k][4] for p in prev) / 20
                ar = sum(p[k][1] - p[k][2] for p in prev) / 20
                if av > 0 and ar > 0 and v >= ABS_V * av and (h - l) <= ABS_R * ar:
                    if new_hi:
                        ab.append((d, k, -1, b))
                    elif new_lo:
                        ab.append((d, k, 1, b))
                if not div_done:
                    if new_hi and hi_k is not None and k - hi_k >= 6 and cum < hi_cum:
                        dv.append((d, k, -1, b)); div_done = True
                    elif new_lo and lo_k is not None and k - lo_k >= 6 and cum > lo_cum:
                        dv.append((d, k, 1, b)); div_done = True
            if hi is None or h > hi:
                hi, hi_k, hi_cum = h, k, cum
            if lo is None or l < lo:
                lo, lo_k, lo_cum = l, k, cum
    return ab, dv


def main():
    global ABS_V, ABS_R
    days = B.load(sys.argv[1])
    ab, dv = scan(days)
    ABS_V, ABS_R = 2.0, 1.0
    ab2, _ = scan(days)
    for name, evs in (("ABSORPTION fade v1 (2.5x vol, range <= 0.6x)", ab), ("ABSORPTION fade v2 (2x vol, range <= 1x)", ab2),
                      ("DELTA DIVERGENCE", dv)):
        print(f"=== {name}")
        for lab, lo, hi in B.ERAS:
            sel = [e for e in evs if lo <= e[0] < hi]
            cells = [f"{h}: {B.stat([(d_, B.fwd(b, k, d, n)) for d_, k, d, b in sel])}" for h, n in B.HOR]
            print(f"   {lab:<8} n {len(sel):5d} ({len({e[0] for e in sel}):4d} days) | " + " | ".join(cells))


if __name__ == "__main__":
    main()
