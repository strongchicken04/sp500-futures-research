# region imports
from AlgorithmImports import *
from collections import deque
# endregion
#
# PROP S4: Monday afternoon weekly-trend momentum.
# Monday ONLY, after 11:00 ET: if NQ > prior Fri close AND > 50-SMA(5m)
# AND > session VWAP: enter LONG on first pullback to 20-EMA that holds
# (close back above 20-EMA after dip to it). SL = Mon low or -60pt
# whichever closer. TP = +120pt. EOD close.
#
# Tag: S4,date,entry,sl,tp,exit,reason,pnl,bars

TF_MIN = 5


class PropS4MonPm(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=False)
        f.SetFilter(0, 180)
        self.future = f
        self.cont = f.Symbol
        self.n_tags = 0
        self.bar_o = None; self.bar_h = None; self.bar_l = None
        self.bar_c = None; self.bar_start = None
        self.cur_date = None; self.day_dow = None
        self.day_low = None
        self.closes_5m = deque(maxlen=100)
        self.ema20 = None; self.k20 = 2.0 / 21
        self.vwap_pv = 0.0; self.vwap_v = 0.0
        self.prev_fri_close = None; self.last_close = None
        self.trade = None
        self.below_ema = False  # for pullback detection

    def _bs(self, t):
        m = (t.minute // TF_MIN) * TF_MIN
        return t.replace(minute=m, second=0, microsecond=0)

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None: return
        bs = self._bs(self.Time)
        if self.bar_start != bs:
            if self.bar_o is not None:
                self._on_bar({'o':self.bar_o,'h':self.bar_h,'l':self.bar_l,
                              'c':self.bar_c,'t':self.bar_start})
            self.bar_o = bar.Open; self.bar_h = bar.High
            self.bar_l = bar.Low; self.bar_c = bar.Close; self.bar_start = bs
        else:
            self.bar_h = max(self.bar_h, bar.High)
            self.bar_l = min(self.bar_l, bar.Low)
            self.bar_c = bar.Close

    def _on_bar(self, b):
        em = b['t'].hour * 60 + b['t'].minute
        d = b['t'].date()
        if self.cur_date != d:
            # if yesterday was Friday, save its close
            if self.day_dow == 4 and self.last_close is not None:
                self.prev_fri_close = self.last_close
            if self.trade is not None:
                self._close(b['c'], 'EOD_roll', b)
            self.cur_date = d
            self.day_dow = b['t'].weekday()
            self.day_low = None
            self.closes_5m.clear()
            self.vwap_pv = 0.0; self.vwap_v = 0.0
            self.below_ema = False

        in_rth = 9*60+30 <= em <= 16*60-1
        if not in_rth: return

        # update intra-RTH state
        if self.day_low is None or b['l'] < self.day_low: self.day_low = b['l']
        self.closes_5m.append(b['c'])
        hlc3 = (b['h']+b['l']+b['c'])/3.0
        self.vwap_pv += hlc3; self.vwap_v += 1.0
        vwap = self.vwap_pv / self.vwap_v
        if self.ema20 is None: self.ema20 = b['c']
        else: self.ema20 = b['c'] * self.k20 + self.ema20 * (1-self.k20)
        sma50 = sum(list(self.closes_5m)[-50:]) / min(len(self.closes_5m), 50)

        # manage trade
        if self.trade is not None:
            tr = self.trade; tr['bars'] += 1
            if b['l'] <= tr['sl']: self._close(tr['sl'], 'SL', b); return
            if b['h'] >= tr['tp']: self._close(tr['tp'], 'TP', b); return
            if em >= 15*60+55: self._close(b['c'], 'EOD', b); return

        # entry: Monday only, after 11:00 ET
        if (self.trade is None and self.day_dow == 0 and em >= 11*60 and em < 15*60
            and self.prev_fri_close is not None and len(self.closes_5m) >= 50):
            trend_ok = b['c'] > self.prev_fri_close and b['c'] > sma50 and b['c'] > vwap
            if trend_ok:
                # pullback: bar's low touches EMA20 but close back above
                if b['l'] <= self.ema20 <= b['c']:
                    sl = max(self.day_low, b['c'] - 60.0)
                    if sl >= b['c']: self.last_close = b['c']; return
                    tp = b['c'] + 120.0
                    self.trade = {'entry':b['c'],'sl':sl,'tp':tp,'bars':0,
                                  'dt': b['t'].strftime('%Y-%m-%d %H:%M')}
        self.last_close = b['c']

    def _close(self, ex, reason, b):
        tr = self.trade
        pnl = ex - tr['entry']
        self._emit(f"S4,{tr['dt']},{tr['entry']:.2f},{tr['sl']:.2f},"
                   f"{tr['tp']:.2f},{ex:.2f},{reason},{pnl:.2f},{tr['bars']}")
        self.trade = None

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px*0.5, 2), tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as e: self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
