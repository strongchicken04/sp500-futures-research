"""Very small targets on the VWAP band: 1-15% of ATR, with a fine grid.

Reads the fine-grid VWAP band export (1-60 bp touch levels, bands 20/40/60
bp) and the ATR from the noise/time-of-day day paths. Trades go with the
break, one a day per band (the first break either way). For each target and
stop (in % of ATR, moved to the nearest grid level and paid there) it prints
the win rate, the win rate a driftless random walk would give for the same
bracket (stop / (target + stop)), and the expectancy after costs.

Costs: $1 commission per MNQ plus one tick of slippage on entry and one on
the stop when it is hit (the target is a resting limit). 0.5 pt = $1.
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from rescore_all import rvol  # noqa: E402
from score_vwap_atr import atr_table  # noqa: E402

LEVELS = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60]
KT = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.075, 0.10, 0.15]
KS = [0.05, 0.10, 0.15, 0.20, 0.30]
SPLIT = "2022-01-01"
COMM, TICK = 0.5, 0.25


def parse(path):
    n = len(LEVELS)
    rows = []
    for raw in open(path):
        f = raw.strip().split(",")
        if f[0] != "G" or len(f) < 15 + 2 * n:
            continue
        d = f[1]
        rows.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "type": f[2], "hm": int(f[3]),
                     "e": float(f[4]), "up": [int(x) for x in f[14:14 + n]],
                     "dn": [int(x) for x in f[14 + n:14 + 2 * n]], "eod": float(f[14 + 2 * n])})
    return rows


def near(bp):
    return min(range(len(LEVELS)), key=lambda i: abs(LEVELS[i] - bp))


def trade(r, kt, ks, atr):
    side = 1 if r["type"][0] == "U" else -1
    ti, si = near(kt * atr / r["e"] * 1e4), near(ks * atr / r["e"] * 1e4)
    tp, sl = r["e"] * LEVELS[ti] / 1e4, r["e"] * LEVELS[si] / 1e4
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    if s >= 0 and (t < 0 or s <= t):
        pts = -sl - TICK
    elif t >= 0:
        pts = tp
    else:
        pts = max(-sl - TICK, side * r["eod"] - TICK)
    return pts - COMM - TICK, sl / (tp + sl), tp


def tstat(v):
    sd = st.pstdev(v) if len(v) > 2 else 0
    return st.mean(v) / sd * math.sqrt(len(v)) if sd > 0 else 0.0


def main():
    sp = sys.argv[1]
    atr = atr_table(f"{sp}/NOISETOD_tags.txt")
    reg = rvol()
    rows = [r for r in parse(f"{sp}/VBFINE_tags.txt") if r["date"] in atr and reg.get(r["date"], 9.0) < 0.30]
    for d in (20, 40, 60):
        first = {}
        for r in rows:
            if int(r["type"][1:]) == d and (r["date"] not in first or r["hm"] < first[r["date"]]["hm"]):
                first[r["date"]] = r
        rs = list(first.values())
        print(f"\n== band {d} bp, with the break: {len(rs)} trades ({len(rs)/8:.0f}/yr)")
        print(f"  {'TP%ATR':>6} {'SL%ATR':>6} {'~TP pt':>6} | {'WR':>5} {'random':>6} {'pts IS':>7} {'t':>5} | "
              f"{'WR':>5} {'random':>6} {'pts OOS':>7} {'t':>5}")
        for kt in KT:
            for ks in KS:
                if ks < kt:
                    continue
                out = []
                tps = []
                for part in ([r for r in rs if r["date"] < SPLIT], [r for r in rs if r["date"] >= SPLIT]):
                    v = [trade(r, kt, ks, atr[r["date"]]) for r in part]
                    p = [x for x, _, _ in v]
                    tps += [tp for _, _, tp in v]
                    out.append(f"{sum(1 for x in p if x > 0) / len(p) * 100:4.1f}% {st.mean(b for _, b, _ in v) * 100:5.1f}% "
                               f"{st.mean(p):+7.2f} {tstat(p):+5.1f}")
                print(f"  {kt*100:6.1f} {ks*100:6.0f} {st.median(tps):6.1f} | {out[0]} | {out[1]}")


if __name__ == "__main__":
    main()
