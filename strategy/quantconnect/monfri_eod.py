# region imports
from AlgorithmImports import *
# endregion
#
# MONDAY LONG / FRIDAY SHORT, held to 15:55 -- as actually traded.
#
# The trades the book was simulated with came from combo_mon_fri_vwap.py,
# which caps the hold with a +40 pt target. That target was identified as a
# bug in an earlier pass (it cuts off the EOD-hold edge) and the live Pine
# indicator has none, so the simulated strategy was not the traded one.
#
# The trigger compares the first 5-minute RTH bar's close with EMA12. A
# TradingView futures chart normally shows the overnight session, so the
# indicator's EMA includes overnight bars, while the old backtest used RTH
# bars only. Both versions are emitted:
#   MFR  EMA12 over RTH 5-minute bars only
#   MFE  EMA12 over all 5-minute bars, overnight included
#
# Entry at the close of the first bar, stop at that bar's wick, flat at
# 15:55. Tracking starts on the next bar. Emitted in the combo tag format so
# existing loaders read it unchanged.
#
# Tag: COMBO,<dt>,<MFR|MFE>,<dir>,<entry>,<sl>,<exit>,<reason>,<pnl>,<bars>

EMA_LEN = 12
K = 2.0 / (EMA_LEN + 1)


class MonFriEod(QCAlgorithm):

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
        self.bo = self.bh = self.bl = self.bc = None
        self.bstart = None
        self.ema_rth = None
        self.ema_all = None
        self.cur_date = None
        self.trades = []

    def _bs(self, t):
        m = (t.minute // 5) * 5
        return t.replace(minute=m, second=0, microsecond=0)

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        bs = self._bs(self.Time)
        if self.bstart != bs:
            if self.bo is not None:
                self._on_bar(self.bo, self.bh, self.bl, self.bc, self.bstart)
            self.bo, self.bh = bar.Open, bar.High
            self.bl, self.bc = bar.Low, bar.Close
            self.bstart = bs
        else:
            self.bh = max(self.bh, bar.High)
            self.bl = min(self.bl, bar.Low)
            self.bc = bar.Close

    def _on_bar(self, o, h, l, c, t):
        em = t.hour * 60 + t.minute
        in_rth = 9 * 60 + 30 <= em < 16 * 60
        # both EMAs include this bar's close, as ta.ema does in Pine
        self.ema_all = c if self.ema_all is None else c * K + self.ema_all * (1 - K)
        if in_rth:
            self.ema_rth = c if self.ema_rth is None else c * K + self.ema_rth * (1 - K)
        if not in_rth:
            return
        d = t.date()
        if d != self.cur_date:
            self.cur_date = d
            self.trades = []
            dow = t.weekday()
            if em == 9 * 60 + 30 and dow in (0, 4):
                for name, ema in (('MFR', self.ema_rth), ('MFE', self.ema_all)):
                    if ema is None:
                        continue
                    if dow == 0 and c > ema:
                        self.trades.append({'n': name, 'dir': 1, 'e': c,
                                            'sl': l, 'bars': 0,
                                            'dt': t.strftime('%Y-%m-%d %H:%M')})
                    elif dow == 4 and c < ema:
                        self.trades.append({'n': name, 'dir': -1, 'e': c,
                                            'sl': h, 'bars': 0,
                                            'dt': t.strftime('%Y-%m-%d %H:%M')})
            return
        keep = []
        for tr in self.trades:
            tr['bars'] += 1
            if tr['dir'] == 1 and l <= tr['sl']:
                self._close(tr, tr['sl'], 'SL')
            elif tr['dir'] == -1 and h >= tr['sl']:
                self._close(tr, tr['sl'], 'SL')
            elif em >= 15 * 60 + 55:
                self._close(tr, c, 'EOD')
            else:
                keep.append(tr)
        self.trades = keep

    def _close(self, tr, px, reason):
        pnl = tr['dir'] * (px - tr['e'])
        self._emit(f"COMBO,{tr['dt']},{tr['n']},{tr['dir']},{tr['e']:.2f},"
                   f"{tr['sl']:.2f},{px:.2f},{reason},{pnl:.2f},{tr['bars']}")

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5, 2),
                                          tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
