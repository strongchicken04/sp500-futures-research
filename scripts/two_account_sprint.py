"""Two evaluations at once with different sprints: how fast and how cheap is
the FIRST funded account? Each account restarts with a new $90 evaluation
after a bust. Compared: RS sprint alone, 09:31 trend sprint alone, both on two
accounts (different signals), RS copied on two accounts.
Data: RS from MFEAT (live rule, 0.15%), 09:31 from CBA T931 with the 50-day
trend bias (bias_sprint). Same sprint bracket and sizing as the live plan.

Usage: two_account_sprint.py SCRATCH_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, sprint_usd  # noqa: E402
from bias_sprint import build, outcome  # noqa: E402

FEE = 90.0


def renew(o, s, horizon):
    """From start s: (days to pass or None, evaluations bought)."""
    t, n = s, 0
    while t < len(o) and t - s < horizon:
        res, d = o[t]
        n += 1
        if res == "pass":
            return t + d - s, n
        t += d
    return None, n


def main():
    sp = sys.argv[1]
    rs = first_signals(parse_mf(f"{sp}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    t931 = {r["date"]: (r, 1 if f["sma50"] > 0 else -1) for r, f in build(sp)}
    cal = sorted(set(rs) | set(t931))
    cal = [d for d in cal if d >= min(t931)]
    for lab, lo, hi in (("2018-2021", "0", "2022"), ("2022-2025", "2022", "9")):
        cc = [d for d in cal if lo <= d < hi]
        A = [Trade(d, sprint_usd(r, s), "S") for d, (r, s) in rs.items() if lo <= d < hi]
        B = [Trade(d, outcome(r, s), "S") for d, (r, s) in t931.items() if lo <= d < hi]
        oA = outcomes(calendar_days(A, cc), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
        oB = outcomes(calendar_days(B, cc), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
        n = min(len(oA), len(oB)) - 150
        res = {"RS alone": [], "09:31 alone": [], "RS + 09:31 (2 accounts)": [], "RS copied on 2 accounts": []}
        for s in range(n):
            da, na = renew(oA, s, 150)
            db, nb = renew(oB, s, 150)
            if da is None or db is None:
                continue
            res["RS alone"].append((da, na))
            res["09:31 alone"].append((db, nb))
            first = min(da, db)
            # evaluations bought until the first pass: each account counts the evals it started by then
            def bought(o, s0, until):
                t, k = s0, 0
                while t < len(o) and t - s0 < until:
                    k += 1
                    t += o[t][1]
                return max(k, 1)
            res["RS + 09:31 (2 accounts)"].append((first, bought(oA, s, first) + bought(oB, s, first)))
            res["RS copied on 2 accounts"].append((da, 2 * na))
        print(f"--- {lab}  ({len(res['RS alone'])} start days)")
        for k, v in res.items():
            print(f"   {k:<26} days to first funded {st.mean(d for d, _ in v):5.1f}  (median {sorted(d for d, _ in v)[len(v) // 2]:3d})   "
                  f"fees ${st.mean(x for _, x in v) * FEE:5.0f}")


if __name__ == "__main__":
    main()
