"""Does the weak ORB leg still help at the recommended funded size (flat 3)?
Books with and without ORB, with and without the RS leg; flat 3 and ladder
K300/250. Same model as funded_sizing (sprint evaluations, mean 24-month cash
per account, 2018-21 | 2022-25). The simulated day stop is $75 + $75 x units
(flat 3: stop trading for the day at -$300), as in all lifecycle sims.

Usage: funded_orb_check.py FIXED_DIR SCRATCH_DIR
"""
from __future__ import annotations

import datetime as dt
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
from funded_sizing import life  # noqa: E402


def main():
    fixed, sp = sys.argv[1], sys.argv[2]
    reg = rvol()
    orb, _, _, _ = parts(fixed, reg)
    T = parse_ls([f"{sp}/LSVWAP_tags.txt", f"{sp}/LSNOISE_tags.txt"])
    leg = lambda k, tag: [Trade(t["date"], t["pts"], tag) for t in T[k] if 0 < t["rv"] < 0.30]
    sig = first_signals(parse_mf(f"{sp}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                        (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    rs = to_usd([Trade(d, rs_pts(r, s, LEVELS.index(125), LEVELS.index(125)), "RS") for d, (r, s) in sig.items() if reg.get(d, 9.0) < 0.30])
    core = merge(to_usd(leg("B5", "VG")), to_usd(leg("NS", "Z")))
    books = {"VWAP + noise + ORB": merge(core, to_usd(orb)), "VWAP + noise": core,
             "VWAP + noise + ORB + RS": merge(merge(core, to_usd(orb)), rs), "VWAP + noise + RS": merge(core, rs)}
    sizers = {"flat 3": (flat(3, 75), flat(3, 75)), "lad K300/250": (lad(300, 4, 75), lad(250, 4, 75))}
    print(f"{'book':<26} {'sizing':<13} 2018-21 | 2022-25 (mean 24-month cash per account)")
    for bn, ts in books.items():
        ts = [t for t in ts if dt.date.fromisoformat(t.date).weekday() != 2 or t.strat in ("Z", "RS")]
        for sn, (s1, s2) in sizers.items():
            out = []
            for lo, hi in (("0", "2022"), ("2022", "9")):
                part = [t for t in ts if lo <= t.date < hi]
                days = calendar_days(part, sorted(set(t.date for t in part)))
                f1 = outcomes(days, s1, window=300, start_pnl=0.0, target=4000.0, consistency=False)
                rp = outcomes(days, s2, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
                out.append(life(f1, rp))
            print(f"{bn:<26} {sn:<13} ${out[0]:8,.0f} | ${out[1]:8,.0f}")


if __name__ == "__main__":
    main()
