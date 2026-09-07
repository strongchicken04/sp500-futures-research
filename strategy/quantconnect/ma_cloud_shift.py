# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion

# MA "cloud" SHIFT test - three variants, NQ 1-min RTH, 2018-2025.
#
# Variant A: HMA cross         fast=HMA(9)  slow=HMA(21)
# Variant B: SSL Channel       upper=SMA(high,10)  lower=SMA(low,10)
#                              close > upper -> +1, close < lower -> -1
# Variant C: EMA cross         fast=EMA(9)  slow=EMA(21)
#
# For each variant separately:
#   - state reset at RTH open (9:30 ET). MAs warm up on RTH bars only.
#   - trade opens on the bar where trend flips (long if fast>slow after
#     being <=, short if fast<slow after being >=). Entry = close of
#     flip bar.
#   - trade closes at the NEXT opposite flip (exit = close of flip bar)
#   - at 15:59 ET, force flat at close.
#
# Emit per trade:
#   MC,variant,date,dir,entry_min,entry_px,exit_min,exit_px,exit_reason,pnl
#     variant   = A / B / C
#     dir       = +1 / -1
#     entry_min = minute-of-day (bar-open time) of entry
#     exit_min  = minute-of-day of exit
#     exit_reason = "F" (opposite flip) / "E" (EOD close)
#     pnl in points, no cost applied here

HMA_FAST = 9
HMA_SLOW = 21
SSL_LEN  = 10
EMA_FAST = 9
EMA_SLOW = 21


def wma(vals, w_from_1):
    """weighted moving average, weights 1..n applied to newest last."""
    n = len(vals)
    if n < len(w_from_1):
        return None
    ws = w_from_1
    tot = sum(ws)
    s = 0.0
    # newest last -> weight = n
    for i in range(len(ws)):
        s += vals[-len(ws) + i] * ws[i]
    return s / tot


def _wma(series, length):
    n = len(series)
    if n < length:
        return None
    s = 0.0
    denom = 0
    for i in range(length):
        w = i + 1
        s += series[n - length + i] * w
        denom += w
    return s / denom


def hma(series, length):
    """Hull MA: wma(2*wma(x,n/2) - wma(x,n), sqrt(n))"""
    half = max(1, length // 2)
    root = max(1, int(math.sqrt(length)))
    a = _wma(series, half)
    b = _wma(series, length)
    if a is None or b is None:
        return None
    # build a mini series of 2a - b over the last `root` observations.
    # We approximate by recomputing on the last `root` snapshots we
    # keep externally. In this exporter we keep raw closes and rebuild.
    if len(series) < length + root - 1:
        return None
    inner = []
    for shift in range(root - 1, -1, -1):
        sub = series[:len(series) - shift]
        aa = _wma(sub, half)
        bb = _wma(sub, length)
        if aa is None or bb is None:
            return None
        inner.append(2.0 * aa - bb)
    return _wma(inner, root)


class NQMACloud(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        self.n_tags = 0
        self.cur_date = None
        self._reset_day()

    def _reset_day(self):
        self.closes = deque(maxlen=64)
        self.highs  = deque(maxlen=32)
        self.lows   = deque(maxlen=32)
        # per variant: prior trend sign, open trade dict, day aggregates
        self.st = {"A": {"trend": 0, "trade": None, "n": 0, "w": 0, "l": 0,
                          "pnl": 0.0, "sq": 0.0, "abspnl": 0.0},
                   "B": {"trend": 0, "trade": None, "n": 0, "w": 0, "l": 0,
                          "pnl": 0.0, "sq": 0.0, "abspnl": 0.0},
                   "C": {"trend": 0, "trade": None, "n": 0, "w": 0, "l": 0,
                          "pnl": 0.0, "sq": 0.0, "abspnl": 0.0}}
        self.rth_open = None
        self.emitted_today = False

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def _record_pnl(self, variant, pnl):
        st = self.st[variant]
        st["n"] += 1
        st["pnl"] += pnl
        st["sq"] += pnl * pnl
        st["abspnl"] += abs(pnl)
        if pnl > 0:
            st["w"] += 1
        elif pnl < 0:
            st["l"] += 1

    def _flip(self, variant, new_trend, mend, px):
        """Close existing trade (if any) and open a new one in new_trend."""
        st = self.st[variant]
        if st["trade"] is not None:
            tr = st["trade"]
            pnl = tr["dir"] * (px - tr["entry"])
            self._record_pnl(variant, pnl)
            st["trade"] = None
        if new_trend != 0:
            st["trade"] = dict(dir=new_trend, entry=px, entry_min=mend)
        st["trend"] = new_trend

    def _force_eod(self, variant, mend, px):
        st = self.st[variant]
        if st["trade"] is not None:
            tr = st["trade"]
            pnl = tr["dir"] * (px - tr["entry"])
            self._record_pnl(variant, pnl)
            st["trade"] = None
        # emit daily summary tag: one per variant per day
        self._emit(f"MD,{variant},{self.cur_date.strftime('%Y-%m-%d')},"
                   f"{st['n']},{st['w']},{st['l']},{st['pnl']:.2f},"
                   f"{st['sq']:.2f},{st['abspnl']:.2f}")

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return

        t = self.Time
        d = t.date()
        mend = t.hour * 60 + t.minute

        if self.cur_date is None:
            self.cur_date = d
        elif d != self.cur_date:
            # emit any leftover trades from previous day as EOD (rare)
            self._reset_day()
            self.cur_date = d

        # RTH only: 9:30-16:00 ET (mend 570..960 on bar-open time)
        if not (570 <= mend <= 959):
            return

        # first RTH bar of the day -> record open, start MA history fresh
        if self.rth_open is None:
            self.rth_open = bar.Open

        self.closes.append(bar.Close)
        self.highs.append(bar.High)
        self.lows.append(bar.Low)

        c = bar.Close
        m_now = mend

        # ---- Variant A: HMA cross ----
        fast_a = hma(list(self.closes), HMA_FAST)
        slow_a = hma(list(self.closes), HMA_SLOW)
        if fast_a is not None and slow_a is not None:
            new = 1 if fast_a > slow_a else (-1 if fast_a < slow_a else 0)
            if new != 0 and new != self.st["A"]["trend"]:
                self._flip("A", new, m_now, c)

        # ---- Variant B: SSL Channel ----
        if len(self.highs) >= SSL_LEN and len(self.lows) >= SSL_LEN:
            hi_avg = sum(list(self.highs)[-SSL_LEN:]) / SSL_LEN
            lo_avg = sum(list(self.lows)[-SSL_LEN:]) / SSL_LEN
            new = self.st["B"]["trend"]
            if c > hi_avg:
                new = 1
            elif c < lo_avg:
                new = -1
            if new != 0 and new != self.st["B"]["trend"]:
                self._flip("B", new, m_now, c)

        # ---- Variant C: EMA cross ----
        # streaming EMA rebuild once per bar (short lookback keeps it OK)
        if len(self.closes) >= EMA_SLOW:
            ce = list(self.closes)
            # seed with SMA of first N, then apply k
            def _ema(xs, n):
                if len(xs) < n:
                    return None
                k = 2.0 / (n + 1)
                e = sum(xs[:n]) / n
                for x in xs[n:]:
                    e = x * k + e * (1 - k)
                return e
            fast_c = _ema(ce, EMA_FAST)
            slow_c = _ema(ce, EMA_SLOW)
            if fast_c is not None and slow_c is not None:
                new = 1 if fast_c > slow_c else (-1 if fast_c < slow_c else 0)
                if new != 0 and new != self.st["C"]["trend"]:
                    self._flip("C", new, m_now, c)

        # ---- EOD flat at 15:59 (mend == 959) ----
        if mend == 959:
            for v in ("A", "B", "C"):
                self._force_eod(v, m_now, c)
            self.emitted_today = True

    def OnEndOfAlgorithm(self):
        self.Log(f"MC_TAGS={self.n_tags}")
