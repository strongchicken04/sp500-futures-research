"""Funded 25K vs 50K per seat (night 2026-10-28/29, owner question; variants
fixed before results). Setup as size_today.py: every era re-priced at NQ
28,530, open-P&L drawdown check (mtm_check.day_seq), paired block bootstrap
24 months, book VG + Z + RS.
50K (funded_model rules): $2,000 EOD DD, lock +$100 at +$2,100, payout at
+$4,000 withdrawing <= $2,000 (<= half the profit), five days >= $150, 90%
split; a bust costs a new evaluation ($265, 10 days - RS sprint, INTRA).
25K ASSUMED half of everything (owner to confirm): $1,000 DD, lock +$100 at
+$1,100, payout at +$2,000 withdrawing <= $1,000, five days >= $75; bust ->
new 25K evaluation ($180, 10 days; eval_25k.py: ~same days, ~2/3 of the fees).
Variants: 50K flat 3 (plan) | 25K flat 1 | 25K flat 2 | 25K VG/Z 2 + RS 1.
Usage: funded_25k.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
import mtm_check as C  # noqa: E402
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse  # noqa: E402
from size_today import rvmap, PRICE  # noqa: E402

ACC = {"50K": dict(dd=2000.0, trig=4000.0, amt=2000.0, pday=150.0, cost=265.0, edays=10),
       "25K": dict(dd=1000.0, trig=2000.0, amt=1000.0, pday=75.0, cost=180.0, edays=10)}
VAR = {"50K flat 3": ("50K", {"VG": 3, "Z": 3, "RS": 3}), "25K flat 1": ("25K", {"VG": 1, "Z": 1, "RS": 1}),
       "25K flat 2": ("25K", {"VG": 2, "Z": 2, "RS": 2}), "25K VG/Z 2, RS 1": ("25K", {"VG": 2, "Z": 2, "RS": 1})}


def run_path(days, a, first_only=False, stats=None):
    """funded_model.run_path with the account parameters (days = increment lists)."""
    dd, lock = a["dd"], a["dd"] + 100.0
    t, cash = (0 if first_only else a["edays"]), -a["cost"]
    s = {"pnl": 0.0, "peak": 0.0, "pdays": 0, "pays": 0}
    while t < len(days):
        line = 100.0 if s["peak"] >= lock else s["peak"] - dd
        eq, bust = s["pnl"], False
        for usd in days[t]:
            eq += usd
            if eq <= line:
                bust = True
                break
        t += 1
        if bust:
            if first_only:
                return False, t
            if stats is not None:
                stats.append(s["pays"])
            cash -= a["cost"]
            t += a["edays"]
            s = {"pnl": 0.0, "peak": 0.0, "pdays": 0, "pays": 0}
            continue
        if eq - s["pnl"] >= a["pday"]:
            s["pdays"] += 1
        s["pnl"] = eq
        s["peak"] = max(s["peak"], eq)
        if s["pnl"] >= a["trig"] and s["pdays"] >= 5 and s["peak"] >= lock:
            if first_only:
                return True, t
            w = min(a["amt"], s["pnl"] / 2.0)
            cash += 0.9 * w
            s["pnl"] -= w
            s["pdays"] = 0
            s["pays"] += 1
    if stats is not None:
        stats.append(s["pays"])
    return None if first_only else cash


def main():
    data = sys.argv[1]
    C.PANEL_LEGS = {}
    reg = rvol()
    ro = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD"))
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < ro.get(d, 9.0) < 0.30, (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))))
    for suf, names, cba, gate, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        tr, by = C.trades(data, suf, gate, PRICE)
        T = {}
        for t in tr:
            T.setdefault(t[0], []).append(t)
        f = lambda e: PRICE / e
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            paths = M.bootstrap(len(cal), 3000, seed=1028)
            print(f"--- {lab} at NQ {PRICE:,.0f}: 24-month cash per seat | p10 | first payout | evaluations bought | payouts")
            for name, (acc, mix) in VAR.items():
                a = ACC[acc]
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                out = []
                for p in paths:
                    lives = []
                    out.append((run_path([dl[i] for i in p], a, stats=lives), len(lives), sum(lives)))
                fp = [r for r in (run_path(dl[s:], a, first_only=True) for s in range(len(dl) - 250)) if r]
                cash = [c for c, _, _ in out]
                print(f"   {name:<17} ${st.mean(cash):7,.0f}  p10 ${sorted(cash)[len(cash) // 10]:7,.0f}  first payout {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%  "
                      f"evals {st.mean(n for _, n, _ in out):4.1f}")


if __name__ == "__main__":
    main()
