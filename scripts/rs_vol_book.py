"""Funded book with the RS leg skipped on HIGH-volume days (day shift
2026-10-26). rs_volume.py (rule fixed before results: a tercile must be the
worst / best in all four eras) found the high tercile (session volume up to
the check >= 1.12 x its 20-day mean, cut fixed on 2018-21) the worst for the
+/-1.25% leg in all four eras and 2026. Here: book VG + Z + RS at 3 MNQ, NQ
28,530, open-P&L, paired bootstrap (rs10_book.py setup):
  BOOK   plan
  RSV    RS leg only when rvol < 1.12
Usage: rs_vol_book.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
import mtm_check as C  # noqa: E402
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse  # noqa: E402
from size_today import rvmap, PRICE  # noqa: E402
from rs_volume import KEND  # noqa: E402

MIX = {"VG": 3, "Z": 3, "RS": 3}
CUT = 1.12


def rvol_map(days):
    idx = {d: i for i, (d, _) in enumerate(days)}
    def f(d, hm):
        i = idx.get(d)
        if i is None or i < 20 or hm not in KEND:
            return None
        k = KEND[hm]
        cur = sum(x[4] for x in days[i][1][:k + 1])
        avg = st.mean(sum(x[4] for x in days[j][1][:k + 1]) for j in range(i - 20, i))
        return cur / avg if avg > 0 else None
    return f


def main():
    data = sys.argv[1]
    rv = rvol_map(B.load(data))
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
        keep = lambda t: t[4] != "RS" or (rv(t[0], t[1]) is not None and rv(t[0], t[1]) < CUT)
        V = {"BOOK": tr, "RSV": [t for t in tr if keep(t)]}
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            paths = M.bootstrap(len(cal), 3000, seed=1027)
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
