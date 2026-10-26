"""Adaptive regime from recent autocorrelation (day shift 2026-10-26, fixed
before results). For each day: AC = lag-1 autocorrelation of consecutive
30-min RTH returns (10:00-16:00, 12 per day) pooled over the previous 20
sessions. Next day's intraday momentum: for each 30-min slot from 10:30 on,
slot return x sign(return since 09:30 at the slot start) (as slot_scan M),
averaged per day. Question: is the next day's momentum higher when AC is
high (trending regime) and negative when AC is low? Terciles of AC fixed on
2018-21. A switch (momentum in trending, reversal in mean-reverting regimes)
counts only if high-AC momentum > low-AC momentum in all four eras and the
low tercile is negative in at least three.
Usage: regime_ac.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402


def r30(b):
    idx = list(range(5, 78, 6))          # closes of bars ending 10:00, 10:30, ..., 16:00
    return [b[idx[i + 1]][3] / b[idx[i]][3] - 1 for i in range(len(idx) - 1)]


def mom(b):
    out = []
    for j in range(11, 78, 6):
        if j + 6 >= len(b):
            break
        pre = b[j][3] / b[0][0] - 1
        if pre:
            out.append((b[j + 6][3] / b[j][3] - 1) * 1e4 * (1 if pre > 0 else -1))
    return st.mean(out) if out else None


def ac(xs):
    a, b = [], []
    for day in xs:
        for i in range(len(day) - 1):
            a.append(day[i]); b.append(day[i + 1])
    ma, mb = st.mean(a), st.mean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / len(a)
    return cov / (st.pstdev(a) * st.pstdev(b))


def main():
    days = B.load(sys.argv[1])
    rets = [r30(b) for _, b in days]
    rows = []
    for i in range(20, len(days)):
        m = mom(days[i][1])
        if m is not None:
            rows.append((days[i][0], ac(rets[i - 20:i]), m))
    tune = sorted(x[1] for x in rows if "2018" <= x[0] < "2022")
    q1, q2 = tune[len(tune) // 3], tune[2 * len(tune) // 3]
    print(f"AC terciles (2018-21): {q1:+.3f} / {q2:+.3f}")
    for lab, lo, hi in B.ERAS:
        sel = [x for x in rows if lo <= x[0] < hi]
        cells = []
        for name, a, c in (("low", -9, q1), ("mid", q1, q2), ("high", q2, 9)):
            g = [(x[0], x[2]) for x in sel if a <= x[1] < c]
            cells.append(f"{name} {B.stat(g)} n{len(g)}")
        print(f"{lab:<8} next-day momentum bp/slot: " + " | ".join(cells))


if __name__ == "__main__":
    main()
