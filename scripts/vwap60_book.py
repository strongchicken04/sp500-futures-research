"""Add the wide VWAP band (60 bp, trade with the break, target 15% ATR, stop
25% ATR) to the book that already holds ORB, the 20 bp VWAP band, the Dow ORB
and noise-area momentum. One trade a day, the first 5-minute close beyond
VWAP +/- 60 bp after 09:40; size in MNQ per book unit, $1 cost per MNQ.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge, load_tags  # noqa: E402
from rescore_all import load_components, rvol, book  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from final_lifecycle import staged, lad, stage_line  # noqa: E402
from score_vwap_atr import parse_band, atr_table, result  # noqa: E402
from score_noise_tod import parse as parse_noise, z_result  # noqa: E402


def main():
    sp = sys.argv[1]
    reg = rvol()
    c, _ = load_components(sp)
    nq = [Trade(t.date, t.points - 1.0, t.strat) for t in book(c, reg, mnq=1)]
    ym = [Trade(t.date, (t.points * 0.5 - 1.0) * 2, "YM")
          for t in load_tags(f"{sp}/XYM_tags.txt", fmt="s1") if reg.get(t.date, 9.0) < 0.30]
    Z, _ = parse_noise(f"{sp}/NOISETOD_tags.txt")
    zt = [Trade(f"{z['ymd'][:4]}-{z['ymd'][4:6]}-{z['ymd'][6:]}", z_result(z) * 2.0, "Z") for z in Z]
    base = merge(merge(nq, ym), zt)
    atr = atr_table(f"{sp}/NOISETOD_tags.txt")
    first = {}
    for r in parse_band([f"{sp}/VBB_tags.txt"]):
        if r["type"] in ("U60", "D60") and r["date"] in atr and reg.get(r["date"], 9.0) < 0.30:
            if r["date"] not in first or r["hm"] < first[r["date"]]["hm"]:
                first[r["date"]] = r
    v60 = []
    for d, r in first.items():
        x = result(r, 1 if r["type"][0] == "U" else -1, 0.15, 0.25, atr[d])
        if x is not None:
            v60.append((d, x))          # points per MNQ, cost already taken
    cal = sorted(set(t.date for t in base) | set(d for d, _ in v60))
    for n in (0, 1, 2):
        ts = merge(base, [Trade(d, x * 2.0 * n, "V60") for d, x in v60]) if n else base
        T = staged(calendar_days(ts, cal), lad(700, 4, 75), lad(800, 4, 75), lad(700, 4, 75))
        stage_line(f"book+noise + VWAP60 {n} MNQ/unit", T)
        r = sim_groups([(5, T)])
        print(f"      5 accounts 24m: p10 {r['p10']:,.0f}  median {r['p50']:,.0f}  p90 {r['p90']:,.0f}")


if __name__ == "__main__":
    main()
