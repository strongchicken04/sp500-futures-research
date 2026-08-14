# region imports
from AlgorithmImports import *
# endregion

# Powell Trades "key opens" test (mechanizovane jadro z videa).
#
# TEST 1 - 10am open: manipulace -> reverz -> retest:
#   open10 = open 1m svicky 10:00 ET (= open 4h/1h svicky)
#   1) manipulace: cena >= MANIP_BPS nad/pod open10 (prvni strana vyhrava)
#   2) reverz: prvni 5m close na OPACNE strane open10
#   3) retest: nasledny 1m dotek open10 -> vstup ve smeru reverzu za open10
#   Zaznamenavame MFE pred vyrazenim stopu 15 b a 25 b + PnL/MAE do 15:59
#   -> lokalne lze vyhodnotit libovolny stop x target bracket.
#   Tag: PT,date,dir,manipbps,entry,mfe15,mfe25,mae,pnlEOD  (body)
#
# TEST 2 - midnight open magnet:
#   mno = open 1m svicky 00:00 ET; overnight (00:00-9:30) exkurze pod/nad
#   v bps; dotek urovne behem RTH; vzdalenost 9:30 openu od urovne.
#   Tag: MN,date,mno,belowbps,abovebps,rthtouch,dist930bps

MANIP_BPS = 20.0
STOPS = (15.0, 25.0)
ENTRY_CUTOFF = 835     # posledni vstup 13:55
EOD = 959


class NQPowellKeyOpen(QCAlgorithm):

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
        self.cur_date = None
        self.n_tags = 0
        self._reset_day()

    def _reset_day(self):
        # test 1
        self.open10 = None
        self.phase = 0          # 0 ceka, 1 manipulace probehla, 2 reverz, 3 v obchode, 4 hotovo
        self.manip_side = 0
        self.manip_max = 0.0
        self.c5_o = None        # 5m konsolidace
        self.bucket5 = None
        self.dirn = 0
        self.entry = None
        self.mfe = 0.0
        self.mae = 0.0
        self.stop_hit = {s: False for s in STOPS}
        self.mfe_pre = {s: 0.0 for s in STOPS}
        self.pnl_eod = None
        # test 2
        self.mno = None
        self.ov_below = 0.0
        self.ov_above = 0.0
        self.rth_touch = False
        self.dist930 = None

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
        if self.cur_date is None:
            self.cur_date = d
        if d != self.cur_date:
            self.cur_date = d
            self._reset_day()

        mend = t.hour * 60 + t.minute

        # ---------- TEST 2: midnight open ----------
        if mend == 1:                      # bar 00:00-00:01
            self.mno = bar.Open
            self.ov_below = 0.0
            self.ov_above = 0.0
            self.rth_touch = False
            self.dist930 = None
        if self.mno is not None:
            if 1 <= mend < 570:            # overnight 00:00-9:30
                self.ov_below = max(self.ov_below, (self.mno - bar.Low) / self.mno * 1e4)
                self.ov_above = max(self.ov_above, (bar.High - self.mno) / self.mno * 1e4)
            elif 571 <= mend <= 960:
                if self.dist930 is None:
                    self.dist930 = (bar.Open - self.mno) / self.mno * 1e4
                if bar.Low <= self.mno <= bar.High:
                    self.rth_touch = True
                if mend == 960:
                    self._emit(f"MN,{d.strftime('%Y-%m-%d')},{self.mno:.2f},"
                               f"{self.ov_below:.1f},{self.ov_above:.1f},"
                               f"{int(self.rth_touch)},{self.dist930:.1f}")

        # ---------- TEST 1: 10am open ----------
        if not (571 <= mend <= 960):
            return
        if mend == 601:                    # bar 10:00-10:01
            self.open10 = bar.Open
            self.bucket5 = (mend - 601) // 5
            self.c5_o = None
            return
        if self.open10 is None or self.phase == 4:
            return
        lvl = self.open10

        # sprava otevreneho obchodu
        if self.phase == 3:
            fav = (bar.High - self.entry) if self.dirn == 1 else (self.entry - bar.Low)
            adv = (self.entry - bar.Low) if self.dirn == 1 else (bar.High - self.entry)
            self.mae = max(self.mae, adv)
            for s in STOPS:
                if not self.stop_hit[s]:
                    if adv >= s:
                        self.stop_hit[s] = True
                    else:
                        self.mfe_pre[s] = max(self.mfe_pre[s], fav)
            self.mfe = max(self.mfe, fav)
            if mend == EOD:
                pnl = self.dirn * (bar.Close - self.entry)
                self._emit(f"PT,{d.strftime('%Y-%m-%d')},{self.dirn},{self.manip_max:.1f},"
                           f"{self.entry:.2f},{self.mfe_pre[STOPS[0]]:.2f},"
                           f"{self.mfe_pre[STOPS[1]]:.2f},{self.mae:.2f},{pnl:.2f}")
                self.phase = 4
            return

        # 5m konsolidace pro reverz-close
        b5 = (mend - 601) // 5
        if self.c5_o is None:
            self.c5_o = bar.Open
        new5 = b5 != self.bucket5
        c5_close = None
        if new5:
            c5_close = self.prev_close if hasattr(self, "prev_close") else bar.Open
            self.bucket5 = b5
            self.c5_o = bar.Open
        self.prev_close = bar.Close

        if self.phase == 0:
            dist_up = (bar.High - lvl) / lvl * 1e4
            dist_dn = (lvl - bar.Low) / lvl * 1e4
            if dist_up >= MANIP_BPS or dist_dn >= MANIP_BPS:
                self.manip_side = 1 if dist_up >= dist_dn else -1
                self.manip_max = max(dist_up, dist_dn)
                self.phase = 1
        elif self.phase == 1:
            # sleduj velikost manipulace dal; reverz = 5m close na opacne strane
            if self.manip_side == 1:
                self.manip_max = max(self.manip_max, (bar.High - lvl) / lvl * 1e4)
            else:
                self.manip_max = max(self.manip_max, (lvl - bar.Low) / lvl * 1e4)
            if new5 and c5_close is not None:
                if self.manip_side == 1 and c5_close < lvl:
                    self.dirn = -1
                    self.phase = 2
                elif self.manip_side == -1 and c5_close > lvl:
                    self.dirn = 1
                    self.phase = 2
        elif self.phase == 2:
            if mend > ENTRY_CUTOFF:
                self.phase = 4
                return
            if bar.Low <= lvl <= bar.High:
                self.entry = lvl
                self.phase = 3
                self.mfe = 0.0
                self.mae = 0.0

    def OnEndOfAlgorithm(self):
        self.Log(f"PT_TAGS={self.n_tags}")
