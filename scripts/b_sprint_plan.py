"""Two-account evaluation with a new account-B sprint (2026-10-23): A = RS
sprint (0.20/0.30) as now, B = one of 09:31 trend (now), VWAP10, MOM30, MOM60
(all 0.25/0.40, size: stop = $1,900). Days and fees to the first funded
account (every start day), correlation of A and B day results, and share of
days on which A and B would hold OPPOSITE positions at the same time
(hedge guard skips A then). 2018-21 | 2022-25 (RS export covers 2018-25), and
2010-13 | 2014-17 from the old exports.
Usage: b_sprint_plan.py DATA_DIR
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

ERAS = (("2010-13", "2010", "2014", "_OLD"), ("2014-17", "2014", "2018", "_OLD"), ("2018-21", "2018", "2022", ""), ("2022-25", "2022", "2026", ""))


def main():
    data = sys.argv[1]
    for lab, lo, hi, suf in ERAS:
        rs = first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                           (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
        rs = {d: v for d, v in rs.items() if lo <= d < hi}
        R = {}
        for r in parse([f"{data}/CBA{suf}_tags.txt"]):
            R.setdefault(r["type"], []).append(r)
        tm = trend_map(R["T931"])
        cands = {
            "09:31 trend (now)": {r["date"]: (r, tm.get(r["date"], 0), 571) for r in R["T931"]},
            "VWAP10": {r["date"]: (r, sgn(r["e"] - r["vwap"]), 600) for r in R["T1000"]},
            "MOM30": {r["date"]: (r, sgn(r["e"] - r["o930"]), 600) for r in R["T1000"]},
            "MOM60": {r["date"]: (r, sgn(r["e"] - r["o930"]), 630) for r in R["T1030"]},
        }
        print(f"--- {lab}")
        for name, B in cands.items():
            B = {d: v for d, v in B.items() if lo <= d < hi and v[1]}
            cal = sorted(d for d in set(rs) | set(B))
            clash = {}
            for d, (ra, sa) in rs.items():
                if d in B:
                    rb, sb, eb = B[d]
                    fav, adv = (rb["up"], rb["dn"]) if sb == 1 else (rb["dn"], rb["up"])
                    xb = exit_min(eb, fav, adv, CLV.index(25), CLV.index(40))
                    eb_in = eb <= ra["hm"] < xb
                    ea_in = False
                    clash[d] = sa != sb and (eb_in or ra["hm"] <= eb)
            A = [Trade(d, a_usd(r, s), "S") for d, (r, s) in rs.items() if not clash.get(d)]
            Bt = [Trade(d, b_usd(r, s), "S") for d, (r, s, _) in B.items()]
            oA = outcomes(calendar_days(A, cal), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
            oB = outcomes(calendar_days(Bt, cal), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
            res = []
            for s in range(min(len(oA), len(oB)) - 150):
                da, na = renew(oA, s, 150)
                db, nb = renew(oB, s, 150)
                if da is None or db is None:
                    continue
                res.append((min(da, db), db))
            ua = {t.date: t.points for t in A}
            ub = {t.date: t.points for t in Bt}
            common = sorted(set(ua) & set(ub))
            c = st.correlation([ua[d] for d in common], [ub[d] for d in common]) if len(common) > 10 else 0.0
            print(f"   B = {name:<18} first funded {st.mean(x for x, _ in res):4.1f} days (B alone {st.mean(y for _, y in res):4.1f}), "
                  f"corr A-B {c:+.2f}, A skipped (opposite) {sum(clash.values()) / max(1, len(rs)) * 100:.0f}% of RS days")


if __name__ == "__main__":
    main()
