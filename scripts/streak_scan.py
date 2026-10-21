"""Is there any signal that wins ~94% of the time at reward:risk 1:3.3?

That is what a 75% chance of five straight wins needs (0.944^5 = 0.75).
Every entry type x one or two context filters x direction x every recorded
bracket with stop/target between 3.0 and 3.4 is scanned. Ranked on the
2018-2021 win rate (at least 40 trades), the same rule's 2022-2025 win rate
is printed next to it, with the random-walk rate stop/(target+stop).
"""
from __future__ import annotations

import itertools
import sys

sys.path.insert(0, "scripts")
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse, add_daily, FILTERS, LEVELS  # noqa: E402

PAIRS = [(ti, si) for ti in range(len(LEVELS)) for si in range(len(LEVELS))
         if 3.0 <= LEVELS[si] / LEVELS[ti] <= 3.4]


def win(r, side, ti, si):
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    if s >= 0 and (t < 0 or s <= t):
        return False
    if t >= 0:
        return True
    return side * r["eod"] / r["e"] * 1e4 > 1.0     # flat at 15:55 in profit after costs


def main():
    sp = sys.argv[1]
    rows = parse([f"{sp}/{x}_tags.txt" for x in ("CBA", "CBB", "CBC", "CBD", "CBE")])
    add_daily(rows)
    reg = rvol()
    rows = [r for r in rows if reg.get(r["date"], 9.0) < 0.30]
    types = sorted({r["type"] for r in rows})
    fl = [f for f in FILTERS if f != "all"]
    combos = [("all",)] + [(f,) for f in fl] + list(itertools.combinations(fl, 2))
    out = []
    for typ in types:
        rs = [r for r in rows if r["type"] == typ]
        for cb in combos:
            sel = [r for r in rs if all(FILTERS[f](r) for f in cb)]
            a = [r for r in sel if r["date"] < "2022"]
            b = [r for r in sel if r["date"] >= "2022"]
            if len(a) < 40 or len(b) < 20:
                continue
            for side in (1, -1):
                for ti, si in PAIRS:
                    wa = sum(win(r, side, ti, si) for r in a) / len(a)
                    wb = sum(win(r, side, ti, si) for r in b) / len(b)
                    out.append((wa, wb, typ, " & ".join(cb), side, LEVELS[ti], LEVELS[si], len(a), len(b)))
    out.sort(key=lambda x: -x[0])
    print(f"{len(out)} rules scanned at reward:risk 1:3.0-1:3.4 (random-walk win rate 75-77%)\n")
    print(f"{'WR 18-21':>8} {'WR 22-25':>8} {'p^5 OOS':>8}  rule")
    for wa, wb, typ, cb, side, tp, sl, na, nb in out[:25]:
        print(f"{wa*100:7.1f}% {wb*100:7.1f}% {wb**5*100:7.1f}%  {typ} {'LONG' if side == 1 else 'SHORT'} [{cb}] TP {tp}bp SL {sl}bp  n {na}/{nb}")
    print(f"\nrules with >= 90% in 2018-21: {sum(1 for x in out if x[0] >= 0.90)};"
          f" of those also >= 90% in 2022-25: {sum(1 for x in out if x[0] >= 0.90 and x[1] >= 0.90)}")
    print(f"rules with >= 85% in BOTH halves: {sum(1 for x in out if x[0] >= 0.85 and x[1] >= 0.85)}")
    best_both = sorted(out, key=lambda x: -min(x[0], x[1]))[:10]
    print("\nbest by the weaker of the two halves:")
    for wa, wb, typ, cb, side, tp, sl, na, nb in best_both:
        print(f"   {wa*100:5.1f}% / {wb*100:5.1f}%  p^5 {min(wa, wb)**5*100:4.1f}%  {typ} {'LONG' if side == 1 else 'SHORT'} [{cb}] TP {tp} SL {sl}  n {na}/{nb} ({(na+nb)/8:.0f}/yr)")


if __name__ == "__main__":
    main()
