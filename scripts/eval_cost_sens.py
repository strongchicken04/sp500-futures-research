"""Sensitivity of the funded size / add-on decisions to the cost of a new
evaluation after a bust (night shift 2026-10-23/24). funded_model assumes
$180 and 11 trading days; here also $360 / 22 days and $540 / 33 days
(slower or failed evaluations). Variants: flat 3, flat 4, flat 4 + OD 4,
flat 5. 2018-21 / 2022-25 real dollars, 2010-17 re-priced at today's NQ.
Usage: eval_cost_sens.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import gate_check as G  # noqa: E402
import level_lab as L  # noqa: E402
import ict_lab as I  # noqa: E402
import funded_scaled_old as O  # noqa: E402
from addon_v2 import extra_legs  # noqa: E402
from mc_runs import sized  # noqa: E402
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse  # noqa: E402

V = {"flat 3": {"VG": 3, "Z": 3, "RS": 3}, "flat 4": {"VG": 4, "Z": 4, "RS": 4},
     "flat 4 + OD 4": {"VG": 4, "Z": 4, "RS": 4, "OD": 4}, "flat 5": {"VG": 5, "Z": 5, "RS": 5}}


def run(lab, cal, legs):
    by = {}
    for t in legs:
        by.setdefault(t[0], []).append(t)
    seq = [sorted(by.get(d, []), key=lambda t: t[2]) for d in cal]
    paths = M.bootstrap(len(cal), 2000, seed=7)
    for cost, days in ((180.0, 11), (360.0, 22), (540.0, 33)):
        M.EVAL_COST, M.EVAL_DAYS = cost, days
        cells = []
        for name, mix in V.items():
            dl = [[t[3] * mix[t[4]] for t in s if t[4] in mix] for s in seq]
            cells.append(f"{name} ${st.mean(M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths):7,.0f}")
        print(f"   {lab:<10} eval ${cost:.0f} / {days} d: " + " | ".join(cells))
    M.EVAL_COST, M.EVAL_DAYS = 180.0, 11


def main():
    data = sys.argv[1]
    reg = rvol()
    new = sized(G.build(data, set()), {"VG": 1, "Z": 1, "RS": 1}) + extra_legs(I.load(data), lambda d: reg.get(d, 9.0) < 0.30)
    full = sorted({r["date"] for r in parse([f"{data}/CBA_tags.txt"])})
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25")):
        run(lab, [d for d in full if lo <= d < hi], new)
    pref = st.mean(t["e"] for t in O.ls_rows(f"{data}/LSNOISE_tags.txt", "NS") if t["date"] >= "2022")
    old, gated = O.legs(data, "_OLD")
    old1 = [(d, eh, xh, (ret * pref - c) * 2.0, leg) for d, eh, xh, ret, c, leg, e in old if leg != "ORB" and gated(d)]
    L.NAMES = ("B2_0A", "B2_0B")
    old1 += extra_legs(L.load(data), gated, pref)
    full = sorted({r["date"] for r in parse([f"{data}/CBA_OLD_tags.txt"])})
    for lo, hi, lab in (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17")):
        run(lab, [d for d in full if lo <= d < hi], old1)


if __name__ == "__main__":
    main()
