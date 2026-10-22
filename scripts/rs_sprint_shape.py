"""RS sprint payoff shape: the same RS signal with other target/stop pairs,
size set so the stop costs ~$1,900 (max 40 MNQ). Cells fixed in advance:
target 15/20/25/30/40/50 bp x stop 30/40/50 bp. Choose on 2018-2021 by
expected trading days to a pass; 2022-2025 reported untouched. Fees = $90 /
pass rate. Consistency (best day <= 50%) and the $1,450 day cap as in the sims.

Usage: rs_sprint_shape.py SCRATCH_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_multi_feature import parse, first_signals, bp, LEVELS  # noqa: E402


def usd(r, side, ti, si):
    x = bp(r, side, ti, si)
    S = r["e"] * LEVELS[si] / 1e4
    n = max(1, min(40, int(1900 / (S * 2.0))))
    return (x / 1e4 * r["e"] - 0.5) * 2.0 * n - n


def main():
    rows = parse(f"{sys.argv[1]}/MFEAT_tags.txt")
    sig = first_signals(rows, lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                        (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    cal = sorted({r["date"] for r in rows})
    out = []
    for tb in (15, 20, 25, 30, 40, 50):
        for sb in (30, 40, 50):
            ti, si = LEVELS.index(tb), LEVELS.index(sb)
            res = []
            for lo, hi in (("0", "2022"), ("2022", "9")):
                trs = [Trade(d, usd(r, s, ti, si), "S") for d, (r, s) in sig.items() if lo <= d < hi]
                cc = [c for c in cal if lo <= c < hi]
                o = outcomes(calendar_days(trs, cc), flat(1, 1e6), window=200, start_pnl=0.0, target=3000.0, consistency=True)
                p = sum(1 for x, _ in o if x == "pass") / len(o)
                res.append((p * 100, st.mean(d for _, d in o) / p if p else 999, 90 / p if p else 0))
            out.append((tb, sb, res))
            (pa, da, fa), (pb, db, fb) = res
            print(f"target {tb:2} bp / stop {sb:2} bp   pass {pa:4.1f}% / {pb:4.1f}%   days {da:5.1f} / {db:5.1f}   fees ${fa:4.0f} / ${fb:4.0f}")
    best = min(out, key=lambda x: x[2][0][1])
    print(f"\nchosen on 2018-21 (fewest days): target {best[0]} / stop {best[1]} bp -> 2022-25 pass {best[2][1][0]:.1f}%, "
          f"{best[2][1][1]:.1f} days, fees ${best[2][1][2]:.0f}")


if __name__ == "__main__":
    main()
