# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# VWAP Trend v7 SL/TP grid test.
# Emits per trade the bar-index at which each SL and TP threshold would
# have been breached (first time). Offline we compute PnL for each combo.
#
# Setup: RTH VWAP + 20bps band. Entry when close crosses band from 9:31.
# Max 1 trade/day. Skip Wed. Max hold MAX_BARS 5min bars (= 2 hours).
# No gates here (user runs them manually or we add later).
#
# Tag format per trade:
#   VG, date, dir, entry, s15..s150, t15..t200, eod_pnl, bars_end
# sXX = bar_index when MAE >= XX pts (first breach), -1 if never
# tXX = bar_index when MFE >= XX pts, -1 if never
# eod_pnl = pnl at MAX_BARS or EOD close
# bars_end = how many bars until trade ended

TF_MIN       = 5
RTH_START_ET = 9 * 60 + 30
RTH_END_ET   = 16 * 60 - 1
EOD_FLAT_ET  = 15 * 60 + 55
VWAP_START_ET= 9 * 60 + 31
BAND_BPS     = 0.002
MAX_BARS     = 60   # 5 hours = basically whole session

SL_LVLS = [15.0, 25.0, 40.0, 60.0, 75.0, 100.0, 150.0]
TP_LVLS = [15.0, 25.0, 40.0, 60.0, 100.0, 150.0, 200.0]


class VwapSlTpGrid(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=False)
        f.SetFilter(0, 180)
        self.future = f
        self.cont = f.Symbol
        self.n_tags = 0

        self.bar_o = None; self.bar_h = None; self.bar_l = None
        self.bar_c = None; self.bar_start = None
        self.cur_date = None
        self.day_dow = None
        self.vwap_sum_pv = 0.0
        self.vwap_sum_v = 0.0
        self.rth_bar_count = 0
        self.trade = None
        self.prev_close_in = None  # for crossover detection

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
                              'c': self.bar_c, 't': self.bar_start})
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

        if self.cur_date != d:
            if self.trade is not None:
                self._emit_trade(b['c'], b)
            self.cur_date = d
            self.day_dow = b['t'].weekday()
            self.vwap_sum_pv = 0.0
            self.vwap_sum_v = 0.0
            self.rth_bar_count = 0
            self.prev_close_in = None

        in_rth = RTH_START_ET <= et_min <= RTH_END_ET
        is_wed = self.day_dow == 2

        if not in_rth:
            return

        hlc3 = (b['h'] + b['l'] + b['c']) / 3.0
        self.vwap_sum_pv += hlc3
        self.vwap_sum_v += 1.0
        self.rth_bar_count += 1
        vwap = self.vwap_sum_pv / self.vwap_sum_v
        upper = vwap * (1.0 + BAND_BPS)
        lower = vwap * (1.0 - BAND_BPS)

        # Manage active trade — track MFE/MAE threshold breaches
        if self.trade is not None:
            tr = self.trade
            tr['bars'] += 1
            # distance in favorable direction (MFE)
            if tr['dir'] == 1:
                mae_pts = tr['entry'] - b['l']   # how much against (positive)
                mfe_pts = b['h'] - tr['entry']   # how much in favor
            else:
                mae_pts = b['h'] - tr['entry']
                mfe_pts = tr['entry'] - b['l']
            # update breach bars (first time each threshold exceeded)
            for i, lvl in enumerate(SL_LVLS):
                if tr['sl_bar'][i] == -1 and mae_pts >= lvl:
                    tr['sl_bar'][i] = tr['bars']
            for i, lvl in enumerate(TP_LVLS):
                if tr['tp_bar'][i] == -1 and mfe_pts >= lvl:
                    tr['tp_bar'][i] = tr['bars']
            # End trade: EOD or MAX_BARS
            if et_min >= EOD_FLAT_ET or tr['bars'] >= MAX_BARS:
                self._emit_trade(b['c'], b)

        # Entry: band break (close > upper or < lower) with real crossover check
        if (self.trade is None and not is_wed
            and et_min >= VWAP_START_ET and et_min < EOD_FLAT_ET
            and self.rth_bar_count >= 2 and self.prev_close_in is not None):
            # LONG: prev close <= upper, current close > upper
            if self.prev_close_in <= self.prev_upper and b['c'] > upper:
                self.trade = {'dir': 1, 'entry': b['c'],
                              'sl_bar': [-1]*len(SL_LVLS),
                              'tp_bar': [-1]*len(TP_LVLS),
                              'bars': 0,
                              'date_time': b['t'].strftime('%Y-%m-%d %H:%M')}
            elif self.prev_close_in >= self.prev_lower and b['c'] < lower:
                self.trade = {'dir': -1, 'entry': b['c'],
                              'sl_bar': [-1]*len(SL_LVLS),
                              'tp_bar': [-1]*len(TP_LVLS),
                              'bars': 0,
                              'date_time': b['t'].strftime('%Y-%m-%d %H:%M')}

        self.prev_close_in = b['c']
        self.prev_upper = upper
        self.prev_lower = lower

    def _emit_trade(self, exit_px, b):
        tr = self.trade
        eod_pnl = tr['dir'] * (exit_px - tr['entry'])
        sl_part = ",".join(str(x) for x in tr['sl_bar'])
        tp_part = ",".join(str(x) for x in tr['tp_bar'])
        self._emit(f"VG,{tr['date_time']},{tr['dir']},{tr['entry']:.2f},"
                   f"{sl_part},{tp_part},{eod_pnl:.2f},{tr['bars']}")
        self.trade = None

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5, 2), tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
