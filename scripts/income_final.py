"""Income per funded seat for the recommended plan (night shift 2026-10-23/24):
no ORB, VG + Z + RS at 4 MNQ (and at 3 for comparison), corrected account
model with the drawdown checked on open P&L (mtm_check), bust = new
evaluation $180 / 11 days. Mean / median / p10 / p90 cash over 24 months and
the share of seats below zero; four eras (2010-17 re-priced at today's NQ).
Usage: income_final.py DATA_DIR
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

MIXES = {"plan 4 MNQ": {"VG": 4, "Z": 4, "RS": 4}, "before 3 MNQ": {"VG": 3, "Z": 3, "RS": 3}}


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
             (("2010", "2014", "2010-13 (today's price)"), ("2014", "2018", "2014-17 (today's price)"))))
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
            paths = M.bootstrap(len(cal), 4000, seed=2024)
            for name, mix in MIXES.items():
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                v = sorted(M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths)
                q = lambda x: v[int(x * (len(v) - 1))]
                print(f"{lab:<24} {name:<13} mean ${st.mean(v):7,.0f} (${st.mean(v) / 24:5,.0f}/month) median ${q(.5):7,.0f} "
                      f"p10 ${q(.1):7,.0f} p90 ${q(.9):7,.0f} below zero {sum(x < 0 for x in v) / len(v) * 100:.1f}%")


if __name__ == "__main__":
    main()
