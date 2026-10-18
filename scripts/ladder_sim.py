"""Size as a function of distance to the trailing drawdown line.

Flat sizing ignores the one state variable that decides survival: how much
room is left above the line. The literature on drawdown-constrained growth
(Grossman & Zhou 1993; Cvitanic & Karatzas 1994) has exposure proportional to
that cushion. Here size = clamp(floor(room / K), 1, cap) MNQ, re-evaluated at
the start of each day, with a daily loss stop that scales with size.
"""
from __future__ import annotations

import csv
import sys

sys.path.insert(0, "scripts")
from prop_sim import by_day  # noqa: E402
from score_multi import load_book  # noqa: E402


def make_days(sp, ceiling=0.30):
    reg = {}
    with open("results/nq_panel_real.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                reg[r["date"]] = float(r["rvol20"])
            except (ValueError, KeyError):
                continue
    book = load_book(sp, lambda ts: [t for t in ts if reg.get(t.date, 9.0) < ceiling])
    return sorted(by_day(book).items())


def ladder(K, cap, floor_n=1):
    def f(room):
        n = int(room // K)
        n = max(floor_n, min(cap, n))
        return 2.0 * n, 75.0 + 75.0 * n
    return f


def run(days, sizer, window=250, start_pnl=0.0, target=3000.0,
        consistency=True, locked=None, lo=None, hi=None):
    """Returns pass%, bust%, median days. locked=float pins the line."""
    if lo or hi:
        days = [d for d in days if (lo is None or d[0] >= lo) and (hi is None or d[0] < hi)]
    P = B = T = 0
    pd = []
    for s in range(0, max(0, len(days) - window)):
        pnl = start_pnl
        peak = start_pnl
        best = 0.0
        out = "timeout"
        dn = 0
        for di in range(s, min(s + window, len(days))):
            dn += 1
            line = locked if locked is not None else min(peak - 2000.0, 100.0)
            dpp, ds = sizer(pnl - line)
            dp = 0.0
            for t in days[di][1]:
                dp += t.points * dpp
                eq = pnl + dp
                if eq <= line:
                    out = "bust"
                    break
                if eq >= target and (not consistency or max(best, dp) <= 0.5 * eq):
                    out = "pass"
                    break
                if dp <= -ds:
                    break
                if consistency and dp >= 1450.0:
                    break
            pnl += dp
            best = max(best, dp)
            if out != "timeout":
                break
            peak = max(peak, pnl)
        if out == "pass":
            P += 1
            pd.append(dn)
        elif out == "bust":
            B += 1
        else:
            T += 1
    n = max(1, P + B + T)
    pd.sort()
    return P / n * 100, B / n * 100, (pd[len(pd) // 2] if pd else 0)


if __name__ == "__main__":
    days = make_days(sys.argv[1])
    print(f"{'K $/MNQ':>8} | " + " ".join(f"cap {c}".rjust(16) for c in (2, 3, 4, 5, 6)))
    for K in (300, 400, 500, 600, 700, 800):
        row = []
        for cap in (2, 3, 4, 5, 6):
            p, b, m = run(days, ladder(K, cap))
            row.append(f"{p:5.1f}/{b:4.1f}/{m:3d}")
        print(f"{K:8d} | " + " ".join(x.rjust(16) for x in row))


def outcomes(days, sizer, window=400, start_pnl=0.0, target=3000.0,
             consistency=True, locked=None):
    """Per-start-day (outcome, trading days used) for one lifecycle stage."""
    res = []
    for s in range(0, max(0, len(days) - window)):
        pnl = start_pnl
        peak = start_pnl
        best = 0.0
        out = "timeout"
        dn = 0
        for di in range(s, min(s + window, len(days))):
            dn += 1
            line = locked if locked is not None else min(peak - 2000.0, 100.0)
            dpp, ds = sizer(pnl - line)
            dp = 0.0
            for t in days[di][1]:
                dp += t.points * dpp
                eq = pnl + dp
                if eq <= line:
                    out = "bust"
                    break
                if eq >= target and (not consistency or max(best, dp) <= 0.5 * eq):
                    out = "pass"
                    break
                if dp <= -ds:
                    break
                if consistency and dp >= 1450.0:
                    break
            pnl += dp
            best = max(best, dp)
            if out != "timeout":
                break
            peak = max(peak, pnl)
        res.append((out, dn))
    return res


def lifecycle(ev, f1, rp, horizon=504, trials=20000, fee=150.0, n_acct=5,
              payout=1800.0, seed=5):
    """Monte Carlo over 24 months: evaluation -> first funded -> repeats.

    ev, f1, rp are outcome tables from outcomes(). A bust in either funded
    stage sends the seat back to a fresh evaluation.
    """
    import random
    import statistics as st
    rnd = random.Random(seed)
    M = min(len(ev), len(f1), len(rp))
    tot, first, rebuilds = [], [], []
    for _ in range(trials):
        t0 = rnd.randrange(0, M)
        cash = 0.0
        t = 0
        fp = None
        rb = 0
        stage = "ev"
        while t < horizon:
            i = (t0 + t) % M
            if stage == "ev":
                o, d = ev[i]
                t += d
                cash -= n_acct * fee
                if o == "pass":
                    stage = "f1"
                elif o == "timeout":
                    t += 5
            elif stage == "f1":
                o, d = f1[i]
                t += d
                if o == "pass":
                    cash += n_acct * payout
                    fp = fp if fp is not None else t
                    stage = "rp"
                elif o == "bust":
                    stage = "ev"
                    rb += 1
            else:
                o, d = rp[i]
                t += max(d, 5)
                if o == "pass":
                    cash += n_acct * payout
                elif o == "bust":
                    stage = "ev"
                    rb += 1
        tot.append(cash)
        first.append(fp / 21.0 if fp else None)
        rebuilds.append(rb)
    tot.sort()
    got = sorted(x for x in first if x is not None)
    q = lambda p: tot[int(len(tot) * p)]
    return {"mean": st.mean(tot), "p10": q(0.10), "p50": q(0.50), "p90": q(0.90),
            "first": got[len(got) // 2] if got else None,
            "rebuilds": st.mean(rebuilds)}
