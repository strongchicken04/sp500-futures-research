"""Conservative income if noise momentum has lost its edge (day shift
2026-10-24): book at today's NQ (28,530), 3 MNQ, open-P&L, four eras:
base VG + Z + RS | Z with zero edge (its trades shifted by its era mean) |
without Z | without Z but VG + RS at 4.
Usage: z_dead.py DATA_DIR
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


def main():
    data = sys.argv[1]
    C.PANEL_LEGS = {}
    reg = rvol()
    ro = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD"))
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < ro.get(d, 9.0) < 0.30, (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))))
    for suf, names, cba, gate, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        tr0, by = C.trades(data, suf, gate, PRICE)
        f = lambda e: PRICE / e
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            sub = [t for t in tr0 if lo <= t[0] < hi]
            zm = st.mean(t[3] for t in sub if t[4] == "Z")
            paths = M.bootstrap(len(cal), 3000, seed=31)
            cells = []
            for name, shift, mix in (("base", 0.0, {"VG": 3, "Z": 3, "RS": 3}), ("Z zero edge", zm, {"VG": 3, "Z": 3, "RS": 3}),
                                     ("without Z", 0.0, {"VG": 3, "RS": 3}), ("without Z, VG+RS at 4", 0.0, {"VG": 4, "RS": 4})):
                T = {}
                for t in sub:
                    T.setdefault(t[0], []).append(t[:3] + (t[3] - (shift if t[4] == "Z" else 0.0),) + t[4:])
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                cells.append(f"{name} ${st.mean(cash):7,.0f}")
            print(f"{lab}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
