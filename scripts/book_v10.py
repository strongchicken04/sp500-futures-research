"""Book with the VWAP-side 10:00 leg (V10) included (day shift 2026-10-24,
fixed before results): size 3 / 4 / 5 MNQ for all four legs, and the 4-MNQ
book without each leg; open-P&L model, four eras (2010-17 re-priced).
Usage: book_v10.py DATA_DIR
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

LEGS = ("VG", "Z", "RS", "V10")
VAR = {"4 legs at 4": {k: 4 for k in LEGS}, "4 legs at 3": {k: 3 for k in LEGS}, "4 legs at 5": {k: 5 for k in LEGS},
       "old book (3 legs at 4)": {"VG": 4, "Z": 4, "RS": 4},
       **{f"at 4 without {x}": {k: 4 for k in LEGS if k != x} for x in ("VG", "Z", "RS")}}


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
            paths = M.bootstrap(len(cal), 3000, seed=31)
            base = None
            print(f"--- {lab}")
            for name, mix in VAR.items():
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                fp = [r for r in (M.first_payout(dl[s:], lambda d, s: d) for s in range(len(dl) - 250)) if r]
                base = base or cash
                dd = [a - b for a, b in zip(cash, base)]
                print(f"   {name:<24} ${st.mean(cash):7,.0f} ({st.mean(dd):+7,.0f}) first payout {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%")


if __name__ == "__main__":
    main()
