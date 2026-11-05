# region imports
from AlgorithmImports import *
import math
import numpy as np
# endregion
#
# LONG-TERM "BUY THE BIG DROP" INVESTMENT MODEL (owner idea 2026-11-05 from a
# video: daily chart, purple = running high, yellow ~ SMA50, red ~ SMA200, BUY
# after a sharp drop below the yellow line toward the red one, a few trades per
# several years). Not a prop rule: positions are held for months (personal
# investing account). Computed INSIDE QuantConnect from daily history; only
# aggregates and per-trade returns (no prices) are returned. Rules fixed
# before results.
#
# Assets: QQQ (Nasdaq-100, from 1999) and SPY (S&P 500), adjusted daily
# closes (dividends included). Fills at the signal day's close; no costs (a
# few trades). One position at a time; a new trade needs a new 252-day high
# close after the last entry (one trade per drawdown episode).
# Entry: drawdown from the 252-day high close >= D (8 / 10 / 15 / 20 / 30%);
#   filter ANY (none) or UP (SMA200 today > SMA200 20 days ago = long-term
#   uptrend still intact); trigger NOW (the close that reaches D) or CONF
#   (first close above the highest close of the 5 days before, once D was
#   reached in the episode).
# Exit: HIGH = back to the 252-day high at entry (the purple line); Y1 = after
#   252 trading days; HS = HIGH, or a -20% stop from the entry price.
# LADDER (own idea for big drops): 1/3 at -10%, 1/3 at -20%, 1/3 at -30% from
#   the 252-day high, all out at that high (return on the deployed capital).
# Metrics per variant: trades, win %, mean / worst trade %, worst drawdown
#   inside a trade (MAE), median days held, time in market, CAGR of the model
#   (cash earns 0%) vs buy-and-hold, model max drawdown. Main variant (trade
#   list printed): D 10%, UP, CONF, HIGH; plus D 20%, ANY, NOW, HIGH.

START = (1999, 1, 1)
DS = (0.08, 0.10, 0.15, 0.20, 0.30)


def rolling_high(c):
    import pandas as pd
    return pd.Series(c).rolling(252, min_periods=1).max().values


def run(c, d, filt, trig, ex, sma200, roll):
    n = len(c)
    trades = []
    pos = None
    armed = True
    reached = False
    eq, peak, mdd = 1.0, 1.0, 0.0
    inmkt = 0
    for i in range(252, n):
        if pos is not None:
            inmkt += 1
            r = c[i] / c[i - 1]
            eq *= r
            pos["mae"] = min(pos["mae"], c[i] / pos["e"] - 1)
            out = False
            if ex in ("HIGH", "HS") and c[i] >= pos["tgt"]:
                out = True
            if ex == "HS" and c[i] <= pos["e"] * 0.8:
                out = True
            if ex == "Y1" and i - pos["i"] >= 252:
                out = True
            if out:
                trades.append((pos["i"], i, c[i] / pos["e"] - 1, pos["mae"]))
                pos = None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if c[i] >= roll[i] and pos is None:
            armed, reached = True, False
        if pos is None and armed:
            dd = c[i] / roll[i] - 1
            ok = True
            if filt == "UP":
                ok = sma200[i] is not None and sma200[i - 20] is not None and sma200[i] > sma200[i - 20]
            if dd <= -d:
                reached = True
            go = False
            if trig == "NOW" and dd <= -d and ok:
                go = True
            if trig == "CONF" and reached and ok and c[i] > c[i - 5:i].max() and dd < 0:
                go = True
            if go:
                pos = {"i": i, "e": c[i], "tgt": roll[i], "mae": 0.0}
                armed = False
    if pos is not None:
        trades.append((pos["i"], n - 1, c[-1] / pos["e"] - 1, pos["mae"]))
    return trades, eq, mdd, inmkt / max(1, n - 252)


def ladder(c, roll):
    n = len(c)
    out = []
    cur = None
    for i in range(252, n):
        if cur is None and c[i] <= roll[i] * 0.9:
            cur = {"i": i, "tgt": roll[i], "buys": [], "mae": 0.0}
        if cur is not None:
            for lv in (0.9, 0.8, 0.7):
                if len(cur["buys"]) < round((1 - lv) * 10) and c[i] <= cur["tgt"] * lv:
                    cur["buys"].append(c[i])
            avg = len(cur["buys"]) / sum(1.0 / b for b in cur["buys"])
            cur["mae"] = min(cur["mae"], c[i] / avg - 1)
            if c[i] >= cur["tgt"]:
                out.append((cur["i"], i, c[i] / avg - 1, cur["mae"], len(cur["buys"])))
                cur = None
    if cur is not None:
        avg = len(cur["buys"]) / sum(1.0 / b for b in cur["buys"])
        out.append((cur["i"], n - 1, c[-1] / avg - 1, cur["mae"], len(cur["buys"])))
    return out


class DipInvestInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2026, 1, 2)
        self.set_end_date(2026, 1, 5)
        self.set_cash(100000)
        self.syms = {k: self.add_equity(k, Resolution.DAILY).symbol for k in ("QQQ", "SPY")}

    def on_end_of_algorithm(self):
        for k, s in self.syms.items():
            h = self.history(s, datetime(*START), datetime(2026, 12, 31), Resolution.DAILY)
            if h is None or len(h) < 600:
                self.set_runtime_statistic(f"DI {k}", "no history")
                continue
            closes = h["close"].values.astype(float)
            idx = h.index.get_level_values(-1) if hasattr(h.index, "levels") else h.index
            dates = [str(x)[:10] for x in idx]
            n = len(closes)
            yrs = (n - 252) / 252.0
            sma = [None] * n
            cs = np.cumsum(np.insert(closes, 0, 0.0))
            for i in range(199, n):
                sma[i] = (cs[i + 1] - cs[i - 199]) / 200.0
            bh = closes[-1] / closes[252]
            RH = rolling_high(closes)
            roll = closes[max(0, n - 252):].max()
            self.set_runtime_statistic(f"DI {k} info", f"{dates[0]}..{dates[-1]} n{n} B&H x{bh:.2f} CAGR {(bh ** (1 / yrs) - 1) * 100:.1f}% "
                                       f"now dd {(closes[-1] / roll - 1) * 100:.1f}% vs SMA200 {(closes[-1] / sma[-1] - 1) * 100:+.1f}%")
            for d in DS:
                cells = []
                for filt in ("ANY", "UP"):
                    for trig in ("NOW", "CONF"):
                        for ex in ("HIGH", "Y1", "HS"):
                            tr, eq, mdd, tim = run(closes, d, filt, trig, ex, sma, RH)
                            if not tr:
                                cells.append(f"{filt[0]}{trig[0]}{ex[0]}:0")
                                continue
                            rr = [t[2] for t in tr]
                            cagr = (eq ** (1 / yrs) - 1) * 100
                            cells.append(f"{filt[0]}{trig[0]}{ex[0]}:{len(tr)} w{np.mean(np.array(rr) > 0) * 100:.0f} "
                                         f"{np.mean(rr) * 100:+.0f}% m{min(t[3] for t in tr) * 100:.0f} c{cagr:.1f} dd{mdd * 100:.0f} t{tim * 100:.0f}")
                for part in range(0, len(cells), 3):
                    self.set_runtime_statistic(f"DI {k} D{int(d * 100)} {part // 3}", " | ".join(cells[part:part + 3]))
            for lab, (d, filt, trig, ex) in (("main", (0.10, "UP", "CONF", "HIGH")), ("d20", (0.20, "ANY", "NOW", "HIGH")),
                                             ("d15hs", (0.15, "ANY", "CONF", "HS"))):
                tr, eq, mdd, tim = run(closes, d, filt, trig, ex, sma, RH)
                txt = " ".join(f"{dates[a][:7]}>{dates[b][:7]} {r * 100:+.0f}% m{m * 100:.0f}" for a, b, r, m in tr)
                for part in range(0, len(txt), 190):
                    self.set_runtime_statistic(f"DI {k} trades {lab} {part // 190}", txt[part:part + 190])
            lt = ladder(closes, RH)
            txt = " ".join(f"{dates[a][:7]}>{dates[b][:7]} {r * 100:+.0f}% m{m * 100:.0f} b{nb}" for a, b, r, m, nb in lt)
            for part in range(0, len(txt), 190):
                self.set_runtime_statistic(f"DI {k} ladder {part // 190}", txt[part:part + 190])
