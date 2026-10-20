"""Find signals whose edge survives the whole bracket grid, not one lucky cell.

For every entry type x context filter x direction, each trade's result is
averaged over a block of target/stop cells (target 10-60 bp, stop 1-4x the
target, the shapes a high-win-rate prop trade would use), giving one smoothed
basis-point result per trade. Its t-statistic on 2018-2021 ranks the signal;
2022-2025 is reported untouched. A signal that only works for one exact
bracket averages out here, which is the point.

Usage: score_plateau.py TAGFILE [TAGFILE ...]
"""
from __future__ import annotations

import math
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse, add_daily, FILTERS, LEVELS, SPLIT  # noqa: E402

CELLS = [(ti, si) for ti in range(len(LEVELS)) for si in range(len(LEVELS))
         if 10 <= LEVELS[ti] <= 60 and LEVELS[ti] <= LEVELS[si] <= 4 * LEVELS[ti]]
COST_BP = 0.5          # about $1 per MNQ round trip at NQ 20,000


def bp(r, side, ti, si):
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    if s >= 0 and (t < 0 or s <= t):
        return -LEVELS[si]
    if t >= 0:
        return LEVELS[ti]
    return max(-LEVELS[si], side * r["eod"] / r["e"] * 1e4)


def smooth(r, side):
    return st.mean(bp(r, side, ti, si) for ti, si in CELLS) - COST_BP


def wr(r, side):
    return st.mean(1.0 if bp(r, side, ti, si) > 0 else 0.0 for ti, si in CELLS)


def tstat(v):
    if len(v) < 5:
        return 0.0
    sd = st.pstdev(v)
    return st.mean(v) / sd * math.sqrt(len(v)) if sd > 0 else 0.0


def main():
    rows = parse(sys.argv[1:])
    add_daily(rows)
    reg = rvol()
    rows = [r for r in rows if reg.get(r["date"], 9.0) < 0.30]
    by_type = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r)
    out = []
    for typ, rs in sorted(by_type.items()):
        for fname, flt in FILTERS.items():
            sel = [r for r in rs if flt(r)]
            a = [r for r in sel if r["date"] < SPLIT]
            b = [r for r in sel if r["date"] >= SPLIT]
            if len(a) < 40 or len(b) < 40:
                continue
            for side in (1, -1):
                va = [smooth(r, side) for r in a]
                vb = [smooth(r, side) for r in b]
                yrs = defaultdict(list)
                for r, x in zip(a + b, va + vb):
                    yrs[r["date"][:4]].append(x)
                pos_years = sum(1 for v in yrs.values() if st.mean(v) > 0)
                out.append((tstat(va), typ, fname, side, st.mean(va), tstat(vb), st.mean(vb),
                            len(sel) / 8, st.mean(wr(r, side) for r in sel) * 100, pos_years, len(yrs)))
    out.sort(key=lambda x: -x[0])
    print(f"{len(out)} signal x filter x direction combinations; smoothed over {len(CELLS)} bracket cells\n")
    print(f"{'signal':<6} {'filter':<17} {'dir':<5} {'n/yr':>5} {'WR':>4} {'bp IS':>6} {'t IS':>5} "
          f"{'bp OOS':>7} {'t OOS':>6} {'yrs+':>5}")
    for t_is, typ, fname, side, m_is, t_oos, m_oos, nyr, w, py, ny in out[:30]:
        print(f"{typ:<6} {fname:<17} {'LONG' if side == 1 else 'SHORT':<5} {nyr:5.0f} {w:3.0f}% {m_is:+6.1f} {t_is:+5.1f} "
              f"{m_oos:+7.1f} {t_oos:+6.1f} {py:>2}/{ny}")
    good = [o for o in out if o[0] >= 2.0 and o[5] >= 2.0]
    print(f"\nt >= 2 in BOTH halves: {len(good)}")
    for t_is, typ, fname, side, m_is, t_oos, m_oos, nyr, w, py, ny in good:
        print(f"   {typ} {fname} {'LONG' if side == 1 else 'SHORT'}  {nyr:.0f}/yr  WR {w:.0f}%  "
              f"IS {m_is:+.1f}bp t{t_is:+.1f}  OOS {m_oos:+.1f}bp t{t_oos:+.1f}  years+ {py}/{ny}")


if __name__ == "__main__":
    main()
