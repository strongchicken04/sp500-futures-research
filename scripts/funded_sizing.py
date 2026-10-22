"""Funded sizing for the real plan: evaluation by the RS sprint (a bust costs a
new evaluation: ~$180 in fees and ~11 trading days on average, from
rs_sprint_shape / two_account_sprint), funded phase traded with the book.
Grid fixed in advance: ladder K (dollars of drawdown room per MNQ unit, cap 4)
for the first-payout stage x the repeat stage, plus flat 2 and 3. Mean
24-month cash per account, computed separately on 2018-2021 and 2022-2025
trade histories (choose on 2018-21, report 2022-25).
Books: live fixed, and live fixed + RS leg.

Usage: funded_sizing.py FIXED_DIR SCRATCH_DIR
"""
from __future__ import annotations

import datetime as dt
import random
import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge  # noqa: E402
from rescore_all import rvol  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from final_lifecycle import lad, flat  # noqa: E402
from book_after_fix import parts, to_usd  # noqa: E402
from score_live_spec import parse as parse_ls  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS  # noqa: E402
from rs_book import pts as rs_pts  # noqa: E402

EVAL_DAYS, EVAL_COST, PAYOUT = 11, 180.0, 1800.0


def life(f1, rp, horizon=504, trials=6000, seed=3):
    rnd = random.Random(seed)
    M = min(len(f1), len(rp))
    tot = []
    for _ in range(trials):
        t0, t, stage, cash = rnd.randrange(M), EVAL_DAYS, "f1", -EVAL_COST
        while t < horizon:
            i = (t0 + t) % M
            o, d = (f1 if stage == "f1" else rp)[i]
            t += d if stage == "f1" else max(d, 5)
            if o == "pass":
                cash += PAYOUT
                stage = "rp"
            elif o == "bust":
                cash -= EVAL_COST
                t += EVAL_DAYS
                stage = "f1"
        tot.append(cash)
    return st.mean(tot)


def main():
    fixed, sp = sys.argv[1], sys.argv[2]
    reg = rvol()
    orb, _, _, _ = parts(fixed, reg)
    T = parse_ls([f"{sp}/LSVWAP_tags.txt", f"{sp}/LSNOISE_tags.txt"])
    leg = lambda k, tag: [Trade(t["date"], t["pts"], tag) for t in T[k] if 0 < t["rv"] < 0.30]
    sig = first_signals(parse_mf(f"{sp}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                        (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    rs = [Trade(d, rs_pts(r, s, LEVELS.index(125), LEVELS.index(125)), "RS") for d, (r, s) in sig.items() if reg.get(d, 9.0) < 0.30]
    base = merge(merge(to_usd(orb), to_usd(leg("B5", "VG"))), to_usd(leg("NS", "Z")))
    books = {"live fixed": base, "live fixed + RS": merge(base, to_usd(rs))}
    sizers = {f"lad K{a}/{b}": (lad(a, 4, 75), lad(b, 4, 75)) for a in (300, 400, 500, 700) for b in (250, 400, 500, 700)}
    sizers["flat 2"] = (flat(2, 75), flat(2, 75))
    sizers["flat 3"] = (flat(3, 75), flat(3, 75))
    for bn, ts in books.items():
        ts = [t for t in ts if dt.date.fromisoformat(t.date).weekday() != 2 or t.strat in ("Z", "RS")]
        res = {}
        for lab, lo, hi in (("a", "0", "2022"), ("b", "2022", "9")):
            part = [t for t in ts if lo <= t.date < hi]
            days = calendar_days(part, sorted(set(t.date for t in part)))
            for sn, (s1, s2) in sizers.items():
                f1 = outcomes(days, s1, window=300, start_pnl=0.0, target=4000.0, consistency=False)
                rp = outcomes(days, s2, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
                res.setdefault(sn, {})[lab] = life(f1, rp)
        best = max(res, key=lambda k: res[k]["a"])
        print(f"== {bn}   (mean 24-month cash per account, 2018-21 | 2022-25)")
        for sn, v in sorted(res.items(), key=lambda kv: -kv[1]["a"]):
            print(f"   {sn:<14} ${v['a']:8,.0f} | ${v['b']:8,.0f}{'   <- chosen on 2018-21' if sn == best else ''}")


if __name__ == "__main__":
    main()
