"""BUBBLE FADE strategy (day shift 2026-10-26; post-hoc from big_trades*.py,
so it has to hold in every era, by year and on the plateau).
Bubble at the close of 5-min bar k (bars ending 10:05 .. 15:30 ET): volume >=
R x the same bar's 20-day mean, estimated aggressive share >= F (bulk volume
classification), and the bubble direction agrees with BOTH the move since
the 09:30 open and the side of the session VWAP (a climactic push).
Trade AGAINST it at the close of bar k; exit at the close of bar k + H (H = 2 /
3 / 4 bars = 10 / 15 / 20 min) or at a stop 0.30% from the entry (checked from
the next bar, filled at the worse of stop and bar open); one position at a
time. Costs at today's NQ 28,530: 0.75 pt per MNQ round trip + 0.25 pt more on
stops (level_lab). Result per trade: gross bp, net $ per MNQ at today's NQ,
t, trades per year, share of positive years. Main cell R 2, F 0.80, H 3.
Usage: bubble_fade.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import level_lab as L  # noqa: E402

PRICE = 28530.0
STOP = 0.003


def trades(ev, R, F, H):
    out, busy_until = [], {}
    for d_, k, rv, sh, b, vw, rso in ev:
        if rv < R:
            continue
        bd = 1 if sh >= F else (-1 if sh <= 1 - F else 0)
        if bd == 0 or not (bd * (b[k][3] - vw) > 0 and bd * rso > 0):
            continue
        if busy_until.get(d_, -1) >= k:
            continue
        d, e = -bd, b[k][3]
        stop = e * (1 - d * STOP)
        x, hit, j = None, False, k
        for j in range(k + 1, min(L.EOD, k + H) + 1):
            o, h, lo, c, _ = b[j]
            if (d == 1 and lo <= stop) or (d == -1 and h >= stop):
                x, hit = (min(stop, o) if d == 1 else max(stop, o)), True
                break
        if x is None:
            x = b[j][3]
        busy_until[d_] = j
        g = d * (x - e) / e * 1e4
        net = g * PRICE / 1e4 * 2.0 - (0.75 + (0.25 if hit else 0)) * 2.0
        out.append((d_, g, net))
    return out


def main():
    days = B.load(sys.argv[1])
    ev_all = B.events(days)
    for R, F, H in [(2, 0.80, 3)] + [(r, f, h) for r in (2, 3) for f in (0.70, 0.80, 0.90) for h in (2, 3, 4) if (r, f, h) != (2, 0.80, 3)]:
        cells = []
        for lab, lo, hi in B.ERAS:
            tr = trades([e for e in ev_all if lo <= e[0] < hi], R, F, H)
            if len(tr) < 10:
                cells.append(f"{lab} n<10")
                continue
            nets = [n for _, _, n in tr]
            t = st.mean(nets) / (st.pstdev(nets) / math.sqrt(len(nets)))
            yrs = defaultdict(list)
            for d_, _, n in tr:
                yrs[d_[:4]].append(n)
            pos = sum(1 for v in yrs.values() if sum(v) > 0)
            ny = max(1, len({d[0][:4] for d in days if lo <= d[0] < hi}))
            cells.append(f"{lab} {st.mean(g for _, g, _ in tr):+4.1f}bp ${st.mean(nets):+5.1f}/MNQ (t{t:+4.1f}) {len(tr) / ny:3.0f}/yr yrs+ {pos}/{len(yrs)}")
        print(f"R{R} F{F:.2f} H{H * 5}m: " + " | ".join(cells))


if __name__ == "__main__":
    main()
