"""Overnight-low touch on a gap-up day, alone and added to the NQ + Dow book.

Rule: the session opens at least 0.25% above the prior 16:00 close; the first
RTH minute that trades down to the overnight low is bought at its close;
target +0.25% of price, stop -0.40%, otherwise flat at 15:55; volatility gate
on. Sized in MNQ per book unit, $1 cost per MNQ.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge, load_tags  # noqa: E402
from rescore_all import load_components, rvol, book  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from final_lifecycle import staged, lad, flat, stage_line  # noqa: E402
from score_cond_bracket import parse, add_daily, LEVELS  # noqa: E402

TI, SI = LEVELS.index(25), LEVELS.index(40)


def pts(r):
    t, s = r["up"][TI], r["dn"][SI]
    tp, sl = r["e"] * 0.0025, r["e"] * 0.0040
    if s >= 0 and (t < 0 or s <= t):
        return -sl
    if t >= 0:
        return tp
    return max(-sl, r["eod"])


def main():
    sp = sys.argv[1]
    reg = rvol()
    rows = parse([f"{sp}/CBC_tags.txt"])
    add_daily(rows)
    sel = [r for r in rows if r["type"] == "ONL" and r["gap"] >= 0.0025 and reg.get(r["date"], 9.0) < 0.30]
    onl = [(r["date"], pts(r)) for r in sel]
    c, _ = load_components(sp)
    nq = [Trade(t.date, t.points - 1.0, t.strat) for t in book(c, reg, mnq=1)]
    ym = [Trade(t.date, (t.points * 0.5 - 1.0) * 2, "YM")
          for t in load_tags(f"{sp}/XYM_tags.txt", fmt="s1") if reg.get(t.date, 9.0) < 0.30]
    base = merge(nq, ym)
    cal = sorted(set(t.date for t in base) | set(d for d, _ in onl))
    for n in (0, 1, 2, 3):
        ts = merge(base, [Trade(d, (p * 2.0 - 1.0) * n, "ONL") for d, p in onl]) if n else base
        T = staged(calendar_days(ts, cal), lad(700, 4, 75), lad(800, 4, 75), lad(700, 4, 75))
        stage_line(f"NQ+MYM + ONL gap-up {n} MNQ/unit", T)
        r = sim_groups([(5, T)])
        print(f"      5 accounts 24m: p10 {r['p10']:,.0f}  median {r['p50']:,.0f}  p90 {r['p90']:,.0f}")


if __name__ == "__main__":
    main()
