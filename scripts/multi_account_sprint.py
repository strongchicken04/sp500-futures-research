"""Evaluation on 1-3 accounts at once, each with a DIFFERENT sprint signal
(pre-specified):
  RS     live RS rule, target 0.20% / stop 0.30% (rs_sprint_shape)
  T931   09:31 entry with the 50-day trend bias, +0.20% / -0.40% (bias_sprint)
  NZ     first noise-momentum signal of the day (Zarattini), bracket +0.20% /
         -0.40%, else the noise exit rule (score_noise_tod.z_result)
Each account buys a new $90 evaluation after a bust. Reported: pass per attempt
of each sprint, daily correlation of sprint results, and for every account set
the trading days to the FIRST funded account and the fees paid by then.

Usage: multi_account_sprint.py SCRATCH_DIR
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
from score_multi_feature import parse as parse_mf, first_signals, LEVELS  # noqa: E402
from rs_sprint_shape import usd as rs_usd  # noqa: E402
from bias_sprint import build, outcome as t931_usd  # noqa: E402
from score_noise_tod import parse as parse_nz, z_result  # noqa: E402

FEE = 90.0


def nz_usd(z):
    p = z_result(z, 20, 40)                    # NQ points per MNQ, cost included
    n = max(1, min(40, int(1900 / (z["e"] * 0.004 * 2.0))))
    return p * 2.0 * n - n * 0.5


def renew(o, s, horizon):
    t, n = s, 0
    while t < len(o) and t - s < horizon:
        res, d = o[t]
        n += 1
        if res == "pass":
            return t + d - s, n
        t += d
    return None, n


def bought(o, s0, until):
    t, k = s0, 0
    while t < len(o) and t - s0 < until:
        k += 1
        t += o[t][1]
    return max(k, 1)


def main():
    sp = sys.argv[1]
    rs = first_signals(parse_mf(f"{sp}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    S = {"RS": {d: rs_usd(r, s, LEVELS.index(20), LEVELS.index(30)) for d, (r, s) in rs.items()},
         "T931": {r["date"]: t931_usd(r, 1 if f["sma50"] > 0 else -1) for r, f in build(sp)}}
    Z, _ = parse_nz(f"{sp}/NOISETOD_tags.txt")
    nz = {}
    for z in sorted(Z, key=lambda z: (z["ymd"], z["ehm"])):
        d = f"{z['ymd'][:4]}-{z['ymd'][4:6]}-{z['ymd'][6:]}"
        if d not in nz:
            nz[d] = nz_usd(z)
    S["NZ"] = nz
    start = max(min(v) for v in S.values())
    cal = sorted(d for d in set().union(*S.values()) if d >= start)
    common = [d for d in cal if all(d in v for v in S.values())]
    print("daily correlation of sprint results on common days:")
    for a, b in itertools.combinations(S, 2):
        print(f"   {a}-{b}: {st.correlation([S[a][d] for d in common], [S[b][d] for d in common]):+.2f}")
    for lab, lo, hi in (("2018-2021", "0", "2022"), ("2022-2025", "2022", "9")):
        cc = [d for d in cal if lo <= d < hi]
        O = {k: outcomes(calendar_days([Trade(d, x, "S") for d, x in v.items() if lo <= d < hi], cc), flat(1, 1e6),
                         window=120, start_pnl=0.0, target=3000.0, consistency=True) for k, v in S.items()}
        print(f"\n--- {lab}")
        for k, o in O.items():
            p = sum(1 for x, _ in o if x == "pass") / len(o)
            print(f"   {k:<5} alone: pass/attempt {p * 100:4.1f}%  trades/yr {sum(1 for d in S[k] if lo <= d < hi) / 4:3.0f}")
        n = min(len(o) for o in O.values()) - 150
        for size in (1, 2, 3):
            for combo in itertools.combinations(O, size):
                res = []
                for s in range(n):
                    r = [renew(O[k], s, 150) for k in combo]
                    if any(x is None for x, _ in r):
                        continue
                    first = min(x for x, _ in r)
                    res.append((first, sum(bought(O[k], s, first) for k in combo)))
                print(f"   {' + '.join(combo):<16} days to first funded {st.mean(d for d, _ in res):5.1f} (median {sorted(d for d, _ in res)[len(res) // 2]:3d})"
                      f"   fees ${st.mean(x for _, x in res) * FEE:4.0f}")


if __name__ == "__main__":
    main()
