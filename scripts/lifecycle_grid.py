"""Unit-size grid (evaluation / first funded / repeat) for NQ, NQ+RTY and
NQ+RTY+GC in one account, five accounts over 24 months."""
import sys
sys.path.insert(0, "scripts")
from prop_sim import merge, load_tags
from rescore_all import load_components, rvol, book, dollars
from mixed_accounts import calendar_days, sim_groups
from final_lifecycle import staged, flat
SP = sys.argv[1]
reg = rvol(); c, _ = load_components(SP)
nq = book(c, reg, mnq=1)
rty = [t for t in load_tags(f"{SP}/XRTY_tags.txt", fmt="s1") if reg.get(t.date, 9.0) < 0.30]
gc = dollars(c["gc"], 10.0)
units = {
    "NQ+RTY": merge(nq, dollars(rty, 5.0 * 2.33)),
    "NQ+RTY+GC": merge(nq, dollars(rty, 5.0 * 2.33), dollars(gc, 10.0 * 2.33)),
    "NQ+GC": merge(nq, dollars(gc, 10.0 * 2.33)),
}
cal = sorted(set(t.date for u in units.values() for t in u))
print(f"{'unit':<11} {'ev/f1/rp':<9} {'ev p/b/d':>14} {'f1 p/b/d':>14} {'rp p/b/d':>14} | {'p10':>8} {'median':>8} {'p90':>8}")
for un, ts in units.items():
    d = calendar_days(ts, cal)
    for e, f, r in ((2, 2, 2), (3, 2, 3), (3, 3, 3), (4, 2, 3), (3, 2, 4), (4, 3, 4)):
        tb = staged(d, flat(e, 75), flat(f, 75), flat(r, 75))
        cells = []
        for s in ("ev", "f1", "rp"):
            o = tb[s]; p = sum(1 for x, _ in o if x == "pass") / len(o) * 100
            b = sum(1 for x, _ in o if x == "bust") / len(o) * 100
            md = sorted(dd for x, dd in o if x == "pass")
            cells.append(f"{p:5.1f}/{b:4.1f}/{md[len(md)//2] if md else 0:3d}")
        res = sim_groups([(5, tb)], trials=12000)
        print(f"{un:<11} {e}/{f}/{r}{'':<4} {cells[0]:>14} {cells[1]:>14} {cells[2]:>14} | {res['p10']:8,.0f} {res['p50']:8,.0f} {res['p90']:8,.0f}")
