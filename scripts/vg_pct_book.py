"""VWAP band leg variants in the book at today's price (day shift 2026-10-24,
fixed before results): Z + RS from the live-spec exports plus the panel VWAP
band leg with LIVE@today (25 / 100 pt at 28,530), P15 (0.15 / 0.60%), P20
(0.20 / 0.80%), P25 (0.25 / 1.00%) or no VG; all at 3 MNQ; every era
re-priced at 28,530, open-P&L check; four eras + 2026 holdout (book total).
Usage: vg_pct_book.py DATA_DIR
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
from vg_pct import vg, VARS  # noqa: E402

KEYS = {"LIVE@today": "VGL", "P15": "VG15", "P20": "VG20", "P25": "VG25"}


def main():
    data = sys.argv[1]
    C.PANEL_LEGS = {leg: vg(*VARS[k]) for k, leg in KEYS.items()}
    reg = rvol()
    ro, r26 = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD")), rvmap(data, ("LSVWAP26", "LSNOISE26"))
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < ro.get(d, 9.0) < 0.30, (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))),
            ("26", ("B2_26",), "CBA26", lambda d: 0 < r26.get(d, 9.0) < 0.30, (("2026", "2027", "2026 H1"),)))
    V = {"no VG": {"Z": 3, "RS": 3}, **{k: {"Z": 3, "RS": 3, leg: 3} for k, leg in KEYS.items()}}
    for suf, names, cba, gate, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        tr, by = C.trades(data, suf, gate, PRICE)
        T = {}
        for t in tr:
            T.setdefault(t[0], []).append(t)
        f = lambda e: PRICE / e
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            cells = []
            base = None
            for name, mix in V.items():
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                if lab == "2026 H1":
                    cells.append(f"{name} ${sum(sum(x) for x in dl):+7,.0f}")
                    continue
                paths = M.bootstrap(len(cal), 3000, seed=31)
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                base = base or cash
                cells.append(f"{name} {st.mean(a - b for a, b in zip(cash, base)):+6,.0f}" if name != "no VG" else f"no VG ${st.mean(cash):,.0f}")
            print(f"{lab}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
