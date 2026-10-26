# region imports
from AlgorithmImports import *
# endregion

# IV/opcni zdi (call wall / put wall z open interestu) - feature exporter.
#
# Kazde rano v 9:35 ET z opcniho retezce QQQ (proxy NDX/NQ, expirace <= 25 dni,
# OI je ze vcerejsiho settle -> past-only):
#   call wall = strike s nejvetsim call OI NAD spotem
#   put wall  = strike s nejvetsim put OI POD spotem
#   pcr       = pomer celkoveho put/call OI
# Na konci dne (16:00) emituje 1 tag s urovneni + dennim RTH OHLC NQ
# + parem cen QQQ/NQ z 9:35 pro prepocet urovni do NQ bodu.
#
# Zadne obchodovani - jen sber dat pro claim testy (magnet/bariera/regime)
# proti base rate. Tag:
# GX,date,qqq935,nq935,cw,pw,cwoi,pwoi,pcr,no,nh,nl,nc

EXP_MAX_DAYS = 25
STRIKE_RANGE = 12


class NQIVWalls(QCAlgorithm):

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
        self.qqq = self.AddEquity("QQQ", Resolution.Minute).Symbol
        opt = self.AddOption("QQQ", Resolution.Minute)
        opt.SetFilter(-STRIKE_RANGE, STRIKE_RANGE, 0, EXP_MAX_DAYS)
        self.opt_sym = opt.Symbol
        self.cur_date = None
        self.n_tags = 0
        self._reset_day()

    def _reset_day(self):
        self.walls = None          # (qqq935, nq935, cw, pw, cwoi, pwoi, pcr)
        self.d_open = None
        self.d_high = None
        self.d_low = None
        self.d_close = None

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def _compute_walls(self, slice, nq_px):
        chain = slice.OptionChains.get(self.opt_sym) if slice.OptionChains is not None else None
        if chain is None:
            return
        spot = self.Securities[self.qqq].Price
        if spot <= 0:
            return
        call_oi = {}
        put_oi = {}
        tot_c = 0.0
        tot_p = 0.0
        for c in chain:
            oi = float(c.OpenInterest)
            if oi <= 0:
                continue
            k = float(c.Strike)
            if c.Right == OptionRight.Call:
                call_oi[k] = call_oi.get(k, 0.0) + oi
                tot_c += oi
            else:
                put_oi[k] = put_oi.get(k, 0.0) + oi
                tot_p += oi
        above = {k: v for k, v in call_oi.items() if k >= spot}
        below = {k: v for k, v in put_oi.items() if k <= spot}
        if not above or not below:
            return
        cw = max(above, key=above.get)
        pw = max(below, key=below.get)
        pcr = tot_p / tot_c if tot_c > 0 else 0.0
        self.walls = (spot, nq_px, cw, pw, above[cw], below[pw], pcr)

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        d = t.date()
        if self.cur_date is None:
            self.cur_date = d
        if d != self.cur_date:
            self.cur_date = d
            self._reset_day()

        mend = t.hour * 60 + t.minute
        if not (571 <= mend <= 960):
            return
        if self.d_open is None:
            self.d_open, self.d_high, self.d_low = bar.Open, bar.High, bar.Low
        self.d_high = max(self.d_high, bar.High)
        self.d_low = min(self.d_low, bar.Low)
        self.d_close = bar.Close

        if self.walls is None and mend >= 575:            # 9:35
            self._compute_walls(slice, bar.Close)

        if mend == 960 and self.walls is not None:
            q, n, cw, pw, cwoi, pwoi, pcr = self.walls
            tag = (f"GX,{d.strftime('%Y-%m-%d')},{q:.2f},{n:.2f},{cw:.1f},{pw:.1f},"
                   f"{cwoi:.0f},{pwoi:.0f},{pcr:.2f},"
                   f"{self.d_open:.2f},{self.d_high:.2f},{self.d_low:.2f},{self.d_close:.2f}")
            self._emit(tag)

    def OnEndOfAlgorithm(self):
        self.Log(f"GX_TAGS={self.n_tags}")
