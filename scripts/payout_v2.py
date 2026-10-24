"""Payout timing for the new book (VG + Z + RS + V10 at 4 MNQ) on the open-P&L
model (day shift 2026-10-24, re-check of payout_policy.py): withdraw at
profit >= 3,000 (half) / 4,000 ($2,000, today) / 5,000 ($2,000) / 6,000
($2,000) / as soon as eligible (>= $2,100, half up to $2,000). Four eras
(2010-17 re-priced).
Usage: payout_v2.py DATA_DIR
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
from vside_plateau import vside  # noqa: E402

POL = {"4000/2000 (today)": (4000.0, 2000.0), "3000/half": (3000.0, 99999.0), "asap": (2100.0, 99999.0),
       "5000/2000": (5000.0, 2000.0), "6000/2000": (6000.0, 2000.0)}


def main():
    data = sys.argv[1]
    C.PANEL_LEGS = {"V10": vside(5, 0.0030, 0.0050)}
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
    mix = {"VG": 4, "Z": 4, "RS": 4, "V10": 4}
    for suf, names, cba, gate, pr, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        tr, by = C.trades(data, suf, gate, pr)
        T = {}
        for t in tr:
            T.setdefault(t[0], []).append(t)
        f = (lambda e: pref / e) if pr else None
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
            paths = M.bootstrap(len(cal), 3000, seed=31)
            base = None
            cells = []
            for name, (trig, amt) in POL.items():
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d, trig=trig, amt=min(amt, 2000.0)) for p in paths]
                base = base or cash
                cells.append(f"{name} {st.mean(a - b for a, b in zip(cash, base)):+6,.0f}")
            print(f"{lab}: today ${st.mean(base):7,.0f} | " + " | ".join(cells[1:]))


if __name__ == "__main__":
    main()
