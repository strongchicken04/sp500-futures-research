"""Hybrid sprint for account A (fixed 2026-10-23 before results): at 10:00, if
the RS rule fires take it (0.20/0.30); otherwise take the VWAP-side trade at
10:00 (0.25/0.40). Later RS checks are skipped that day. Compared, as single
accounts: RS (now, first signal 10:00-14:30), VWAP10, hybrid; and the
two-account plan hybrid + 09:31 (hedge guard) vs RS + 09:31. Four eras.
Usage: hybrid_sprint.py DATA_DIR
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
from pair_sprint import ERAS  # noqa: E402
from pair_guard import first_funded  # noqa: E402
from score_multi_feature import LEVELS as ML  # noqa: E402


def single(T, cal):
    o = outcomes(calendar_days(T, cal), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
    v = [renew(o, s, 150) for s in range(len(o) - 150)]
    v = [x for x in v if x[0] is not None]
    return st.mean(d for d, _ in v), st.mean(n for _, n in v) * FEE


def main():
    data = sys.argv[1]
    for lab, lo, hi, suf in ERAS:
        rule = lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)
        rows = [r for r in parse_mf(f"{data}/MFEAT{suf}_tags.txt") if lo <= r["date"] < hi]
        rs = first_signals(rows, rule)
        rs10 = {r["date"]: (r, rule(r)) for r in rows if r["hm"] == 600 and rule(r)}
        R = {}
        for r in parse([f"{data}/CBA{suf}_tags.txt"]):
            R.setdefault(r["type"], []).append(r)
        vw = {r["date"]: (r, sgn(r["e"] - r["vwap"])) for r in R["T1000"] if lo <= r["date"] < hi and sgn(r["e"] - r["vwap"])}
        tm = trend_map(R["T931"])
        t9 = {r["date"]: (r, tm[r["date"]]) for r in R["T931"] if lo <= r["date"] < hi and tm.get(r["date"])}
        cal = sorted(set(rs) | set(vw) | set(t9))
        H = {}
        for d in cal:
            if d in rs10:
                H[d] = ("RS", rs10[d][0], rs10[d][1], 600)
            elif d in vw:
                H[d] = ("VW", vw[d][0], vw[d][1], 600)
        TR = [Trade(d, a_usd(r, s), "S") for d, (r, s) in rs.items()]
        TV = [Trade(d, b_usd(r, s), "S") for d, (r, s) in vw.items()]
        TH = [Trade(d, a_usd(r, s) if k == "RS" else b_usd(r, s), "S") for d, (k, r, s, _) in H.items()]
        a, b, c = single(TR, cal), single(TV, cal), single(TH, cal)
        # two accounts with the 09:31 sprint and the hedge guard (A skips against an open 09:31 trade)
        t9x = {}
        for d, (r, s) in t9.items():
            fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
            t9x[d] = exit_min(571, fav, adv, CLV.index(25), CLV.index(40))
        T9 = [Trade(d, b_usd(r, s), "S") for d, (r, s) in t9.items()]
        A_now = [Trade(d, a_usd(r, s), "S") for d, (r, s) in rs.items() if not (d in t9 and t9[d][1] != s and r["hm"] < t9x[d])]
        A_hyb = [Trade(d, a_usd(r, s) if k == "RS" else b_usd(r, s), "S") for d, (k, r, s, e) in H.items()
                 if not (d in t9 and t9[d][1] != s and e < t9x[d])]
        p1, p2 = first_funded(A_now, T9, cal), first_funded(A_hyb, T9, cal)
        print(f"{lab}: single RS {a[0]:5.1f} d ${a[1]:4.0f} | VWAP10 {b[0]:5.1f} d ${b[1]:4.0f} | hybrid {c[0]:5.1f} d ${c[1]:4.0f}"
              f"   || two accounts: RS+09:31 {p1[0]:5.1f} d ${p1[1]:4.0f} | hybrid+09:31 {p2[0]:5.1f} d ${p2[1]:4.0f}")


if __name__ == "__main__":
    main()
