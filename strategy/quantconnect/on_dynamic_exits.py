# region imports
from AlgorithmImports import *
# endregion

# Strategy: at RTH open, given ON range (18:00 prev - 9:30):
#   ONM = (ONH + ONL) / 2
#   if open > ONM: LONG,  TP=ONH
#   if open < ONM: SHORT, TP=ONL
# Test FOUR dynamic exit variants in one backtest:
#   W  = wide SL: at opposite extreme +/- 25% of ON range past it
#   V  = very wide SL: at opposite extreme +/- 50% of ON range past it
#   B  = break-even move: SL at 1:1 mirror initially; when MFE >= 50% TP dist,
#        move SL to entry (breakeven)
#   T  = trailing SL: SL trails 30 pts behind current favorable extreme
# For all: if TP hit -> +TP_dist. If SL hit -> -SL_dist_at_that_moment.
# Neither -> EOD close.
#
# Tag: OD,date,dir,open,onh,onl,close,
#      resW,pnlW,resV,pnlV,resB,pnlB,pnlBsl_used,resT,pnlT,pnlTsl_used


TRAIL_PTS = 30.0
BE_TRIGGER_FRAC = 0.5


class NQOnDynExits(QCAlgorithm):

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
        self.n_tags = 0

        self.on_h = None
        self.on_l = None
        self.cur_date = None
        self._reset_rth()

    def _reset_rth(self):
        self.rth_open = None
        self.onh_frozen = None
        self.onl_frozen = None
        self.dir = 0
        self.tp_lvl = None
        self.tp_dist = 0.0
        # state per variant:
        # each entry: dict(sl_lvl, res=None, pnl=None, extra info)
        self.v = {}
        self.emitted_today = False

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def _init_trade(self):
        o = self.rth_open
        onh = self.onh_frozen
        onl = self.onl_frozen
        onm = (onh + onl) / 2.0
        R = onh - onl

        if o > onm:
            self.dir = 1
            self.tp_lvl = onh
            self.tp_dist = onh - o
            # SL levels (below open for long)
            sl_W = onl - 0.25 * R
            sl_V = onl - 0.50 * R
            sl_B = o - self.tp_dist        # 1:1 mirror, may move to entry
            sl_T = o - TRAIL_PTS           # trailing, may rise as MFE grows
        elif o < onm:
            self.dir = -1
            self.tp_lvl = onl
            self.tp_dist = o - onl
            # SL levels (above open for short)
            sl_W = onh + 0.25 * R
            sl_V = onh + 0.50 * R
            sl_B = o + self.tp_dist
            sl_T = o + TRAIL_PTS
        else:
            self.dir = 0
            return

        self.v["W"] = dict(sl=sl_W, res=None, pnl=None)
        self.v["V"] = dict(sl=sl_V, res=None, pnl=None)
        self.v["B"] = dict(sl=sl_B, res=None, pnl=None, moved=False)
        self.v["T"] = dict(sl=sl_T, res=None, pnl=None, best_favorable=0.0)

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        d = t.date()
        mend = t.hour * 60 + t.minute

        in_on = (mend >= 1080) or (mend <= 570)
        in_rth = 571 <= mend <= 960

        if in_on:
            if self.on_h is None:
                self.on_h = bar.High; self.on_l = bar.Low
            else:
                self.on_h = max(self.on_h, bar.High)
                self.on_l = min(self.on_l, bar.Low)

        if self.cur_date is None:
            self.cur_date = d
        elif d != self.cur_date:
            if not self.emitted_today:
                self._emit_day(bar_close=bar.Close)
            self._reset_rth()
            self.cur_date = d

        if mend == 571 and self.rth_open is None and self.on_h is not None:
            self.rth_open = bar.Open
            self.onh_frozen = self.on_h
            self.onl_frozen = self.on_l
            self.on_h = None; self.on_l = None
            self._init_trade()

        if in_rth and self.dir != 0:
            self._process_bar(bar)

        if mend == 960 and not self.emitted_today and self.rth_open is not None:
            self._emit_day(bar_close=bar.Close)
            self.emitted_today = True

    def _process_bar(self, bar):
        o = self.rth_open
        dr = self.dir
        # favorable / adverse for this bar
        if dr == 1:
            fav = bar.High - o
            adv = o - bar.Low
            bar_hi = bar.High; bar_lo = bar.Low
        else:
            fav = o - bar.Low
            adv = bar.High - o
            bar_hi = bar.High; bar_lo = bar.Low

        # BE variant: move SL to entry when MFE >= 50% of TP dist
        stB = self.v.get("B")
        if stB and stB["res"] is None and not stB["moved"]:
            if fav >= BE_TRIGGER_FRAC * self.tp_dist:
                stB["sl"] = o
                stB["moved"] = True

        # T variant: raise SL to best_favorable - TRAIL_PTS (only tightens)
        stT = self.v.get("T")
        if stT and stT["res"] is None:
            if fav > stT["best_favorable"]:
                stT["best_favorable"] = fav
                new_sl = (o + stT["best_favorable"] - TRAIL_PTS) if dr == 1 else (o - stT["best_favorable"] + TRAIL_PTS)
                if dr == 1 and new_sl > stT["sl"]:
                    stT["sl"] = new_sl
                elif dr == -1 and new_sl < stT["sl"]:
                    stT["sl"] = new_sl

        # For every variant not yet resolved: check TP / SL first-hit
        for key, st in self.v.items():
            if st["res"] is not None:
                continue
            if dr == 1:
                tp_hit = bar_hi >= self.tp_lvl
                sl_hit = bar_lo <= st["sl"]
            else:
                tp_hit = bar_lo <= self.tp_lvl
                sl_hit = bar_hi >= st["sl"]
            if tp_hit and sl_hit:
                st["res"] = "B"        # ambivalent
                st["pnl"] = dr * (st["sl"] - o)
            elif tp_hit:
                st["res"] = "T"
                st["pnl"] = dr * (self.tp_lvl - o)
            elif sl_hit:
                st["res"] = "S"
                st["pnl"] = dr * (st["sl"] - o)

    def _emit_day(self, bar_close):
        if self.rth_open is None or self.onh_frozen is None or self.dir == 0:
            return
        # any still open -> EOD
        for st in self.v.values():
            if st["res"] is None:
                st["res"] = "E"
                st["pnl"] = self.dir * (bar_close - self.rth_open)

        parts = [
            "OD", self.cur_date.strftime("%Y-%m-%d"), str(self.dir),
            f"{self.rth_open:.2f}", f"{self.onh_frozen:.2f}", f"{self.onl_frozen:.2f}",
            f"{bar_close:.2f}",
        ]
        for key in ("W", "V", "B", "T"):
            st = self.v[key]
            parts.append(st["res"])
            parts.append(f"{st['pnl']:.2f}")
            parts.append(f"{st['sl']:.2f}")
        self._emit(",".join(parts))

    def OnEndOfAlgorithm(self):
        self.Log(f"OD_TAGS={self.n_tags}")
