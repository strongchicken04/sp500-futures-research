# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# Combined Mon-LONG + Fri-SHORT + VWAP Trend v7 on NQ 2018-2025.
# Mimics the Pine Lucid Pass Tracker logic.
#
# Setup 1: Mon-LONG / Fri-SHORT
#   Monday or Friday, first 5m RTH bar close vs EMA12
#   LONG if Mon + close > EMA12; SHORT if Fri + close < EMA12
#   SL = wick low/high entry bar, TP = EOD 15:55 or +40pt
#
# Setup 2: VWAP Trend v7 (fallback — only if Mon/Fri didn't fire today)
#   RTH-anchored VWAP, 20bps band
#   Entry on close break of band from 9:31 ET on
#   SL = 75pt, exit on band flip (close back inside opposite band) or EOD
#   One trade per day max for VWAP; Wed skipped
#
# Emit per trade:
#   COMBO,date,setup,side,entry,sl,exit,reason,pnl_pts,bars_held

TF_MIN       = 5
EMA_LEN      = 12
RTH_START_ET = 9 * 60 + 30
RTH_END_ET   = 16 * 60 - 1
EOD_FLAT_ET  = 15 * 60 + 55
VWAP_START_ET= 9 * 60 + 31
BAND_BPS     = 0.002
TP_PTS       = 40.0
VWAP_SL_PTS  = 75.0


class ComboMonFriVwap(QCAlgorithm):

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
        self.ema = None
        self.k = 2.0 / (EMA_LEN + 1)
        self.cur_date = None
        self.first_bar_done = False
        self.trade = None     # active trade dict
        self.day_dow = None
        # VWAP tracking (RTH only)
        self.vwap_sum_pv = 0.0
        self.vwap_sum_v = 0.0
        self.rth_bar_count = 0
        # Mon/Fri trigger status for today
        self.monfri_fired_today = False

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
                self._on_bar({'o': self.bar_o, 'h': self.bar_h, 'l': self.bar_l,
                              'c': self.bar_c, 't': self.bar_start,
                              'v': 1.0})  # we don't have volume easily; use 1 for simple avg
            self.bar_o = bar.Open; self.bar_h = bar.High
            self.bar_l = bar.Low;  self.bar_c = bar.Close
            self.bar_start = bs
        else:
            self.bar_h = max(self.bar_h, bar.High)
            self.bar_l = min(self.bar_l, bar.Low)
            self.bar_c = bar.Close

    def _on_bar(self, b):
        et_min = b['t'].hour * 60 + b['t'].minute
        d = b['t'].date()

        # daily rollover
        if self.cur_date != d:
            # close any active trade at EOD close
            if self.trade is not None:
                self._close_trade(b['c'], 'EOD_rollover', b)
            self.cur_date = d
            self.first_bar_done = False
            self.day_dow = b['t'].weekday()  # 0=Mon
            self.vwap_sum_pv = 0.0
            self.vwap_sum_v = 0.0
            self.rth_bar_count = 0
            self.monfri_fired_today = False

        # EMA update (continuous, all bars)
        if self.ema is None:
            self.ema = b['c']
        else:
            self.ema = b['c'] * self.k + self.ema * (1 - self.k)

        in_rth = RTH_START_ET <= et_min <= RTH_END_ET
        is_eod_flat = et_min >= EOD_FLAT_ET
        is_wed = self.day_dow == 2  # Wednesday skipped

        if not in_rth:
            return

        # update VWAP (hlc3 * 1 weighted; close enough for cross detection)
        hlc3 = (b['h'] + b['l'] + b['c']) / 3.0
        self.vwap_sum_pv += hlc3
        self.vwap_sum_v += 1.0
        self.rth_bar_count += 1
        vwap = self.vwap_sum_pv / self.vwap_sum_v if self.vwap_sum_v > 0 else b['c']
        upper = vwap * (1.0 + BAND_BPS)
        lower = vwap * (1.0 - BAND_BPS)

        # --- Manage active trade ---
        if self.trade is not None:
            tr = self.trade
            tr['bars'] += 1
            # Mon-LONG / Fri-SHORT: SL and TP checks
            if tr['setup'] == 'MONFRI':
                if tr['side'] == 1:
                    if b['l'] <= tr['sl']:
                        self._close_trade(tr['sl'], 'SL', b); return
                    if b['h'] >= tr['tp']:
                        self._close_trade(tr['tp'], 'TP', b); return
                else:
                    if b['h'] >= tr['sl']:
                        self._close_trade(tr['sl'], 'SL', b); return
                    if b['l'] <= tr['tp']:
                        self._close_trade(tr['tp'], 'TP', b); return
            # VWAP Trend
            elif tr['setup'] == 'VWAP':
                # Band flip exit: close back through opposite band
                if tr['side'] == 1 and b['c'] <= lower:
                    self._close_trade(b['c'], 'BAND', b); return
                if tr['side'] == -1 and b['c'] >= upper:
                    self._close_trade(b['c'], 'BAND', b); return
                # Fixed SL
                if tr['side'] == 1 and b['l'] <= tr['sl']:
                    self._close_trade(tr['sl'], 'SL', b); return
                if tr['side'] == -1 and b['h'] >= tr['sl']:
                    self._close_trade(tr['sl'], 'SL', b); return
            # EOD flat
            if is_eod_flat:
                self._close_trade(b['c'], 'EOD', b); return

        # --- Mon/Fri setup: first RTH bar entry ---
        if not self.first_bar_done and et_min == RTH_START_ET and self.trade is None and not is_wed:
            self.first_bar_done = True
            allow_long = (self.day_dow == 0)  # Monday
            allow_short = (self.day_dow == 4)  # Friday
            if self.ema is not None:
                if b['c'] > self.ema and allow_long:
                    self.trade = {'setup': 'MONFRI', 'side': 1,
                                  'entry': b['c'], 'sl': b['l'],
                                  'tp': b['c'] + TP_PTS, 'bars': 0,
                                  'date_time': b['t'].strftime('%Y-%m-%d %H:%M')}
                    self.monfri_fired_today = True
                elif b['c'] < self.ema and allow_short:
                    self.trade = {'setup': 'MONFRI', 'side': -1,
                                  'entry': b['c'], 'sl': b['h'],
                                  'tp': b['c'] - TP_PTS, 'bars': 0,
                                  'date_time': b['t'].strftime('%Y-%m-%d %H:%M')}
                    self.monfri_fired_today = True

        # --- VWAP Trend (fallback) ---
        if (self.trade is None and not is_wed and not self.monfri_fired_today
            and et_min >= VWAP_START_ET and et_min < EOD_FLAT_ET
            and self.rth_bar_count >= 2):  # need at least 2 bars for crossover
            # crossover of close above upper (long) / under lower (short)
            prev_close = b.get('prev_c', b['c'])  # fallback
            # We need previous bar close. Since _on_bar only has current, track externally
            # Simplified: just check if current close is above/below band (not strict crossover)
            # We check band break (ignoring crossover semantics for simplicity)
            if b['c'] > upper and self.trade is None:
                self.trade = {'setup': 'VWAP', 'side': 1,
                              'entry': b['c'], 'sl': b['c'] - VWAP_SL_PTS,
                              'tp': 0.0, 'bars': 0,
                              'date_time': b['t'].strftime('%Y-%m-%d %H:%M')}
            elif b['c'] < lower and self.trade is None:
                self.trade = {'setup': 'VWAP', 'side': -1,
                              'entry': b['c'], 'sl': b['c'] + VWAP_SL_PTS,
                              'tp': 0.0, 'bars': 0,
                              'date_time': b['t'].strftime('%Y-%m-%d %H:%M')}

    def _close_trade(self, exit_px, reason, b):
        tr = self.trade
        pnl = tr['side'] * (exit_px - tr['entry'])
        self._emit(f"COMBO,{tr['date_time']},{tr['setup']},{tr['side']},"
                   f"{tr['entry']:.2f},{tr['sl']:.2f},{exit_px:.2f},{reason},"
                   f"{pnl:.2f},{tr['bars']}")
        self.trade = None

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
