"""RS funded leg bracket under the open-P&L drawdown check (night shift
2026-10-23/24, fixed before results). Book VG + Z + RS at 4 MNQ each (the new
size recommendation); RS bracket symmetric 0.75 / 1.00 / 1.25 (today) /
1.50%, else 15:55. Four eras (2010-17 re-priced at today's NQ), corrected
account model with open P&L checked on every 5-min bar (mtm_check).
Usage: rs_bracket.py DATA_DIR
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

MIX = {"VG": 4, "Z": 4, "RS": 4}


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
    res = {}
    for suf, names, cba, gate, pr, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        for lvl in (75, 100, 125, 150):
            C.RS_LEVEL = lvl
            tr, by = C.trades(data, suf, gate, pr)
            T = {}
            for t in tr:
                T.setdefault(t[0], []).append(t)
            f = (lambda e: pref / e) if pr else None
            for lo, hi, lab in halves:
                cal = [d for d in full if lo <= d < hi]
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, MIX, f, True) for d in cal]
                paths = M.bootstrap(len(cal), 3000, seed=31)
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                fp = [x for x in (M.first_payout(dl[s:], lambda d, s: d) for s in range(len(dl) - 250)) if x]
                res[(lab, lvl)] = (cash, sum(r for r, _ in fp) / len(fp))
    for lab in ("2018-21", "2022-25", "2010-13", "2014-17"):
        b = res[(lab, 125)][0]
        cells = []
        for lvl in (75, 100, 125, 150):
            c, fp = res[(lab, lvl)]
            d = [x - y for x, y in zip(c, b)]
            cells.append(f"{lvl / 100:.2f}%: ${st.mean(c):7,.0f} ({st.mean(d):+6,.0f}, {fp * 100:4.1f}%)")
        print(f"{lab}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
