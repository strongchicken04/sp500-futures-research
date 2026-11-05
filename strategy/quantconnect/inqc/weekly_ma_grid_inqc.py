# region imports
from AlgorithmImports import *
import numpy as np
import pandas as pd
# endregion
#
# ROBUSTNESS OF THE WEEKLY DIP-BUY PATTERN TO THE (UNKNOWN) LINE DEFINITION
# (owner 2026-11-05: "are you sure the lines are SMAs?"). The video's indicator
# ("TradeX TimeSeries Momentum tripl...") is not public; its yellow line looks
# like a 20-40-week average, the red one like a 100-200-week average, purple =
# all-time high. Grid fixed before results: yellow = SMA or EMA of 20 / 30 / 40 /
# 50 weeks; zone A = the week's low below yellow (now or in the 3 weeks before),
# zone B = A and the close above the red line (SMA / EMA 200w, same type);
# trigger T0 (first week in the zone), T1 (bullish close in the top 40% of the
# range), T5 (T1 and range >= 1.2 x the 10-week mean); 13-week cooldown; entry at
# the week's close. Per cell: signals, mean 52-week return, share positive, and
# the signals in the two bear markets (2000-03..2003-03, 2007-10..2009-03): count
# and mean 52-week return. SPY / QQQ adjusted 1999-2026 (zone B from 2003: the
# 200-week line needs 4 years). Aggregates only.

START = (1999, 1, 1)


def weekly(h):
    df = h[["open", "high", "low", "close", "volume"]].copy()
    if isinstance(df.index, pd.MultiIndex):
        df.index = df.index.get_level_values(-1)
    df.index = pd.to_datetime(df.index)
    return df.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()


def ma(x, n, typ):
    s = pd.Series(x)
    return (s.rolling(n).mean() if typ == "SMA" else s.ewm(span=n, adjust=False, min_periods=n).mean()).values


def bear(d):
    return ("2000-03" <= d < "2003-04") or ("2007-10" <= d < "2009-04")


class WeeklyMaGridInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2026, 10, 26)
        self.set_end_date(2026, 11, 5)
        self.set_cash(100000)
        self.syms = {k: self.add_equity(k, Resolution.DAILY).symbol for k in ("SPY", "QQQ")}

    def on_end_of_algorithm(self):
        for k, s in self.syms.items():
            w = weekly(self.history(s, datetime(*START), self.time, Resolution.DAILY))
            dates = [str(x)[:7] for x in w.index]
            o, h, l, c = (w[x].values.astype(float) for x in ("open", "high", "low", "close"))
            n = len(c)
            rng = h - l
            clv = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1), 0.5)
            r10 = pd.Series(rng).rolling(10).mean().shift(1).values
            t1 = (c > o) & (clv >= 0.6)
            trig = {"T0": None, "T1": t1, "T5": t1 & (rng >= 1.2 * np.nan_to_num(r10, nan=1e18))}
            for typ in ("SMA", "EMA"):
                red = ma(c, 200, typ)
                for L in (20, 30, 40, 50):
                    yel = ma(c, L, typ)
                    for zn in ("A", "B"):
                        z = np.nan_to_num(l < yel, nan=0) > 0
                        if zn == "B":
                            z = z & (np.nan_to_num(c > red, nan=0) > 0)
                        recent = np.array([z[max(0, i - 3):i + 1].any() for i in range(n)])
                        cells = []
                        for t, tr in trig.items():
                            sig, last, prev = [], -999, False
                            for i in range(max(L, 52) if zn == "A" else 200, n - 1):
                                if i - last >= 13:
                                    ok = (z[i] and not prev) if tr is None else (recent[i] and tr[i])
                                    if ok:
                                        sig.append(i)
                                        last = i
                                prev = z[i]
                            f = [(c[i + 52] / c[i] - 1, dates[i]) for i in sig if i + 52 < n]
                            if not f:
                                cells.append(f"{t}:0")
                                continue
                            r = np.array([x[0] for x in f])
                            b = [x[0] for x in f if bear(x[1])]
                            cells.append(f"{t}:{len(sig)} {r.mean() * 100:+.0f}% p{np.mean(r > 0) * 100:.0f} "
                                         f"bear{len(b)}:{(np.mean(b) * 100 if b else 0):+.0f}%")
                        self.set_runtime_statistic(f"MG {k} {typ}{L} {zn}", " | ".join(cells))
            base = np.mean([c[i + 52] / c[i] - 1 for i in range(52, n - 52)]) * 100
            self.set_runtime_statistic(f"MG {k} info", f"{dates[0]}..{dates[-1]} all weeks 52w {base:+.1f}%")
