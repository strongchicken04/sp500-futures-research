"""Best pair of evaluation sprints for two accounts (2026-10-23), four eras.
Sprints: RS (0.20/0.30), 09:31 trend, VWAP10 (side of VWAP at 10:00), MOM60
(09:30 -> 10:30 direction, entry 10:30), the last three at 0.25/0.40; size so the
stop costs $1,900. Days and fees to the first funded account (no hedge guard
here; the clash share is printed).
Usage: pair_sprint.py DATA_DIR
"""
from __future__ import annotations

import itertools
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
from hedge_check import a_usd, b_usd  # noqa: E402
from b_sprint_lab import trend_map, sgn  # noqa: E402

ERAS = (("2010-13", "2010", "2014", "_OLD"), ("2014-17", "2014", "2018", "_OLD"), ("2018-21", "2018", "2022", ""), ("2022-25", "2022", "2026", ""))


def bought(o, s0, until):
    t, k = s0, 0
    while t < len(o) and t - s0 < until:
        k += 1
        t += o[t][1]
    return max(k, 1)


def main():
    data = sys.argv[1]
    for lab, lo, hi, suf in ERAS:
        rs = first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                           (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
        R = {}
        for r in parse([f"{data}/CBA{suf}_tags.txt"]):
            R.setdefault(r["type"], []).append(r)
        tm = trend_map(R["T931"])
        S = {"RS": {d: (a_usd(r, s), s) for d, (r, s) in rs.items() if lo <= d < hi},
             "T931": {r["date"]: (b_usd(r, tm[r["date"]]), tm[r["date"]]) for r in R["T931"] if lo <= r["date"] < hi and tm.get(r["date"])},
             "VWAP10": {r["date"]: (b_usd(r, sgn(r["e"] - r["vwap"])), sgn(r["e"] - r["vwap"])) for r in R["T1000"] if lo <= r["date"] < hi and sgn(r["e"] - r["vwap"])},
             "MOM60": {r["date"]: (b_usd(r, sgn(r["e"] - r["o930"])), sgn(r["e"] - r["o930"])) for r in R["T1030"] if lo <= r["date"] < hi and sgn(r["e"] - r["o930"])}}
        cal = sorted({d for v in S.values() for d in v})
        O = {k: outcomes(calendar_days([Trade(d, u, "S") for d, (u, _) in v.items()], cal), flat(1, 1e6), window=120,
                         start_pnl=0.0, target=3000.0, consistency=True) for k, v in S.items()}
        print(f"--- {lab}")
        for a, b in itertools.combinations(S, 2):
            res = []
            for s in range(min(len(O[a]), len(O[b])) - 150):
                da, _ = renew(O[a], s, 150)
                db, _ = renew(O[b], s, 150)
                if da is None or db is None:
                    continue
                f = min(da, db)
                res.append((f, (bought(O[a], s, f) + bought(O[b], s, f)) * FEE))
            common = set(S[a]) & set(S[b])
            opp = sum(S[a][d][1] != S[b][d][1] for d in common) / max(1, len(common))
            print(f"   {a:>6} + {b:<6} first funded {st.mean(x for x, _ in res):5.1f} days, fees ${st.mean(y for _, y in res):4.0f}, opposite direction on {opp * 100:.0f}% of common days")


if __name__ == "__main__":
    main()
