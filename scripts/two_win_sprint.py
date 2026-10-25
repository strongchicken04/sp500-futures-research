"""Two-win evaluation sprint (2026-10-23, fixed before results).

Lucid Flex 50K evaluation: +$3,000 target, best day <= 50% of the profit,
day profit cap ~$1,450, $2,000 EOD trailing drawdown that locks at +$100 once
an EOD balance reaches +$2,100. Today's sprint sizes the stop at $1,900, so a
win is ~$950-1,270 and three wins are needed. Two-win design: size so a WIN is
~$1,450 (loss must stay under ~$1,950), then, once the drawdown has locked,
finish with a small trade (win ~$200) - pass after two big wins and one small.

Policies per signal day (one trade, bracket +T / -S, flat 15:55, $1 + 1 tick
per contract):
  now      n = floor(1900 / loss per MNQ), same size every trade
  two-win  n = min(floor(1450 / win per MNQ), floor(1950 / loss per MNQ));
           when the balance is >= +$2,100 (drawdown locked) and the target is
           <= $1,450 away: the size whose win just finishes the target
           (+$60 margin), capped so a loss cannot reach the drawdown
A bust (balance at or below the drawdown line) restarts with a new $90
evaluation the next day.

INTRA (default since 2026-10-25, guardrail 6d): Lucid breaches the drawdown
as soon as the INTRADAY balance touches it. Every trade is then sized so its
stop-out (with costs) stays $50 above the line; when even 1 MNQ does not fit
(e.g. after a first full loss: ~$50 left) the account is dead and a new
evaluation trades that day. breach() covers sims that size otherwise.
INTRA = False reproduces the old closed-trade check. Days and fees to a pass from every start day, single
account, for the RS sprint, the 09:31 trend sprint and the 10:00 VWAP sprint,
over a bracket grid, in four eras.

Usage: two_win_sprint.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from b_sprint_lab import trend_map, sgn  # noqa: E402

ERAS = (("2010-13", "2010", "2014", "_OLD"), ("2014-17", "2014", "2018", "_OLD"),
        ("2018-21", "2018", "2022", ""), ("2022-25", "2022", "2026", ""))
FEE = 90.0
INTRA = True


class TP(tuple):
    """(points, T, S) plus .adv = largest bracket level (bp) touched against
    the trade before it closed (0 if none), .lv the levels, .e the entry."""


def trade_pts(r, s, lv, tp, sp):
    """Gross points per contract for bracket +tp / -sp bp, entry r['e']."""
    ti, si = lv.index(tp), lv.index(sp)
    fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
    t, sl = fav[ti], adv[si]
    T, S = r["e"] * tp / 1e4, r["e"] * sp / 1e4
    if sl >= 0 and (t < 0 or sl <= t):
        out, end = (-S - 0.25, T, S), sl
    elif t >= 0:
        out, end = (T, T, S), t
    else:
        out, end = (max(-S - 0.25, s * r["eod"]), T, S), None
    x = TP(out)
    hit = [lev for k, lev in enumerate(lv[:si + 1]) if adv[k] >= 0 and (end is None or adv[k] <= end)]
    x.adv, x.lv, x.e = (max(hit) if hit else 0), lv, r["e"]
    return x


def stop_usd(sig, n):
    """Dollar loss of n MNQ stopped out (1 tick slippage, $1 + 1 tick costs)."""
    return (sig[2] + 0.75) * 2.0 * n + n


def breach(sig, n, room):
    """INTRA: did the intraday balance touch the line (room $ below the
    start-of-trade balance)? Conservative: the largest bracket level within
    the room counts as the touch; a stop-out that fits the room never does."""
    if not INTRA or stop_usd(sig, n) < room:
        return False
    room_bp = (room / (2.0 * n) - 0.25) / sig.e * 1e4
    lev = [x for x in sig.lv if x <= room_bp]
    return sig.adv >= (max(lev) if lev else sig.lv[0])


def attempt_days(days, start, policy):
    """From day index start: (days used, evaluations bought) until a pass, or None."""
    i, evals = start, 1
    pnl, peak, best = 0.0, 0.0, 0.0
    while i < len(days):
        sig = days[i]
        i += 1
        if sig is None:
            continue
        pts, T, S = sig
        line = 100.0 if peak >= 2100.0 else peak - 2000.0
        win1, loss1 = T * 2.0, S * 2.0
        if INTRA and stop_usd(sig, 1) > pnl - line - 50.0:   # dead account -> new evaluation today
            evals += 1
            pnl, peak, best, line = 0.0, 0.0, 0.0, -2000.0
        if policy == "now":
            n = max(1, min(40, int(1900 / loss1)))
        else:
            if peak >= 2100.0 and 3000.0 - pnl <= 1450.0:
                need = 3000.0 - pnl + 60.0                       # finish with a margin
                n = max(1, math.ceil(need / (win1 - 2.0)))
                n = max(1, min(n, int((pnl - line - 50.0) / (loss1 + 3.0))))   # never risk the account
            else:
                n = max(1, min(40, int(1450 / win1), int(1950 / loss1)))
        if INTRA:
            n = max(1, min(n, int((pnl - line - 50.0 - stop_usd(sig, 0)) / (stop_usd(sig, 1)))))
        usd = (pts - 0.5) * 2.0 * n - n
        usd = min(usd, 1450.0)                       # day profit cap
        eq = pnl + usd
        if eq <= line or breach(sig, n, pnl - line):  # bust -> new evaluation tomorrow
            evals += 1
            pnl, peak, best = 0.0, 0.0, 0.0
            continue
        pnl = eq
        best = max(best, usd)
        peak = max(peak, pnl)
        if pnl >= 3000.0 and best <= 0.5 * pnl:
            return i - start, evals
        if i - start > 250:
            return None
    return None


def run(sig, cal, tp, sp, lv, policy):
    days = []
    for d in cal:
        if d in sig:
            r, s = sig[d]
            days.append(trade_pts(r, s, lv, tp, sp))
        else:
            days.append(None)
    res = [attempt_days(days, s0, policy) for s0 in range(0, len(days) - 260)]
    res = [x for x in res if x]
    return st.mean(d for d, _ in res), st.mean(e for _, e in res) * FEE


def main():
    data = sys.argv[1]
    grid = {"RS": [(20, 30), (25, 30), (25, 40), (30, 40)], "T931": [(25, 40), (25, 30), (30, 40)], "VWAP10": [(25, 40), (25, 30), (30, 40)]}
    for lab, lo, hi, suf in ERAS:
        rs = {d: v for d, v in first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                             (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)).items() if lo <= d < hi}
        R = {}
        for r in parse([f"{data}/CBA{suf}_tags.txt"]):
            R.setdefault(r["type"], []).append(r)
        tm = trend_map(R["T931"])
        S = {"RS": (rs, ML),
             "T931": ({r["date"]: (r, tm[r["date"]]) for r in R["T931"] if lo <= r["date"] < hi and tm.get(r["date"])}, CL),
             "VWAP10": ({r["date"]: (r, sgn(r["e"] - r["vwap"])) for r in R["T1000"] if lo <= r["date"] < hi and sgn(r["e"] - r["vwap"])}, CL)}
        cal = sorted({d for v, _ in S.values() for d in v})
        print(f"--- {lab}  (days to a pass / fees, single account)")
        for name, brs in grid.items():
            sig, lv = S[name]
            cells = []
            for tp, sp in brs:
                a = run(sig, cal, tp, sp, lv, "now")
                b = run(sig, cal, tp, sp, lv, "two-win")
                cells.append(f"+{tp / 100:.2f}/-{sp / 100:.2f}: now {a[0]:5.1f} d ${a[1]:4.0f} | two-win {b[0]:5.1f} d ${b[1]:4.0f}")
            print(f"   {name:<6} " + "   ".join(cells))


if __name__ == "__main__":
    main()
