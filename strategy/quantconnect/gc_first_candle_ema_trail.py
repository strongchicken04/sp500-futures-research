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
TRAIL_MODE = "eod_only"      # "tight" | "chandelier3" | "eod_only" (no trail, EOD flat)
DOW_FILTER = "mon_long_fri_short"   # None | "mon_long_fri_short"


class GCFirstCandleEMATrail(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
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
        self.day_open = None    # first RTH bar OPEN (for day_move computation)
        self.day_dow = None     # day-of-week 0-6
        # last 3 bar lows/highs for chandelier trail
        self.last_lows = deque(maxlen=3)
        self.last_highs = deque(maxlen=3)

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
        # QC default timezone is NY (America/New_York), so b['t'].hour is ET
        et_min = b['t'].hour * 60 + b['t'].minute
        d = b['t'].date()

        # daily rollover
        if self.cur_date != d:
            if self.trade is not None:
                pnl = self.trade['dir'] * (b['c'] - self.trade['entry_px'])
                self._emit(f"FCET,{self.cur_date.strftime('%Y-%m-%d')},{self.trade['dir']},"
                           f"{self.trade['entry_px']:.2f},{self.trade['init_sl']:.2f},{b['c']:.2f},"
                           f"E,{pnl:.2f},{self.trade['mfe']:.2f},{self.trade['mae']:.2f},{self.trade['bars']},"
                           f"0.00,{self.day_dow if self.day_dow is not None else -1}")
                self.trade = None
            self.cur_date = d
            self.first_bar_done = False
            self.day_open = None
            self.day_dow = b['t'].weekday()

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
            if tr['dir'] == 1:
                tr['mfe'] = max(tr['mfe'], b['h'] - tr['entry_px'])
                tr['mae'] = min(tr['mae'], b['l'] - tr['entry_px'])
                # SL only if trail is active (not eod_only)
                if TRAIL_MODE != "eod_only" and b['l'] <= tr['stop']:
                    ex_px = tr['stop']
                    pnl = ex_px - tr['entry_px']
                    self._emit(f"FCET,{d.strftime('%Y-%m-%d')},1,{tr['entry_px']:.2f},"
                               f"{tr['init_sl']:.2f},{ex_px:.2f},T,{pnl:.2f},{tr['mfe']:.2f},{tr['mae']:.2f},{tr['bars']}")
                    self.trade = None
                else:
                    if TRAIL_MODE == "tight":
                        cand = b['l']
                        if cand > tr['stop']: tr['stop'] = cand
                    elif TRAIL_MODE == "chandelier3":
                        lows = list(self.last_lows) + [b['l']]
                        cand = min(lows[-3:])
                        if cand > tr['stop']: tr['stop'] = cand
                    # eod_only: no trail update
                    if is_eod:
                        pnl = b['c'] - tr['entry_px']
                        day_move = (b['c'] - self.day_open) if self.day_open is not None else 0.0
                        self._emit(f"FCET,{d.strftime('%Y-%m-%d')},1,{tr['entry_px']:.2f},"
                                   f"{tr['init_sl']:.2f},{b['c']:.2f},E,{pnl:.2f},{tr['mfe']:.2f},{tr['mae']:.2f},{tr['bars']},"
                                   f"{day_move:.2f},{self.day_dow if self.day_dow is not None else -1}")
                        self.trade = None
            else:
                tr['mfe'] = max(tr['mfe'], tr['entry_px'] - b['l'])
                tr['mae'] = min(tr['mae'], tr['entry_px'] - b['h'])
                if TRAIL_MODE != "eod_only" and b['h'] >= tr['stop']:
                    ex_px = tr['stop']
                    pnl = tr['entry_px'] - ex_px
                    self._emit(f"FCET,{d.strftime('%Y-%m-%d')},-1,{tr['entry_px']:.2f},"
                               f"{tr['init_sl']:.2f},{ex_px:.2f},T,{pnl:.2f},{tr['mfe']:.2f},{tr['mae']:.2f},{tr['bars']}")
                    self.trade = None
                else:
                    if TRAIL_MODE == "tight":
                        cand = b['h']
                        if cand < tr['stop']: tr['stop'] = cand
                    elif TRAIL_MODE == "chandelier3":
                        highs = list(self.last_highs) + [b['h']]
                        cand = max(highs[-3:])
                        if cand < tr['stop']: tr['stop'] = cand
                    if is_eod:
                        pnl = tr['entry_px'] - b['c']
                        day_move = (b['c'] - self.day_open) if self.day_open is not None else 0.0
                        self._emit(f"FCET,{d.strftime('%Y-%m-%d')},-1,{tr['entry_px']:.2f},"
                                   f"{tr['init_sl']:.2f},{b['c']:.2f},E,{pnl:.2f},{tr['mfe']:.2f},{tr['mae']:.2f},{tr['bars']},"
                                   f"{day_move:.2f},{self.day_dow if self.day_dow is not None else -1}")
                        self.trade = None

        # update rolling lows/highs AFTER trade management (bar is complete)
        self.last_lows.append(b['l'])
        self.last_highs.append(b['h'])

        # ---- first bar of RTH: entry ----
        if not self.first_bar_done and et_min == RTH_START_ET and self.trade is None:
            self.first_bar_done = True
            self.day_open = b['o']  # RTH session open (first RTH bar's open)
            dow = b['t'].weekday()
            self.day_dow = dow
            allow_long  = True
            allow_short = True
            if DOW_FILTER == "mon_long_fri_short":
                allow_long  = (dow == 0)  # Monday only
                allow_short = (dow == 4)  # Friday only
            if self.ema is not None:
                if b['c'] > self.ema and allow_long:
                    self.trade = {'dir': 1, 'entry_px': b['c'], 'init_sl': b['l'],
                                  'stop': b['l'], 'bars': 0, 'mfe': 0.0, 'mae': 0.0}
                elif b['c'] < self.ema and allow_short:
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
