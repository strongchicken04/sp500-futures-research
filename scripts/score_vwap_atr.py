"""VWAP band with target and stop as a share of ATR: which distance, which bracket?

Reads the VWAP band exporter (bands 10-60 bp) and the day paths from the
noise/time-of-day exporter for a 14-day ATR of the regular session. Every
band distance x direction (with the break, or fading it) x target x stop in
ATR units is scored on 2018-2021 and reported on 2022-2025, both per trade
(expectancy in ATR, win rate) and as an evaluation sprint.

Touches come from a basis-point grid, so each target is taken at the grid
level at or above it (harder to reach) and each stop at the level at or
below it (hit sooner): the rounding always works against the rule.

Usage: score_vwap_atr.py SCRATCH_DIR
"""
from __future__ import annotations

import bisect
import math
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from rescore_all import rvol  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402

LEVELS = [5, 8, 10, 12, 15, 18, 20, 25, 30, 35, 40, 50, 60, 70, 80, 100, 125, 150, 200]
KT = [0.05, 0.075, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
KS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.75, 1.00]
SPLIT = "2022-01-01"
COST_PTS = 0.5


def parse_band(paths):
    rows = []
    for p in paths:
        for raw in open(p):
            f = raw.strip().split(",")
            if f[0] != "G" or len(f) < 53:
                continue
            d = f[1]
            rows.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "type": f[2], "hm": int(f[3]),
                         "e": float(f[4]), "up": [int(x) for x in f[14:33]],
                         "dn": [int(x) for x in f[33:52]], "eod": float(f[52])})
    return rows


def atr_table(path, n=14):
    days = []
    for raw in open(path):
        f = raw.strip().split(",")
        if f[0] != "P" or len(f) < 44:
            continue
        d = f[1]
        pc = float(f[3])
        hi = max(float(x) for x in f[18:31])
        lo = min(float(x) for x in f[31:44])
        days.append((f"{d[:4]}-{d[4:6]}-{d[6:]}", max(hi - lo, abs(hi - pc), abs(lo - pc))))
    atr = {}
    for i in range(n, len(days)):
        atr[days[i][0]] = st.mean(tr for _, tr in days[i - n:i])
    return atr


def lvl_up(bp):
    i = bisect.bisect_left(LEVELS, bp)
    return i if i < len(LEVELS) else None


def lvl_dn(bp):
    i = bisect.bisect_right(LEVELS, bp) - 1
    return max(i, 0)


def result(r, side, kt, ks, atr):
    tp, sl = kt * atr, ks * atr
    ti, si = lvl_up(tp / r["e"] * 1e4), lvl_dn(sl / r["e"] * 1e4)
    if ti is None:
        return None
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    if s >= 0 and (t < 0 or s <= t):
        return -sl - COST_PTS
    if t >= 0:
        return tp - COST_PTS
    return max(-sl, side * r["eod"]) - COST_PTS


def tstat(v):
    sd = st.pstdev(v) if len(v) > 2 else 0
    return st.mean(v) / sd * math.sqrt(len(v)) if sd > 0 else 0.0


def main():
    sp = sys.argv[1]
    rows = parse_band([f"{sp}/VBA_tags.txt", f"{sp}/VBB_tags.txt"])
    atr = atr_table(f"{sp}/NOISETOD_tags.txt")
    reg = rvol()
    rows = [r for r in rows if r["date"] in atr and reg.get(r["date"], 9.0) < 0.30]
    dists = sorted({int(r["type"][1:]) for r in rows})
    print(f"{len(rows)} band entries, distances {dists} bp\n")
    res = []
    for d in dists:
        # one trade a day: the first of the up or down break at this distance
        first = {}
        for r in rows:
            if int(r["type"][1:]) == d and (r["date"] not in first or r["hm"] < first[r["date"]]["hm"]):
                first[r["date"]] = r
        rs = sorted(first.values(), key=lambda r: r["date"])
        for mode in ("with", "fade"):
            for kt in KT:
                for ks in KS:
                    if ks < kt:
                        continue
                    v = []
                    for r in rs:
                        side = (1 if r["type"][0] == "U" else -1) * (1 if mode == "with" else -1)
                        x = result(r, side, kt, ks, atr[r["date"]])
                        if x is not None:
                            v.append((r["date"], x / atr[r["date"]], x))
                    a = [x for dt, x, _ in v if dt < SPLIT]
                    b = [x for dt, x, _ in v if dt >= SPLIT]
                    if len(a) < 50 or len(b) < 50:
                        continue
                    res.append((tstat(a), d, mode, kt, ks, st.mean(a), st.mean(b), tstat(b),
                                sum(1 for x in a if x > 0) / len(a) * 100,
                                sum(1 for x in b if x > 0) / len(b) * 100, len(v) / 8, v))
    res.sort(key=lambda x: -x[0])
    print(f"{'band':>4} {'mode':<5} {'TP%ATR':>6} {'SL%ATR':>6} {'n/yr':>5} {'WR IS':>6} {'WR OOS':>6} "
          f"{'EV IS (ATR)':>11} {'t':>5} {'EV OOS':>7} {'t':>5}")
    for t_is, d, mode, kt, ks, m_is, m_oos, t_oos, w_is, w_oos, nyr, _ in res[:25]:
        print(f"{d:4} {mode:<5} {kt*100:6.1f} {ks*100:6.0f} {nyr:5.0f} {w_is:5.0f}% {w_oos:5.0f}% "
              f"{m_is:+11.4f} {t_is:+5.1f} {m_oos:+7.4f} {t_oos:+5.1f}")

    print("\nper band and mode: share of brackets with positive expectancy (IS | OOS) and best IS cell")
    agg = defaultdict(list)
    for x in res:
        agg[(x[1], x[2])].append(x)
    for (d, mode), xs in sorted(agg.items()):
        pi = sum(1 for x in xs if x[5] > 0) / len(xs) * 100
        po = sum(1 for x in xs if x[6] > 0) / len(xs) * 100
        print(f"   {d:3} bp {mode:<5} {pi:4.0f}% | {po:4.0f}%   mean EV IS {st.mean(x[5] for x in xs):+.4f}  OOS {st.mean(x[6] for x in xs):+.4f} ATR")

    print("\nevaluation sprint with the top 5 (size: target worth ~$1,000, max 40 MNQ, stop inside the line)")
    cal = sorted({r["date"] for r in rows})
    for t_is, d, mode, kt, ks, *_rest in res[:5]:
        v = _rest[-1]
        trs = []
        for dt, xa, x in v:
            n = max(1, min(40, round(1000.0 / (kt * atr[dt] * 2.0))))
            if ks * atr[dt] * 2.0 * n > 1950:
                n = max(1, int(1950 / (ks * atr[dt] * 2.0)))
            trs.append(Trade(dt, x * 2.0 * n, "VB"))
        out = []
        for lo, hi in (("0", SPLIT), (SPLIT, "9")):
            o = outcomes(calendar_days([t for t in trs if lo <= t.date < hi], [c for c in cal if lo <= c < hi]),
                         flat(1, 1e6), window=160, start_pnl=0.0, target=3000.0, consistency=True)
            p = sum(1 for x, _ in o if x == "pass") / len(o) * 100
            md = sorted(dd for x, dd in o if x == "pass")
            out.append(f"{p:4.1f}% in {md[len(md)//2] if md else 0} d")
        print(f"   {d} bp {mode} TP {kt*100:.1f}% SL {ks*100:.0f}% ATR:  2018-21 {out[0]}  |  2022-25 {out[1]}")


if __name__ == "__main__":
    main()
