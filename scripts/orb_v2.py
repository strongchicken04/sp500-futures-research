"""ORB (Lucid 1, live spec O5) on the open-P&L model (night shift 2026-10-23/24,
fixed before results): VG + Z + RS at 4 MNQ vs + ORB at 4, and the old
book (all four legs at 3) vs no-ORB flat 3; ORB from the live-spec export
(LSORB_A/B, LSORB_OLD; not on Wednesdays; vol gate). Four eras (2010-17
re-priced at today's NQ). Template: leg_drop.py.
Usage: orb_v2.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
import mtm_check as C  # noqa: E402
C.WITH_ORB = True
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse  # noqa: E402

VAR = {"VG+Z+RS": {"VG": 4, "Z": 4, "RS": 4}, "+ ORB 4": {"VG": 4, "Z": 4, "RS": 4, "ORB": 4}, "+ ORB 3, rest 3": {"VG": 3, "Z": 3, "RS": 3, "ORB": 3}, "flat 3 no ORB": {"VG": 3, "Z": 3, "RS": 3}}


def main():
    data = sys.argv[1]
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
            cells = []
            for name, mix in VAR.items():
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                fp = [r for r in (M.first_payout(dl[s:], lambda d, s: d) for s in range(len(dl) - 250)) if r]
                base = base or cash
                dd = [a - b for a, b in zip(cash, base)]
                cells.append(f"{name}: ${st.mean(cash):7,.0f} ({st.mean(dd):+7,.0f}, first payout {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%)")
            print(f"{lab}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
