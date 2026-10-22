"""Month-end Treasury long (queue item 5, ZN): long 10-year note futures from
09:00 to 15:00 ET on the last trading day of the month (index rebalancing
demand), against the same window on all other days. Fixed before looking.
Ticks are 1/64; result in ticks per contract net of 1 tick + $2.5 (~0.16 tick)
cost. Also shown: the last 2 days and the 08:20 open to 15:00 hold.

Usage: zn_month_end.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

TICK = 1 / 64
COST = 1.16


def stat(v):
    if len(v) < 3:
        return "n<3"
    sd = st.pstdev(v)
    return f"{st.mean(v):+5.2f} ticks t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f} n{len(v):>4} WR {sum(x > 0 for x in v) / len(v) * 100:3.0f}%"


def main():
    rows = {}
    for raw in open(f"{sys.argv[1]}/ZNDAY_tags.txt"):
        f = raw.strip().split(",")
        if f[0] != "Z" or len(f) < 11:
            continue
        v = [float(x) for x in f[2:11]]
        rows[f"{f[1][:4]}-{f[1][4:6]}-{f[1][6:]}"] = dict(zip(("o", "p900", "p1130", "p1255", "p1305", "p1330", "p1500", "lo", "hi"), v))
    ds = sorted(rows)
    last = {ds[i] for i in range(len(ds) - 1) if ds[i][:7] != ds[i + 1][:7]}
    last2 = last | {ds[i - 1] for i in range(1, len(ds)) if ds[i] in last}
    win = lambda d, a, b: (rows[d][b] - rows[d][a]) / TICK - COST
    print(f"{len(ds)} ZN days, {len(last)} month ends\n")
    for lab, lo, hi in (("2018-2021", "0", "2022"), ("2022-2025", "2022", "9")):
        sel = [d for d in ds if lo <= d < hi]
        print(f"--- {lab}")
        print(f"  09:00-15:00 last day      {stat([win(d, 'p900', 'p1500') for d in sel if d in last])}")
        print(f"  09:00-15:00 other days    {stat([win(d, 'p900', 'p1500') for d in sel if d not in last])}")
        print(f"  09:00-15:00 last 2 days   {stat([win(d, 'p900', 'p1500') for d in sel if d in last2])}")
        print(f"  08:20-15:00 last day      {stat([win(d, 'o', 'p1500') for d in sel if d in last])}")
    yr = sorted({d[:4] for d in last})
    print("last day 09-15 by year: " + "  ".join(f"{y} {st.mean([win(d, 'p900', 'p1500') for d in last if d[:4] == y]):+.1f}" for y in yr))


if __name__ == "__main__":
    main()
