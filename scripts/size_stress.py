"""Stress test of flat 4 vs flat 3 (night shift 2026-10-23/24): extra cost of
0.5 and 1.0 pt per MNQ per trade ($1 / $2) on every book trade (worse fills),
open-P&L model, four eras (2010-17 re-priced at today's NQ).
Usage: size_stress.py DATA_DIR
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
        tr0, by = C.trades(data, suf, gate, pr)
        f = (lambda e: pref / e) if pr else None
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            paths = M.bootstrap(len(cal), 3000, seed=31)
            cells = []
            for extra in (0.0, 1.0, 2.0):
                T = {}
                for t in tr0:
                    if t[4] in ("VG", "Z", "RS"):
                        T.setdefault(t[0], []).append(t[:3] + (t[3] - extra,) + t[4:])
                res = {}
                for n in (3, 4):
                    dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, {"VG": n, "Z": n, "RS": n}, f, True) for d in cal]
                    res[n] = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                dd = [a - b for a, b in zip(res[4], res[3])]
                cells.append(f"+${extra:.0f}/MNQ: flat 3 ${st.mean(res[3]):7,.0f}, flat 4 ${st.mean(res[4]):7,.0f} ({st.mean(dd):+6,.0f}, better {sum(x > 0 for x in dd) / len(dd) * 100:3.0f}%)")
            print(f"{lab}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
