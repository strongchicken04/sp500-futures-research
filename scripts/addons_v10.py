"""Second round of add-on legs on top of VG + Z + RS + V10 at 4 MNQ (day shift
2026-10-24, fixed before results), open-P&L model, four eras (2010-17
re-priced). One leg at 4 MNQ each, vol gate:
  V11    VWAP side at 11:00, +0.30 / -0.50%
  MOM30  10:00, sign of the 09:30 open -> 10:00 move, +0.30 / -0.50%
  MOM60  10:30, sign of the 09:30 open -> 10:30 move, +0.30 / -0.50%
  OD     open drive (Lucid 10)
  NR     NR4 break
Adopted only if it adds in all four eras.
Usage: addons_v10.py DATA_DIR
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
from vside_plateau import vside  # noqa: E402


def mom(i, tp=0.0030, sp=0.0050):
    def make(days):
        def f(d, p):
            b = d["bars"]
            c, o = b[i][3], b[0][0]
            s = 1 if c > o else -1 if c < o else 0
            return (s, L.run(b, i, s, c, c * (1 - s * sp), c * (1 + s * tp))) if s else None
        return f
    return make


C.PANEL_LEGS = {"V10": vside(5, 0.0030, 0.0050), "V11": vside(17, 0.0030, 0.0050), "MOM30": mom(5), "MOM60": mom(11),
                "OD": lambda days: (lambda d, p: L.odrive(d, p, 0.0005, 0.0015)), "NR": nr4}
BASE = {"VG": 4, "Z": 4, "RS": 4, "V10": 4}


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
    adds = [k for k in C.PANEL_LEGS if k != "V10"]
    res = {}
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
            dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, BASE, f, True) for d in cal]
            base = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
            res[("base", lab)] = st.mean(base)
            for k in adds:
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, dict(BASE, **{k: 4}), f, True) for d in cal]
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                res[(k, lab)] = st.mean(a - b for a, b in zip(cash, base))
    labs = ("2018-21", "2022-25", "2010-13", "2014-17")
    print("base VG + Z + RS + V10 at 4: " + " / ".join(f"${res[('base', l)]:,.0f}" for l in labs))
    for k in adds:
        v = [res[(k, l)] for l in labs]
        print(f"   + {k:<6} " + " / ".join(f"{x:+6,.0f}" for x in v) + ("   ALL +" if min(v) > 0 else ""))


if __name__ == "__main__":
    main()
