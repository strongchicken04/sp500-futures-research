"""Funded size at TODAY's NQ price (day shift 2026-10-24). NQ was ~28,500 on
2026-07-24 (last QC bar), while the sims used 2018-25 dollars (NQ 6,000-
22,000) and 2010-17 re-priced at 17,090 - so "4 MNQ" in the sims is much less
risk than 4 MNQ today (an RS stop of 1.25% at 3 MNQ is ~$2,140 now, more than
the $2,000 drawdown). Here EVERY era is re-priced at 28,530 (gross % per trade,
today's costs 0.75 pt / 1.0 on stops), open-P&L check, book VG + Z + RS;
sizes 1 / 2 / 3 / 4 MNQ per leg, and RS at 1 / 2 with VG + Z at 2 / 3.
Usage: size_today.py DATA_DIR
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

PRICE = 28530.0
VAR = {"1 each": {"VG": 1, "Z": 1, "RS": 1}, "2 each": {"VG": 2, "Z": 2, "RS": 2}, "3 each": {"VG": 3, "Z": 3, "RS": 3},
       "4 each": {"VG": 4, "Z": 4, "RS": 4}, "VG/Z 3, RS 2": {"VG": 3, "Z": 3, "RS": 2}, "VG/Z 2, RS 1": {"VG": 2, "Z": 2, "RS": 1},
       "VG/Z 3, RS 1": {"VG": 3, "Z": 3, "RS": 1}}


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
    ro = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD"))
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < ro.get(d, 9.0) < 0.30, (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))))
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
            paths = M.bootstrap(len(cal), 3000, seed=31)
            print(f"--- {lab} at NQ {PRICE:,.0f}: 24-month cash per seat | first payout | evaluations")
            for name, mix in VAR.items():
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                out = []
                for p in paths:
                    lives = []
                    out.append((M.run_path([dl[i] for i in p], lambda d, s: d, stats=lives), len(lives)))
                fp = [r for r in (M.first_payout(dl[s:], lambda d, s: d) for s in range(len(dl) - 250)) if r]
                cash = [c for c, _ in out]
                print(f"   {name:<14} ${st.mean(cash):7,.0f}  p10 ${sorted(cash)[len(cash) // 10]:7,.0f}  first payout {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%  "
                      f"funded accounts {st.mean(n for _, n in out):4.1f}")


if __name__ == "__main__":
    main()
