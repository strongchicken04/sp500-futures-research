"""Contingency if noise momentum is cut (day shift 2026-10-24, fixed before
results): book VG + RS at 3 MNQ plus ONE of OD (open drive), NR (NR4 break),
V11 (VWAP side 11:00, +0.30/-0.50) at 3, or Z for reference; today's NQ
(28,530), open-P&L, four eras (bootstrap) + 2025-01..2026-07 (book total).
Usage: z_replace.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
import mtm_check as C  # noqa: E402
from mc_simple import nr4  # noqa: E402
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse  # noqa: E402
from size_today import PRICE, rvmap  # noqa: E402
from vside_plateau import vside  # noqa: E402

C.PANEL_LEGS = {"OD": lambda days: (lambda d, p: L.odrive(d, p, 0.0005, 0.0015)), "NR": nr4, "V11": vside(17, 0.0030, 0.0050)}
BASE = {"VG": 3, "RS": 3}
V = {"VG+RS": BASE, "+ Z": dict(BASE, Z=3), "+ OD": dict(BASE, OD=3), "+ NR": dict(BASE, NR=3), "+ V11": dict(BASE, V11=3),
     "+ OD + NR": dict(BASE, OD=3, NR=3)}


def main():
    data = sys.argv[1]
    reg = rvol()
    ro, r26 = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD")), rvmap(data, ("LSVWAP26", "LSNOISE26"))
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < ro.get(d, 9.0) < 0.30, (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))))
    recent = {k: 0.0 for k in V}
    for suf, names, cba, gate, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        tr, by = C.trades(data, suf, gate, PRICE)
        T = {}
        for t in tr:
            T.setdefault(t[0], []).append(t)
        f = lambda e: PRICE / e
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            paths = M.bootstrap(len(cal), 3000, seed=31)
            base = None
            cells = []
            for name, mix in V.items():
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                base = base or cash
                cells.append(f"{name} ${st.mean(cash):,.0f}" if name == "VG+RS" else f"{name} {st.mean(a - b for a, b in zip(cash, base)):+6,.0f}")
            print(f"{lab}: " + " | ".join(cells))
        if suf == "":
            for name, mix in V.items():
                recent[name] += sum(t[3] * mix.get(t[4], 0) for t in tr if t[0] >= "2025")
    L.NAMES = ("B2_26",)
    tr, by = C.trades(data, "26", lambda d: 0 < r26.get(d, 9.0) < 0.30, PRICE)
    for name, mix in V.items():
        recent[name] += sum(t[3] * mix.get(t[4], 0) for t in tr if t[0] >= "2026")
    print("2025-01..2026-07 closed P&L of the book: " + " | ".join(f"{k} ${v:+,.0f}" for k, v in recent.items()))


if __name__ == "__main__":
    main()
