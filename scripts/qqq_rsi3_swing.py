"""'QQQ RSI(3) + 10-day VWAP' swing long (owner screenshot 2026-10-27), tested
on NQ RTH daily values built from our 5-min bars (rules as published, fixed
before results):
  1 RSI(3) (Wilder) of the RTH close < 22
  2 EMA(100) of the close > its value 5 days ago
  3 close <= 1% below the 10-day rolling VWAP (all 5-min bars of the last
    10 sessions incl. today)
  4 buy at the next session's RTH open
  5 exit at the RTH close of the first day RSI(3) > 55; one position at a time
SWING holds overnight -> NOT allowed on Lucid Flex (owner rule), shown for
information. Data are RAW continuous futures (QC open-interest mapping), so
a trade over a quarterly roll carries the roll gap (contango, ~+0.1-0.4%):
SWING is slightly flattered. Intraday variants (Lucid-compatible, no roll):
  D1  signal day + 1: buy 09:30 open, sell 15:55
  D1x same but only while the swing would still be open (every held day)
Usage: qqq_rsi3_swing.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402


def tt(v):
    return st.mean(v) / (st.pstdev(v) / math.sqrt(len(v))) if len(v) > 2 and st.pstdev(v) else 0.0


def cell(v):
    if not v:
        return "      -       "
    return f"{st.mean(v):+6.1f}({tt(v):+4.1f})n{len(v):<4d}"


def by_era(rs):
    return [[x for d, x in rs if lo <= d < hi] for _, lo, hi in B.ERAS]


def series(days):
    cl = [b[77][3] for _, b in days]
    pv = [sum((x[1] + x[2] + x[3]) / 3 * x[4] for x in b) for _, b in days]
    vv = [sum(x[4] for x in b) for _, b in days]
    rsi, ag, al = [None] * len(cl), 0.0, 0.0
    for i in range(1, len(cl)):
        ch = cl[i] - cl[i - 1]
        g, lo = max(ch, 0.0), max(-ch, 0.0)
        if i <= 3:
            ag += g / 3; al += lo / 3
        else:
            ag = (ag * 2 + g) / 3; al = (al * 2 + lo) / 3
        if i >= 3:
            rsi[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    ema, a = [cl[0]], 2 / 101
    for c in cl[1:]:
        ema.append(ema[-1] + a * (c - ema[-1]))
    vw = [None] * len(cl)
    for i in range(9, len(cl)):
        vw[i] = sum(pv[i - 9:i + 1]) / sum(vv[i - 9:i + 1])
    return cl, rsi, ema, vw


def main():
    days = B.load(sys.argv[1])
    cl, rsi, ema, vw = series(days)
    swing, d1, d1x, held = [], [], [], 0
    i = 110
    while i < len(days) - 1:
        if rsi[i] < 22 and ema[i] > ema[i - 5] and cl[i] <= vw[i] * 0.99:
            j = i + 1
            e = days[j][1][0][0]
            d1.append((days[j][0], (days[j][1][76][3] / e - 1) * 1e4))
            k = j
            while k < len(days) - 1 and not rsi[k] > 55:
                k += 1
            for m in range(j, k + 1):
                b = days[m][1]
                d1x.append((days[m][0], (b[76][3] / b[0][0] - 1) * 1e4))
            swing.append((days[j][0], (cl[k] / e - 1) * 1e4))
            held += k - j + 1
            i = k + 1
            continue
        i += 1
    allday = [(days[m][0], (days[m][1][76][3] / days[m][1][0][0] - 1) * 1e4) for m in range(110, len(days))]
    hold = [(days[m][0], (cl[m] / cl[m - 1] - 1) * 1e4) for m in range(110, len(days))]
    print("eras:", " | ".join(e[0] for e in B.ERAS), "  (gross bp per trade / day)")
    print("SWING published   ", " ".join(cell(v) for v in by_era(swing)))
    xs = [x for _, x in swing]
    print(f"  all: n {len(xs)}, mean {st.mean(xs):+.1f} bp, win {sum(x > 0 for x in xs) / len(xs):.0%}, "
          f"days held {held} ({held / (len(days) - 110):.0%} of days), worst {min(xs):+.0f} bp, "
          f"sum {sum(xs) / 100:+.0f}% simple")
    print(f"  buy & hold close-close per day {st.mean(x for _, x in hold):+.2f} bp x days held = "
          f"{st.mean(x for _, x in hold) * held / 100:+.0f}% simple (exposure-matched baseline)")
    print("D1 open->15:55    ", " ".join(cell(v) for v in by_era(d1)))
    print("D1x every held day", " ".join(cell(v) for v in by_era(d1x)))
    print("any day open->15:55", " ".join(cell(v) for v in by_era(allday)))
    yr = {}
    for d, x in swing:
        yr.setdefault(d[:4], []).append(x)
    print("SWING by year:", " ".join(f"{y}:{sum(v):+.0f}/{len(v)}" for y, v in sorted(yr.items())))


if __name__ == "__main__":
    main()
