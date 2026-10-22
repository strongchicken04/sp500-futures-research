"""Compare book variants with a stable metric. sim_groups' median is lumpy
(copied accounts move in steps of 5 x $1,800), so this reports the MEAN 24-month
cash per account (fees and payouts) with its standard error, the share of
start dates without any payout, and the stage pass rates.
Variants: research book, live now (old Lucid 2), live fixed, + RS leg,
+ ONL 1 / 2 MNQ, + RS + ONL 2.

Usage: book_compare.py FIXED_DIR SCRATCH_DIR
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
from final_lifecycle import staged, lad  # noqa: E402
from book_after_fix import parts, to_usd  # noqa: E402
from score_live_spec import parse as parse_ls  # noqa: E402
from score_cond_bracket import parse, add_daily  # noqa: E402
from onl_gapup_book import pts as onl_pts  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS  # noqa: E402
from rs_book import pts as rs_pts  # noqa: E402


def life(tb, horizon=504, trials=20000, fee=90.0, payout=1800.0, seed=7):
    rnd = random.Random(seed)
    M = len(tb["ev"])
    tot, none = [], 0
    for _ in range(trials):
        t0, t, stage, cash, paid = rnd.randrange(M), 0, "ev", 0.0, False
        while t < horizon:
            i = (t0 + t) % M
            o, d = tb[stage][i]
            if stage == "ev":
                t += d
                cash -= fee
                if o == "pass":
                    stage = "f1"
                elif o == "timeout":
                    t += 5
            elif stage == "f1":
                t += d
                if o == "pass":
                    cash += payout
                    paid = True
                    stage = "rp"
                elif o == "bust":
                    stage = "ev"
            else:
                t += max(d, 5)
                if o == "pass":
                    cash += payout
                    paid = True
                elif o == "bust":
                    stage = "ev"
        tot.append(cash)
        none += not paid
    return st.mean(tot), st.pstdev(tot) / len(tot) ** 0.5, none / trials * 100


def main():
    fixed, sp = sys.argv[1], sys.argv[2]
    reg = rvol()
    orb, vg, _, nz = parts(fixed, reg)
    T = parse_ls([f"{sp}/LSVWAP_tags.txt", f"{sp}/LSNOISE_tags.txt"])
    leg = lambda k, tag: [Trade(t["date"], t["pts"], tag) for t in T[k] if 0 < t["rv"] < 0.30]
    rows = parse([f"{sp}/CBC_tags.txt"])
    add_daily(rows)
    onl = [Trade(r["date"], onl_pts(r) - 0.75, "ONL") for r in rows
           if r["type"] == "ONL" and r["gap"] >= 0.0025 and reg.get(r["date"], 9.0) < 0.30]
    sig = first_signals(parse_mf(f"{sp}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                        (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    rs = [Trade(d, rs_pts(r, s, LEVELS.index(125), LEVELS.index(125)), "RS") for d, (r, s) in sig.items() if reg.get(d, 9.0) < 0.30]
    fixed_book = merge(merge(to_usd(orb), to_usd(leg("B5", "VG"))), to_usd(leg("NS", "Z")))
    x2 = lambda ts: [Trade(t.date, t.points * 2.0, t.strat) for t in ts]
    V = {
        "research book": merge(merge(to_usd(orb), to_usd(vg)), to_usd(nz)),
        "live now (old Lucid 2)": merge(merge(to_usd(orb), to_usd(leg("P5", "VG"))), to_usd(leg("N0", "Z"))),
        "live fixed": fixed_book,
        "live fixed + RS": merge(fixed_book, to_usd(rs)),
        "live fixed + ONL 1": merge(fixed_book, to_usd(onl)),
        "live fixed + ONL 2": merge(fixed_book, x2(to_usd(onl))),
        "live fixed + RS + ONL 2": merge(merge(fixed_book, to_usd(rs)), x2(to_usd(onl))),
    }
    print(f"{'variant':<26} {'eval pass':>9} {'f1 pass':>8} {'repeat':>7} | mean 24m cash per account (+-se, two seeds)   no payout")
    for lab, ts in V.items():
        ts = [t for t in ts if dt.date.fromisoformat(t.date).weekday() != 2 or t.strat in ("Z", "RS", "ONL")]
        cal = sorted(set(t.date for t in ts))
        tb = staged(calendar_days(ts, cal), lad(400, 4, 75), lad(500, 4, 75), lad(400, 4, 75))
        pr = [sum(1 for o, _ in tb[s] if o == "pass") / len(tb[s]) * 100 for s in ("ev", "f1", "rp")]
        m1, se1, n1 = life(tb, seed=7)
        m2, se2, _ = life(tb, seed=11)
        print(f"{lab:<26} {pr[0]:8.1f}% {pr[1]:7.1f}% {pr[2]:6.1f}% | ${m1:7,.0f} +-{se1:4,.0f}   ${m2:7,.0f} +-{se2:4,.0f}        {n1:4.1f}%")


if __name__ == "__main__":
    main()
