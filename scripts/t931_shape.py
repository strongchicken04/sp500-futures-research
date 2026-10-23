"""09:31 trend sprint (Lucid 7) payoff shape, same method as rs_sprint_shape:
target 15/20/25/30 bp x stop 30/40/50 bp, size so the stop costs ~$1,900;
choose on 2018-2021 by expected days to a pass, report 2022-2025.

Usage: t931_shape.py SCRATCH_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from bias_sprint import build  # noqa: E402
from score_cond_bracket import LEVELS  # noqa: E402


def usd(r, side, tb, sb):
    ti, si = LEVELS.index(tb), LEVELS.index(sb)
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    T, S = r["e"] * tb / 1e4, r["e"] * sb / 1e4
    if s >= 0 and (t < 0 or s <= t):
        p = -S - 0.25
    elif t >= 0:
        p = T
    else:
        p = max(-S - 0.25, side * r["eod"] - 0.25)
    n = max(1, min(40, int(1900 / (S * 2.0))))
    return (p - 0.25) * 2.0 * n - n


def main():
    pairs = build(sys.argv[1])
    cal = sorted({r["date"] for r, _ in pairs})
    out = []
    for tb in (15, 20, 25, 30):
        for sb in (30, 40, 50):
            res = []
            for lo, hi in (("0", "2022"), ("2022", "9")):
                trs = [Trade(r["date"], usd(r, 1 if f["sma50"] > 0 else -1, tb, sb), "S") for r, f in pairs if lo <= r["date"] < hi]
                cc = [c for c in cal if lo <= c < hi]
                o = outcomes(calendar_days(trs, cc), flat(1, 1e6), window=200, start_pnl=0.0, target=3000.0, consistency=True)
                p = sum(1 for x, _ in o if x == "pass") / len(o)
                res.append((p * 100, st.mean(d for _, d in o) / p if p else 999, 90 / p if p else 0))
            out.append((tb, sb, res))
            (pa, da, fa), (pb, db, fb) = res
            print(f"target {tb:2} / stop {sb:2} bp   pass {pa:4.1f}% / {pb:4.1f}%   days {da:5.1f} / {db:5.1f}   fees ${fa:4.0f} / ${fb:4.0f}")
    best = min(out, key=lambda x: x[2][0][1])
    print(f"\nchosen on 2018-21: target {best[0]} / stop {best[1]} bp -> 2022-25 pass {best[2][1][0]:.1f}%, {best[2][1][1]:.1f} days, fees ${best[2][1][2]:.0f}")


if __name__ == "__main__":
    main()
