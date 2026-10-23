"""Score the live-spec exports (LSVWAP / LSNOISE tags): the indicators' rules as
traded, against the research exports the book was built on.

Costs per trade in NQ points per MNQ: 0.5 ($1 round trip) + 0.25 entry
slippage + 0.25 more when the exit is a stop. Vol gate: skip days whose
prior-day 20d realised vol >= 0.30 (as the indicators do); 'gate off' shown too.

Usage: score_live_spec.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys
from collections import defaultdict

NAMES = {"P5": "Lucid 2 on a 5-min chart (VWAP cross)", "P1": "Lucid 2 on a 1-min chart (VWAP cross)",
         "B5": "research band 0.20% (first trade only)", "N0": "Lucid 6 noise, published",
         "NS": "Lucid 6 noise, 0.50% hard stop"}


def parse(paths):
    out = defaultdict(list)
    for p in paths:
        try:
            fh = open(p)
        except FileNotFoundError:
            continue
        for raw in fh:
            f = raw.strip().split(",")
            if f[0] != "L" or len(f) < 10:
                continue
            d, e, x = int(f[3]), float(f[5]), float(f[7])
            cost = 0.75 + (0.25 if f[8] in ("SL", "STOP") else 0.0)
            out[f[1]].append({"date": f"{f[2][:4]}-{f[2][4:6]}-{f[2][6:]}", "pts": d * (x - e) - cost,
                              "why": f[8], "rv": int(f[9]) / 1000.0, "ehm": int(f[4]), "xhm": int(f[6])})
    return out


def line(v):
    if len(v) < 3:
        return f"n {len(v)}"
    sd = st.pstdev(v)
    return (f"{st.mean(v):+6.2f} pt t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f} n{len(v):>5} "
            f"WR {sum(x > 0 for x in v) / len(v) * 100:3.0f}%")


def main():
    sp = sys.argv[1]
    T = parse([f"{sp}/LSVWAP_tags.txt", f"{sp}/LSNOISE_tags.txt"])
    for k in ("P5", "P1", "B5", "N0", "NS"):
        if k not in T:
            continue
        ts = T[k]
        print(f"== {k}: {NAMES[k]}")
        for gate in (True, False):
            g = [t for t in ts if not gate or 0 < t["rv"] < 0.30]
            a = [t["pts"] for t in g if t["date"] < "2022"]
            b = [t["pts"] for t in g if t["date"] >= "2022"]
            print(f"   gate {'on ' if gate else 'off'}  2018-21 {line(a)}  |  2022-25 {line(b)}")
        g = [t for t in ts if 0 < t["rv"] < 0.30]
        yrs = sorted({t["date"][:4] for t in g})
        print("   by year (gate on): " + "  ".join(f"{y} {sum(t['pts'] for t in g if t['date'][:4] == y):+.0f}" for y in yrs))
        why = defaultdict(int)
        for t in g:
            why[t["why"]] += 1
        print("   exits: " + ", ".join(f"{w} {n}" for w, n in sorted(why.items())))
        worst = sorted(t["pts"] for t in g)[:3]
        print(f"   worst trades: {', '.join(f'{x:.0f}' for x in worst)}\n")


if __name__ == "__main__":
    main()
