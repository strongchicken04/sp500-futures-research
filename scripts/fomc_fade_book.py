"""Add the FOMC press-conference fade to the NQ + Dow book.

The fade: at 14:35 ET on an FOMC day, trade against the 14:30-14:35 candle,
stop at its far extreme + 1 tick + 0.25 x its range, exit at 15:35. FOMC is
always a Wednesday and the rest of the book skips Wednesday, so nothing
overlaps. Sized as N MNQ per book unit; costs as in real_costs.py.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge, load_tags  # noqa: E402
from rescore_all import load_components, rvol, book  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from final_lifecycle import staged, lad, stage_line  # noqa: E402
from score_news import parse, outcome  # noqa: E402

COST = 1.0   # $ per micro round trip: $0.50 commission + 1 tick


def main():
    sp = sys.argv[1]
    reg = rvol()
    c, _ = load_components(sp)
    nq = [Trade(t.date, t.points - COST, t.strat) for t in book(c, reg, mnq=1)]
    ym = [Trade(t.date, (t.points * 0.5 - COST) * 2, "YM")
          for t in load_tags(f"{sp}/XYM_tags.txt", fmt="s1") if reg.get(t.date, 9.0) < 0.30]
    base = merge(nq, ym)
    ev, _ = parse([f"{sp}/NEWSNQ_tags.txt"])
    fomc = [e for e in ev if e["kind"] == "N" and e["fomc"] and e["s"] == 870 and e["tf"] == 5]
    fd = [(f"{e['ymd'][:4]}-{e['ymd'][4:6]}-{e['ymd'][6:]}", outcome(e, None, 2, 3)[0]) for e in fomc]
    for n in (0, 1, 2, 3):
        ts = merge(base, [Trade(d, (p * 2.0 - COST) * n, "FOMC") for d, p in fd]) if n else base
        d = calendar_days(ts, sorted(set(t.date for t in ts)))
        T = staged(d, lad(700, 4, 75), lad(800, 4, 75), lad(700, 4, 75))
        stage_line(f"NQ+MYM + FOMC fade {n} MNQ/unit", T)
        r = sim_groups([(5, T)])
        print(f"      5 accounts 24m: p10 {r['p10']:,.0f}  median {r['p50']:,.0f}  p90 {r['p90']:,.0f}")


if __name__ == "__main__":
    main()
