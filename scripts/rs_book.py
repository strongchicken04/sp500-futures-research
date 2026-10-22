"""RS signal as a funded-book leg (queue item 2).

Signal fixed in advance (the live RS sprint rule): NQ-ES return since the open
> 0.15% and price above VWAP (mirror short), first of 10:00/11:00/13:00/14:30.
Exit: a bracket chosen ONLY on 2018-2021 by a smoothed score (mean over the
3x3 neighbourhood of target/stop cells), then 2022-2025 reported untouched.
Points per MNQ net of 0.75 pt (+0.25 on stops). Then added at 1 MNQ per unit
to the fixed live book (book_live_spec 'live fixed') to see if it helps.
(Trailing exits need a path export; not tested here.)

Usage: rs_book.py FIXED_DIR SCRATCH_DIR
"""
from __future__ import annotations

import datetime as dt
import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge  # noqa: E402
from rescore_all import rvol  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from final_lifecycle import staged, lad, stage_line  # noqa: E402
from book_after_fix import parts, to_usd  # noqa: E402
from score_live_spec import parse as parse_ls  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS  # noqa: E402


def pts(r, side, ti, si):
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    if s >= 0 and (t < 0 or s <= t):
        return -LEVELS[si] / 1e4 * r["e"] - 1.0
    if t >= 0:
        return LEVELS[ti] / 1e4 * r["e"] - 0.75
    return max(-LEVELS[si] / 1e4 * r["e"], side * r["eod"]) - 0.75


def tstat(v):
    sd = st.pstdev(v)
    return st.mean(v) / sd * math.sqrt(len(v)) if sd else 0.0


def main():
    fixed, sp = sys.argv[1], sys.argv[2]
    rows = parse_mf(f"{sp}/MFEAT_tags.txt")
    sig = first_signals(rows, lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                        (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    n = len(LEVELS)
    mean = {}
    for ti in range(n):
        for si in range(n):
            a = [pts(r, s, ti, si) for d, (r, s) in sig.items() if d < "2022"]
            mean[(ti, si)] = st.mean(a)
    smooth = {}
    for ti in range(1, n - 1):
        for si in range(1, n - 1):
            smooth[(ti, si)] = st.mean(mean[(ti + a, si + b)] for a in (-1, 0, 1) for b in (-1, 0, 1))
    best = max(smooth, key=smooth.get)
    ti, si = best
    print(f"{len(sig)} RS signals; bracket chosen on 2018-21: target {LEVELS[ti]} bp / stop {LEVELS[si]} bp "
          f"(smoothed {smooth[best]:+.2f} pt)\n")
    for lab, lo, hi in (("2018-21", "0", "2022"), ("2022-25", "2022", "9")):
        v = [pts(r, s, ti, si) for d, (r, s) in sig.items() if lo <= d < hi]
        b = [st.mean(pts(r, s, ti + x, si + y) for x in (-1, 0, 1) for y in (-1, 0, 1)) for d, (r, s) in sig.items() if lo <= d < hi]
        print(f"  {lab}: cell {st.mean(v):+6.2f} pt t{tstat(v):+4.1f} WR {sum(x > 0 for x in v) / len(v) * 100:3.0f}%   "
              f"neighbourhood {st.mean(b):+6.2f} pt t{tstat(b):+4.1f}   n {len(v)}")
    years = sorted({d[:4] for d in sig})
    print("  by year: " + "  ".join(f"{y} {st.mean([pts(r, s, ti, si) for d, (r, s) in sig.items() if d[:4] == y]):+.1f}" for y in years))

    reg = rvol()
    orb, _, _, _ = parts(fixed, reg)
    T = parse_ls([f"{sp}/LSVWAP_tags.txt", f"{sp}/LSNOISE_tags.txt"])
    leg = lambda k, tag: [Trade(t["date"], t["pts"], tag) for t in T[k] if 0 < t["rv"] < 0.30]
    base = merge(merge(to_usd(orb), to_usd(leg("B5", "VG"))), to_usd(leg("NS", "Z")))
    rs = [Trade(d, pts(r, s, ti, si), "RS") for d, (r, s) in sig.items() if reg.get(d, 9.0) < 0.30]
    print()
    for lab, ts in (("live fixed book", base), ("+ RS leg 1 MNQ/unit", merge(base, to_usd(rs)))):
        ts = [t for t in ts if dt.date.fromisoformat(t.date).weekday() != 2 or t.strat in ("Z", "RS")]
        cal = sorted(set(t.date for t in ts))
        T3 = staged(calendar_days(ts, cal), lad(400, 4, 75), lad(500, 4, 75), lad(400, 4, 75))
        stage_line(f"{lab:<22} ladder 400/500/400", T3)
        r = sim_groups([(5, T3)])
        print(f"      5 accounts 24m: p10 {r['p10']:,.0f}  median {r['p50']:,.0f}  p90 {r['p90']:,.0f}")


if __name__ == "__main__":
    main()
