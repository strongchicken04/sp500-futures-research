# region imports
from AlgorithmImports import *
from collections import defaultdict
# endregion

# NQ Prior-Day Value Area rotation test (Auction Market Theory).
# 2018-2025, RTH only. Setup per Orochi Framework:
#
# Each day: compute YESTERDAY's value area (Volume Profile of RTH bars):
#   POC   = highest-volume $2 price bin
#   Expand around POC until cumulative volume >= 68% of day's total
#   VAH   = top of expanded bins, VAL = bottom
#
# TODAY (RTH 9:30-15:59 ET):
#   SHORT if this bar's high >= VAH AND prior bar close < VAH  (touch from below)
#         target = POC, SL = VAH + SL_PTS
#   LONG  if this bar's low  <= VAL AND prior bar close > VAL  (touch from above)
#         target = POC, SL = VAL - SL_PTS
#   Exits: target | SL | EOD 15:59 flat
#   Max ONE trade per level per day (VAH and VAL tracked independently).
#
# Emit per trade:
#   AMT,date,level,dir,entry,poc,sl,exit,exit_reason,pnl,bars_held
#     level = H/L, exit_reason = T/L/E (target/loss/eod)

BIN_SIZE = 2.0
SL_PTS = 15.0           # legacy, unused if SL_MODE="va_pct"
SL_MODE = "va_pct"      # "fixed" | "va_pct"
SL_VA_PCT = 0.30        # 30% VA width beyond entry level
VA_PCT = 0.68           # value area coverage
REQUIRE_OPEN_INSIDE_VA = True    # today's RTH open must be inside prior VA
REQUIRE_REJECTION_CLOSE = True   # bar close must be back inside VA (rejection candle)


class NQAmtVaRotation(QCAlgorithm):

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

        # today's building profile
        self.day_bins = defaultdict(float)   # bin_key -> volume
        self.day_total_vol = 0.0
        self.cur_date = None

        # yesterday's value area (used TODAY)
        self.yVAH = None
        self.yPOC = None
        self.yVAL = None

        # today's tracking
        self.prev_close = None
        self.h_traded = False
        self.l_traded = False
        self.trade = None
        self.bar_5m_id = 0
        self.rth_open = None       # today's first RTH close (used as "open")
        self.open_inside_va = None # bool cached once open is known

    # ---------- helpers ----------
    def _compute_va(self, bins):
        if not bins:
            return None
        # find POC (highest volume bin key)
        poc_key = max(bins.keys(), key=lambda k: bins[k])
        total = sum(bins.values())
        target = VA_PCT * total
        # expand around poc
        included = {poc_key}
        acc = bins[poc_key]
        lo, hi = poc_key, poc_key
        while acc < target:
            # candidates: hi+1, lo-1
            up = bins.get(hi + 1, 0.0)
            dn = bins.get(lo - 1, 0.0)
            # need at least one bin remaining
            has_up = (hi + 1) in bins
            has_dn = (lo - 1) in bins
            if not has_up and not has_dn:
                break
            if (has_up and not has_dn) or (has_up and has_dn and up >= dn):
                hi += 1; acc += up
            else:
                lo -= 1; acc += dn
        # convert bin index to price (bin center)
        vah = (hi + 0.5) * BIN_SIZE
        val = (lo - 0.5) * BIN_SIZE
        poc = (poc_key + 0.5) * BIN_SIZE
        # clamp: vah = top of highest bin, val = bottom of lowest bin
        vah = (hi + 1) * BIN_SIZE
        val = lo * BIN_SIZE
        poc = (poc_key + 0.5) * BIN_SIZE
        return (val, poc, vah)

    def _roll_day(self, new_date):
        # finalize prior day's profile -> yesterday's VA for use TODAY
        va = self._compute_va(self.day_bins)
        if va is not None:
            self.yVAL, self.yPOC, self.yVAH = va
        else:
            self.yVAL = self.yPOC = self.yVAH = None
        # reset today's accumulators
        self.day_bins = defaultdict(float)
        self.day_total_vol = 0.0
        self.prev_close = None
        self.h_traded = False
        self.l_traded = False
        self.trade = None
        self.rth_open = None
        self.open_inside_va = None
        self.cur_date = new_date

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        d = t.date()
        mend = t.hour * 60 + t.minute

        # date rollover
        if self.cur_date is None:
            self.cur_date = d
        elif d != self.cur_date:
            self._roll_day(d)

        in_rth = 570 <= mend <= 959  # 9:30 - 15:59 inclusive
        is_eod = (mend == 959)

        # build today's profile (RTH only, using close bin)
        if in_rth:
            key = int(bar.Close // BIN_SIZE)
            self.day_bins[key] += bar.Volume if bar.Volume > 0 else 1.0
            self.day_total_vol += (bar.Volume if bar.Volume > 0 else 1.0)

        # trading requires yesterday's VA
        if not in_rth or self.yVAH is None:
            self.prev_close = bar.Close if in_rth else self.prev_close
            return

        h = bar.High; l = bar.Low; c = bar.Close

        # capture today's RTH open on first bar (mend==570)
        if self.rth_open is None:
            self.rth_open = bar.Open
            self.open_inside_va = (self.yVAL <= self.rth_open <= self.yVAH)

        # optional acceptance filter
        if REQUIRE_OPEN_INSIDE_VA and not self.open_inside_va:
            self.prev_close = c
            return

        # ---- manage active trade ----
        if self.trade is not None:
            tr = self.trade
            done = False; ex_px = None; reason = None
            # SL priority (conservative)
            if tr['dir'] == -1:
                if h >= tr['sl']:
                    done, ex_px, reason = True, tr['sl'], 'L'
            else:
                if l <= tr['sl']:
                    done, ex_px, reason = True, tr['sl'], 'L'
            # target
            if not done:
                if tr['dir'] == -1:
                    if l <= tr['target']:
                        done, ex_px, reason = True, tr['target'], 'T'
                else:
                    if h >= tr['target']:
                        done, ex_px, reason = True, tr['target'], 'T'
            # EOD force flat
            if not done and is_eod:
                done, ex_px, reason = True, c, 'E'
            if done:
                pnl = tr['dir'] * (ex_px - tr['entry_px'])
                bars_held = (t.hour * 60 + t.minute) - tr['entry_min']
                self._emit(f"AMT,{d.strftime('%Y-%m-%d')},{tr['level']},{tr['dir']},"
                           f"{tr['entry_px']:.2f},{tr['target']:.2f},{tr['sl']:.2f},"
                           f"{ex_px:.2f},{reason},{pnl:.2f},{bars_held}")
                self.trade = None

        # ---- entry checks ----
        if self.trade is None and not is_eod and self.prev_close is not None:
            # compute SL offset (dynamic or fixed)
            va_width = self.yVAH - self.yVAL
            if SL_MODE == "va_pct":
                sl_off = SL_VA_PCT * va_width
            else:
                sl_off = SL_PTS
            # SHORT at VAH: touch from below + rejection close
            if (not self.h_traded) and (self.prev_close < self.yVAH) and (h >= self.yVAH):
                if not REQUIRE_REJECTION_CLOSE or (c < self.yVAH):
                    entry_px = c   # entry at close of rejection bar
                    self.trade = {
                        'dir': -1, 'entry_px': entry_px, 'target': self.yPOC,
                        'sl': self.yVAH + sl_off, 'level': 'H',
                        'entry_min': t.hour * 60 + t.minute}
                    self.h_traded = True
            # LONG at VAL: touch from above + rejection close
            elif (not self.l_traded) and (self.prev_close > self.yVAL) and (l <= self.yVAL):
                if not REQUIRE_REJECTION_CLOSE or (c > self.yVAL):
                    entry_px = c
                    self.trade = {
                        'dir': 1, 'entry_px': entry_px, 'target': self.yPOC,
                        'sl': self.yVAL - sl_off, 'level': 'L',
                        'entry_min': t.hour * 60 + t.minute}
                    self.l_traded = True

        # track prev close (RTH bars only)
        if in_rth:
            self.prev_close = c

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
