"""RS sprint variants (queue item 1) from rs_variants_exporter tags (RSVA/RSVB).

Pre-specified variants, each over a threshold neighbourhood 10/15/20/25 bp
(the reported verdict uses the block average, not the best threshold):
  base      NQ-ES > thr and above VWAP (mirror short) at 10:00/11:00/13:00/14:30
            (replicates the live RS sprint; sanity check against MFEAT)
  5min      the same rule checked every 5 minutes 10:00-15:00
  30min     every 30 minutes 10:00-15:00
  early     every 5 minutes 10:00-11:00 only
  volthr    base, threshold scaled by 20d realised vol / its 2018-21 median
  ema       base with EMA21 (5-min) instead of VWAP
  ym, rty   base against YM / RTY instead of ES
  breadth   NQ ahead of ES, YM AND RTY by thr (mirror short)
  avg3      NQ ahead of the average of ES, YM, RTY by thr
First signal of the day only; sprint bracket +0.20% / -0.40% with costs.
Scored as sprint evaluation (pass per attempt, expected trading days to a pass)
and as edge per trade (bp, net of 0.5 bp), 2018-2021 vs 2022-2025.

Usage: score_rs_variants.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402

FIX4 = {600, 660, 780, 870}
M30 = set(range(600, 901, 30))
EARLY = set(range(600, 661, 5))
ALL = set(range(600, 901, 5))
THRS = (10, 15, 20, 25)


def parse(paths):
    days = {}
    for p in paths:
        for raw in open(p):
            f = raw.strip().split(",", 5)
            if f[0] != "R" or len(f) < 6:
                continue
            d = f"{f[1][:4]}-{f[1][4:6]}-{f[1][6:]}"
            day = days.setdefault(d, {"px": float(f[3]), "rv": int(f[4]) / 1000.0, "rows": []})
            for g in f[5].split(";"):
                x = g.split(":")
                if len(x) != 9:
                    continue
                hm, ret, es, ym, rty, vw, e21 = (int(v) for v in x[:7])
                day["rows"].append({"hm": hm, "ret": ret, "es": es, "ym": ym, "rty": rty, "vw": vw, "e21": e21,
                                    "L": float(x[7]), "S": float(x[8])})
    for d in days.values():
        d["rows"].sort(key=lambda r: r["hm"])
    return days


def usd(px, x):
    n = max(1, min(40, int(1900 / (px * 0.004 * 2.0))))
    return (x / 1e4 * px - 0.5) * 2.0 * n - n


def signals(days, times, rule):
    out = {}
    for d, day in days.items():
        for r in day["rows"]:
            if r["hm"] not in times or 999 in (r["es"], r["ym"], r["rty"]):
                continue
            s = rule(r, day)
            if s:
                out[d] = (day, r, s)
                break
    return out


def sprint(sig, cal, lo, hi):
    trs = [Trade(d, usd(day["px"], r["L"] if s == 1 else r["S"]), "S") for d, (day, r, s) in sig.items() if lo <= d < hi]
    cc = [c for c in cal if lo <= c < hi]
    o = outcomes(calendar_days(trs, cc), flat(1, 1e6), window=200, start_pnl=0.0, target=3000.0, consistency=True)
    p = sum(1 for x, _ in o if x == "pass") / len(o)
    return p * 100, (st.mean(dd for _, dd in o) / p if p else 0)


def edge(sig, lo, hi):
    v = [(r["L"] if s == 1 else r["S"]) - 0.5 for d, (day, r, s) in sig.items() if lo <= d < hi]
    if len(v) < 3:
        return 0.0, 0.0, len(v)
    sd = st.pstdev(v)
    return st.mean(v), st.mean(v) / sd * math.sqrt(len(v)) if sd else 0.0, len(v)


def main():
    sp = sys.argv[1]
    days = parse([f"{sp}/RSVA_tags.txt", f"{sp}/RSVB_tags.txt"])
    cal = sorted(days)
    rv_med = st.median(day["rv"] for d, day in days.items() if d < "2022" and day["rv"] > 0)
    print(f"{len(days)} days, {sum(len(x['rows']) for x in days.values())} checks; 2018-21 median rv {rv_med:.3f}\n")

    def mk(key, cond, scale=False):
        def rule_for(thr):
            def rule(r, day):
                t = thr * (day["rv"] / rv_med if scale and day["rv"] > 0 else 1.0)
                rs = (r["es"] + r["ym"] + r["rty"]) / 3.0 if key == "avg3" else r[key]
                c = r[cond]
                return 1 if (rs > t and c > 0) else (-1 if (rs < -t and c < 0) else 0)
            return rule
        return rule_for

    def breadth_rule(thr):
        def rule(r, day):
            if min(r["es"], r["ym"], r["rty"]) > thr and r["vw"] > 0:
                return 1
            if max(r["es"], r["ym"], r["rty"]) < -thr and r["vw"] < 0:
                return -1
            return 0
        return rule

    V = [("base (live)", FIX4, mk("es", "vw")), ("5min", ALL, mk("es", "vw")), ("30min", M30, mk("es", "vw")),
         ("early 10-11", EARLY, mk("es", "vw")), ("volthr", FIX4, mk("es", "vw", True)), ("ema21", FIX4, mk("es", "e21")),
         ("vs YM", FIX4, mk("ym", "vw")), ("vs RTY", FIX4, mk("rty", "vw")), ("breadth (all 3)", FIX4, breadth_rule),
         ("avg of 3", FIX4, mk("avg3", "vw"))]
    print(f"{'variant':<16} {'thr':>4} | {'n/yr':>4} {'bp':>6} {'t':>5} | {'n/yr':>4} {'bp':>6} {'t':>5} | sprint pass / days  2018-21 | 2022-25")
    summary = []
    for name, times, rf in V:
        blk = {"a": [], "b": [], "pa": [], "pb": [], "da": [], "db": []}
        for thr in THRS:
            sig = signals(days, times, rf(thr))
            ea, ta, na = edge(sig, "0", "2022")
            eb, tb, nb = edge(sig, "2022", "9")
            pa, da = sprint(sig, cal, "0", "2022")
            pb, db = sprint(sig, cal, "2022", "9")
            for k, v in zip(blk, (ea, eb, pa, pb, da, db)):
                blk[k].append(v)
            print(f"{name:<16} {thr:>4} | {na/4:4.0f} {ea:+6.2f} {ta:+5.1f} | {nb/4:4.0f} {eb:+6.2f} {tb:+5.1f} | "
                  f"{pa:5.1f}% {da:5.1f}d | {pb:5.1f}% {db:5.1f}d")
        m = {k: st.mean(v) for k, v in blk.items()}
        summary.append((name, m))
        print(f"{'':<16} {'avg':>4} | {'':>4} {m['a']:+6.2f} {'':>5} | {'':>4} {m['b']:+6.2f} {'':>5} | "
              f"{m['pa']:5.1f}% {m['da']:5.1f}d | {m['pb']:5.1f}% {m['db']:5.1f}d\n")
    print("== block averages (thresholds 10-25 bp)")
    for name, m in summary:
        print(f"   {name:<16} edge {m['a']:+5.2f} / {m['b']:+5.2f} bp   sprint {m['pa']:4.1f}% / {m['pb']:4.1f}%   days {m['da']:4.1f} / {m['db']:4.1f}")


if __name__ == "__main__":
    main()
