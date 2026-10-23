"""A second funded book on a second account (2026-10-23): the small momentum
signals that are positive per trade but do not fit into the main book.
Book 2 = open drive (OD) + NR4 + Silver Bullet 2R (SB) + PMTREND (PM), 3 MNQ
each, vol gate. Lifecycle mean per account (bootstrap, as mc_book) in four
eras, the daily P&L correlation with book 1 (VG + Z + RS), and the share of
days on which book 1 and book 2 hold OPPOSITE positions at the same time
(Lucid hedging rule across one trader's accounts).
Usage: book2.py DATA_DIR
"""
from __future__ import annotations

import random
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
import ict_lab as I  # noqa: E402
import gate_check as G  # noqa: E402
import old_check as O  # noqa: E402
import mc_book as M  # noqa: E402
from mc_simple import nr4  # noqa: E402
from pm_lab import pm  # noqa: E402
from mc_runs import sized  # noqa: E402
from rescore_all import rvol  # noqa: E402


def legs2(data, names, keep):
    L.NAMES = names
    out = []
    for cost, leg, fn_of in ((0.75, "OD", lambda ds: (lambda d, p: L.odrive(d, p, 0.0005, 0.0015))),
                             (0.75, "NR", lambda ds: nr4(ds)), (0.5, "SB", lambda ds: (lambda d, p: I.sb(d, p, 2.0))),
                             (0.75, "PM", lambda ds: (lambda d, p: (lambda r: (r[0], r[1]) if r else None)(pm(d["bars"], True))))):
        L.COST, L.STOP_COST = cost, 0.25
        days = L.load(data)
        fn = fn_of(days)
        for t in L.trades(days, fn):
            if keep(t["date"]):
                out.append((t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, leg, t["d"]))
    return out


def main():
    data = sys.argv[1]
    reg = rvol()
    b1 = [t for t in G.build(data, set()) if t[4] in ("VG", "Z", "RS")]
    b2 = legs2(data, ("BARS5A", "BARS5B"), lambda d: reg.get(d, 9.0) < 0.30)
    allt = O.legs(data)
    gated = {t[0] for t in allt if t[5]}
    ob1 = [t[:5] for t in allt if t[5] and t[4] in ("VG", "Z", "RS")]
    ob2 = legs2(data, ("B2_0A", "B2_0B"), lambda d: d in gated)
    for one, two, halves in ((b1, b2, (("2018-21", "0", "2022"), ("2022-25", "2022", "9"))), (ob1, ob2, O.HALVES)):
        two5 = [t[:5] for t in two]
        cal_all = sorted({t[0] for t in one + two5})
        for lab, lo, hi in halves:
            cal = [d for d in cal_all if lo <= d < hi]
            res = M.compare({"book 1 (VG+Z+RS)": sized(one, {"VG": 3, "Z": 3, "RS": 3}),
                             "book 2 (OD+NR4+SB+PM)": sized(two5, {"OD": 3, "NR": 3, "SB": 3, "PM": 3})}, cal, trials=2500, seed=131)
            d1, d2 = defaultdict(float), defaultdict(float)
            for t in one:
                if lo <= t[0] < hi:
                    d1[t[0]] += t[3]
            for t in two:
                if lo <= t[0] < hi:
                    d2[t[0]] += t[3]
            c = st.correlation([d1[d] for d in cal], [d2[d] for d in cal])
            print(f"--- {lab}: book 1 ${st.mean(res['book 1 (VG+Z+RS)']):8,.0f} | book 2 ${st.mean(res['book 2 (OD+NR4+SB+PM)']):8,.0f} per account (24 m); daily corr {c:+.2f}")
    print("(hedging overlap of book 1 and book 2 needs book-1 directions; see note in the report)")


if __name__ == "__main__":
    main()
