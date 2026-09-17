# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# GC First-5min-candle + 12EMA direction + trailing stop.
# 2018-2025. 5min bars.
#
# Setup:
#   - At the FIRST 5min bar of RTH each day (9:30 ET), enter at bar close.
#   - LONG if close > EMA12 else SHORT.
#   - Initial SL: low of entry candle (long) / high of entry candle (short).
#   - Trailing stop: each subsequent bar, if bar low > current stop -> raise
#     stop to bar low. For short: bar high < current stop -> lower stop to
#     bar high. Never move stop against position.
#   - Exit: when NEXT bar's low <= stop (long) / high >= stop (short), exit
#     at stop price. Or EOD 15:59 ET flat.
#
# Emit per trade:
#   FCET,date,dir,entry_px,init_sl,exit_px,exit_reason,pnl,mfe,mae,bars
#     exit_reason: T (trailing stop hit), E (EOD)

TF_MIN = 5
EMA_LEN = 12
RTH_START_ET = 9 * 60 + 30   # 09:30
RTH_END_ET   = 16 * 60 - 1   # 15:59


class GCFirstCandleEMATrail(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Metals.Gold, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 180)
        self.future = f
        self.cont = f.Symbol
        self.n_tags = 0
        # 5min bar builder
        self.bar_o = None; self.bar_h = None; self.bar_l = None
        self.bar_c = None; self.bar_v = 0.0; self.bar_start = None
        # EMA state
        self.ema = None
        self.k = 2.0 / (EMA_LEN + 1)
        # daily state
        self.cur_date = None
        self.first_bar_done = False
        self.trade = None

    def _bucket_start(self, t):
        m = (t.minute // TF_MIN) * TF_MIN
        return t.replace(minute=m, second=0, microsecond=0)

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        bs = self._bucket_start(t)
        if self.bar_start != bs:
            if self.bar_o is not None:
                self._on_bar({
                    'o': self.bar_o, 'h': self.bar_h, 'l': self.bar_l,
                    'c': self.bar_c, 't': self.bar_start})
            self.bar_o = bar.Open; self.bar_h = bar.High
            self.bar_l = bar.Low;  self.bar_c = bar.Close
            self.bar_v = bar.Volume; self.bar_start = bs
        else:
            self.bar_h = max(self.bar_h, bar.High)
            self.bar_l = min(self.bar_l, bar.Low)
            self.bar_c = bar.Close

    def _on_bar(self, b):
        # ET time-of-day
        et = b['t'].astimezone(pytz.timezone("America/New_York")) if hasattr(b['t'], 'astimezone') else None
        # We can approximate: use UTC + subtract 5 (EST) or 4 (EDT). Cleaner: use hour/minute of ET directly.
        # QC's self.Time is in algorithm timezone (default NY). Use the raw bar time as ET-ish.
        et_min = b['t'].hour * 60 + b['t'].minute  # b['t'] is UTC in our slice; but we track in QC timezone
        # In QC, default TimeZone is NY (America/New_York). So b['t'].hour is ET already.
        d = b['t'].date()

        # daily rollover
        if self.cur_date != d:
            # force-close any open trade at prev day close (rare edge)
            if self.trade is not None:
                pnl = self.trade['dir'] * (b['c'] - self.trade['entry_px'])
                self._emit(f"FCET,{self.cur_date.strftime('%Y-%m-%d')},{self.trade['dir']},"
                           f"{self.trade['entry_px']:.2f},{self.trade['init_sl']:.2f},{b['c']:.2f},"
                           f"E,{pnl:.2f},{self.trade['mfe']:.2f},{self.trade['mae']:.2f},{self.trade['bars']}")
                self.trade = None
            self.cur_date = d
            self.first_bar_done = False

        # update EMA (regardless of RTH — but only use it during RTH for entry)
        if self.ema is None:
            self.ema = b['c']
        else:
            self.ema = b['c'] * self.k + self.ema * (1 - self.k)

        in_rth = RTH_START_ET <= et_min <= RTH_END_ET
        is_eod = et_min >= RTH_END_ET

        if not in_rth:
            return

        # ---- active trade: trail management ----
        if self.trade is not None:
            tr = self.trade
            tr['bars'] += 1
            # update MFE/MAE
            if tr['dir'] == 1:
                tr['mfe'] = max(tr['mfe'], b['h'] - tr['entry_px'])
                tr['mae'] = min(tr['mae'], b['l'] - tr['entry_px'])
                # check stop hit FIRST (on this bar's low)
                if b['l'] <= tr['stop']:
                    ex_px = tr['stop']
                    pnl = ex_px - tr['entry_px']
                    self._emit(f"FCET,{d.strftime('%Y-%m-%d')},1,{tr['entry_px']:.2f},"
                               f"{tr['init_sl']:.2f},{ex_px:.2f},T,{pnl:.2f},{tr['mfe']:.2f},{tr['mae']:.2f},{tr['bars']}")
                    self.trade = None
                else:
                    # raise stop if this bar's low is higher
                    if b['l'] > tr['stop']:
                        tr['stop'] = b['l']
                    # EOD flat
                    if is_eod:
                        pnl = b['c'] - tr['entry_px']
                        self._emit(f"FCET,{d.strftime('%Y-%m-%d')},1,{tr['entry_px']:.2f},"
                                   f"{tr['init_sl']:.2f},{b['c']:.2f},E,{pnl:.2f},{tr['mfe']:.2f},{tr['mae']:.2f},{tr['bars']}")
                        self.trade = None
            else:  # short
                tr['mfe'] = max(tr['mfe'], tr['entry_px'] - b['l'])
                tr['mae'] = min(tr['mae'], tr['entry_px'] - b['h'])
                if b['h'] >= tr['stop']:
                    ex_px = tr['stop']
                    pnl = tr['entry_px'] - ex_px
                    self._emit(f"FCET,{d.strftime('%Y-%m-%d')},-1,{tr['entry_px']:.2f},"
                               f"{tr['init_sl']:.2f},{ex_px:.2f},T,{pnl:.2f},{tr['mfe']:.2f},{tr['mae']:.2f},{tr['bars']}")
                    self.trade = None
                else:
                    if b['h'] < tr['stop']:
                        tr['stop'] = b['h']
                    if is_eod:
                        pnl = tr['entry_px'] - b['c']
                        self._emit(f"FCET,{d.strftime('%Y-%m-%d')},-1,{tr['entry_px']:.2f},"
                                   f"{tr['init_sl']:.2f},{b['c']:.2f},E,{pnl:.2f},{tr['mfe']:.2f},{tr['mae']:.2f},{tr['bars']}")
                        self.trade = None

        # ---- first bar of RTH: entry ----
        if not self.first_bar_done and et_min == RTH_START_ET and self.trade is None:
            self.first_bar_done = True
            if self.ema is not None:
                if b['c'] > self.ema:
                    self.trade = {'dir': 1, 'entry_px': b['c'], 'init_sl': b['l'],
                                  'stop': b['l'], 'bars': 0, 'mfe': 0.0, 'mae': 0.0}
                elif b['c'] < self.ema:
                    self.trade = {'dir': -1, 'entry_px': b['c'], 'init_sl': b['h'],
                                  'stop': b['h'], 'bars': 0, 'mfe': 0.0, 'mae': 0.0}

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
