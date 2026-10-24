"""Plateau check of the VWAP-side funded leg (day shift 2026-10-24, fixed
before results): entry at the close of the bar ending 10:00 / 10:30 / 11:00,
side of the session VWAP, bracket +0.25/-0.40, +0.30/-0.50 (the candidate),
+0.40/-0.60 %, else flat 15:55; vol gate; 4 MNQ on top of VG + Z + RS at 4.
Corrected model with the open-P&L check, four eras (2010-17 re-priced).
Usage: vside_plateau.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
import mtm_check as C  # noqa: E402
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse  # noqa: E402

TIMES = {"10:00": 5, "10:30": 11, "11:00": 17}
BRS = ((0.0025, 0.0040), (0.0030, 0.0050), (0.0040, 0.0060))


def vside(i, tp, sp):
    def make(days):
        def f(d, p):
            b = d["bars"]
            c, vw = b[i][3], L.vwaps(b)[i]
            s = 1 if c > vw else -1 if c < vw else 0
            return (s, L.run(b, i, s, c, c * (1 - s * sp), c * (1 + s * tp))) if s else None
        return f
    return make


def main():
    data = sys.argv[1]
    keys = {}
    for tn, i in TIMES.items():
        for tp, sp in BRS:
            keys[f"V{tn} {tp * 100:.2f}/{sp * 100:.2f}"] = vside(i, tp, sp)
    C.PANEL_LEGS = keys
    reg = rvol()
    pref = st.mean(float(p.split(",")[5]) for p in open(f"{data}/LSNOISE_tags.txt")
                   if p.startswith(("L,NS,2022", "L,NS,2023", "L,NS,2024", "L,NS,2025")))
    rvo = {}
    for f in ("LSVWAP_OLD", "LSNOISE_OLD"):
        for raw in open(f"{data}/{f}_tags.txt"):
            p = raw.strip().split(",")
            if p[0] == "L" and len(p) >= 10 and int(p[9]) > 0:
                rvo[f"{p[2][:4]}-{p[2][4:6]}-{p[2][6:]}"] = int(p[9]) / 1000.0
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, None,
             (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < rvo.get(d, 9.0) < 0.30, pref,
             (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))))
    base_mix = {"VG": 4, "Z": 4, "RS": 4}
    res = {}
    for suf, names, cba, gate, pr, halves in eras:
        L.NAMES = names
        L.COST, L.STOP_COST = 0.75, 0.25
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        tr, by = C.trades(data, suf, gate, pr)
        T = {}
        for t in tr:
            T.setdefault(t[0], []).append(t)
        f = (lambda e: pref / e) if pr else None
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            paths = M.bootstrap(len(cal), 3000, seed=31)
            dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, base_mix, f, True) for d in cal]
            base = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
            for k in keys:
                mix = dict(base_mix, **{k: 4})
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                res[(k, lab)] = st.mean(a - b for a, b in zip(cash, base))
    labs = ("2018-21", "2022-25", "2010-13", "2014-17")
    print("add-on vs VG + Z + RS at 4 MNQ (24-month cash per seat, open-P&L check): " + " / ".join(labs))
    for k in keys:
        v = [res[(k, l)] for l in labs]
        print(f"   {k:<18} " + " / ".join(f"{x:+6,.0f}" for x in v) + f"   {'ALL +' if min(v) > 0 else ''}")


if __name__ == "__main__":
    main()
