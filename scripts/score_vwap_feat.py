"""VWAP band with an adaptive target: TP from the breakout candle and the
volatility around it, capped at 15 points, stop = 3.3 x TP.

Reads the VWAP band feature exporter. Target rules:
    fixed     TP = constant
    c5r       TP = k x range of the breakout 5-minute candle
    atr5      TP = k x mean range of the last 12 five-minute bars
    blend     TP = k x (c5r + atr5) / 2
    atrd      TP = k x 14-day ATR
each clamped to [2, 15] points; k is set so the median target lands on
3, 5, 8, 10, 12 or 15 points. Target and stop are moved to the nearest
recorded level and paid there. Costs: $1 commission per MNQ, one tick on
entry and one more on a stop. The random-walk win rate for the bracket is
stop / (target + stop), about 77% at 3.3:1, and the question is how far a
rule beats it after costs.

Then, for the best rule, every recorded feature is split into terciles to
see whether it predicts where the edge is (and so could scale the target).

Usage: score_vwap_feat.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402

LEVELS = [1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
          16.5, 20, 23, 26, 30, 33, 36.5, 40, 43, 46.5, 50]
FEATS = ["c5r", "c5b", "cloc", "rvol5", "atr5", "atrd", "rv20", "dist", "vslp"]
SPLIT = "2022"
RATIO = 3.3
COMM, TICK = 0.5, 0.25


def parse(paths):
    n = len(LEVELS)
    rows = []
    for p in paths:
        for raw in open(p):
            f = raw.strip().split(",")
            if f[0] != "V" or len(f) < 14 + 2 * n + 1:
                continue
            r = {"ymd": f[1], "type": f[2], "hm": int(f[3]), "e": float(f[4]),
                 "up": [int(x) for x in f[14:14 + n]], "dn": [int(x) for x in f[14 + n:14 + 2 * n]],
                 "eod": float(f[14 + 2 * n])}
            for k, x in zip(FEATS, f[5:14]):
                r[k] = float(x)
            r["blend"] = (r["c5r"] + r["atr5"]) / 2.0
            # scale-free versions, so terciles compare like with like across
            # 2018 (NQ ~6,500) and 2025 (NQ ~21,000)
            r["c5r/atr5"] = r["c5r"] / r["atr5"] if r["atr5"] > 0 else 1.0
            r["body/rng"] = r["c5b"] / r["c5r"] if r["c5r"] > 0 else 0.0
            r["atrd %"] = r["atrd"] / r["e"] * 100
            r["dist/atr5"] = abs(r["dist"]) / r["atr5"] if r["atr5"] > 0 else 0.0
            r["vslp/atr5"] = r["vslp"] / r["atr5"] * (1 if r["type"][0] == "U" else -1) if r["atr5"] > 0 else 0.0
            rows.append(r)
    return rows


def near(x):
    return min(range(len(LEVELS)), key=lambda i: abs(LEVELS[i] - x))


def trade(r, side, tp):
    tp = min(15.0, max(2.0, tp))
    ti, si = near(tp), near(RATIO * tp)
    T, S = LEVELS[ti], LEVELS[si]
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    if s >= 0 and (t < 0 or s <= t):
        pts = -S - TICK
    elif t >= 0:
        pts = T
    else:
        pts = max(-S - TICK, side * r["eod"] - TICK)
    return pts - COMM - TICK, S / (T + S)


def tstat(v):
    sd = st.pstdev(v) if len(v) > 2 else 0
    return st.mean(v) / sd * math.sqrt(len(v)) if sd > 0 else 0.0


def summary(rs, side_of, tp_of):
    out = []
    for part in ([r for r in rs if r["ymd"][:4] < SPLIT], [r for r in rs if r["ymd"][:4] >= SPLIT]):
        v = [trade(r, side_of(r), tp_of(r)) for r in part]
        p = [x for x, _ in v]
        if not p:
            out.append((0.0, 0.0, 0.0, 0.0, 0))
            continue
        wr = sum(1 for x in p if x > 0) / len(p) * 100
        base = st.mean(b for _, b in v) * 100
        out.append((st.mean(p), tstat(p), wr, wr - base, len(p)))
    return out


def fmt(o):
    return f"{o[0]:+5.2f} pt t{o[1]:+4.1f} WR {o[2]:4.1f}% ({o[3]:+4.1f} vs random)"


def main():
    sp = sys.argv[1]
    rows = parse([f"{sp}/VFA_tags.txt", f"{sp}/VFB_tags.txt"])
    dists = sorted({int(r["type"][1:]) for r in rows})
    print(f"{len(rows)} band entries, bands {dists} bp; stop = {RATIO} x target\n")
    best = []
    for d in dists:
        rs = [r for r in rows if int(r["type"][1:]) == d]
        for mode in ("with", "fade"):
            side_of = (lambda r, m=mode: (1 if r["type"][0] == "U" else -1) * (1 if m == "with" else -1))
            res = []
            for x in ("fixed", "c5r", "atr5", "blend", "atrd"):
                med = 1.0 if x == "fixed" else st.median(r[x] for r in rs if r["ymd"][:4] < SPLIT)
                for target in (3, 5, 8, 10, 12, 15):
                    k = target / med
                    tp_of = (lambda r, x=x, k=k: k if x == "fixed" else k * r[x])
                    o = summary(rs, side_of, tp_of)
                    res.append((o[0][0], x, target, o, tp_of))
            res.sort(key=lambda z: -z[0])
            ev, x, target, o, tp_of = res[0]
            print(f"band {d:2} bp {mode:<4}  best on 2018-21: {x:<5} median TP {target:2} pt")
            print(f"     2018-21 {fmt(o[0])}   |   2022-25 {fmt(o[1])}   n {o[0][4]}+{o[1][4]}")
            best.append((ev, d, mode, x, target, tp_of, side_of, rs))
    best.sort(key=lambda z: -z[0])
    pick = [b for b in best if b[1] == 20 and b[2] == "with"] or best
    ev, d, mode, x, target, tp_of, side_of, rs = pick[0]
    print(f"\n== feature terciles for the best rule: band {d} bp {mode}, TP from {x} (median {target} pt)")
    for f in ["c5r/atr5", "body/rng", "cloc", "rvol5", "atrd %", "rv20", "dist/atr5", "vslp/atr5", "hm"]:
        vals = sorted(r[f] for r in rs if r["ymd"][:4] < SPLIT)
        q1, q2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
        line = []
        for lab, sel in (("low", lambda r: r[f] <= q1), ("mid", lambda r: q1 < r[f] <= q2), ("high", lambda r: r[f] > q2)):
            o = summary([r for r in rs if sel(r)], side_of, tp_of)
            line.append(f"{lab} {o[0][0]:+5.2f}/{o[1][0]:+5.2f}pt ({o[0][3]:+4.1f}/{o[1][3]:+4.1f})")
        print(f"   {f:<6} cut {q1:9.3f} {q2:9.3f}   " + "   ".join(line))
    print("   (each cell: points per trade 2018-21/2022-25, win rate minus random-walk rate in brackets)")


if __name__ == "__main__":
    main()
