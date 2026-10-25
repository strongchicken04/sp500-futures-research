"""Barrier-model check (2026-10-25, owner sent SSRN 7445798, Villahermosa,
"Prop-Firm Challenges: A Barrier Model of Pass Rates and Expected Value").

The paper: a participant WITHOUT edge passes at most L / (T + L) of the
evaluations (L = drawdown, T = profit target); a trailing floor, fees and a
bounded horizon only lower it. Lucid 50K: L = $2,000, T = $3,000 -> 40%.

Check of our evaluation simulation (two_win_sprint.attempt_days, two-win
policy, single account): pass rate per evaluation bought for the real signal
and for a RANDOM direction on the same days and brackets (mean of 20 seeds).
The random version must stay <= 40%; the real one above it is the edge.
pass rate per evaluation = starts / evaluations bought over all start days.

Usage: paper_barrier.py DATA_DIR
"""
from __future__ import annotations

import math
import random
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from b_sprint_lab import trend_map, sgn  # noqa: E402
import two_win_sprint as W  # noqa: E402
from two_win_sprint import trade_pts, attempt_days, ERAS  # noqa: E402

# Second check: the evaluation sim tests the drawdown only on the CLOSED
# result of a trade. If the account fails as soon as the intraday balance
# touches the line, a trade taken with little room (e.g. after a first full
# loss: ~$50 left) dies on the first small adverse move. INTRA: bust when the
# adverse excursion before the target reaches the room left (largest bracket
# level <= the room in bp; below the smallest level: the 5 bp level, lenient).
# Modes: "eod" = old sim (W.INTRA False); "room" = two_win_sprint with INTRA
# (every trade sized to fit the room, dead account -> new evaluation);
# SIZE: "full" = the plan (loss <= $1,950, room only checked on the finishing
# trade); "half" = loss <= min($950, room - $50), never more than the room.

BR = {"RS": (20, 30), "T931": (25, 40), "VWAP10": (25, 40)}


def adverse_bp(r, s, lv, tp):
    """Largest bracket level (bp) the price moved against s before the target
    (or the close); 0 if not even the smallest."""
    fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
    t = fav[lv.index(tp)]
    hit = [lev for k, lev in enumerate(lv) if adv[k] >= 0 and (t < 0 or adv[k] < t)]
    return max(hit) if hit else 0


def attempt_intra(days, start, size):
    i, evals = start, 1
    pnl, peak, best = 0.0, 0.0, 0.0
    while i < len(days):
        sig = days[i]
        i += 1
        if sig is None:
            continue
        pts, T, S, adv, e = sig
        line = 100.0 if peak >= 2100.0 else peak - 2000.0
        win1, loss1 = T * 2.0, S * 2.0
        room = pnl - line
        if peak >= 2100.0 and 3000.0 - pnl <= 1450.0:
            n = max(1, math.ceil((3000.0 - pnl + 60.0) / (win1 - 2.0)))
            n = max(1, min(n, int((room - 50.0) / (loss1 + 3.0))))
        elif size == "full":
            n = max(1, min(40, int(1450 / win1), int(1950 / loss1)))
        else:
            n = max(1, min(40, int(1450 / win1), int(min(950.0, room - 50.0) / (loss1 + 3.0))))
        room_bp = room / (2.0 * n) / e * 1e4
        lev = [x for x in LV if x <= room_bp]
        if adv >= (max(lev) if lev else LV[0]):
            evals += 1
            pnl, peak, best = 0.0, 0.0, 0.0
            continue
        usd = min((pts - 0.5) * 2.0 * n - n, 1450.0)
        eq = pnl + usd
        if eq <= line:
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


LV = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150]


def pass_rate(sig, cal, lv, tp, sp, flip=None, mode="eod"):
    days = []
    for d in cal:
        if d in sig:
            r, s = sig[d]
            if flip is not None:
                s = flip[d]
            days.append(trade_pts(r, s, lv, tp, sp) + (adverse_bp(r, s, lv, tp), r["e"]))
        else:
            days.append(None)
    if mode in ("eod", "room"):
        W.INTRA = mode == "room"
        tp_days = [trade_pts(sig[d][0], (flip or {}).get(d, sig[d][1]), lv, tp, sp) if d in sig else None for d in cal]
        res = [attempt_days(tp_days, s0, "two-win") for s0 in range(0, len(days) - 260)]
    else:
        res = [attempt_intra(days, s0, mode) for s0 in range(0, len(days) - 260)]
    res = [x for x in res if x]
    return len(res) / sum(e for _, e in res), st.mean(d for d, _ in res), st.mean(e for _, e in res) * 90.0


def main():
    data = sys.argv[1]
    print("ceiling without edge (Lucid 50K, L 2000 / T 3000): 40.0% of evaluations")
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
        print(f"--- {lab}  pass rate per evaluation (days, fees to a pass)")
        for name, (sig, lv) in S.items():
            tp, sp = BR[name]
            for mode in ("eod", "full", "room"):
                real, rd, fee = pass_rate(sig, cal, lv, tp, sp, mode=mode)
                rnd = []
                for seed in range(20):
                    g = random.Random(seed)
                    rnd.append(pass_rate(sig, cal, lv, tp, sp, {d: g.choice((1, -1)) for d in sig}, mode)[0])
                tag = {"eod": "old sim (closed)", "full": "intraday, plan size", "room": "intraday, fit room"}[mode]
                print(f"   {name:<6} {tag:<20} real {real * 100:5.1f}% ({rd:5.1f} d, ${fee:4.0f})   "
                      f"random {st.mean(rnd) * 100:5.1f}% (range {min(rnd) * 100:4.1f}-{max(rnd) * 100:4.1f})")


if __name__ == "__main__":
    main()
