"""Integrated seat model (day shift 2026-10-24, fixed before results): one
funded "seat" runs evaluation -> funded -> (bust) -> evaluation ... on the
SAME day path, instead of charging a fixed $180 / 11 days per bust. Answers:
does the evaluation plan change now that a funded seat is worth ~$1,000-1,600
a month?
Evaluation plans (two-win sizing with the exact finisher, as two_win_sprint):
  E1 pair: RS 0.20/0.30 (A) + 09:31 trend 0.25/0.40 (B), hedge guard (today)
  E2 RS alone       E3 VWAP10 alone (0.25/0.40)       E4 09:31 alone
  E5 pair: VWAP10 (A) + 09:31 (B), VWAP10 skips if B is open against it
A pair ends at the first pass (the other account is dropped; its fees count).
Each evaluation costs $90; a bust buys a new one the next day.
Funded: book VG + Z + RS + V10 at 4 MNQ, drawdown on open P&L (mtm_check),
payout rules as funded_model. 2018-21 / 2022-25, 24-month paths of 20-day
blocks (same paths for every plan).
Usage: integrated_seat.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
import mtm_check as C  # noqa: E402
from rescore_all import rvol  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from b_sprint_lab import trend_map, sgn  # noqa: E402
from hedge_check import exit_min  # noqa: E402
from two_win_sprint import trade_pts  # noqa: E402
from vside_plateau import vside  # noqa: E402

FEE = 90.0


class Eval:
    def __init__(self):
        self.reset()
        self.bought = 1

    def reset(self):
        self.pnl = self.peak = self.best = 0.0

    def step(self, sig):
        """One day; returns True on a pass."""
        if sig is None:
            return False
        pts, T, S = sig
        line = 100.0 if self.peak >= 2100.0 else self.peak - 2000.0
        win1, loss1 = T * 2.0, S * 2.0
        if self.peak >= 2100.0 and 3000.0 - self.pnl <= 1450.0:
            n = max(1, math.ceil((3000.0 - self.pnl + 60.0) / (win1 - 2.0)))
            n = max(1, min(n, int((self.pnl - line - 50.0) / (loss1 + 3.0))))
        else:
            n = max(1, min(40, int(1450 / win1), int(1950 / loss1)))
        usd = min((pts - 0.5) * 2.0 * n - n, 1450.0)
        eq = self.pnl + usd
        if eq <= line:
            self.bought += 1
            self.reset()
            return False
        self.pnl = eq
        self.best = max(self.best, usd)
        self.peak = max(self.peak, eq)
        return self.pnl >= 3000.0 and self.best <= 0.5 * self.pnl


def seat(path, accts):
    """path: day dicts; accts: keys of the sprint signals used ('A','B'). Returns (cash, evals, eval days)."""
    t, cash, evals, edays = 0, 0.0, 0, 0
    while t < len(path):
        E = {k: Eval() for k in accts}
        passed = False
        while t < len(path) and not passed:
            for k in accts:
                if E[k].step(path[t][k]):
                    passed = True
            t += 1
            edays += 1
        evals += sum(e.bought for e in E.values())
        cash -= FEE * sum(e.bought for e in E.values())
        if not passed:
            break
        st_ = {"pnl": 0.0, "peak": 0.0, "pdays": 0, "pays": 0}
        while t < len(path):
            line = 100.0 if st_["peak"] >= 2100.0 else st_["peak"] - 2000.0
            eq, bust = st_["pnl"], False
            for usd in path[t]["book"]:
                eq += usd
                if eq <= line:
                    bust = True
                    break
            t += 1
            if bust:
                break
            if eq - st_["pnl"] >= 150.0:
                st_["pdays"] += 1
            st_["pnl"] = eq
            st_["peak"] = max(st_["peak"], eq)
            if st_["pnl"] >= 4000.0 and st_["pdays"] >= 5:
                w = min(2000.0, st_["pnl"] / 2.0)
                cash += 0.9 * w
                st_["pnl"] -= w
                st_["pdays"] = 0
    return cash, evals, edays


def main():
    data = sys.argv[1]
    C.PANEL_LEGS = {"V10": vside(5, 0.0030, 0.0050)}
    reg = rvol()
    L.NAMES = ("BARS5A", "BARS5B")
    tr, by = C.trades(data, "", lambda d: reg.get(d, 9.0) < 0.30, None)
    T = {}
    for t in tr:
        T.setdefault(t[0], []).append(t)
    mix = {"VG": 4, "Z": 4, "RS": 4, "V10": 4}
    rs = first_signals(parse_mf(f"{data}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    R = {}
    for r in parse([f"{data}/CBA_tags.txt"]):
        R.setdefault(r["type"], []).append(r)
    tm = trend_map(R["T931"])
    t9 = {r["date"]: (r, tm[r["date"]]) for r in R["T931"] if tm.get(r["date"])}
    vw = {r["date"]: (r, sgn(r["e"] - r["vwap"])) for r in R["T1000"] if sgn(r["e"] - r["vwap"])}

    def b_open_against(d, s, e_min):
        if d not in t9 or t9[d][1] == s:
            return False
        rb, sb = t9[d]
        fav, adv = (rb["up"], rb["dn"]) if sb == 1 else (rb["dn"], rb["up"])
        return e_min < exit_min(571, fav, adv, CL.index(25), CL.index(40))

    full = sorted({r["date"] for r in R["T931"]} | set(rs) | set(vw))
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25")):
        cal = [d for d in full if lo <= d < hi]
        days = []
        for d in cal:
            a_rs = trade_pts(rs[d][0], rs[d][1], ML, 20, 30) if d in rs else None
            a_rs_g = None if (d in rs and b_open_against(d, rs[d][1], rs[d][0]["hm"])) else a_rs
            a_vw = trade_pts(vw[d][0], vw[d][1], CL, 25, 40) if d in vw else None
            a_vw_g = None if (d in vw and b_open_against(d, vw[d][1], 600)) else a_vw
            b931 = trade_pts(t9[d][0], t9[d][1], CL, 25, 40) if d in t9 else None
            book = C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, None, True)
            days.append({"RSg": a_rs_g, "RS": a_rs, "VW": a_vw, "VWg": a_vw_g, "B": b931, "book": book})
        paths = M.bootstrap(len(days), 2000, seed=77)
        plans = {"E1 RS + 09:31 (guard)": ("RSg", "B"), "E2 RS alone": ("RS",), "E3 VWAP10 alone": ("VW",),
                 "E4 09:31 alone": ("B",), "E5 VWAP10 + 09:31 (guard)": ("VWg", "B")}
        print(f"--- {lab}: 24-month cash per seat (evaluation fees included) | evaluations bought | share of days in evaluation")
        base = None
        for name, accts in plans.items():
            out = [seat([days[i] for i in p], accts) for p in paths]
            cash = [c for c, _, _ in out]
            base = base or cash
            dd = [a - b for a, b in zip(cash, base)]
            print(f"   {name:<26} ${st.mean(cash):7,.0f} ({st.mean(dd):+6,.0f}) | {st.mean(e for _, e, _ in out):4.1f} | "
                  f"{st.mean(x for _, _, x in out) / 504 * 100:4.1f}%")


if __name__ == "__main__":
    main()
