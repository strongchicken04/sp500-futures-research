# region imports
from AlgorithmImports import *
import math
import numpy as np
import pandas as pd
# endregion
#
# LONG-HORIZON "MOMENTUM + MEAN REVERSION" INVESTING MODELS (owner 2026-11-05:
# "can we build a more precise momentum / mean-reversion model? far less noise
# than intraday and the market's drift matters"). Personal investing account,
# positions held overnight / for weeks. Computed INSIDE QuantConnect from daily
# history; aggregates only. Rules and the verdict FIXED BEFORE RESULTS.
#
# Assets SPY, QQQ adjusted daily 1999-2026. A position is set from the close
# of day t and earns the close t -> t+1 return (market-on-close at the signal);
# cost 2 bp per unit of exposure traded; cash earns 0% (conservative for every
# timing model); leverage above 1x pays 3% a year on the borrowed part.
# Models (sources):
#   BH    buy and hold
#   SMA   hold when close > SMA200, else cash (Faber 2007 / classic trend rule)
#   TSM   hold when the 252-day return > 0, checked monthly (Moskowitz, Ooi &
#         Pedersen 2012 time-series momentum)
#   RSI2  Connors: long when close > SMA200 and RSI(2) < 10, exit when close >
#         SMA5 (short-term mean reversion inside the uptrend; overnight)
#   SMA+R core SMA (1x) + 0.5x extra while an RSI2 trade is open (dip boost
#         inside the trend; max 1.5x)
#   VT    volatility target: exposure = min(1.5, 15% / 20-day realised vol),
#         only while close > SMA200 (Moreira & Muir 2017 + trend filter)
#   DIPT  dip buying ONLY in an uptrend: 1x while close > SMA200; 1.5x while the
#         drawdown from the 252-day high is >= 7% and close > SMA200 (buy the
#         dip, but never in a bear market - the failure of the weekly tests)
# Metrics: CAGR, max drawdown, Sharpe (daily, rf 0), time in market, trades a
#   year; by period 1999-2008 / 2009-2017 / 2018-2026: CAGR and Sharpe.
# Verdict: a model is BETTER than BH only if its Sharpe is higher in all three
#   periods for both assets AND its max drawdown is smaller for both assets.

START = (1999, 1, 1)
PERIODS = (("99-08", "1999", "2009"), ("09-17", "2009", "2018"), ("18-26", "2018", "2027"))


def rsi2(c):
    d = np.diff(c, prepend=c[0])
    g, l = np.maximum(d, 0), np.maximum(-d, 0)
    ag = pd.Series(g).ewm(alpha=0.5, adjust=False).mean().values
    al = pd.Series(l).ewm(alpha=0.5, adjust=False).mean().values
    return np.where(al > 0, 100 - 100 / (1 + ag / np.where(al > 0, al, 1)), 100.0)


def positions(c, dates):
    n = len(c)
    s200 = pd.Series(c).rolling(200).mean().values
    s5 = pd.Series(c).rolling(5).mean().values
    up = np.nan_to_num(c > s200, nan=0) > 0
    r = rsi2(c)
    ret1 = np.r_[0.0, c[1:] / c[:-1] - 1]
    vol20 = pd.Series(ret1).rolling(20).std().values * math.sqrt(252)
    hi252 = pd.Series(c).rolling(252, min_periods=1).max().values
    P = {k: np.zeros(n) for k in ("BH", "SMA", "TSM", "RSI2", "SMA+R", "VT", "DIPT")}
    P["BH"][:] = 1.0
    inr = False
    tsm = 0.0
    for i in range(n):
        if i < 252:
            continue
        P["SMA"][i] = 1.0 if up[i] else 0.0
        if dates[i][:7] != dates[i - 1][:7]:                   # first day of a month: re-check TSM
            tsm = 1.0 if c[i] / c[i - 252] - 1 > 0 else 0.0
        P["TSM"][i] = tsm
        if not inr and up[i] and r[i] < 10:
            inr = True
        elif inr and c[i] > s5[i]:
            inr = False
        P["RSI2"][i] = 1.0 if inr else 0.0
        P["SMA+R"][i] = P["SMA"][i] + (0.5 if inr else 0.0)
        v = vol20[i]
        P["VT"][i] = min(1.5, 0.15 / v) if (up[i] and v > 0) else 0.0
        P["DIPT"][i] = (1.5 if c[i] <= hi252[i] * 0.93 else 1.0) if up[i] else 0.0
    return P, ret1


def evaluate(pos, ret1, dates, lo=None, hi=None):
    n = len(ret1)
    idx = [i for i in range(253, n) if (lo is None or lo <= dates[i] < hi)]
    if len(idx) < 50:
        return None
    pr = []
    turn = 0.0
    for i in idx:
        p = pos[i - 1]
        x = p * ret1[i] - abs(pos[i - 1] - pos[i - 2]) * 0.0002 - max(0.0, p - 1.0) * 0.03 / 252
        turn += abs(pos[i - 1] - pos[i - 2])
        pr.append(x)
    pr = np.array(pr)
    eq = np.cumprod(1 + pr)
    yrs = len(pr) / 252.0
    cagr = (eq[-1] ** (1 / yrs) - 1) * 100
    dd = float(np.min(eq / np.maximum.accumulate(eq) - 1)) * 100
    sh = pr.mean() / pr.std() * math.sqrt(252) if pr.std() > 0 else 0.0
    tim = float(np.mean(np.array([pos[i - 1] for i in idx]) > 0)) * 100
    return cagr, dd, sh, tim, turn / yrs / 2


class TrendMrInvestInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2026, 10, 26)
        self.set_end_date(2026, 11, 5)
        self.set_cash(100000)
        self.syms = {k: self.add_equity(k, Resolution.DAILY).symbol for k in ("SPY", "QQQ")}

    def on_end_of_algorithm(self):
        for k, s in self.syms.items():
            h = self.history(s, datetime(*START), self.time, Resolution.DAILY)
            c = h["close"].values.astype(float)
            idx = h.index.get_level_values(-1) if isinstance(h.index, pd.MultiIndex) else h.index
            dates = [str(x)[:10] for x in idx]
            P, ret1 = positions(c, dates)
            self.set_runtime_statistic(f"TM {k} info", f"{dates[0]}..{dates[-1]} days {len(c)}")
            for m, pos in P.items():
                a = evaluate(pos, ret1, dates)
                per = []
                for lab, lo, hi in PERIODS:
                    e = evaluate(pos, ret1, dates, lo, hi)
                    per.append(f"{lab} c{e[0]:.1f} s{e[2]:.2f}" if e else f"{lab} -")
                self.set_runtime_statistic(f"TM {k} {m}", f"CAGR {a[0]:.1f}% DD {a[1]:.0f}% Sh {a[2]:.2f} in {a[3]:.0f}% tr/y {a[4]:.1f} | " + " ".join(per))
