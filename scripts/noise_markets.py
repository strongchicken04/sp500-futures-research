"""Noise momentum (Lucid 6 rules, live-spec exports) on NQ, ES and YM, in
dollars per micro contract net of $1 round trip + 1 tick slippage (+1 tick on
stops). Vol gate on each market's own prior-day 20d realised vol < 0.30.
Then the correlation of daily results between markets.

Usage: noise_markets.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys
from collections import defaultdict

SPEC = {"NQ": ("LSNOISE", 2.0, 0.25), "ES": ("LSNOISE_ES", 5.0, 0.25), "YM": ("LSNOISE_YM", 0.5, 1.0)}


def load(path, mult, tick):
    out = defaultdict(list)
    for raw in open(path):
        f = raw.strip().split(",")
        if f[0] != "L" or len(f) < 10:
            continue
        d, e, x = int(f[3]), float(f[5]), float(f[7])
        usd = d * (x - e) * mult - 1.0 - tick * mult * (2 if f[8] == "STOP" else 1)
        out[f[1]].append((f"{f[2][:4]}-{f[2][4:6]}-{f[2][6:]}", usd, int(f[9]) / 1000.0))
    return out


def stat(v):
    if len(v) < 3:
        return "n<3"
    sd = st.pstdev(v)
    return f"${st.mean(v):+6.2f} t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f} n{len(v):>4}"


def main():
    sp = sys.argv[1]
    daily = {}
    for m, (f, mult, tick) in SPEC.items():
        T = load(f"{sp}/{f}_tags.txt", mult, tick)
        for k in ("N0", "NS"):
            g = [(d, u) for d, u, rv in T[k] if 0 < rv < 0.30]
            a = [u for d, u in g if d < "2022"]
            b = [u for d, u in g if d >= "2022"]
            yrs = sorted({d[:4] for d, _ in g})
            print(f"{m} {k}: 2018-21 {stat(a)} | 2022-25 {stat(b)}   years+ {sum(1 for y in yrs if sum(u for d, u in g if d[:4] == y) > 0)}/{len(yrs)}")
            if k == "NS":
                dd = defaultdict(float)
                for d, u in g:
                    dd[d] += u
                daily[m] = dd
    print()
    for a, b in (("NQ", "ES"), ("NQ", "YM"), ("ES", "YM")):
        common = sorted(set(daily[a]) & set(daily[b]))
        both = [d for d in common]
        if len(both) > 10:
            print(f"daily correlation {a}-{b}: {st.correlation([daily[a][d] for d in both], [daily[b][d] for d in both]):+.2f} on {len(both)} common days")


if __name__ == "__main__":
    main()
