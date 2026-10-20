"""Score the noise-area momentum trades and the time-of-day path tags.

Z tags: the Zarattini, Aziz & Barbon (2024) rules on NQ as published, then the
same trades with a profit target (exit at +X bp if reached before the
trailing exit), which is the obvious way to raise the win rate. Finally the
published version is added to the NQ + Dow book at 1-2 MNQ per unit.

P tags: mean NQ return in every half-hour window and the lunch effect
(Vojtko & Dujava 2024: long 12:00-14:00), 2018-2021 against 2022-2025.
"""
from __future__ import annotations

import math
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge, load_tags  # noqa: E402
from rescore_all import load_components, rvol, book  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from final_lifecycle import staged, lad, stage_line  # noqa: E402

LEVELS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150]
SPLIT = "2022"
COST_PTS = 0.5          # $1 per MNQ round trip
CHECKS = ["09:30"] + [f"{9 + (30 + 30 * i) // 60}:{(30 + 30 * i) % 60:02d}" for i in range(1, 13)] + ["15:55"]


def tstat(v):
    if len(v) < 3:
        return 0.0
    sd = st.pstdev(v)
    return st.mean(v) / sd * math.sqrt(len(v)) if sd > 0 else 0.0


def line(lab, v):
    return (f"{lab:<4} n {len(v):5}  WR {sum(1 for x in v if x > 0) / max(1, len(v)) * 100:4.1f}%  "
            f"{st.mean(v) if v else 0:+6.2f} pt  t {tstat(v):+.1f}")


def parse(path):
    Z, P = [], []
    for raw in open(path):
        f = raw.strip().split(",")
        if f[0] == "Z" and len(f) >= 34:
            Z.append({"ymd": f[1], "side": int(f[2]), "ehm": int(f[3]), "e": float(f[4]),
                      "xhm": int(f[5]), "x": float(f[6]), "sig": float(f[7]),
                      "up": [int(v) for v in f[8:21]], "dn": [int(v) for v in f[21:34]]})
        elif f[0] == "P" and len(f) >= 44:
            P.append({"ymd": f[1], "dow": int(f[2]), "pc": float(f[3]),
                      "px": [float(v) for v in f[4:18]]})
    return Z, P


def z_result(z, tp=None, sl=None):
    dur = z["xhm"] - z["ehm"]
    fav, adv = (z["up"], z["dn"]) if z["side"] == 1 else (z["dn"], z["up"])
    t = fav[LEVELS.index(tp)] if tp else -1
    s = adv[LEVELS.index(sl)] if sl else -1
    t = t if 0 <= t <= dur else -1
    s = s if 0 <= s <= dur else -1
    if s >= 0 and (t < 0 or s <= t):
        return -z["e"] * sl / 1e4 - COST_PTS
    if t >= 0:
        return z["e"] * tp / 1e4 - COST_PTS
    return z["side"] * (z["x"] - z["e"]) - COST_PTS


def main():
    sp = sys.argv[1]
    Z, P = parse(f"{sp}/NOISETOD_tags.txt")
    reg = rvol()
    print(f"{len(Z)} noise-area trades, {len(P)} day paths\n")
    print("== noise-area momentum as published (NQ points per trade, $1/MNQ cost)")
    for gate in (False, True):
        zz = [z for z in Z if not gate or reg.get(f"{z['ymd'][:4]}-{z['ymd'][4:6]}-{z['ymd'][6:]}", 9) < 0.30]
        for lab, part in (("IS", [z for z in zz if z["ymd"][:4] < SPLIT]), ("OOS", [z for z in zz if z["ymd"][:4] >= SPLIT])):
            print(f"   vol gate {'on ' if gate else 'off'} {line(lab, [z_result(z) for z in part])}  ({len(part)/4:.0f}/yr)")
    yr = defaultdict(list)
    for z in Z:
        yr[z["ymd"][:4]].append(z_result(z))
    print("   by year:", {k: round(sum(v)) for k, v in sorted(yr.items())})

    print("\n== with a profit target (still the published trailing exit otherwise)")
    for tp in (10, 15, 20, 25, 30, 40, 50, 75):
        a = [z_result(z, tp) for z in Z if z["ymd"][:4] < SPLIT]
        b = [z_result(z, tp) for z in Z if z["ymd"][:4] >= SPLIT]
        print(f"   TP {tp:3} bp   {line('IS', a)}   |   {line('OOS', b)}")

    print("\n== half-hour seasonality, mean NQ points (t)")
    for i in range(len(CHECKS) - 1):
        a = [p["px"][i + 1] - p["px"][i] for p in P if p["ymd"][:4] < SPLIT]
        b = [p["px"][i + 1] - p["px"][i] for p in P if p["ymd"][:4] >= SPLIT]
        print(f"   {CHECKS[i]}-{CHECKS[i + 1]}   IS {st.mean(a):+6.2f} (t{tstat(a):+.1f})   OOS {st.mean(b):+6.2f} (t{tstat(b):+.1f})")
    for lab, i, j in (("lunch long 12:00-14:00", 5, 9), ("short 11:00-12:00", 3, 5)):
        sgn = -1 if "short" in lab else 1
        a = [sgn * (p["px"][j] - p["px"][i]) - COST_PTS for p in P if p["ymd"][:4] < SPLIT]
        b = [sgn * (p["px"][j] - p["px"][i]) - COST_PTS for p in P if p["ymd"][:4] >= SPLIT]
        print(f"   {lab:<24} {line('IS', a)}  |  {line('OOS', b)}")

    print("\n== noise-area momentum added to the NQ + Dow book")
    c, _ = load_components(sp)
    nq = [Trade(t.date, t.points - 1.0, t.strat) for t in book(c, reg, mnq=1)]
    ym = [Trade(t.date, (t.points * 0.5 - 1.0) * 2, "YM")
          for t in load_tags(f"{sp}/XYM_tags.txt", fmt="s1") if reg.get(t.date, 9.0) < 0.30]
    base = merge(nq, ym)
    zt = [(f"{z['ymd'][:4]}-{z['ymd'][4:6]}-{z['ymd'][6:]}", z_result(z)) for z in Z]
    cal = sorted(set(t.date for t in base) | set(d for d, _ in zt))
    for n in (0, 1, 2):
        ts = merge(base, [Trade(d, p * 2.0 * n, "Z") for d, p in zt]) if n else base
        T = staged(calendar_days(ts, cal), lad(700, 4, 75), lad(800, 4, 75), lad(700, 4, 75))
        stage_line(f"book + noise momentum {n} MNQ/unit", T)
        r = sim_groups([(5, T)])
        print(f"      5 accounts 24m: p10 {r['p10']:,.0f}  median {r['p50']:,.0f}  p90 {r['p90']:,.0f}")


if __name__ == "__main__":
    main()
