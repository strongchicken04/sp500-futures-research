"""Hedging risk of the two-account evaluation plan (owner question 2026-10-23).

Lucid bans hedging, including opposite positions across one trader's accounts.
Account A trades the RS sprint (first RS signal 10:00/11:00/13:00/14:30,
target 0.20% / stop 0.30%), account B the 09:31 trend sprint (50-day bias,
target 0.25% / stop 0.40%). Counts the days on which both are in the market
at the same time in OPPOSITE directions (B's trade still open when A enters),
and what a guard "A skips a signal against B's open trade" costs in pass speed.

Usage: hedge_check.py SCRATCH_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, bp, LEVELS as MLV  # noqa: E402
from bias_sprint import build  # noqa: E402
from score_cond_bracket import LEVELS as CLV  # noqa: E402
from two_account_sprint import renew, FEE  # noqa: E402

EOD = 955


def exit_min(e_min, fav, adv, ti, si):
    hits = [k for k in (fav[ti], adv[si]) if k >= 0]
    return min(EOD, e_min + min(hits)) if hits else EOD


def a_usd(r, s):
    ti, si = MLV.index(20), MLV.index(30)
    x = bp(r, s, ti, si)
    S = r["e"] * 0.003
    n = max(1, min(40, int(1900 / (S * 2.0))))
    return (x / 1e4 * r["e"] - 0.5) * 2.0 * n - n


def b_usd(r, s):
    ti, si = CLV.index(25), CLV.index(40)
    fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
    t, sl = fav[ti], adv[si]
    T, S = r["e"] * 0.0025, r["e"] * 0.0040
    if sl >= 0 and (t < 0 or sl <= t):
        p = -S - 0.25
    elif t >= 0:
        p = T
    else:
        p = max(-S - 0.25, s * r["eod"] - 0.25)
    n = max(1, min(40, int(1900 / (S * 2.0))))
    return (p - 0.25) * 2.0 * n - n


def main():
    sp = sys.argv[1]
    rs = first_signals(parse_mf(f"{sp}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    t931 = {r["date"]: (r, 1 if f["sma50"] > 0 else -1) for r, f in build(sp)}
    cal = sorted(d for d in set(rs) | set(t931) if d >= min(t931))
    clash = {}
    for d, (ra, sa) in rs.items():
        if d not in t931:
            continue
        rb, sb = t931[d]
        fav, adv = (rb["up"], rb["dn"]) if sb == 1 else (rb["dn"], rb["up"])
        xb = exit_min(571, fav, adv, CLV.index(25), CLV.index(40))
        clash[d] = sa != sb and ra["hm"] < xb
    for lab, lo, hi in (("2018-2021", "0", "2022"), ("2022-2025", "2022", "9")):
        both = [d for d in rs if d in t931 and lo <= d < hi]
        nc = sum(clash[d] for d in both)
        opp = sum(rs[d][1] != t931[d][1] for d in both)
        print(f"--- {lab}: days with both signals {len(both)}, opposite direction {opp}, "
              f"opposite AND both open at once {nc} ({nc / max(1, len(both)) * 100:.0f}%)")
        cc = [d for d in cal if lo <= d < hi]
        B = [Trade(d, b_usd(r, s), "S") for d, (r, s) in t931.items() if lo <= d < hi]
        oB = outcomes(calendar_days(B, cc), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
        for guard in (False, True):
            A = [Trade(d, a_usd(r, s), "S") for d, (r, s) in rs.items() if lo <= d < hi and not (guard and clash.get(d))]
            oA = outcomes(calendar_days(A, cc), flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
            n = min(len(oA), len(oB)) - 150
            v = []
            for s in range(n):
                da, na = renew(oA, s, 150)
                db, nb = renew(oB, s, 150)
                if da is None or db is None:
                    continue
                v.append((min(da, db), na, da))
            print(f"   {'guard: A skips signals against B' if guard else 'no guard':<34} first funded {st.mean(x for x, _, _ in v):4.1f} days, "
                  f"A alone {st.mean(x for _, _, x in v):4.1f} days, A evaluations {st.mean(x for _, x, _ in v):.2f}")


if __name__ == "__main__":
    main()
