"""Funded RS leg only on the 10:00 check (day shift 2026-10-26). Found in
rs_buckets.py (so NOT fixed before results - post-hoc, needs every check):
the +/-1.25% leg earns at the 10:00 check in all four eras (+4.3 / +2.4 /
+9.8 / +10.4 bp, 2026 +11.6) and ~0 at 11:00 / 13:00 / 14:30, which still
carry the full ~$2,140 stop at 3 MNQ.
Variants at NQ 28,530 (size_today.py setup: every era re-priced, open-P&L
check, funded_model with the new eval cost), book VG + Z + RS at 3 MNQ:
  BOOK   RS leg on the first signal of 10:00 / 11:00 / 13:00 / 14:30 (plan)
  RS10   RS leg only when the first signal comes at 10:00
Paired bootstrap 24 months; first payout from every start day. Then the
timing check 6c on the RS timing exports (MFEAT*_M5 / _P5) in rs10_timing.
Usage: rs10_book.py DATA_DIR
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
from size_today import rvmap, PRICE  # noqa: E402

MIX = {"VG": 3, "Z": 3, "RS": 3}


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
        f = lambda e: PRICE / e
        V = {"BOOK": tr, "RS10": [t for t in tr if not (t[4] == "RS" and t[1] != 600)]}
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            paths = M.bootstrap(len(cal), 3000, seed=1026)
            print(f"--- {lab} at NQ {PRICE:,.0f}: 24-month cash per seat (paired) | first payout")
            base = None
            for name, trs in V.items():
                T = {}
                for t in trs:
                    T.setdefault(t[0], []).append(t)
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, MIX, f, True) for d in cal]
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                fp = [r for r in (M.first_payout(dl[s:], lambda d, s: d) for s in range(len(dl) - 250)) if r]
                base = base or cash
                dd = [x - y for x, y in zip(cash, base)]
                nrs = sum(1 for t in trs if t[4] == "RS" and lo <= t[0] < hi)
                print(f"   {name:<5} ${st.mean(cash):7,.0f}  p10 ${sorted(cash)[len(cash) // 10]:7,.0f}  vs BOOK {st.mean(dd):+6,.0f} "
                      f"(+/- {1.96 * st.pstdev(dd) / len(dd) ** 0.5:,.0f}) better {sum(x > 0 for x in dd) / len(dd) * 100:3.0f}%  "
                      f"first payout {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%  RS trades {nrs}")


if __name__ == "__main__":
    main()
