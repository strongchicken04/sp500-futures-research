"""Fastest expected route to a funded account, counting failed attempts.

An evaluation is a ticket: what matters is the expected number of trading
days (and fees) until one passes, = mean days per attempt / pass rate.
Compared on NQ 2018-2025 with costs and the account rules:
  sprint brackets  one trade a day on a signal, target worth ~$1,000 and stop
                   ~1.9-2x that (inside the $2,000 line), max 40 MNQ
  book             ORB + VWAP band + noise momentum (fixed fills) at several
                   sizes
Fee per attempt FEE.

Usage: eval_speed.py SCRATCH_DIR
"""
from __future__ import annotations

import datetime as dt
import statistics as st
import sys

sys.path.insert(0, "scripts")
import book_after_fix as B  # noqa: E402
from prop_sim import Trade, merge  # noqa: E402
from rescore_all import rvol  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat, lad  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_cond_bracket import parse, add_daily, FILTERS, LEVELS  # noqa: E402

FEE = 150.0


def attempt_stats(days, sizer, window=200):
    o = outcomes(days, sizer, window=window, start_pnl=0.0, target=3000.0, consistency=True)
    p = sum(1 for x, _ in o if x == "pass") / len(o)
    mean_days = st.mean(d for _, d in o)
    return p, mean_days


def bracket_trades(rows, pick, side_of, tp, sl, w):
    ti, si = LEVELS.index(tp), LEVELS.index(sl)
    first = {}
    for r in rows:
        if pick(r) and (r["date"] not in first or r["hm"] < first[r["date"]]["hm"]):
            first[r["date"]] = r
    out = []
    for d, r in first.items():
        side = side_of(r)
        fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
        t, s = fav[ti], adv[si]
        T, S = r["e"] * tp / 1e4, r["e"] * sl / 1e4
        n = max(1, min(40, round(w / (T * 2.0))))
        if S * 2.0 * n > 1950:
            n = max(1, int(1950 / (S * 2.0)))
        if s >= 0 and (t < 0 or s <= t):
            p = -S - 0.25
        elif t >= 0:
            p = T
        else:
            p = max(-S - 0.25, side * r["eod"] - 0.25)
        out.append(Trade(d, (p - 0.25) * 2.0 * n - n, "B"))
    return out


def main():
    sp = sys.argv[1]
    reg = rvol()
    rows = parse([f"{sp}/{x}_tags.txt" for x in ("CBA", "CBB", "CBD")])
    add_daily(rows)
    rows = [r for r in rows if reg.get(r["date"], 9.0) < 0.30]
    cal = sorted({r["date"] for r in rows})
    above = FILTERS["above 200d"]
    cands = {
        "sprint: first noise signal (long or short)": (lambda r: r["type"] in ("NZU", "NZD"),
                                                       lambda r: 1 if r["type"] == "NZU" else -1),
        "sprint: ORB long (first break)": (lambda r: r["type"] == "ORB", lambda r: 1),
        "sprint: 11:00 long above 200d": (lambda r: r["type"] == "T1100" and above(r), lambda r: 1),
        "sprint: 9:31 long (random control)": (lambda r: r["type"] == "T931", lambda r: 1),
    }
    print(f"{'route':<46} {'pass/att':>8} {'days/att':>8} {'E[days to pass]':>15} {'E[fees]':>8}")
    for name, (pick, side_of) in cands.items():
        best = None
        for tp, sl in ((20, 40), (25, 50), (30, 60), (40, 75), (50, 100)):
            for w in (750.0, 1000.0):
                tr = bracket_trades(rows, pick, side_of, tp, sl, w)
                p, md = attempt_stats(calendar_days(tr, cal), flat(1, 1e6))
                if p > 0 and (best is None or md / p < best[0]):
                    best = (md / p, p, md, tp, sl, w)
        e, p, md, tp, sl, w = best
        print(f"{name:<46} {p*100:7.0f}% {md:8.1f} {e:15.1f} {FEE/p:8.0f}   (TP {tp}bp SL {sl}bp, ~${w:.0f} win)")
    fx = f"{sp}/fixed"
    orb, vg, ym, nz = B.parts(fx, reg)
    nowed = lambda ts: [t for t in ts if dt.date.fromisoformat(t.date).weekday() != 2]
    bk = merge(merge(B.to_usd(nowed(orb)), B.to_usd(nowed(vg))), B.to_usd(nz))
    d = calendar_days(bk, sorted(set(t.date for t in bk)))
    for lab, sz in (("book ORB+VWAP+noise, ladder room/700 max 3", lad(700, 3, 75)),
                    ("book, flat 2 units", flat(2, 75)), ("book, flat 3 units", flat(3, 75)),
                    ("book, flat 4 units", flat(4, 75)), ("book, flat 6 units", flat(6, 75))):
        p, md = attempt_stats(d, sz, window=250)
        print(f"{lab:<46} {p*100:7.0f}% {md:8.1f} {md/p:15.1f} {FEE/p:8.0f}")


if __name__ == "__main__":
    main()
