"""The book after the trailed-stop fill fix.

Compares, through the evaluation and the 24-month five-account lifecycle:
  old      ORB (as previously exported) + VWAP band + Dow ORB + noise momentum
  fixed    the same with both ORBs re-exported with stops filled at the bar
           open when the trailed stop sat above the market
  no ORB   VWAP band + noise momentum only
Costs $1 per micro per trade. Sizing by drawdown room as in the plan.

Usage: book_after_fix.py OLD_DIR FIXED_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge, load_tags  # noqa: E402
from rescore_all import load_components, rvol, book  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from final_lifecycle import staged, lad, flat, stage_line  # noqa: E402
from score_noise_tod import parse as parse_noise, z_result  # noqa: E402


def parts(sp, reg):
    c, _ = load_components(sp)
    orb = [Trade(t.date, t.points - 0.5, "S1") for t in c["s1"] if reg.get(t.date, 9.0) < 0.30]
    vg = [Trade(t.date, t.points - 0.5, "VG") for t in c["vg"] if reg.get(t.date, 9.0) < 0.30]
    ym = [Trade(t.date, (t.points * 0.5 - 1.0) * 2 / 2.0, "YM")
          for t in load_tags(f"{sp}/XYM_tags.txt", fmt="s1") if reg.get(t.date, 9.0) < 0.30]
    Z, _ = parse_noise(f"{sp}/NOISETOD_tags.txt")
    nz = [Trade(f"{z['ymd'][:4]}-{z['ymd'][4:6]}-{z['ymd'][6:]}", z_result(z), "Z") for z in Z]
    return orb, vg, ym, nz        # NQ points per MNQ (YM converted to MNQ-equivalent points)


def to_usd(ts, mult=2.0):
    return [Trade(t.date, t.points * mult, t.strat) for t in ts]


def main():
    old, fixed = sys.argv[1], sys.argv[2]
    reg = rvol()
    import datetime as dt
    books = {}
    for lab, sp in (("old", old), ("fixed", fixed)):
        orb, vg, ym, nz = parts(sp, reg)
        books[lab] = merge(merge(merge(to_usd(orb), to_usd(vg)), to_usd(ym)), to_usd(nz))
        if lab == "fixed":
            books["no ORB"] = merge(to_usd(vg), to_usd(nz))
            books["fixed, no Dow"] = merge(merge(to_usd(orb), to_usd(vg)), to_usd(nz))
    for lab, ts in books.items():
        ts = [t for t in ts if dt.date.fromisoformat(t.date).weekday() != 2 or t.strat == "Z"]
        cal = sorted(set(t.date for t in ts))
        d = calendar_days(ts, cal)
        for K, sizer in (("ladder K400/500/400", (lad(400, 4, 75), lad(500, 4, 75), lad(400, 4, 75))),
                         ("flat 2/2/2", (flat(2, 75),) * 3), ("flat 3/2/3", (flat(3, 75), flat(2, 75), flat(3, 75)))):
            T = staged(d, *sizer)
            stage_line(f"{lab:<14} {K}", T)
        r = sim_groups([(5, staged(d, lad(400, 4, 75), lad(500, 4, 75), lad(400, 4, 75)))])
        print(f"      5 accounts 24m (ladder): p10 {r['p10']:,.0f}  median {r['p50']:,.0f}  p90 {r['p90']:,.0f}\n")


if __name__ == "__main__":
    main()
