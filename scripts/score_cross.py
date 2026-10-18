"""Score the cross-asset exporter (crude EIA momentum, gold Asian session).

Trades are converted to dollars per micro contract (MCL $100 per $1 of
crude, MGC $10 per $1 of gold) and sized so the average loss is comparable
to an NQ ORB loss. Stop/target is chosen on 2018-2021 and reported on
2022-2025, and the score that matters is the change in pass rate when the
stream is added to the existing book.
"""
from __future__ import annotations

import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, TIERS  # noqa: E402
from rescore_all import load_components, rvol, book  # noqa: E402

SPLIT = "2022-01-01"
GRID = {"CL": [0.0010, 0.0020, 0.0030, 0.0050, 0.0080],
        "GC": [0.0005, 0.0010, 0.0020, 0.0035, 0.0060]}
MICRO = {"CL": 100.0, "GC": 10.0}


def parse(path):
    out = defaultdict(list)
    for line in open(path):
        p = line.strip().split(",")
        if len(p) < 16 or p[0] != "C":
            continue
        dt = p[2]
        out[p[1]].append({"date": f"{dt[0:4]}-{dt[4:6]}-{dt[6:8]}",
                          "dir": int(p[3]), "e": float(p[4]),
                          "sb": [int(x) for x in p[5:10]],
                          "tb": [int(x) for x in p[10:15]],
                          "x": float(p[15])})
    return out


def pts(r, grid, si, ti):
    s = r["sb"][si]
    t = r["tb"][ti] if ti is not None else -1
    if s >= 0 and (t < 0 or s <= t):
        return -grid[si] * r["e"]
    if t >= 0:
        return grid[ti] * r["e"]
    return r["x"]


def main():
    sp, path = sys.argv[1], sys.argv[2]
    reg = rvol()
    c, _ = load_components(sp)
    bk = book(c, reg, mnq=3)
    TIERS.clear()
    TIERS.append((0.0, 1.0, 300.0))

    def sc(ts, lo=None, hi=None):
        ts = [t for t in ts if (lo is None or t.date >= lo) and (hi is None or t.date < hi)]
        r = simulate(ts, window=250, day_stop_profit=1450.0)
        return r.pass_rate, r.bust_rate, r.median_days

    b_is, b_oos, b_full = sc(bk, hi=SPLIT), sc(bk, lo=SPLIT), sc(bk)
    print(f"book 3 MNQ: full {b_full[0]:.1f}/{b_full[1]:.1f}  IS {b_is[0]:.1f}  OOS {b_oos[0]:.1f}\n")
    sigs = parse(path)
    for name, rows in sorted(sigs.items()):
        inst = name[:2]
        grid = GRID[inst]
        best = None
        for si in range(5):
            for ti in [None] + list(range(5)):
                v = [pts(r, grid, si, ti) for r in rows if r["date"] < SPLIT]
                if not v:
                    continue
                m = st.mean(v)
                if best is None or m > best[0]:
                    best = (m, si, ti)
        _, si, ti = best
        raw = [Trade(r["date"], pts(r, grid, si, ti), name) for r in rows]
        v = [t.points for t in raw]
        losses = [x for x in v if x <= 0]
        avgl_usd = (st.mean(losses) if losses else -1) * MICRO[inst]
        n_micro = max(1, round(78.0 / abs(avgl_usd))) if avgl_usd else 1
        usd = [Trade(t.date, t.points * MICRO[inst] * n_micro, name) for t in raw]
        i = [t.points for t in usd if t.date < SPLIT]
        o = [t.points for t in usd if t.date >= SPLIT]
        f = sc(merge(bk, usd)), sc(merge(bk, usd), hi=SPLIT), sc(merge(bk, usd), lo=SPLIT)
        tstr = "exit" if ti is None else f"{grid[ti]*100:.2f}%"
        print(f"{name}  n={len(v)} ({len(v)/8:.0f}/yr)  stop {grid[si]*100:.2f}%  target {tstr}"
              f"  -> {n_micro} micro(s)")
        print(f"   WR {sum(1 for x in v if x > 0)/len(v)*100:.1f}%  "
              f"\$/trade IS {st.mean(i) if i else 0:+.1f}  OOS {st.mean(o) if o else 0:+.1f}")
        print(f"   +book full {f[0][0]:.1f}/{f[0][1]:.1f} ({f[0][0]-b_full[0]:+.1f})  "
              f"IS {f[1][0]:.1f} ({f[1][0]-b_is[0]:+.1f})  OOS {f[2][0]:.1f} ({f[2][0]-b_oos[0]:+.1f})\n")


if __name__ == "__main__":
    main()
