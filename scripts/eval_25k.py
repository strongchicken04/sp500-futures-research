"""Lucid Flex 25K vs 50K evaluation with our RS sprint (owner question
2026-10-28; rules fixed before results).

Accounts (third-party summaries 2026-10; owner to confirm):
  50K  target +$3,000, EOD trailing drawdown $2,000 (locks at +$100 once an EOD
       balance reaches +$2,100), day profit cap ~$1,450, max 40 MNQ, fee $90
  25K  target +$1,250, EOD trailing drawdown $1,000 (locks at +$100 once an EOD
       balance reaches +$1,100), no day cap assumed, max 20 MNQ, fee $60
       (discounted; regular $100), minimum 2 trading days
  both: best day <= 50% of the profit; intraday breach of the line (INTRA,
  guardrail 6d) - every trade is sized so its stop-out stays $50 above the
  line; a dead account buys a new evaluation the same day.
Signal: RS sprint (first RS signal of 10:00 / 11:00 / 13:00 / 14:30), bracket
+0.20 / -0.30 (plan) and +0.25 / -0.40, flat 15:55. EVERY era re-priced at NQ
28,530 (size_today rule: the dollar granularity of a small account matters).
Sizing ("two-win" logic scaled to the account): the win per trade is capped
at about half the target (consistency) and the stop at the room; once the
drawdown is locked and the target is within one win, the size just finishes
(+$60). Random-direction check: the same days with a coin-flip side must pass
<= L / (T + L) of evaluations (50K 40%, 25K 44%).
Usage: eval_25k.py DATA_DIR
"""
from __future__ import annotations

import hashlib
import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import two_win_sprint as W  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402

PRICE = 28530.0
ACC = {"50K": dict(target=3000.0, dd=2000.0, cap=1450.0, maxc=40, fee=90.0),
       "25K": dict(target=1250.0, dd=1000.0, cap=None, maxc=20, fee=60.0)}


def scaled(r, s, tp, sp):
    x = W.trade_pts(r, s, ML, tp, sp)
    f = PRICE / r["e"]
    y = W.TP((x[0] * f, x[1] * f, x[2] * f))
    y.adv, y.lv, y.e = x.adv, x.lv, PRICE
    return y


def attempt(days, start, a):
    """(days used, evaluations, passed attempts) from day index start until a pass."""
    T, DD = a["target"], a["dd"]
    i, evals = start, 1
    pnl = peak = best = 0.0
    tdays = 0
    while i < len(days):
        sig = days[i]
        i += 1
        if sig is None:
            continue
        pts, Tp, Sp = sig
        line = 100.0 if peak >= DD + 100.0 else peak - DD
        win1 = Tp * 2.0
        if W.stop_usd(sig, 1) > pnl - line - 50.0:            # dead account -> new evaluation today
            evals += 1
            pnl = peak = best = 0.0
            tdays = 0
            line = -DD
        wcap = 0.5 * T if a["cap"] is None else min(a["cap"], 0.5 * T + 200.0)
        n = max(1, min(a["maxc"], int(wcap / win1)))
        if peak >= DD + 100.0 and T - pnl <= wcap:
            n = max(1, math.ceil((T - pnl + 60.0) / (win1 - 2.0)))
        n = max(1, min(n, a["maxc"], int((pnl - line - 50.0 - W.stop_usd(sig, 0)) / W.stop_usd(sig, 1))))
        usd = (pts - 0.5) * 2.0 * n - n
        if a["cap"] is not None:
            usd = min(usd, a["cap"])
        eq = pnl + usd
        tdays += 1
        if eq <= line or W.breach(sig, n, pnl - line):
            evals += 1
            pnl = peak = best = 0.0
            tdays = 0
            continue
        pnl = eq
        best = max(best, usd)
        peak = max(peak, pnl)
        if pnl >= T and best <= 0.5 * pnl and tdays >= 2:
            return i - start, evals
        if i - start > 250:
            return None
    return None


def run(sig, cal, a):
    days = [sig.get(d) for d in cal]
    res = [x for x in (attempt(days, s0, a) for s0 in range(0, len(days) - 260)) if x]
    d = st.mean(x[0] for x in res)
    e = st.mean(x[1] for x in res)
    return d, e, 1.0 / e


def main():
    data = sys.argv[1]
    for lab, lo, hi, suf in W.ERAS:
        mf = parse_mf(f"{data}/MFEAT{suf}_tags.txt")
        rs = {d: v for d, v in first_signals(mf, lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                             (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)).items() if lo <= d < hi}
        cal = sorted({r["date"] for r in mf if lo <= r["date"] < hi})
        print(f"--- {lab}  RS sprint at NQ {PRICE:,.0f}: trading days to a pass | evaluations bought | pass per attempt | fees")
        for tp, sp in ((20, 30), (25, 40)):
            for real in (True, False):
                sig = {}
                for d, (r, s) in rs.items():
                    if not real:
                        s = 1 if hashlib.md5(d.encode()).digest()[0] & 1 else -1
                    sig[d] = scaled(r, s, tp, sp)
                cells = []
                for name, a in ACC.items():
                    dd, ev, p = run(sig, cal, a)
                    cells.append(f"{name}: {dd:5.1f} d  {ev:4.2f} eval  pass {p * 100:4.1f}%  ${ev * a['fee']:4.0f}")
                print(f"   +{tp / 100:.2f}/-{sp / 100:.2f} {'RS    ' if real else 'random'}  " + "   ".join(cells))


if __name__ == "__main__":
    main()
