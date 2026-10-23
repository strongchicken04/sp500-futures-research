"""How long can the two-account evaluation take? Distribution (median, 80th,
95th percentile, worst) of trading days to the first funded account and of
fees, RS sprint (A, 0.20/0.30, hedge guard) + 09:31 sprint (B, 0.25/0.40),
over every start day of 2018-21 and 2022-25.
Usage: eval_spread.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals  # noqa: E402
from bias_sprint import build  # noqa: E402
from two_account_sprint import renew, FEE  # noqa: E402
from hedge_check import a_usd, b_usd, exit_min, CLV  # noqa: E402


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


def main():
    sp = sys.argv[1]
    rs = first_signals(parse_mf(f"{sp}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    t931 = {r["date"]: (r, 1 if f["sma50"] > 0 else -1) for r, f in build(sp)}
    cal = sorted(d for d in set(rs) | set(t931) if d >= min(t931))
    clash = {}
    for d, (ra, sa) in rs.items():
        if d in t931:
            rb, sb = t931[d]
            fav, adv = (rb["up"], rb["dn"]) if sb == 1 else (rb["dn"], rb["up"])
            clash[d] = sa != sb and ra["hm"] < exit_min(571, fav, adv, CLV.index(25), CLV.index(40))
    for lab, lo, hi in (("2018-2021", "0", "2022"), ("2022-2025", "2022", "9")):
        cc = [d for d in cal if lo <= d < hi]
        A = [Trade(d, a_usd(r, s), "S") for d, (r, s) in rs.items() if lo <= d < hi and not clash.get(d)]
        B = [Trade(d, b_usd(r, s), "S") for d, (r, s) in t931.items() if lo <= d < hi]
        oA = outcomes(calendar_days(A, cc), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
        oB = outcomes(calendar_days(B, cc), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
        days, fees = [], []
        for s in range(min(len(oA), len(oB)) - 150):
            da, na = renew(oA, s, 150)
            db, nb = renew(oB, s, 150)
            if da is None or db is None:
                continue
            first = min(da, db)
            def bought(o, s0, until):
                t, k = s0, 0
                while t < len(o) and t - s0 < until:
                    k += 1
                    t += o[t][1]
                return max(k, 1)
            days.append(first)
            fees.append((bought(oA, s, first) + bought(oB, s, first)) * FEE)
        print(f"{lab}: days to first funded  median {pct(days, .5)}, 80% {pct(days, .8)}, 95% {pct(days, .95)}, worst {max(days)};"
              f"  fees median ${pct(fees, .5):.0f}, 80% ${pct(fees, .8):.0f}, 95% ${pct(fees, .95):.0f}, worst ${max(fees):.0f}")


if __name__ == "__main__":
    main()
