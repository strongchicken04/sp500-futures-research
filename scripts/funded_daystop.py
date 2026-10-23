"""Funded day stop at flat 3 (queue item, pre-specified levels): stop trading
for the day once the day's P&L reaches -$150, -$300 (sims' default), -$600, or
never. Books: live fixed and live fixed + RS. Same model as funded_sizing.

Usage: funded_daystop.py FIXED_DIR SCRATCH_DIR
"""
from __future__ import annotations

import datetime as dt
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge  # noqa: E402
from rescore_all import rvol  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
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
    base = merge(merge(to_usd(orb), to_usd(leg("B5", "VG"))), to_usd(leg("NS", "Z")))
    print(f"{'book':<18} {'day stop':>9}  2018-21 | 2022-25 (mean 24-month cash per account, flat 3)")
    for bn, ts in (("live fixed", base), ("live fixed + RS", merge(base, rs))):
        ts = [t for t in ts if dt.date.fromisoformat(t.date).weekday() != 2 or t.strat in ("Z", "RS")]
        for ds in (150, 300, 600, 10 ** 9):
            sz = lambda room, ds=ds: (3.0, float(ds))
            out = []
            for lo, hi in (("0", "2022"), ("2022", "9")):
                part = [t for t in ts if lo <= t.date < hi]
                days = calendar_days(part, sorted(set(t.date for t in part)))
                f1 = outcomes(days, sz, window=300, start_pnl=0.0, target=4000.0, consistency=False)
                rp = outcomes(days, sz, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
                out.append(life(f1, rp))
            lab = "none" if ds > 10 ** 6 else f"-${ds}"
            print(f"{bn:<18} {lab:>9}  ${out[0]:8,.0f} | ${out[1]:8,.0f}")


if __name__ == "__main__":
    main()
