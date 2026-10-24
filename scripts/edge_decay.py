"""What if the edge fades? (day shift 2026-10-24, risk view for the owner).
Book VG + Z + RS + V10 at 4 MNQ (and at 3), open-P&L model, corrected account
model (bust = new evaluation $180 / 11 days). Each leg's mean $ per MNQ trade
in the era is reduced by 50% / 100% (zero edge) / 150% (negative edge) by
shifting every trade of that leg - the trade-by-trade risk stays the same.
24-month cash per seat, share of seats below zero; 2018-21 / 2022-25.
Usage: edge_decay.py DATA_DIR
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
    L.NAMES = ("BARS5A", "BARS5B")
    tr, by = C.trades(data, "", lambda d: reg.get(d, 9.0) < 0.30, None)
    full = sorted({r["date"] for r in parse([f"{data}/CBA_tags.txt"])})
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25")):
        cal = [d for d in full if lo <= d < hi]
        sub = [t for t in tr if lo <= t[0] < hi]
        mean = {k: st.mean(t[3] for t in sub if t[4] == k) for k in LEGS}
        paths = M.bootstrap(len(cal), 3000, seed=31)
        print(f"--- {lab}: mean $ per MNQ trade " + ", ".join(f"{k} {v:+.1f}" for k, v in mean.items()))
        for n in (4, 3):
            cells = []
            for cut in (0.0, 0.5, 1.0, 1.5):
                T = {}
                for t in sub:
                    T.setdefault(t[0], []).append(t[:3] + (t[3] - cut * mean.get(t[4], 0.0),) + t[4:])
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, {k: n for k in LEGS}, None, True) for d in cal]
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                cells.append(f"edge -{int(cut * 100)}%: ${st.mean(cash):7,.0f} (below 0: {sum(c < 0 for c in cash) / len(cash) * 100:3.0f}%)")
            print(f"   {n} MNQ  " + " | ".join(cells))


if __name__ == "__main__":
    main()
