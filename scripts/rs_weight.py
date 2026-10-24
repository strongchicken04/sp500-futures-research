"""Tilt size toward the RS funded leg (day shift 2026-10-24, fixed before
results): all at 4 (base) vs RS 6 / others 4, RS 8 / others 4, RS 6 / others
3. Book VG + Z + RS, open-P&L model, four eras (2010-17 re-priced) + the
2026 holdout (book total and first payouts from each start).
Usage: rs_weight.py DATA_DIR
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

VAR = {"all 4": {"VG": 4, "Z": 4, "RS": 4}, "RS 6, others 4": {"VG": 4, "Z": 4, "RS": 6},
       "RS 8, others 4": {"VG": 4, "Z": 4, "RS": 8}, "RS 6, others 3": {"VG": 3, "Z": 3, "RS": 6}}


def rvmap(data, files):
    m = {}
    for f in files:
        for raw in open(f"{data}/{f}_tags.txt"):
            p = raw.strip().split(",")
            if p[0] == "L" and len(p) >= 10 and int(p[9]) > 0:
                m[f"{p[2][:4]}-{p[2][4:6]}-{p[2][6:]}"] = int(p[9]) / 1000.0
    return m


def main():
    data = sys.argv[1]
    C.PANEL_LEGS = {}
    reg = rvol()
    pref = st.mean(float(p.split(",")[5]) for p in open(f"{data}/LSNOISE_tags.txt")
                   if p.startswith(("L,NS,2022", "L,NS,2023", "L,NS,2024", "L,NS,2025")))
    ro, r26 = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD")), rvmap(data, ("LSVWAP26", "LSNOISE26"))
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, None,
             (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < ro.get(d, 9.0) < 0.30, pref,
             (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))),
            ("26", ("B2_26",), "CBA26", lambda d: 0 < r26.get(d, 9.0) < 0.30, None, (("2026", "2027", "2026 H1"),)))
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
            cells = []
            base = None
            for name, mix in VAR.items():
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                if lab == "2026 H1":
                    fp = [r for r in (M.first_payout(dl[s:], lambda d, s: d) for s in range(len(dl) - 60)) if r]
                    cells.append(f"{name}: total ${sum(sum(x) for x in dl):+7,.0f}, first payout {sum(r for r, _ in fp)}/{len(fp)}")
                    continue
                paths = M.bootstrap(len(cal), 3000, seed=31)
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                base = base or cash
                cells.append(f"{name}: ${st.mean(cash):7,.0f} ({st.mean(a - b for a, b in zip(cash, base)):+6,.0f})")
            print(f"{lab}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
