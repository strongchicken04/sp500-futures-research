"""Volatility-scaled sprint bracket (night shift 2026-10-23, fixed before results).

Idea: a fixed % bracket (e.g. +0.25% / -0.40%) is wide in calm markets (few
trades resolve, the sprint waits) and narrow in wild ones. The dollar result
of a win or loss does not depend on the bracket width (size = risk / stop), so
scaling the bracket with volatility might keep the resolution rate - and the
days to a pass - stable across regimes.

Rules:
  rv20 = 20-day realised vol of daily closes up to YESTERDAY (from the 'pc'
         field of the T931 rows, no look-ahead), annualised
  ref  = median rv20 over 2018-2021 (tuning era only)
  m    = clip(rv20 / ref, 0.5, 2.0)        variant LIN
  m    = clip(sqrt(rv20 / ref), 0.5, 2.0)  variant SQRT
  bracket = pair from the ladder below whose target is nearest base_T * m
  ladder: (10,15) (15,25) (20,30) (25,40) (30,50) (40,60) (50,75) bp
Sprints and base brackets as the plan: RS 0.20/0.30, 09:31 trend 0.25/0.40,
VWAP10 0.25/0.40. Policy: two-win (finishing trade), single account, days and
fees to a pass from every start day, four eras (two_win_sprint.attempt_days).
Also resolved win minus random by era for the scaled vs fixed bracket.

Usage: vol_bracket.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from b_sprint_lab import trend_map, sgn  # noqa: E402
from two_win_sprint import trade_pts, attempt_days, ERAS, FEE  # noqa: E402

LADDER = ((10, 15), (15, 25), (20, 30), (25, 40), (30, 50), (40, 60), (50, 75))
BASE = {"RS": (20, 30), "T931": (25, 40), "VWAP10": (25, 40)}


def rv_map(t931):
    rows = sorted(t931, key=lambda r: r["date"])
    pcs = [r["pc"] for r in rows]
    m = {}
    for i, r in enumerate(rows):
        if i >= 21:
            rets = [math.log(pcs[j] / pcs[j - 1]) for j in range(i - 19, i + 1)]
            m[r["date"]] = st.pstdev(rets) * math.sqrt(252)
    return m


def pick(base_t, mult):
    want = base_t * mult
    return min(LADDER, key=lambda p: abs(p[0] - want))


def resolved_rate(sig, br_of, lv):
    h = s_ = 0
    rnd_sum = 0.0
    for d, (r, s) in sig.items():
        tp, sp = br_of(d)
        ti, si = lv.index(tp), lv.index(sp)
        fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
        t, sl = fav[ti], adv[si]
        if t >= 0 and (sl < 0 or t < sl):
            h += 1
            rnd_sum += sp / (tp + sp)
        elif sl >= 0:
            s_ += 1
            rnd_sum += sp / (tp + sp)
    n = h + s_
    return (h / n - rnd_sum / n) * 100 if n else float("nan"), n, n / max(1, len(sig))


def run(sig, cal, br_of, lv):
    days = [trade_pts(sig[d][0], sig[d][1], lv, *br_of(d)) if d in sig else None for d in cal]
    res = [x for x in (attempt_days(days, s0, "two-win") for s0 in range(0, len(days) - 260)) if x]
    return st.mean(d for d, _ in res), st.mean(e for _, e in res) * FEE


def main():
    data = sys.argv[1]
    eras = []
    for lab, lo, hi, suf in ERAS:
        rs = {d: v for d, v in first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                             (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)).items() if lo <= d < hi}
        R = {}
        for r in parse([f"{data}/CBA{suf}_tags.txt"]):
            R.setdefault(r["type"], []).append(r)
        tm = trend_map(R["T931"])
        rv = rv_map(R["T931"])
        S = {"RS": (rs, ML),
             "T931": ({r["date"]: (r, tm[r["date"]]) for r in R["T931"] if lo <= r["date"] < hi and tm.get(r["date"])}, CL),
             "VWAP10": ({r["date"]: (r, sgn(r["e"] - r["vwap"])) for r in R["T1000"] if lo <= r["date"] < hi and sgn(r["e"] - r["vwap"])}, CL)}
        eras.append((lab, lo, hi, S, rv))
    ref = st.median(v for lab, lo, hi, S, rv in eras for d, v in rv.items() if "2018" <= d < "2022")
    print(f"ref rv20 (median 2018-21) = {ref:.3f}")
    for lab, lo, hi, S, rv in eras:
        vals = [v for d, v in rv.items() if lo <= d < hi]
        print(f"   {lab}: median rv20 {st.median(vals):.3f}")
    for lab, lo, hi, S, rv in eras:
        cal = sorted({d for v, _ in S.values() for d in v})
        print(f"--- {lab}  days to a pass / fees (two-win, single account) | resolved win - random pp, share of signal days resolved")
        for name, (sig, lv) in S.items():
            bt, bs = BASE[name]
            variants = {
                "fixed": lambda d: (bt, bs),
                "LIN": lambda d: pick(bt, min(2.0, max(0.5, rv.get(d, ref) / ref))),
                "SQRT": lambda d: pick(bt, min(2.0, max(0.5, math.sqrt(rv.get(d, ref) / ref)))),
            }
            cells = []
            for vn, fn in variants.items():
                days, fees = run(sig, cal, fn, lv)
                edge, n, share = resolved_rate(sig, fn, lv)
                cells.append(f"{vn} {days:5.1f} d ${fees:4.0f} {edge:+4.1f} pp {share * 100:3.0f}%")
            print(f"   {name:<6} " + " | ".join(cells))


if __name__ == "__main__":
    main()
