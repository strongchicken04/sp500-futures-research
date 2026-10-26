# region imports
from AlgorithmImports import *
# endregion
#
# PROP S8-MAE: gap reversal, instrumented to sweep stop width offline.
#
# The 15-point stop was tuned on a 2005-2020 daily panel where NQ traded
# between 1,600 and 9,000. At 5,000 that stop is 0.30% of price; at today's
# 22,000 it is 0.07%. The live 2018-2025 backtest shows what that does: a
# 14.8% win rate, 412 stop-outs against 73 winners. The stop was never
# re-expressed for the price level, so it silently became five times tighter.
#
# Rather than guess a replacement, this records per trade the first bar at
# which each candidate stop would have been breached, in points and in
# percent and in ATR multiples, plus the eventual EOD result. Every stop
# definition can then be priced offline from one backtest, the way the VWAP
# grid already works.
#
# Tag: S8M,datetime,gap_pct,entry,atr,<pt breaches>,<pct breaches>,
#      <atr breaches>,mae_pts,eod_pnl
# Each breach field is the bar index of first touch, or -1 if never touched.

TF_MIN = 5
GAP_THRESH = -0.0025
SKIP_WED = True  # inverted below: Wednesday only

STOP_PTS = [10.0, 15.0, 25.0, 40.0, 60.0, 90.0]
STOP_PCT = [0.0005, 0.0010, 0.0020, 0.0035, 0.0050]
STOP_ATR = [0.25, 0.50, 0.75, 1.00, 1.50]


class PropS8MaeExporter(QCAlgorithm):

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
        self.bar_o = None
        self.bar_h = None
        self.bar_l = None
        self.bar_c = None
        self.bar_start = None
        self.cur_date = None
        self.day_dow = None
        self.prev_close = None
        self.last_close = None
        self.day_hi = None
        self.day_lo = None
        self.ranges = []
        self.trade = None
        self.done_today = False

    def _bs(self, t):
        m = (t.minute // TF_MIN) * TF_MIN
        return t.replace(minute=m, second=0, microsecond=0)

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        bs = self._bs(self.Time)
        if self.bar_start != bs:
            if self.bar_o is not None:
                self._on_bar({'o': self.bar_o, 'h': self.bar_h,
                              'l': self.bar_l, 'c': self.bar_c,
                              't': self.bar_start})
            self.bar_o = bar.Open
            self.bar_h = bar.High
            self.bar_l = bar.Low
            self.bar_c = bar.Close
            self.bar_start = bs
        else:
            self.bar_h = max(self.bar_h, bar.High)
            self.bar_l = min(self.bar_l, bar.Low)
            self.bar_c = bar.Close

    def _on_bar(self, b):
        em = b['t'].hour * 60 + b['t'].minute
        d = b['t'].date()

        if self.cur_date != d:
            # A position still open here means the prior session never
            # produced a 15:55 bar -- a holiday or a data gap. Drop it rather
            # than marking it against the next day's price, which is how the
            # earlier run produced a single -253 point outlier.
            self.trade = None
            if self.day_hi is not None:
                self.ranges.append(self.day_hi - self.day_lo)
                if len(self.ranges) > 20:
                    self.ranges.pop(0)
            if self.last_close is not None:
                self.prev_close = self.last_close
            self.cur_date = d
            self.day_dow = b['t'].weekday()
            self.day_hi = None
            self.day_lo = None
            self.done_today = False

        in_rth = 9 * 60 + 30 <= em <= 16 * 60 - 1
        if not in_rth:
            return

        self.day_hi = b['h'] if self.day_hi is None else max(self.day_hi, b['h'])
        self.day_lo = b['l'] if self.day_lo is None else min(self.day_lo, b['l'])

        if self.trade is not None:
            tr = self.trade
            tr['bars'] += 1
            adverse = tr['entry'] - b['l']
            if adverse > tr['mae']:
                tr['mae'] = adverse
            for key, levels in (('pt', tr['lv_pt']), ('pct', tr['lv_pct']),
                                ('atr', tr['lv_atr'])):
                for i, (lvl, hit) in enumerate(levels):
                    if hit < 0 and adverse >= lvl:
                        levels[i] = (lvl, tr['bars'])
            if em >= 15 * 60 + 55:
                self._emit_trade(b['c'])
                self.last_close = b['c']
                return

        if (self.trade is None and not self.done_today
                and em == 9 * 60 + 30
                and self.prev_close is not None
                and len(self.ranges) >= 10
                and self.day_dow == 2):
            gap = (b['o'] - self.prev_close) / self.prev_close
            if gap <= GAP_THRESH:
                atr = sum(self.ranges) / len(self.ranges)
                e = b['o']
                self.trade = {
                    'entry': e, 'gap': gap, 'atr': atr, 'bars': 0, 'mae': 0.0,
                    'lv_pt': [(x, -1) for x in STOP_PTS],
                    'lv_pct': [(e * x, -1) for x in STOP_PCT],
                    'lv_atr': [(atr * x, -1) for x in STOP_ATR],
                    'dt': b['t'].strftime('%Y-%m-%d %H:%M'),
                }
                self.done_today = True
                # Entry is at this bar's open, so its whole range is after
                # the fill and its low counts. An earlier version skipped
                # it, which ignored the most volatile five minutes of the
                # day -- right after a gap -- and flattered every stop.
                tr = self.trade
                adverse = e - b['l']
                tr['mae'] = max(tr['mae'], adverse)
                for key in ('lv_pt', 'lv_pct', 'lv_atr'):
                    tr[key] = [(lvl, 0 if adverse >= lvl else hit)
                               for lvl, hit in tr[key]]

        self.last_close = b['c']

    def _emit_trade(self, exit_px):
        tr = self.trade
        pt = ",".join(str(h) for _, h in tr['lv_pt'])
        pc = ",".join(str(h) for _, h in tr['lv_pct'])
        at = ",".join(str(h) for _, h in tr['lv_atr'])
        self._emit(f"S8M,{tr['dt']},{tr['gap']*100:.3f},{tr['entry']:.2f},"
                   f"{tr['atr']:.2f},{pt},{pc},{at},{tr['mae']:.2f},"
                   f"{exit_px - tr['entry']:.2f}")
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
