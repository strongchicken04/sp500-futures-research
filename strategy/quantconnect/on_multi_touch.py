# region imports
from AlgorithmImports import *
# endregion

# ON fade — every-touch variant.
#
# Same ON range as before (18:00 prev day -> 9:30 today, Globex).
# Levels: ONH, ONL, ONM. Filter: ON range >= 65 pts.
#
# Direction is ALWAYS toward the RTH open (mean revert to opening bias):
#   ONH: open > ONH -> LONG at ONH,  open < ONH -> SHORT at ONH
#   ONL: open < ONL -> SHORT at ONL, open > ONL -> LONG  at ONL
#   ONM: same rule (open > ONM -> LONG, open < ONM -> SHORT)
#
# Every time price re-touches the level and no fade trade is open on it,
# a new fade is opened. Bracket 1:1, TP/SL = +/-15 pts, EOD flat 15:59.
# Same-bar both-hit -> SL (conservative).
#
# Emit one tag PER TRADE (there can be many per day):
#   MT,date,level,dir,entry,tp,sl,res,pnl
#     level = H/L/M, dir = +1/-1, res = T/S/B/E, pnl in pts

B = 15.0


class NQOnMultiTouch(QCAlgorithm):

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
        self.on_h = None
        self.on_l = None
        self.cur_date = None
        self._reset_rth()

    def _reset_rth(self):
        self.rth_open = None
        self.onh = None
        self.onl = None
        self.onm = None
        # per-level: current open trade (entry, dir, tp, sl) or None
        self.open_trade = {"H": None, "L": None, "M": None}
        # bar-side memory to detect "re-touches": did the PREVIOUS bar
        # contain the level? If yes and this bar doesn't, we've stepped
        # away and are eligible for another entry when we step back.
        self.was_touching = {"H": False, "L": False, "M": False}
        # for ONM we only allow ONE trade per day (per user spec)
        self.m_done = False

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return

        t = self.Time
        d = t.date()
        mend = t.hour * 60 + t.minute
        in_on = (mend >= 1080) or (mend <= 570)
        in_rth = 571 <= mend <= 960
        is_eod = (mend == 960)

        # ---- ON accumulation ----
        if in_on:
            if self.on_h is None:
                self.on_h = bar.High
                self.on_l = bar.Low
            else:
                self.on_h = max(self.on_h, bar.High)
                self.on_l = min(self.on_l, bar.Low)

        # ---- date rollover ----
        if self.cur_date is None:
            self.cur_date = d
        elif d != self.cur_date:
            self._reset_rth()
            self.cur_date = d

        # ---- RTH open freeze ----
        if mend == 571 and self.rth_open is None and self.on_h is not None:
            self.rth_open = bar.Open
            self.onh = self.on_h
            self.onl = self.on_l
            self.onm = (self.onh + self.onl) / 2.0
            self.on_h = None
            self.on_l = None

        if not in_rth or self.rth_open is None:
            return

        # ---- filter: ON range >= 65 ----
        if (self.onh - self.onl) < 65.0:
            return

        # ---- process each level ----
        for key, lvl, once in (("H", self.onh, False),
                                ("L", self.onl, False),
                                ("M", self.onm, self.m_done)):
            if once:
                continue

            # 1) if trade is open on this level, check bracket
            tr = self.open_trade[key]
            if tr is not None:
                dirn = tr["dir"]
                if dirn == 1:
                    tp_hit = bar.High >= tr["tp"]
                    sl_hit = bar.Low  <= tr["sl"]
                else:
                    tp_hit = bar.Low  <= tr["tp"]
                    sl_hit = bar.High >= tr["sl"]
                res = None
                pnl = 0.0
                if tp_hit and sl_hit:
                    res = "B"; pnl = -B
                elif tp_hit:
                    res = "T"; pnl = B
                elif sl_hit:
                    res = "S"; pnl = -B
                elif is_eod:
                    res = "E"; pnl = dirn * (bar.Close - tr["entry"])
                if res is not None:
                    self._emit(f"MT,{self.cur_date.strftime('%Y-%m-%d')},{key},"
                               f"{dirn},{tr['entry']:.2f},{tr['tp']:.2f},"
                               f"{tr['sl']:.2f},{res},{pnl:.2f}")
                    self.open_trade[key] = None
                    if key == "M":
                        self.m_done = True

            # 2) if no trade open and this bar touches the level and prev
            #    bar didn't, open a new fade toward RTH open
            touching = (bar.High >= lvl) and (bar.Low <= lvl)
            can_open = (self.open_trade[key] is None
                        and touching and not self.was_touching[key]
                        and not is_eod)
            if can_open:
                # direction toward open
                if self.rth_open > lvl:
                    dirn = 1
                elif self.rth_open < lvl:
                    dirn = -1
                else:
                    dirn = 0
                if dirn != 0:
                    if dirn == 1:
                        tp = lvl + B
                        sl = lvl - B
                    else:
                        tp = lvl - B
                        sl = lvl + B
                    self.open_trade[key] = dict(entry=lvl, dir=dirn, tp=tp, sl=sl)

            self.was_touching[key] = touching

    def OnEndOfAlgorithm(self):
        self.Log(f"MT_TAGS={self.n_tags}")
