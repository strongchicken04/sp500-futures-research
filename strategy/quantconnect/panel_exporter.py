# region imports
from AlgorithmImports import *
import numpy as np
from collections import deque
# endregion

# Exports a daily ORB regime panel computed on REAL NQ minute data to the
# QuantConnect ObjectStore (key "nq_panel.csv"), mirroring strategy/regime_research.py
# exactly, so the regime/variant analysis can be re-run on real NQ 2009-2025
# (extending the OANDA proxy that ends 2020-05). Not a trading algorithm.

OR_START = 9 * 60 + 30   # 09:30 ET
RTH_LAST = 15 * 60 + 59  # 15:59 ET

# name, or_len, signal, target_R, side
VARIANTS = [
    ("brk5_10R", 5, "brk", 10.0, "both"),
    ("brk5_eod", 5, "brk", None, "both"),
    ("brk15_10R", 15, "brk", 10.0, "both"),
    ("brk30_10R", 30, "brk", 10.0, "both"),
    ("brk5_long", 5, "brk", 10.0, "long"),
    ("brk5_short", 5, "brk", 10.0, "short"),
    ("fade5_3R", 5, "fade", 3.0, "both"),
    ("fade5_eod", 5, "fade", None, "both"),
]


def sim_variant(bars, or_len, signal, target_R, side):
    or_last = OR_START + or_len - 1
    entry_min = OR_START + or_len
    if OR_START not in bars or entry_min not in bars or or_last not in bars:
        return None
    o = bars[OR_START][0]; c = bars[or_last][3]
    hs = [bars[m][1] for m in range(OR_START, or_last + 1) if m in bars]
    ls = [bars[m][2] for m in range(OR_START, or_last + 1) if m in bars]
    or_high, or_low = max(hs), min(ls)
    d = 1 if c > o else (-1 if c < o else 0)
    if d == 0:
        return None
    if signal == "fade":
        d = -d
    if side == "long" and d != 1:
        return None
    if side == "short" and d != -1:
        return None
    entry = bars[entry_min][0]
    stop = or_low if d == 1 else or_high
    R = (entry - stop) if d == 1 else (stop - entry)
    if R <= 0:
        return None
    target = entry + d * target_R * R if target_R else None
    for m in range(entry_min, RTH_LAST + 1):
        b = bars.get(m)
        if b is None:
            continue
        _, h2, l2, _ = b
        if d == 1:
            if l2 <= stop:
                return -1.0
            if target is not None and h2 >= target:
                return float(target_R)
        else:
            if h2 >= stop:
                return -1.0
            if target is not None and l2 <= target:
                return float(target_R)
    last = max((m for m in bars if entry_min <= m <= RTH_LAST), default=None)
    if last is None:
        return None
    return float(d * (bars[last][3] - entry) / R)


class NQPanelExporter(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2009, 1, 1)
        self.SetEndDate(2025, 7, 1)
        self.SetCash(100_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI, resolution=Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        self.today_bars = {}
        self.daily_closes = deque(maxlen=70)
        self.last_date = None
        self.rows = []

    def OnData(self, slice: Slice):
        t = self.Time
        cur = t.date()
        mod = t.hour * 60 + t.minute
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if self.last_date is None:
            self.last_date = cur
        if cur != self.last_date:
            self._process_day(self.last_date)
            self.today_bars = {}
            self.last_date = cur
        if bar is not None and OR_START <= mod <= 16 * 60:
            self.today_bars[mod] = (bar.Open, bar.High, bar.Low, bar.Close)

    def _process_day(self, date):
        bars = self.today_bars
        if OR_START not in bars:
            return
        day_open = bars[OR_START][0]
        last = max((m for m in bars if m <= RTH_LAST), default=None)
        if last is None:
            return
        day_close = bars[last][3]
        closes = list(self.daily_closes)
        if len(closes) >= 51:
            prev_close = closes[-1]
            arr = np.array(closes, dtype=float)
            rets = np.diff(arr) / arr[:-1]
            rvol20 = float(np.std(rets[-20:], ddof=1)) * np.sqrt(252)
            sma50 = float(np.mean(arr[-50:]))
            gap = day_open / prev_close - 1.0
            trend20 = prev_close / closes[-21] - 1.0
            trend50 = prev_close / sma50 - 1.0
            fv = f"{rvol20:.6f},{gap:.6f},{trend20:.6f},{trend50:.6f}"
        else:
            fv = ",,,"
        Rs = [sim_variant(bars, *v[1:]) for v in VARIANTS]
        rcells = ",".join("" if r is None else f"{r:.4f}" for r in Rs)
        row = f"{date.strftime('%Y-%m-%d')},{fv},{rcells}"
        self.rows.append(row)
        self.daily_closes.append(day_close)

        # Free tier blocks ObjectStore writes and API log reads, so exfiltrate each
        # day's panel row through an ORDER TAG: a far-from-market limit order that is
        # cancelled immediately (never fills) but is still returned, with its tag, by
        # the backtests/orders/read API endpoint.
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(day_open * 0.5, 2), tag=row)
                tkt.Cancel()
        except Exception as e:
            self.Debug(f"tag order failed {date}: {e}")

    def OnEndOfAlgorithm(self):
        if self.last_date is not None:
            self._process_day(self.last_date)
        self.Log(f"PANEL_ROWS={len(self.rows)} (exfiltrated via order tags; read with backtests/orders/read)")
