"""Funded: RS sprint only until the drawdown LOCKS, then the book (night shift
2026-10-25/26, fixed before results). Idea from SSRN 7445798 (Villahermosa):
the trailing floor is best crossed in as few days as possible ("bold play");
our book at 3 MNQ needs weeks to clear +$2,100 while the floor trails. The
earlier test (funded_v2, sprint until the FIRST PAYOUT) lost because of the
five-profitable-day rule; here the sprint stops at the lock (peak >= +$2,100,
about two wins), so the book collects the profitable days.

Variants (every era re-priced at NQ 28,530 as size_today.py, open-P&L check,
funded_model with the new evaluation cost):
  BOOK            VG + Z + RS, 3 MNQ each, from day one (the plan)
  LOCK idle       RS sprint 0.20/0.30, wins up to $1,450 (funded_sprint S3
                  sizing, a loss always fits the room), until the peak is
                  >= +$2,100; days without a sprint signal: no trade; then BOOK
  LOCK + book     as LOCK idle, but the book trades on days without a signal
Paired bootstrap (24 months, 20-day blocks), four eras; first payout rate.
Note: Lucid may review "excessive single-day profits" - a $1,450 day on a
funded account is a risk this sim cannot price.
Usage: lock_sprint.py DATA_DIR
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
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from two_win_sprint import trade_pts  # noqa: E402
from funded_sprint import sprint_usd  # noqa: E402
from size_today import rvmap, PRICE  # noqa: E402

MIX = {"VG": 3, "Z": 3, "RS": 3}


def lock_fn(with_book):
    def f(day, s):
        if s["peak"] >= 2100.0:
            return day["book"]
        if day["rs"]:
            return [sprint_usd(day["rs"], s["pnl"], s["line"], s["peak"], s["pdays"], "S3")]
        return day["book"] if with_book else []
    return f


V = {"BOOK": lambda d, s: d["book"], "LOCK idle": lock_fn(False), "LOCK + book": lock_fn(True)}


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
        rs = first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                           (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
        rs = {d: trade_pts(r, s, ML, 20, 30) for d, (r, s) in rs.items()}
        f = lambda e: PRICE / e
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            days = [{"book": C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, MIX, f, True), "rs": rs.get(d)} for d in cal]
            paths = M.bootstrap(len(cal), 3000, seed=2526)
            print(f"--- {lab} at NQ {PRICE:,.0f}: 24-month cash per seat (paired) | first payout from every start day")
            base = None
            for name, fn in V.items():
                cash = [M.run_path([days[i] for i in p], fn) for p in paths]
                fp = [r for r in (M.first_payout(days[s:], fn) for s in range(len(days) - 250)) if r]
                ok = [n for r, n in fp if r]
                base = base or cash
                dd = [x - y for x, y in zip(cash, base)]
                print(f"   {name:<12} ${st.mean(cash):7,.0f}  p10 ${sorted(cash)[len(cash) // 10]:7,.0f}  vs BOOK {st.mean(dd):+6,.0f} "
                      f"(+/- {1.96 * st.pstdev(dd) / len(dd) ** 0.5:,.0f}) better {sum(x > 0 for x in dd) / len(dd) * 100:3.0f}%  "
                      f"first payout {len(ok) / len(fp) * 100:4.1f}% in {st.mean(ok) if ok else 0:5.1f} d")


if __name__ == "__main__":
    main()
