"""QQQ late-day long (qqq_late_long.py, owner screenshot 2026-10-27) as a
funded book leg LL (night 2026-10-27/28, variants fixed before results).
Setup as rs10_book.py: every era re-priced at NQ 28,530, open-P&L check,
funded_model, paired bootstrap 24 months, book VG + Z + RS at 3 MNQ.
LL rules as published: prev RTH close < SMA50, open > prev close +0.60%, at
15:00 close > open and range position > 0.77 -> long at the 15:00 close,
stop 1%, exit 16:00 close. Costs 0.75 pt (1.0 on the stop) per MNQ side as
the other legs.
Variants: BOOK | + LL 3 MNQ (no vol gate - the signal lives on downtrend
days) | + LL 3 gated (rv20 < 30% as the other legs) | + LL 2.
Usage: late_long_book.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
import mtm_check as C  # noqa: E402
import qqq_late_long as Q  # noqa: E402
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse  # noqa: E402
from size_today import rvmap, PRICE  # noqa: E402

BASE = {"VG": 3, "Z": 3, "RS": 3}


def ll_trades(data):
    days = B.load(data)
    by = dict(days)
    out = []
    for d, _ in Q.rows(days):
        b = by[d]
        e = b[Q.K_SIG][3]
        stop = any(x[2] <= e * (1 - Q.STOP) for x in b[Q.K_SIG + 1:Q.K_END + 1])
        g = -Q.STOP if stop else b[Q.K_END][3] / e - 1
        c = 1.0 if stop else 0.75
        out.append((d, 900, 960, (g * PRICE - c) * 2.0, "LL", 1))
    return out


def main():
    data = sys.argv[1]
    C.PANEL_LEGS = {}
    reg = rvol()
    ro = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD"))
    ll = ll_trades(data)
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < ro.get(d, 9.0) < 0.30, (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))))
    for suf, names, cba, gate, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        tr, by = C.trades(data, suf, gate, PRICE)
        f = lambda e: PRICE / e
        V = {"BOOK": (tr, BASE), "+LL 3": (tr + ll, {**BASE, "LL": 3}),
             "+LL 3 gated": (tr + [t for t in ll if gate(t[0])], {**BASE, "LL": 3}), "+LL 2": (tr + ll, {**BASE, "LL": 2})}
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            paths = M.bootstrap(len(cal), 3000, seed=1027)
            print(f"--- {lab} at NQ {PRICE:,.0f}: 24-month cash per seat (paired) | first payout")
            base = None
            for name, (trs, mix) in V.items():
                T = {}
                for t in trs:
                    T.setdefault(t[0], []).append(t)
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                fp = [r for r in (M.first_payout(dl[s:], lambda d, s: d) for s in range(len(dl) - 250)) if r]
                base = base or cash
                dd = [x - y for x, y in zip(cash, base)]
                nll = sum(1 for t in trs if t[4] == "LL" and lo <= t[0] < hi)
                print(f"   {name:<12} ${st.mean(cash):7,.0f}  p10 ${sorted(cash)[len(cash) // 10]:7,.0f}  vs BOOK {st.mean(dd):+6,.0f} "
                      f"(+/- {1.96 * st.pstdev(dd) / len(dd) ** 0.5:,.0f}) better {sum(x > 0 for x in dd) / len(dd) * 100:3.0f}%  "
                      f"first payout {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%  LL trades {nll}")


if __name__ == "__main__":
    main()
