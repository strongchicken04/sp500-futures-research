"""Book decisions re-checked at TODAY's NQ price (28,530) and 3 MNQ per leg
(day shift 2026-10-24, fixed before results): ORB added, each leg dropped,
RS bracket 0.75 / 1.00 / 1.25 (today) / 1.50%. Every era re-priced, open-P&L
check, four eras.
Usage: today_checks.py DATA_DIR
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
from size_today import PRICE, rvmap  # noqa: E402

BASE = {"VG": 3, "Z": 3, "RS": 3}


def main():
    data = sys.argv[1]
    C.PANEL_LEGS = {}
    reg = rvol()
    ro = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD"))
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < ro.get(d, 9.0) < 0.30, (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))))
    res = {}
    labs = []
    for suf, names, cba, gate, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        f = lambda e: PRICE / e
        built = {}
        for lvl in (75, 100, 125, 150):
            C.RS_LEVEL, C.WITH_ORB = lvl, (lvl == 125)
            built[lvl] = C.trades(data, suf, gate, PRICE)
        C.RS_LEVEL, C.WITH_ORB = 125, False
        for lo, hi, lab in halves:
            labs.append(lab)
            cal = [d for d in full if lo <= d < hi]
            paths = M.bootstrap(len(cal), 3000, seed=31)

            def cash(lvl, mix):
                tr, by = built[lvl]
                T = {}
                for t in tr:
                    T.setdefault(t[0], []).append(t)
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                return [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
            base = cash(125, BASE)
            res[("base", lab)] = st.mean(base)
            V = {"+ ORB 3": (125, dict(BASE, ORB=3)), "without VG": (125, {"Z": 3, "RS": 3}), "without Z": (125, {"VG": 3, "RS": 3}),
                 "without RS": (125, {"VG": 3, "Z": 3}), "RS 0.75%": (75, BASE), "RS 1.00%": (100, BASE), "RS 1.50%": (150, BASE)}
            for k, (lvl, mix) in V.items():
                res[(k, lab)] = st.mean(a - b for a, b in zip(cash(lvl, mix), base))
    print(f"at NQ {PRICE:,.0f}, 3 MNQ per leg, vs base (VG + Z + RS, RS 1.25%): " + " / ".join(labs))
    print("   base           " + " / ".join(f"${res[('base', l)]:,.0f}" for l in labs))
    for k in ("+ ORB 3", "without VG", "without Z", "without RS", "RS 0.75%", "RS 1.00%", "RS 1.50%"):
        v = [res[(k, l)] for l in labs]
        print(f"   {k:<14} " + " / ".join(f"{x:+6,.0f}" for x in v) + ("   ALL +" if min(v) > 0 else "   ALL -" if max(v) < 0 else ""))


if __name__ == "__main__":
    main()
