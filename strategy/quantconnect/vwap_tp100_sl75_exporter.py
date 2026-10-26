# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# Win-rate experiment: finalni VWAP konfigurace (pasmo 20 bps, gap 25,
# trend 60, 1. obchod dne od 9:31) s obracenym RR: TP 16.5 b / SL 75 b.
# Ocekavani: mechanicka nahodna baze = 75/(75+16.5) ~ 82 % vyher; merime,
# kolik prida edge strategie. Exit: bracket intrabar, jinak EOD 16:00 close.
# Tag: VT,date,dir,entry,outcome(T/S/E/A),pnl_pts
#   A = ambiguozni bar (TP i SL v jedne minute) -> pocitano konzervativne jako SL

BAND = 0.002
TP_PTS = 100.0
SL_PTS = 75.0
GAP_PCT = 25.0
TREND_PCT = 60.0


class NQVwapTp100Sl75(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        self.cur_date = None
        self.prev_day = None
        self.gap_hist = deque(maxlen=250)
        self.trend_hist = deque(maxlen=250)
        self.n_tags = 0
        self._reset_day()

    def _reset_day(self):
        self.cpv = 0.0
        self.cv = 0.0
        self.pos = 0
        self.entry = 0.0
        self.traded = False
        self.gap_ok = True
        self.trend_ok = True
        self.d_open = None
        self.d_high = None
        self.d_low = None
        self.d_close = None

    @staticmethod
    def _rank(hist, v):
        if len(hist) < 60 or v is None:
            return None
        n = 0
        for x in hist:
            if x <= v:
                n += 1
        return 100.0 * n / len(hist)

    def _compute_gates(self, today_open):
        if self.prev_day is not None:
            po, ph, pl, pc = self.prev_day
            ytr = abs(pc - po) / (ph - pl) if ph > pl else None
            r = self._rank(self.trend_hist, ytr)
            self.trend_ok = True if r is None else (r <= TREND_PCT)
            if ytr is not None:
                self.trend_hist.append(ytr)
            gap = abs(today_open / pc - 1.0) if pc > 0 else None
            r = self._rank(self.gap_hist, gap)
            self.gap_ok = True if r is None else (r >= GAP_PCT)
            if gap is not None:
                self.gap_hist.append(gap)

    def _emit(self, date, direction, outcome, pnl):
        tag = f"VT,{date.strftime('%Y-%m-%d')},{direction},{self.entry:.2f},{outcome},{pnl:.2f}"
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail {date}: {e}")

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        d = t.date()
        if self.cur_date is None:
            self.cur_date = d
        if d != self.cur_date:
            if self.d_open is not None:
                self.prev_day = (self.d_open, self.d_high, self.d_low, self.d_close)
            self.cur_date = d
            self._reset_day()

        mend = t.hour * 60 + t.minute
        if not (571 <= mend <= 960):
            return
        if self.d_open is None:
            self.d_open, self.d_high, self.d_low = bar.Open, bar.High, bar.Low
            self._compute_gates(bar.Open)
        self.d_high = max(self.d_high, bar.High)
        self.d_low = min(self.d_low, bar.Low)
        self.d_close = bar.Close

        hlc3 = (bar.High + bar.Low + bar.Close) / 3.0
        self.cpv += hlc3 * float(bar.Volume)
        self.cv += float(bar.Volume)
        if self.cv <= 0:
            return
        vwap = self.cpv / self.cv
        up, dn = vwap * (1 + BAND), vwap * (1 - BAND)

        # sprava otevrene pozice (bar PO vstupnim baru)
        if self.pos != 0:
            if self.pos == 1:
                hit_tp = bar.High >= self.entry + TP_PTS
                hit_sl = bar.Low <= self.entry - SL_PTS
            else:
                hit_tp = bar.Low <= self.entry - TP_PTS
                hit_sl = bar.High >= self.entry + SL_PTS
            if hit_tp and hit_sl:
                self._emit(d, self.pos, "A", -SL_PTS)   # konzervativne SL
                self.pos = 0
            elif hit_sl:
                self._emit(d, self.pos, "S", -SL_PTS)
                self.pos = 0
            elif hit_tp:
                self._emit(d, self.pos, "T", TP_PTS)
                self.pos = 0
            elif mend == 960:
                self._emit(d, self.pos, "E", self.pos * (bar.Close - self.entry))
                self.pos = 0

        if mend == 960 or mend < 572:
            return
        if self.pos == 0 and not self.traded and self.gap_ok and self.trend_ok:
            if bar.Close > up:
                self.pos, self.entry, self.traded = 1, bar.Close, True
            elif bar.Close < dn:
                self.pos, self.entry, self.traded = -1, bar.Close, True

    def OnEndOfAlgorithm(self):
        self.Log(f"VT165_TAGS={self.n_tags}")
