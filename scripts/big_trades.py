"""Big-trades bubbles (owner 2026-10-26: "when ~3x the average number of
aggressive orders hits one side at a given time a bubble shows - is it worth
entering on that alone, how long to hold, does another signal help? only
after the first half hour"). Rules fixed before results.

DATA LIMIT: our local data are 5-minute OHLCV bars (no tick data, no
aggressor side). Aggressive buy / sell volume is ESTIMATED with bulk volume
classification (Easley, Lopez de Prado, O'Hara 2012): buy share of a bar =
Phi(r / sigma), r = close / previous close - 1, sigma = stdev of 5-min returns
over the previous 20 sessions. A real big-trades indicator counts actual
aggressor-side trades; this is the closest test our data allow.

Bubble at the close of bar k (bars ending 10:05 .. 15:30 ET):
  rvol = bar volume / mean volume of the same bar over the previous 20 days
  BUY bubble:  rvol >= R and buy share >= F;  SELL: rvol >= R and buy share <= 1 - F
  main cell R = 3, F = 0.80; plateau R 2 / 3 / 4 x F 0.70 / 0.80 / 0.90
Trade WITH the bubble from the close of bar k; gross bp (costs ~0.3 bp at
NQ 28,500) after 15 / 30 / 60 min and at 15:55. Negative = fading pays.
Day-clustered t (events averaged per day). First bubble of the day and all.
Combinations (main cell): + VWAP side agrees, + trend since the open agrees,
+ both, and the control without the volume condition (buy share only).
Eras 2010-13 / 2014-17 / 2018-21 / 2022-25 / 2026.
Usage: big_trades.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402

ERAS = (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"),
        ("2022-25", "2022", "2026"), ("2026", "2026", "2027"))
HOR = (("15m", 3), ("30m", 6), ("60m", 12), ("EOD", None))
K0, K1 = 6, 71          # bars ending 10:05 .. 15:30


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def load(data):
    days = {}
    for names in (("B2_0A", "B2_0B"), ("BARS5A", "BARS5B"), ("B2_26",)):
        L.NAMES = names
        for d in L.load(data):
            days[d["date"]] = d["bars"]
    return [(d, days[d]) for d in sorted(days)]


def events(days):
    """yield (date, k, dir, rvol, buy share, bars, vwap_k, ret_since_open)"""
    out = []
    for i in range(20, len(days)):
        d, b = days[i]
        prev = [x[1] for x in days[i - 20:i]]
        rets = [p[k][3] / p[k - 1][3] - 1 for p in prev for k in range(1, 78)]
        sig = st.pstdev(rets)
        if sig <= 0:
            continue
        pv = vv = 0.0
        for k in range(0, K1 + 1):
            o, h, lo, c, v = b[k]
            pv += (h + lo + c) / 3 * v
            vv += v
            if k < K0:
                continue
            av = sum(p[k][4] for p in prev) / 20
            if av <= 0:
                continue
            share = phi((c / b[k - 1][3] - 1) / sig)
            out.append((d, k, v / av, share, b, pv / vv if vv > 0 else c, c / b[0][0] - 1))
    return out


def fwd(b, k, d, h):
    j = L.EOD if h is None else min(L.EOD, k + h)
    return d * (b[j][3] / b[k][3] - 1) * 1e4


def stat(rows):
    """rows: (date, value). Day-clustered mean and t."""
    by = defaultdict(list)
    for d, x in rows:
        by[d].append(x)
    m = [st.mean(v) for v in by.values()]
    if len(m) < 10:
        return "   n<10      "
    t = st.mean(m) / (st.pstdev(m) / math.sqrt(len(m))) if st.pstdev(m) else 0
    return f"{st.mean(m):+5.1f} (t{t:+4.1f})"


def table(ev, lab, R, F, filt=lambda e, d: True, first=False, need_vol=True):
    sel = []
    seen = set()
    for e in ev:
        d_, k, rv, sh, b, vw, rso = e
        if need_vol and rv < R:
            continue
        d = 1 if sh >= F else (-1 if sh <= 1 - F else 0)
        if d == 0 or not filt(e, d):
            continue
        if first:
            if d_ in seen:
                continue
            seen.add(d_)
        sel.append((d_, k, d, b))
    cells = [f"{h}: {stat([(d_, fwd(b, k, d, n)) for d_, k, d, b in sel])}" for h, n in HOR]
    nd = len({x[0] for x in sel})
    return f"{lab:<28} n {len(sel):5d} ({nd:4d} days) | " + " | ".join(cells)


def main():
    data = sys.argv[1]
    days = load(data)
    print(f"sessions {len(days)}: {days[0][0]} .. {days[-1][0]}")
    ev_all = events(days)
    vwap_ok = lambda e, d: d * (e[4][e[1]][3] - e[5]) > 0
    trend_ok = lambda e, d: d * e[6] > 0
    for lab, lo, hi in ERAS:
        ev = [e for e in ev_all if lo <= e[0] < hi]
        print(f"=== {lab}: gross bp WITH the bubble (day-clustered t)")
        print("   " + table(ev, "MAIN R3 F0.80 all", 3, 0.80))
        print("   " + table(ev, "MAIN first of day", 3, 0.80, first=True))
        print("   " + table(ev, "+ VWAP side agrees", 3, 0.80, vwap_ok))
        print("   " + table(ev, "+ trend since open agrees", 3, 0.80, trend_ok))
        print("   " + table(ev, "+ both", 3, 0.80, lambda e, d: vwap_ok(e, d) and trend_ok(e, d)))
        print("   " + table(ev, "+ AGAINST trend (fade setup)", 3, 0.80, lambda e, d: not trend_ok(e, d)))
        print("   " + table(ev, "control: share only, no vol", 3, 0.80, need_vol=False))
        for R in (2, 3, 4):
            for F in (0.70, 0.80, 0.90):
                if (R, F) != (3, 0.80):
                    print("   " + table(ev, f"plateau R{R} F{F:.2f}", R, F))


if __name__ == "__main__":
    main()
