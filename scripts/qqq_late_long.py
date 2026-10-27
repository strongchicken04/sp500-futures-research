"""'Quantified Strategies' QQQ late-day long (owner screenshot 2026-10-27),
tested on NQ 5-min RTH bars (rules as published, fixed before results):
  1 previous RTH close < 50-day SMA of RTH closes
  2 RTH open > previous RTH close x (1 + 0.60%)
  3 at 15:00 ET (close of bar 65) close > today's open
  4 at 15:00 range position (close - low) / (high - low) > 0.77
  5 buy at 15:00 close (= ~15:05 bar open), long only
  6 hard stop 1% below entry (1% of the position)
  7 exit at the 16:00 close (bar 77)
Gross bp per trade, by era + 2026; baselines: every day 15:00->16:00 long,
and rules 3+4 alone (no trend / gap filter). Small robustness grid around
the published thresholds (gap 0.4/0.6/0.8, range 0.70/0.77/0.85, SMA on/off).
Usage: qqq_late_long.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402

K_SIG, K_END = 65, 77      # bar ending 15:00, bar ending 16:00
STOP = 0.01
FEE_BP = 0.6               # MNQ round turn + 1 tick slippage at NQ ~28.5k


def trade(b):
    e = b[K_SIG][3]
    for o, h, lo, c, v in b[K_SIG + 1:K_END + 1]:
        if lo <= e * (1 - STOP):
            return -STOP * 1e4
    return (b[K_END][3] / e - 1) * 1e4


def tt(v):
    return st.mean(v) / (st.pstdev(v) / math.sqrt(len(v))) if len(v) > 2 and st.pstdev(v) else 0.0


def cell(v):
    if not v:
        return "      -      "
    return f"{st.mean(v):+5.1f}({tt(v):+4.1f})n{len(v):<3d}"


def rows(days, gap=0.006, rng=0.77, sma=True, need_gap=True):
    out = []
    closes = [b[K_END][3] for _, b in days]
    for i in range(50, len(days)):
        d, b = days[i]
        pc = closes[i - 1]
        if sma and not pc < sum(closes[i - 50:i]) / 50:
            continue
        if need_gap and not b[0][0] > pc * (1 + gap):
            continue
        c = b[K_SIG][3]
        hi = max(x[1] for x in b[:K_SIG + 1])
        lo = min(x[2] for x in b[:K_SIG + 1])
        if not (c > b[0][0] and hi > lo and (c - lo) / (hi - lo) > rng):
            continue
        out.append((d, trade(b)))
    return out


def by_era(rs):
    return [[x for d, x in rs if lo <= d < hi] for _, lo, hi in B.ERAS]


def main():
    days = B.load(sys.argv[1])
    print("eras:", " | ".join(e[0] for e in B.ERAS), f"  (gross bp, fee ~{FEE_BP} bp)")
    base = [(d, trade(b)) for d, b in days[50:]]
    print("every day 15:00->16:00  ", " ".join(cell(v) for v in by_era(base)))
    print("rules 3+4 only          ", " ".join(cell(v) for v in by_era(rows(days, sma=False, need_gap=False))))
    print("rules 2+3+4 (no SMA)    ", " ".join(cell(v) for v in by_era(rows(days, sma=False))))
    pub = rows(days)
    print("PUBLISHED 1-7           ", " ".join(cell(v) for v in by_era(pub)))
    xs = [x for _, x in pub]
    if xs:
        print(f"  all: n {len(xs)}, mean {st.mean(xs):+.1f} bp, win {sum(x > 0 for x in xs) / len(xs):.0%}, "
              f"stops {sum(x <= -99.9 for x in xs)}, per trade on 1 MNQ at 28,530: "
              f"${st.mean(xs) / 1e4 * 28530 * 2 - 3:+.0f} net")
    print("grid (all years): gap x range, SMA on / off")
    for g in (0.004, 0.006, 0.008):
        line = []
        for r in (0.70, 0.77, 0.85):
            for s in (True, False):
                v = [x for _, x in rows(days, g, r, s)]
                line.append(f"{'S' if s else '-'}{r:.2f}:{st.mean(v) if v else 0:+5.1f}({tt(v):+4.1f})n{len(v)}")
        print(f"  gap {g:.1%}  " + "  ".join(line))


if __name__ == "__main__":
    main()
