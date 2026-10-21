"""ORB 09:30-09:45 with fixed point brackets (default target 15 / stop 45).

Reads the ORB points exporter. For each type (ORB / ORS = first 5-minute close
beyond the opening range; ORBV / ORSV = also beyond VWAP) the first signal of
the day is traded with the bracket; a minute touching both counts as the stop.
Costs: $1 commission per MNQ plus one tick on entry and one on a stop.
Usage: score_orb_points.py SCRATCH_DIR [TP SL]
"""
from __future__ import annotations

import statistics as st
import sys
from collections import defaultdict

LEVELS = [5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100]


def parse(path):
    n = len(LEVELS)
    rows = []
    for raw in open(path):
        f = raw.strip().split(",")
        if f[0] != "V" or len(f) < 14 + 2 * n + 1:
            continue
        rows.append({"ymd": f[1], "type": f[2], "hm": int(f[3]),
                     "up": [int(x) for x in f[14:14 + n]], "dn": [int(x) for x in f[14 + n:14 + 2 * n]],
                     "eod": float(f[14 + 2 * n])})
    return rows


def res(r, tp, sl):
    side = 1 if r["type"].startswith("ORB") else -1
    ti, si = LEVELS.index(tp), LEVELS.index(sl)
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    if s >= 0 and (t < 0 or s <= t):
        return -sl - 0.25 - 0.75
    if t >= 0:
        return tp - 0.75
    return max(-sl - 0.25, side * r["eod"] - 0.25) - 0.75


def main():
    sp = sys.argv[1]
    tp, sl = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (15.0, 45.0)
    rows = parse(f"{sp}/ORBPTS_tags.txt")
    print(f"TP {tp:g} / SL {sl:g} points, random-walk win rate {sl/(tp+sl)*100:.0f}%")
    for typ, lab in (("ORBV", "ORB long (above OR high and VWAP) - the book's entry"),
                     ("ORB", "ORB long, no VWAP condition"),
                     ("ORSV", "ORB short (below OR low and VWAP)"),
                     ("ORS", "ORB short, no VWAP condition")):
        rs = [r for r in rows if r["type"] == typ]
        yr = defaultdict(list)
        for r in rs:
            yr[r["ymd"][:4]].append(res(r, tp, sl))
        v = [x for vv in yr.values() for x in vv]
        p = sum(1 for x in v if x > 0) / len(v)
        a = [x for y, vv in yr.items() if y < "2022" for x in vv]
        b = [x for y, vv in yr.items() if y >= "2022" for x in vv]
        print(f"\n{lab}: {len(v)} trades ({len(v)/8:.0f}/yr)")
        print(f"   WR {p*100:.1f}%  (2018-21 {sum(x>0 for x in a)/len(a)*100:.1f}%, 2022-25 {sum(x>0 for x in b)/len(b)*100:.1f}%)"
              f"   {st.mean(v):+.2f} pt/trade after costs")
        print("   by year:", {y: round(sum(x > 0 for x in vv) / len(vv) * 100) for y, vv in sorted(yr.items())})
        print(f"   streaks: 2x {p**2*100:.0f}%  3x {p**3*100:.0f}%  5x {p**5*100:.0f}%")


if __name__ == "__main__":
    main()
