"""Score the VWAP trend exports (VWTREND, Zarattini & Aziz 2023): per day and
variant gross NQ points and entries; cost 0.75 pt per entry per MNQ. Vol gate
(prior-day 20d realised vol < 0.30) shown on and off. Days, not trades, are
the unit (always in the market).

Usage: score_vwap_trend.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys
from collections import defaultdict


def stat(v):
    if len(v) < 3:
        return "n<3"
    sd = st.pstdev(v)
    return f"{st.mean(v):+6.2f} pt/day t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f} n{len(v):>4}"


def main():
    D = defaultdict(list)
    for raw in open(f"{sys.argv[1]}/VWTREND_tags.txt"):
        f = raw.strip().split(",")
        if f[0] != "W" or len(f) < 6:
            continue
        D[f[1]].append((f"{f[2][:4]}-{f[2][4:6]}-{f[2][6:]}", float(f[3]), int(f[4]), int(f[5]) / 1000.0))
    for k in ("V1", "V5", "V15", "B5"):
        rows = D[k]
        print(f"== {k}: {st.mean(n for _, _, n, _ in rows):.1f} entries a day")
        for gate in (False, True):
            g = [(d, p - 0.75 * n) for d, p, n, rv in rows if not gate or 0 < rv < 0.30]
            gross = [p for d, p, n, rv in rows if not gate or 0 < rv < 0.30]
            a = [x for d, x in g if d < "2022"]
            b = [x for d, x in g if d >= "2022"]
            print(f"   gate {'on ' if gate else 'off'} net 2018-21 {stat(a)} | 2022-25 {stat(b)}   (gross {st.mean(gross):+.2f})")
        yrs = sorted({d[:4] for d, *_ in rows})
        print("   net by year: " + "  ".join(f"{y} {sum(p - 0.75 * n for d, p, n, rv in rows if d[:4] == y):+.0f}" for y in yrs))


if __name__ == "__main__":
    main()
