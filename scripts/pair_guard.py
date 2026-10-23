"""Pairs with the hedge guard (2026-10-23): the later-entering account skips its
trade when the other account still holds an opposite position at its entry.
Pairs: RS + 09:31 (now; RS skips), 09:31 + VWAP10 (VWAP10 skips if the 09:31
trade is open at 10:00 against it). Days / fees to the first funded account,
share of skipped days, four eras.
Usage: pair_guard.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals  # noqa: E402
from score_cond_bracket import parse  # noqa: E402
from two_account_sprint import renew, FEE  # noqa: E402
from hedge_check import a_usd, b_usd, exit_min, CLV  # noqa: E402
from b_sprint_lab import trend_map, sgn  # noqa: E402
from pair_sprint import ERAS, bought  # noqa: E402


def first_funded(TA, TB, cal):
    oA = outcomes(calendar_days(TA, cal), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
    oB = outcomes(calendar_days(TB, cal), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
    res = []
    for s in range(min(len(oA), len(oB)) - 150):
        da, _ = renew(oA, s, 150)
        db, _ = renew(oB, s, 150)
        if da is None or db is None:
            continue
        f = min(da, db)
        res.append((f, (bought(oA, s, f) + bought(oB, s, f)) * FEE))
    return st.mean(x for x, _ in res), st.mean(y for _, y in res)


def main():
    data = sys.argv[1]
    ti, si = CLV.index(25), CLV.index(40)
    for lab, lo, hi, suf in ERAS:
        rs = {d: v for d, v in first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                             (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)).items() if lo <= d < hi}
        R = {}
        for r in parse([f"{data}/CBA{suf}_tags.txt"]):
            R.setdefault(r["type"], []).append(r)
        tm = trend_map(R["T931"])
        t9 = {r["date"]: (r, tm[r["date"]]) for r in R["T931"] if lo <= r["date"] < hi and tm.get(r["date"])}
        vw = {r["date"]: (r, sgn(r["e"] - r["vwap"])) for r in R["T1000"] if lo <= r["date"] < hi and sgn(r["e"] - r["vwap"])}
        t9x = {}
        for d, (r, s) in t9.items():
            fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
            t9x[d] = exit_min(571, fav, adv, ti, si)
        cal = sorted(set(rs) | set(t9) | set(vw))
        T9 = [Trade(d, b_usd(r, s), "S") for d, (r, s) in t9.items()]
        skipA = {d for d, (r, s) in rs.items() if d in t9 and t9[d][1] != s and r["hm"] < t9x[d]}
        skipV = {d for d, (r, s) in vw.items() if d in t9 and t9[d][1] != s and 600 < t9x[d]}
        A = [Trade(d, a_usd(r, s), "S") for d, (r, s) in rs.items() if d not in skipA]
        V = [Trade(d, b_usd(r, s), "S") for d, (r, s) in vw.items() if d not in skipV]
        d1, f1 = first_funded(A, T9, cal)
        d2, f2 = first_funded(V, T9, cal)
        print(f"{lab}: RS + 09:31 (guard, {len(skipA) / max(1, len(rs)) * 100:.0f}% RS skipped) {d1:5.1f} d ${f1:4.0f} | "
              f"09:31 + VWAP10 (guard, {len(skipV) / max(1, len(vw)) * 100:.0f}% VWAP10 skipped) {d2:5.1f} d ${f2:4.0f}")


if __name__ == "__main__":
    main()
