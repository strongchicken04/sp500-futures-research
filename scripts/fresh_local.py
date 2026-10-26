"""Fresh ideas on the local 5-min NQ panels (day shift 2026-10-26, rules fixed
before results; owner: "completely fresh" angles).

F7 ROUND NUMBERS: grid 100 pt (price >= 10,000), 50 pt (4,000-10,000), 25 pt
   (below). The first bar after 10:00 ET whose range crosses a grid level that
   the session (from 09:30) has not touched yet; direction of approach d = +1
   if the previous close was below the level. Forward return from the LEVEL in
   the approach direction (continuation > 0 = break, < 0 = bounce) to the close
   of bar k + 3 / 6 / 12 and 15:55. First such touch per day.
F8 COMPRESSION -> BREAKOUT: at the close of bar k (ending 10:30 .. 14:30 ET)
   the last 12 bars (1 hour) span (max high - min low) <= 0.5 x the 20-day mean
   span of the same hour; the first later 5-min close outside the box -> trade
   that way, stop at the other side of the box, exit 15:55. One per day.
   Gross bp per trade.
Day-clustered t, four eras + 2026.
Usage: fresh_local.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import level_lab as L  # noqa: E402


def grid(p):
    return 100.0 if p >= 10000 else (50.0 if p >= 4000 else 25.0)


def f7(days):
    out = []
    for d, b in days:
        lo = min(x[2] for x in b[:6])
        hi = max(x[1] for x in b[:6])
        for k in range(6, B.K1 + 1):
            o, h, l, c, v = b[k]
            g = grid(c)
            prev = b[k - 1][3]
            lv = None
            if h > hi:
                cand = math.floor(h / g) * g
                if cand > hi and cand > prev:
                    lv, dd = cand, 1
            if lv is None and l < lo:
                cand = math.ceil(l / g) * g
                if cand < lo and cand < prev:
                    lv, dd = cand, -1
            hi, lo = max(hi, h), min(lo, l)
            if lv is not None:
                out.append((d, k, dd, lv, b))
                break
    return out


def f8(days):
    out = []
    for i in range(20, len(days)):
        d, b = days[i]
        prev = [x[1] for x in days[i - 20:i]]
        for k in range(12, 60):
            span = max(x[1] for x in b[k - 11:k + 1]) - min(x[2] for x in b[k - 11:k + 1])
            ref = st.mean(max(x[1] for x in p[k - 11:k + 1]) - min(x[2] for x in p[k - 11:k + 1]) for p in prev)
            if ref > 0 and span <= 0.5 * ref:
                top, bot = max(x[1] for x in b[k - 11:k + 1]), min(x[2] for x in b[k - 11:k + 1])
                for j in range(k + 1, L.EOD):
                    c = b[j][3]
                    if c > top or c < bot:
                        dd = 1 if c > top else -1
                        pts, *_ = L.run(b, j, dd, c, bot if dd == 1 else top)
                        out.append((d, (pts + L.COST) / c * 1e4))
                        break
                break
    return out


def main():
    days = B.load(sys.argv[1])
    ev7 = f7(days)
    print("=== F7 round numbers: continuation from the level (bp; < 0 = bounce)")
    for lab, lo, hi in B.ERAS:
        sel = [e for e in ev7 if lo <= e[0] < hi]
        cells = []
        for h, n in (("15m", 3), ("30m", 6), ("60m", 12), ("EOD", None)):
            rows = []
            for d, k, dd, lv, b in sel:
                j = L.EOD if n is None else min(L.EOD, k + n)
                rows.append((d, dd * (b[j][3] / lv - 1) * 1e4))
            cells.append(f"{h}: {B.stat(rows)}")
        print(f"   {lab:<8} n {len(sel):4d} | " + " | ".join(cells))
    ev8 = f8(days)
    print("=== F8 compression breakout, stop other side, exit 15:55 (gross bp)")
    for lab, lo, hi in B.ERAS:
        sel = [(d, x) for d, x in ev8 if lo <= d < hi]
        print(f"   {lab:<8} n {len(sel):4d} | {B.stat(sel)}")


if __name__ == "__main__":
    main()
