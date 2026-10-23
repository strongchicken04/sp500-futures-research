"""Open drive in the evaluation sprint (account A, day shift 2026-10-23).
Variant: at 10:00, if the open drive fires (0.05% / 0.15%), account A takes it
with the sprint bracket (target 0.20% / stop 0.30%, size: stop = $1,900) instead
of waiting for the RS signal; otherwise the RS sprint as now. OD brackets are
tracked on 5-min bars (a bar touching both = stop). Compared: days to pass and
evaluations for account A alone, and the two-account plan with the 09:31 sprint.

Usage: od_sprint.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals  # noqa: E402
from bias_sprint import build  # noqa: E402
from two_account_sprint import renew  # noqa: E402
from hedge_check import a_usd, b_usd  # noqa: E402


def od_usd(day):
    L.COST, L.STOP_COST = 0.0, 0.0
    b = day["bars"]
    o = b[0][0]
    hi, lo, c = max(x[1] for x in b[:6]), min(x[2] for x in b[:6]), b[5][3]
    if lo >= o * 0.9995 and c >= o * 1.0015:
        d = 1
    elif hi <= o * 1.0005 and c <= o * 0.9985:
        d = -1
    else:
        return None
    pts = L.run(b, 5, d, c, c * (1 - d * 0.003), c * (1 + d * 0.002))[0]
    S = c * 0.003
    n = max(1, min(40, int(1900 / (S * 2.0))))
    return (pts - 0.5) * 2.0 * n - n


def main():
    data = sys.argv[1]
    days = {d["date"]: d for d in L.load(data)}
    rs = first_signals(parse_mf(f"{data}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    t931 = {r["date"]: (r, 1 if f["sma50"] > 0 else -1) for r, f in build(data)}
    cal = sorted(d for d in set(rs) | set(t931) if d >= min(t931))
    od = {d: od_usd(days[d]) for d in cal if d in days}
    od = {d: v for d, v in od.items() if v is not None}
    for lab, lo, hi in (("2018-2021", "0", "2022"), ("2022-2025", "2022", "9")):
        cc = [d for d in cal if lo <= d < hi]
        v = [od[d] for d in cc if d in od]
        print(f"--- {lab}: OD days {len(v)}, OD sprint win rate {sum(x > 0 for x in v) / len(v) * 100:.0f}%, mean ${st.mean(v):+.0f}")
        B = [Trade(d, b_usd(r, s), "S") for d, (r, s) in t931.items() if lo <= d < hi]
        oB = outcomes(calendar_days(B, cc), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
        rsw = [a_usd(*rs[d]) for d in cc if d in rs and d in od]
        print(f"   RS on the same days: win rate {sum(x > 0 for x in rsw) / max(1, len(rsw)) * 100:.0f}%, mean ${st.mean(rsw) if rsw else 0:+.0f}")
        for use_od in (False, True):
            A = []
            for d in cc:
                if use_od and d in od:
                    A.append(Trade(d, od[d], "S"))
                elif d in rs:
                    A.append(Trade(d, a_usd(*rs[d]), "S"))
            oA = outcomes(calendar_days(A, cc), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
            n = min(len(oA), len(oB)) - 150
            res = []
            for s in range(n):
                da, na = renew(oA, s, 150)
                db, nb = renew(oB, s, 150)
                if da is None or db is None:
                    continue
                res.append((da, na, min(da, db)))
            print(f"   {'A = OD at 10:00, else RS' if use_od else 'A = RS (now)':<26} A alone {st.mean(x for x, _, _ in res):5.1f} days, "
                  f"{st.mean(x for _, x, _ in res):.2f} evaluations; with B first funded {st.mean(x for _, _, x in res):4.1f} days")


if __name__ == "__main__":
    main()
