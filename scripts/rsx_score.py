"""Relative strength against other index futures (day shift 2026-10-26, rules
fixed before the exports came back). The RS leg (NQ vs ES since the open,
with VWAP agreement) is the strongest part of the plan. Exports MFY*
(strategy/quantconnect/rsx) add NQ vs YM (Dow) and NQ vs RTY (Russell 2000;
CME data only from 2017-07, so no 2010-17 check possible) at the same checks.

Signals (first signal of 10:00 / 11:00 / 13:00 / 14:30, VWAP agreement as RS):
  RS     rs_es  > +0.15% and vwapd > 0 -> long; mirror short   (the plan)
  RSY    rs_ym  instead of rs_es
  RS&Y   both rs_es and rs_ym beyond +/-0.15% in the same direction
  RSR    rs_rty instead of rs_es (2018+ only, information)
Measures: sprint 0.20/0.30 resolved win minus the random rate (60%); eval
days / fees to a pass (two_win_sprint INTRA, single account); funded leg
+/-1.25% gross bp per trade and t; trades per year. Four eras + 2026.
Adopt (as a replacement or filter) only if better than RS in all four eras
and not worse in 2026.
Usage: rsx_score.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML, bp  # noqa: E402
from score_cond_bracket import parse  # noqa: E402
from two_win_sprint import trade_pts, attempt_days, FEE  # noqa: E402

ERAS = (("2010-13", "2010", "2014", "MFY_OLD", 260), ("2014-17", "2014", "2018", "MFY_OLD", 260),
        ("2018-21", "2018", "2022", "MFY", 260), ("2022-25", "2022", "2026", "MFY", 260), ("2026", "2026", "2027", "MFY26", 40))
CAL = {"MFY_OLD": "CBA_OLD", "MFY": "CBA", "MFY26": "CBA26"}
TH = 0.0015


def sig_fn(kind):
    def f(r):
        a, y, z, v = r["rs"], r["_a"], r["_b"], r["vwapd"]
        x = {"RS": a, "RSY": y, "RSR": z}.get(kind)
        if kind == "RS&Y":
            if a > TH and y > TH and v > 0:
                return 1
            if a < -TH and y < -TH and v < 0:
                return -1
            return 0
        if x == 0.0 and kind != "RS":
            return 0
        return 1 if (x > TH and v > 0) else (-1 if (x < -TH and v < 0) else 0)
    return f


def main():
    data = sys.argv[1]
    ti, si = ML.index(20), ML.index(30)
    big = ML.index(125)
    for lab, lo, hi, nm, left in ERAS:
        rows = [r for r in parse_mf(f"{data}/{nm}_tags.txt") if lo <= r["date"] < hi]
        cal = sorted(d for d in {r["date"] for r in parse([f"{data}/{CAL[nm]}_tags.txt"]) if r["type"] == "T931"} if lo <= d < hi)
        yrs = max(1.0, len(cal) / 252)
        nz = sum(1 for r in rows if r["_b"] != 0.0) / max(1, len(rows))
        print(f"--- {lab} ({len(cal)} days; RTY feature present on {nz * 100:.0f}% of rows)")
        for kind in ("RS", "RSY", "RS&Y", "RSR"):
            sig = first_signals(rows, sig_fn(kind))
            if not sig:
                print(f"   {kind:<5} no signals")
                continue
            res = [bp(r, s, ti, si) for r, s in sig.values()]
            hit = sum(1 for x in res if x == 20)
            miss = sum(1 for x in res if x == -30)
            win = hit / (hit + miss) * 100 if hit + miss else float("nan")
            leg = [bp(r, s, big, big) for r, s in sig.values()]
            t = st.mean(leg) / (st.pstdev(leg) / math.sqrt(len(leg))) if len(leg) > 2 and st.pstdev(leg) else 0.0
            days = [trade_pts(sig[d][0], sig[d][1], ML, 20, 30) if d in sig else None for d in cal]
            ev = [x for x in (attempt_days(days, s0, "two-win") for s0 in range(len(days) - left)) if x]
            evs = f"{st.mean(d for d, _ in ev):5.1f} d ${st.mean(e for _, e in ev) * FEE:4.0f}" if ev else "  no pass"
            print(f"   {kind:<5} {len(sig) / yrs:4.0f}/yr  sprint win {win:5.1f}% (random 60.0)  eval {evs}  "
                  f"leg +/-1.25% {st.mean(leg):+6.1f} bp (t{t:+4.1f})")


if __name__ == "__main__":
    main()
