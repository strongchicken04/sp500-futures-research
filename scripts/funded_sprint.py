"""Sprint on the FUNDED account (night shift 2026-10-23, fixed before results).

Today the funded account trades the book (no ORB: VG + Z + RS, flat 3) from day
one; 56-58% of funded accounts bust before the first payout (+$4,000). Idea:
trade the evaluation sprint on the funded account until the first payout (one
big bracket trade a day, same sizing as the evaluation two-win sprint), then
switch to the book.

Account model as mc_book.run_path (bust = new evaluation $180 + 11 days,
$1,800 per payout, restart at +$2,000 with the drawdown locked at +$100,
payouts >= 5 trading days apart, 24-month paths of 20-day blocks, paired).
Sprint sizing: see sprint_usd (wins <= $1,450 - the evaluation day cap kept,
conservative; a loss never reaches the drawdown line). Days without a sprint
signal: no trade.

Payout rule (LucidFlex 50K, third-party summaries 2026-10 - confirm with the
owner): +$4,000 AND five profitable days (>= $150) in the cycle, the count
resets after a payout; no consistency rule on the funded account. Enforced for
every variant, the book too (mc_book does not check it).

Variants:  BOOK              book from day one (today's recommendation)
           RS S3->BOOK       RS sprint 0.20/0.30, big wins (as the evaluation)
                             until +$4,000, then $170 wins until five
                             profitable days; book after the first payout
           RS S5->BOOK       RS sprint sized so five wins reach +$4,000
           VWAP10 S3/S5->BOOK  same with the VWAP10 sprint 0.25/0.40
           RS S5 always      RS S5 sprint in every stage
Also: share of funded starts that reach the first payout and mean trading days
to it (walk from every start day of the half).

Usage: funded_sprint.py DATA_DIR
"""
from __future__ import annotations

import math
import random
import statistics as st
import sys

sys.path.insert(0, "scripts")
import gate_check as G  # noqa: E402
from mc_runs import sized  # noqa: E402
from mc_book import EVAL_DAYS, EVAL_COST, PAYOUT, HORIZON, BLOCK  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from b_sprint_lab import sgn  # noqa: E402
from two_win_sprint import trade_pts  # noqa: E402


def sprint_usd(sig, pnl, line, peak, pdays, size):
    """One sprint trade sized for the remaining profit R = 4000 - pnl.
    S3: big wins (<= $1,450, loss <= $1,950) until R <= 0, then $170 wins until
        five profitable days.
    S5: win per trade = clip((R + 60) / max(1, 5 - profitable days), 170, 1450).
    Always: a loss cannot reach the drawdown line (loss <= pnl - line - 50)."""
    pts, T, S = sig
    win1, loss1 = T * 2.0, S * 2.0
    R = 4000.0 - pnl
    if size == "S3":
        want = min(1450.0, R + 60.0) if R > 0 else 170.0
    else:
        want = min(1450.0, max(170.0, (R + 60.0) / max(1, 5 - pdays)))
    n = max(1, math.ceil(want / (win1 - 2.0)))
    n = min(n, 40, int(1950 / loss1), int(1450 / win1))
    n = max(1, min(n, int((pnl - line - 50.0) / (loss1 + 3.0))))
    return min((pts - 0.5) * 2.0 * n - n, 1450.0)


def step(day, mode, pnl, line, peak, pdays):
    book, rs, vw = day
    if mode == "book":
        return book
    kind, size = mode.split("-")
    sig = rs if kind == "rs" else vw
    return [sprint_usd(sig, pnl, line, peak, pdays, size)] if sig else []


PD_RULE = True   # income2.py switches it off to compare with the old model


def run_path(days, policy, first_only=False):
    """Payout needs +$4,000 AND five days with >= $150 profit in the cycle
    (LucidFlex 50K); the count resets after each payout. first_only: return
    (reached the first payout?, days used) from day 0, no evaluation lag."""
    t, cash = (0 if first_only else EVAL_DAYS), -EVAL_COST
    stage, pnl, peak, last_pay, pdays = "f1", 0.0, 0.0, -99, 0
    while t < len(days):
        line = 100.0 if stage == "rp" else min(peak - 2000.0, 100.0)
        seq = step(days[t], policy[stage], pnl, line, peak, pdays)
        eq, bust = pnl, False
        for usd in seq:
            eq += usd
            if eq <= line:
                bust = True
                break
        t += 1
        if bust:
            if first_only:
                return False, t
            cash -= EVAL_COST
            t += EVAL_DAYS
            stage, pnl, peak, pdays = "f1", 0.0, 0.0, 0
            continue
        if eq - pnl >= 150.0:
            pdays += 1
        pnl = eq
        peak = max(peak, pnl)
        if pnl >= 4000.0 and (pdays >= 5 or not PD_RULE) and (stage == "f1" or t - last_pay >= 5):
            if first_only:
                return True, t
            cash += PAYOUT
            last_pay = t
            stage, pnl, peak, pdays = "rp", 2000.0, 2000.0, 0
    return None if first_only else cash


POLICIES = {"BOOK": {"f1": "book", "rp": "book"},
            "RS S3->BOOK": {"f1": "rs-S3", "rp": "book"}, "RS S5->BOOK": {"f1": "rs-S5", "rp": "book"},
            "VWAP10 S3->BOOK": {"f1": "vw-S3", "rp": "book"}, "VWAP10 S5->BOOK": {"f1": "vw-S5", "rp": "book"},
            "RS S5 always": {"f1": "rs-S5", "rp": "rs-S5"}}


def main():
    data = sys.argv[1]
    tr = sized(G.build(data, set()), {"VG": 3, "Z": 3, "RS": 3})
    rs = first_signals(parse_mf(f"{data}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    rs = {d: trade_pts(r, s, ML, 20, 30) for d, (r, s) in rs.items()}
    vw = {r["date"]: trade_pts(r, sgn(r["e"] - r["vwap"]), CL, 25, 40)
          for r in parse([f"{data}/CBA_tags.txt"]) if r["type"] == "T1000" and sgn(r["e"] - r["vwap"])}
    by = {}
    for t in tr:
        by.setdefault(t[0], []).append(t)
    cal_all = sorted(set(by) | set(rs) | set(vw))
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25")):
        cal = [d for d in cal_all if lo <= d < hi]
        days = [([t[3] for t in sorted(by.get(d, []), key=lambda t: t[2])], rs.get(d), vw.get(d)) for d in cal]
        print(f"--- {lab}: first payout from a funded start (walk from every start day)")
        for name, pol in POLICIES.items():
            res = [x for x in (run_path(days[s:], pol, True) for s in range(len(days) - 200)) if x]
            ok = [d for r, d in res if r]
            print(f"   {name:<16} reached {len(ok) / len(res) * 100:4.1f}%  days to it {st.mean(ok):5.1f}  "
                  f"days to a bust {st.mean([d for r, d in res if not r]):5.1f}")
        rnd = random.Random(911)
        out = {k: [] for k in POLICIES}
        for _ in range(4000):
            idx = []
            while len(idx) < HORIZON:
                s = rnd.randrange(0, len(days) - BLOCK)
                idx.extend(range(s, s + BLOCK))
            path = [days[i] for i in idx[:HORIZON]]
            for k, pol in POLICIES.items():
                out[k].append(run_path(path, pol))
        b = out["BOOK"]
        print(f"   24-month cash per funded seat (bootstrap, paired):")
        for k, v in out.items():
            d = [x - y for x, y in zip(v, b)]
            sv = sorted(v)
            print(f"   {k:<16} mean ${st.mean(v):7,.0f}  p10 ${sv[len(sv) // 10]:7,.0f}  vs BOOK {st.mean(d):+7,.0f} "
                  f"(+/- {1.96 * st.pstdev(d) / len(d) ** 0.5:,.0f}) better {sum(x > 0 for x in d) / len(d) * 100:3.0f}%")


if __name__ == "__main__":
    main()
