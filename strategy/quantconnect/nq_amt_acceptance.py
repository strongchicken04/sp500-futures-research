# region imports
from AlgorithmImports import *
from collections import defaultdict
# endregion

# NQ AMT "Acceptance Rotation" (Orochi Framework).
# 2018-2025, RTH.
#
# Compute YESTERDAY's value area (Volume Profile of RTH bars):
#   POC = highest-volume $2 bin, expand to 68% -> VAH/VAL
#
# TODAY setup:
#   Track OUTSIDE-vs-INSIDE state of price vs prior VA.
#   ACCEPTANCE = price was OUTSIDE VA and this bar CLOSES back INSIDE.
#     - If accepting from ABOVE (was > VAH, now close in [VAL, VAH])
#       -> SHORT toward VAL (traversal)
#     - If accepting from BELOW (was < VAL, now close in [VAL, VAH])
#       -> LONG toward VAH (traversal)
#   SL: back OUTSIDE VA (SL_BUFFER * VA_width above VAH / below VAL)
#   Exit: target (opposite VA edge) | SL | EOD 15:59
#   Max 1 trade per day.
#
# Emit: AMT2,date,dir,kind,entry,target,sl,exit,reason,pnl,bars

BIN_SIZE = 2.0
VA_PCT = 0.68
SL_BUFFER_PCT = 0.20   # SL = 20% of VA width beyond outer edge
MIN_TIME_OUTSIDE_BARS = 5  # must have been outside for at least N bars before acceptance
LONG_ONLY = True           # only take accept-from-below (dip buy)


class NQAmtAcceptance(QCAlgorithm):

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
        self.day_bins = defaultdict(float)
        self.cur_date = None
        self.yVAH = None; self.yPOC = None; self.yVAL = None
        self.rth_open = None
        # outside/inside state tracking (based on close)
        self.was_outside = None    # None|'above'|'below'|'inside'
        self.outside_bars = 0
        self.traded_today = False
        self.trade = None

    def _compute_va(self, bins):
        if not bins: return None
        poc_key = max(bins.keys(), key=lambda k: bins[k])
        total = sum(bins.values())
        target = VA_PCT * total
        acc = bins[poc_key]; lo, hi = poc_key, poc_key
        while acc < target:
            has_up = (hi + 1) in bins; has_dn = (lo - 1) in bins
            if not has_up and not has_dn: break
            up = bins.get(hi + 1, 0.0); dn = bins.get(lo - 1, 0.0)
            if (has_up and not has_dn) or (has_up and has_dn and up >= dn):
                hi += 1; acc += up
            else:
                lo -= 1; acc += dn
        vah = (hi + 1) * BIN_SIZE
        val = lo * BIN_SIZE
        poc = (poc_key + 0.5) * BIN_SIZE
        return (val, poc, vah)

    def _roll_day(self, new_date):
        va = self._compute_va(self.day_bins)
        if va is not None:
            self.yVAL, self.yPOC, self.yVAH = va
        else:
            self.yVAL = self.yPOC = self.yVAH = None
        self.day_bins = defaultdict(float)
        self.rth_open = None
        self.was_outside = None
        self.outside_bars = 0
        self.traded_today = False
        self.trade = None
        self.cur_date = new_date

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None: return
        t = self.Time; d = t.date()
        mend = t.hour * 60 + t.minute

        if self.cur_date is None:
            self.cur_date = d
        elif d != self.cur_date:
            self._roll_day(d)

        in_rth = 570 <= mend <= 959
        is_eod = (mend == 959)

        if in_rth:
            key = int(bar.Close // BIN_SIZE)
            self.day_bins[key] += bar.Volume if bar.Volume > 0 else 1.0

        if not in_rth or self.yVAH is None:
            return

        h = bar.High; l = bar.Low; c = bar.Close
        if self.rth_open is None:
            self.rth_open = bar.Open

        # ---- exit management ----
        if self.trade is not None:
            tr = self.trade
            done = False; ex_px = None; reason = None
            if tr['dir'] == -1:
                if h >= tr['sl']:
                    done, ex_px, reason = True, tr['sl'], 'L'
                elif l <= tr['target']:
                    done, ex_px, reason = True, tr['target'], 'T'
            else:
                if l <= tr['sl']:
                    done, ex_px, reason = True, tr['sl'], 'L'
                elif h >= tr['target']:
                    done, ex_px, reason = True, tr['target'], 'T'
            if not done and is_eod:
                done, ex_px, reason = True, c, 'E'
            if done:
                pnl = tr['dir'] * (ex_px - tr['entry_px'])
                self._emit(f"AMT2,{d.strftime('%Y-%m-%d')},{tr['dir']},{tr['kind']},"
                           f"{tr['entry_px']:.2f},{tr['target']:.2f},{tr['sl']:.2f},"
                           f"{ex_px:.2f},{reason},{pnl:.2f},{tr.get('bars',0)}")
                self.trade = None

        # ---- state transitions (based on close) ----
        # classify current position
        if c > self.yVAH:
            cur_state = 'above'
        elif c < self.yVAL:
            cur_state = 'below'
        else:
            cur_state = 'inside'

        # ---- entry: acceptance = was outside for N+ bars, now closes inside ----
        if self.trade is None and not self.traded_today and not is_eod:
            va_width = self.yVAH - self.yVAL
            sl_buf = SL_BUFFER_PCT * va_width
            if cur_state == 'inside' and self.was_outside in ('above','below') and self.outside_bars >= MIN_TIME_OUTSIDE_BARS:
                if self.was_outside == 'above' and not LONG_ONLY:
                    self.trade = {'dir': -1, 'entry_px': c, 'target': self.yVAL,
                                  'sl': self.yVAH + sl_buf, 'kind': 'A2', 'bars': 0}
                    self.traded_today = True
                elif self.was_outside == 'below':
                    self.trade = {'dir': 1, 'entry_px': c, 'target': self.yVAH,
                                  'sl': self.yVAL - sl_buf, 'kind': 'B2', 'bars': 0}
                    self.traded_today = True

        # update outside tracking
        if cur_state == 'inside':
            if self.was_outside in ('above','below'):
                # transition
                pass
            self.was_outside = 'inside'
            self.outside_bars = 0
        else:
            if self.was_outside != cur_state:
                self.was_outside = cur_state
                self.outside_bars = 1
            else:
                self.outside_bars += 1

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
