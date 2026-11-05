# region imports
from AlgorithmImports import *
import math
import numpy as np
import pandas as pd
# endregion
#
# WEEKLY "BELOW A LEVEL, THEN A STRONG BULLISH WEEK" BUY SIGNAL (owner
# 2026-11-05: in the video the BUY is not printed when price falls below a
# level; it comes after price has been below a level AND a strong bullish
# weekly candle closes - strength / volume - so it catches the bottom).
# Computed INSIDE QuantConnect from daily history resampled to weeks (Friday);
# only aggregates and per-signal returns are returned. Rules fixed before
# results.
#
# Assets SPY, QQQ (adjusted, 1999-2026). Zones (true in the signal week or in
# one of the 3 weeks before):
#   Z50  the week's low below the 50-week SMA (yellow line)
#   ZDD  the week's low >= 10% below the 52-week high close
#   Z200 the week's low within 3% of the 200-week SMA (red line) or below it
# Trigger = the signal week's candle:
#   T0  none: the first week the zone is touched (blind dip buy, baseline)
#   T1  bullish: close > open and close in the top 40% of the week's range
#   T2  T1 and volume >= 1.2 x the 20-week mean volume
#   T3  close above the previous week's high (reversal / engulfing)
#   T4  hammer: lower wick >= 2 x body, close in the top 40% of the range
#   T5  T1 and range >= 1.2 x the 10-week mean range (a strong candle)
# After a signal the same zone/trigger waits 13 weeks (one signal per dip).
# Entry at the signal week's close. Metrics: n, share positive and mean return
# after 13 / 26 / 52 weeks, BOTTOM = share of signals whose week low is not
# broken by a weekly close in the next 26 weeks, worst drawdown from the entry
# within 52 weeks; baseline: all weeks (unconditional 13 / 26 / 52-week return).
# v2: Z50 / ZDD signals from week 52 (v1 started at week 200 for all zones and
# missed 2000-02). BOTTOM is biased up for any trigger that waits for a bullish
# candle (random-walk check in results/weekly_reversal_null.txt).
# Verdict (fixed): a trigger "catches bottoms" only if BOTTOM and the 26- and
# 52-week mean returns beat T0 of the same zone in BOTH assets.

START = (1999, 1, 1)
ZONES = ("Z50", "ZDD", "Z200")
TRIG = ("T0", "T1", "T2", "T3", "T4", "T5")


def weekly(h):
    df = h[["open", "high", "low", "close", "volume"]].copy()
    if isinstance(df.index, pd.MultiIndex):
        df.index = df.index.get_level_values(-1)
    df.index = pd.to_datetime(df.index)
    w = df.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    return w


def signals(w):
    o, h, l, c, v = (w[k].values.astype(float) for k in ("open", "high", "low", "close", "volume"))
    n = len(c)
    s50 = pd.Series(c).rolling(50).mean().values
    s200 = pd.Series(c).rolling(200).mean().values
    hi52 = pd.Series(c).rolling(52, min_periods=1).max().values
    v20 = pd.Series(v).rolling(20).mean().shift(1).values
    rng = h - l
    r10 = pd.Series(rng).rolling(10).mean().shift(1).values
    zone = {"Z50": l < s50, "ZDD": l <= hi52 * 0.9, "Z200": l <= s200 * 1.03}
    clv = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1), 0.5)
    body = np.abs(c - o)
    lw = np.minimum(o, c) - l
    t1 = (c > o) & (clv >= 0.6)
    trig = {"T1": t1, "T2": t1 & (v >= 1.2 * v20), "T3": np.r_[False, c[1:] > h[:-1]],
            "T4": (lw >= 2 * body) & (clv >= 0.6), "T5": t1 & (rng >= 1.2 * r10)}
    out = {}
    for z in ZONES:
        zz = np.nan_to_num(zone[z].astype(float)) > 0
        recent = np.array([zz[max(0, i - 3):i + 1].any() for i in range(n)])
        for t in TRIG:
            sig = []
            last = -999
            prev_in = False
            for i in range(200 if z == "Z200" else 52, n - 1):     # v2: Z50 / ZDD from 1 year (2000-02 included)
                if i - last < 13:
                    prev_in = zz[i]
                    continue
                if t == "T0":
                    ok = zz[i] and not prev_in
                else:
                    ok = recent[i] and trig[t][i]
                prev_in = zz[i]
                if ok:
                    sig.append(i)
                    last = i
            out[(z, t)] = sig
    return out, c, l


def stats(sig, c, l, dates):
    n = len(c)
    rows = []
    for i in sig:
        f = {}
        for k in (13, 26, 52):
            f[k] = c[i + k] / c[i] - 1 if i + k < n else None
        held = all(c[j] >= l[i] for j in range(i + 1, min(n, i + 27))) if i + 1 < n else None
        mae = min(c[i + 1:min(n, i + 53)] / c[i] - 1) if i + 1 < n else 0.0
        rows.append((i, f, held, mae))
    return rows


class WeeklyReversalInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2026, 10, 26)
        self.set_end_date(2026, 11, 5)
        self.set_cash(100000)
        self.syms = {k: self.add_equity(k, Resolution.DAILY).symbol for k in ("SPY", "QQQ")}

    def on_end_of_algorithm(self):
        for k, s in self.syms.items():
            h = self.history(s, datetime(*START), self.time, Resolution.DAILY)
            if h is None or len(h) < 2000:
                self.set_runtime_statistic(f"WR {k}", "no history")
                continue
            w = weekly(h)
            dates = [str(x)[:10] for x in w.index]
            sig, c, l = signals(w)
            n = len(c)
            base = {kk: np.mean([c[i + kk] / c[i] - 1 for i in range(52, n - kk)]) * 100 for kk in (13, 26, 52)}
            base_pos = {kk: np.mean([c[i + kk] > c[i] for i in range(52, n - kk)]) * 100 for kk in (13, 26, 52)}
            self.set_runtime_statistic(f"WR {k} info", f"{dates[0]}..{dates[-1]} weeks {n}; all weeks 13/26/52w: "
                                       f"{base[13]:+.1f}/{base[26]:+.1f}/{base[52]:+.1f}% pos {base_pos[13]:.0f}/{base_pos[26]:.0f}/{base_pos[52]:.0f}%")
            for z in ZONES:
                cells = []
                for t in TRIG:
                    rows = stats(sig[(z, t)], c, l, dates)
                    if not rows:
                        cells.append(f"{t}:0")
                        continue
                    def m(kk):
                        v = [r[1][kk] for r in rows if r[1][kk] is not None]
                        return (np.mean(v) * 100, np.mean(np.array(v) > 0) * 100) if v else (0.0, 0.0)
                    b = [r[2] for r in rows if r[2] is not None]
                    cells.append(f"{t}:{len(rows)} b{np.mean(b) * 100:.0f} {m(26)[0]:+.0f}/{m(52)[0]:+.0f}% p{m(52)[1]:.0f} m{min(r[3] for r in rows) * 100:.0f}")
                self.set_runtime_statistic(f"WR {k} {z} a", " | ".join(cells[:3]))
                self.set_runtime_statistic(f"WR {k} {z} b", " | ".join(cells[3:]))
            for z, t in (("Z50", "T2"), ("Z50", "T5")):
                rows = stats(sig[(z, t)], c, l, dates)
                txt = " ".join(f"{dates[i][:7]} {('%+.0f' % (f[52] * 100)) if f[52] is not None else 'na'}%{'' if held else '!'}" for i, f, held, mae in rows)
                for part in range(0, min(len(txt), 380), 190):
                    self.set_runtime_statistic(f"WR {k} list {z}{t} {part // 190}", txt[part:part + 190])
