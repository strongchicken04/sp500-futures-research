"""Does the overnight-level fade survive honest fills?

Reads the OC tags from on_fade_fill_test.py, which evaluate every level under
three fill rules side by side:

  T  fill at the level on first touch      (the original, optimistic)
  X  fill only once price trades 1 tick through the level
  C  fill at the close of the first touching 1-minute bar

If the edge lives mostly in exact touches that reverse, it will show up in T
and vanish in X and C. Only X and C are tradeable assumptions.
"""
from __future__ import annotations

import csv
import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, TIERS  # noqa: E402
from score_multi import load_book  # noqa: E402

COST = 0.75
SPLIT = "2022-01-01"
BRK = {"10": 0, "15": 1, "20": 2}
MODES = {"T": 0, "X": 1, "C": 2}


def parse(path):
    rows = []
    with open(path) as fh:
        for line in fh:
            p = line.strip().split(",")
            if len(p) < 23 or p[0] != "OC":
                continue
            ds = p[1]
            rec = {"date": f"{ds[0:4]}-{ds[4:6]}-{ds[6:8]}", "leg": p[2],
                   "dir": int(p[3]), "rng": float(p[4]), "m": {}}
            for name, k in MODES.items():
                base = 5 + 6 * k
                rec["m"][name] = {
                    "fmin": int(p[base]), "e": float(p[base + 1]),
                    "r": p[base + 2:base + 5], "eod": float(p[base + 5]),
                }
            rows.append(rec)
    return rows


def trades(rows, mode, b, legs="HLM", min_range=65.0, cost=COST):
    out = []
    bi = BRK[b]
    B = float(b)
    for r in sorted(rows, key=lambda x: (x["date"], x["m"][mode]["fmin"])):
        if r["leg"] not in legs or r["rng"] < min_range:
            continue
        m = r["m"][mode]
        if m["fmin"] < 0:
            continue
        res = m["r"][bi]
        if res == "T":
            p = B
        elif res == "S":
            p = -B
        elif res == "E":
            p = m["eod"]
        else:
            continue
        out.append(Trade(r["date"], p - cost, "ONF" + r["leg"]))
    return out


def main() -> None:
    sp, path = sys.argv[1], sys.argv[2]
    rows = parse(path)
    print(f"{len(rows)} level-days parsed")
    for mode in MODES:
        filled = sum(1 for r in rows if r["m"][mode]["fmin"] >= 0)
        print(f"   mode {mode}: {filled} fills")
    reg = {}
    with open("results/nq_panel_real.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                reg[r["date"]] = float(r["rvol20"])
            except (ValueError, KeyError):
                continue

    def gate(ts, c=0.30):
        return [t for t in ts if reg.get(t.date, 9.0) < c]

    book = load_book(sp, gate)
    orig = list(TIERS)
    print("\nper-trade expectancy after 0.75 pt cost, all legs, range >= 65")
    print(f"{'mode':<5} {'B':>3} {'n':>5} {'WR':>6} {'avg':>7} {'IS':>7} {'OOS':>7}")
    for mode in MODES:
        for b in BRK:
            tr = gate(trades(rows, mode, b))
            v = [t.points for t in tr]
            if not v:
                continue
            w = [x for x in v if x > 0]
            i = [t.points for t in tr if t.date < SPLIT]
            o = [t.points for t in tr if t.date >= SPLIT]
            print(f"{mode:<5} {b:>3} {len(v):5d} {len(w)/len(v)*100:5.1f}% "
                  f"{st.mean(v):+7.2f} {st.mean(i):+7.2f} {st.mean(o):+7.2f}")
    for leg in "HLM":
        print(f"\nleg {leg} only, B=15:")
        for mode in MODES:
            tr = gate(trades(rows, mode, "15", legs=leg))
            v = [t.points for t in tr]
            if v:
                print(f"   {mode}: n={len(v):4d} avg {st.mean(v):+6.2f}")

    for sn, tier in (("3 MNQ", (0.0, 6.0, 300.0)), ("2 MNQ", (0.0, 4.0, 240.0))):
        TIERS.clear()
        TIERS.append(tier)
        b0 = simulate(book, window=250, day_stop_profit=1450.0)
        bo = simulate([t for t in book if t.date >= SPLIT], window=250,
                      day_stop_profit=1450.0)
        print(f"\n===== {sn}, 250d =====  book {b0.pass_rate:.1f}/"
              f"{b0.bust_rate:.1f}/{b0.median_days:.0f}  OOS {bo.pass_rate:.1f}/"
              f"{bo.bust_rate:.1f}")
        for mode in MODES:
            for b in ("15", "20"):
                tr = gate(trades(rows, mode, b))
                al = simulate(tr, window=250, day_stop_profit=1450.0)
                f = simulate(merge(book, tr), window=250, day_stop_profit=1450.0)
                o = simulate(merge([t for t in book if t.date >= SPLIT],
                                   [t for t in tr if t.date >= SPLIT]),
                             window=250, day_stop_profit=1450.0)
                print(f"  {mode} B={b}  alone {al.pass_rate:5.1f}/{al.bust_rate:4.1f}/"
                      f"{al.median_days:3.0f}   +book {f.pass_rate:5.1f}/"
                      f"{f.bust_rate:4.1f}/{f.median_days:3.0f}   "
                      f"OOS {o.pass_rate:5.1f}/{o.bust_rate:4.1f}")
    TIERS.clear()
    TIERS.extend(orig)


if __name__ == "__main__":
    main()
