"""Size up to the LucidFlex scaling cap (day shift 2026-10-24, fixed before
results). Book VG + Z + RS + V10, open-P&L model, corrected account model
(bust = new evaluation $180 / 11 days), four eras (2010-17 re-priced).
  flat 4        4 MNQ per leg (recommendation)
  flat 5        5 per leg (= the 20-MNQ cap below $1,000 profit)
  scaling max   5 per leg below $1,000 profit, 7 below $2,000, 10 above
                (20 / 28 / 40 MNQ - the scaling tiers), size set at the day start
Reports cash, first-payout rate and evaluations bought per seat in 24 months.
Usage: scaling_size.py DATA_DIR
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
            DL = {n: [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, {k: n for k in LEGS}, f, True) for d in cal]
                  for n in (4, 5, 7, 10)}
            idx = list(range(len(cal)))
            paths = M.bootstrap(len(cal), 3000, seed=31)
            pol = {"flat 4": lambda i, s: DL[4][i], "flat 5": lambda i, s: DL[5][i],
                   "scaling max": lambda i, s: DL[5 if s["pnl"] < 1000 else 7 if s["pnl"] < 2000 else 10][i]}
            print(f"--- {lab}")
            base = None
            for name, fn in pol.items():
                out = []
                for p in paths:
                    lives = []
                    c = M.run_path([idx[i] for i in p], fn, stats=lives)
                    out.append((c, len(lives)))
                cash = [c for c, _ in out]
                fp = [r for r in (M.first_payout(idx[s:], fn) for s in range(len(idx) - 250)) if r]
                base = base or cash
                print(f"   {name:<12} ${st.mean(cash):7,.0f} ({st.mean(a - b for a, b in zip(cash, base)):+7,.0f}) "
                      f"first payout {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%  evaluations per seat {st.mean(n for _, n in out):4.1f}  "
                      f"p10 ${sorted(cash)[len(cash) // 10]:7,.0f}")


if __name__ == "__main__":
    main()
