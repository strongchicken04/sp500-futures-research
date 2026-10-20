"""One bracketed bet per day, sized so a win is about $1,000: does it pass fast?

Reads the daily bracket exporter. For each entry time, direction, target and
stop (in basis points of price), every day becomes one trade: stop first
(a minute touching both counts as the stop), else the target, else the
15:55 mark. The size is set each day so the target is worth ~$1,000 in MNQ;
costs are $1 per MNQ. Pass rate is measured on the real day sequence with the
account rules, starting on every day in turn; a rule is chosen on 2018-2021
and reported on 2022-2025.
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from rescore_all import rvol  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402

LEVELS = [10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200]
SPLIT = "2022-01-01"
COST = 1.0
MAX_MNQ = 40          # 4 NQ minis, the 50K account's limit
MAX_LOSS = 1950.0     # the stop must sit inside the $2,000 line, or the
                      # account is liquidated intraday before the stop


def parse(path):
    rows = []
    for line in open(path):
        f = line.strip().split(",")
        if f[0] != "B" or len(f) < 31:
            continue
        d = f[1]
        rows.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "hm": int(f[2]), "e": float(f[3]),
                     "up": [int(x) for x in f[4:17]], "dn": [int(x) for x in f[17:30]],
                     "eod": float(f[30])})
    return rows


def day_trade(r, side, ti, si, win_usd):
    """Dollar result of one bracket on one day."""
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    tp_pts = r["e"] * LEVELS[ti] / 1e4
    sl_pts = r["e"] * LEVELS[si] / 1e4
    n = max(1, min(MAX_MNQ, round(win_usd / (tp_pts * 2.0))))
    if s >= 0 and (t < 0 or s <= t):
        pts = -sl_pts
    elif t >= 0:
        pts = tp_pts
    else:
        pts = max(-sl_pts, side * r["eod"])
    return pts * 2.0 * n - COST * n, n


def pass_stats(trades, lo=None, hi=None):
    ts = [t for t in trades if (lo is None or t.date >= lo) and (hi is None or t.date < hi)]
    d = calendar_days(ts, sorted(set(t.date for t in ts)))
    o = outcomes(d, flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
    p = sum(1 for x, _ in o if x == "pass") / len(o) * 100
    md = sorted(dd for x, dd in o if x == "pass")
    return p, (md[len(md) // 2] if md else 0)


def main():
    rows = parse(sys.argv[1])
    reg = rvol()
    print(f"{len(rows)} entries")
    for gate in (False, True):
        for hm in sorted(set(r["hm"] for r in rows)):
            rs = [r for r in rows if r["hm"] == hm and (not gate or reg.get(r["date"], 9.0) < 0.30)]
            res = []
            for side in (1, -1):
                for w in (500.0, 750.0, 1000.0, 1450.0):
                    for ti in range(len(LEVELS)):
                        for si in range(len(LEVELS)):
                            if LEVELS[si] < LEVELS[ti] or LEVELS[si] / LEVELS[ti] * w > MAX_LOSS:
                                continue
                            tr = [Trade(r["date"], day_trade(r, side, ti, si, w)[0], "B") for r in rs]
                            v_is = [t.points for t in tr if t.date < SPLIT]
                            res.append((pass_stats(tr, hi=SPLIT)[0], side, ti, si, tr, st.mean(v_is), w))
            res.sort(key=lambda x: -x[0])
            print(f"\nentry {hm // 60}:{hm % 60:02d}  vol gate {'on' if gate else 'off'}  (best 5 by 2018-21 pass)")
            for p_is, side, ti, si, tr, ev_is, w in res[:5]:
                v = [t.points for t in tr]
                wr = sum(1 for x in v if x > 0) / len(v) * 100
                p_oos, md_oos = pass_stats(tr, lo=SPLIT)
                ev_oos = st.mean([t.points for t in tr if t.date >= SPLIT])
                print(f"  {'LONG ' if side == 1 else 'SHORT'} win ${w:.0f} TP {LEVELS[ti]:3}bp SL {LEVELS[si]:3}bp  WR {wr:4.1f}%"
                      f"  $/day IS {ev_is:+6.0f} OOS {ev_oos:+6.0f}"
                      f"  pass IS {p_is:5.1f}%  OOS {p_oos:5.1f}% (median {md_oos} d)")


if __name__ == "__main__":
    main()
