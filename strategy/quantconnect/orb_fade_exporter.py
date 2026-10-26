# region imports
from AlgorithmImports import *
# endregion

# ORB FADE test - preregistrovana konfigurace (uzivatelov navrh).
#
# Pravidla:
#   range = high/low 9:30-9:45 ET (3 x 5min = 15 min, na 1min chartu)
#   signal: 1m close VENKU za range, nasledne 1m close ZPET UVNITR
#   vstup: close reclaim svicky (te, ktera vratila cenu do range)
#   smer:  proti breakoutu (up-break -> short, down-break -> long)
#   TP:    entry +/- 0.5 * R  (50 % velikosti range, ve smeru fade)
#   SL:    entry -/+ 0.5 * R  (1:1 RR)
#   1 fade na stranu/den, EOD 15:59 flat, vstupy do 15:00
#
# Preregistrovana pass kriteria (fix pred spustenim):
#   1) avg bps/obchod > 0 net (0.75 pts costs) pres 2018-2025
#   2) z > 1.0
#
# Tag: OF,date,dir,R,entry,tp,sl,tmin,mfe,mae,exit,pnl,how
#   how: T=TP, S=SL, E=EOD, A=ambivalent (TP+SL v jedne minute -> pocitano SL)

ENTRY_CUTOFF = 900   # posledni vstup 15:00


class NQOrbFade(QCAlgorithm):

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
        self.cur_date = None
        self.n_tags = 0
        self._reset_day()

    def _reset_day(self):
        self.rh = None
        self.rl = None
        # stav breakoutu pro kazdou stranu:
        #  None = nic; "out" = 1m close venku (ceka na reclaim);
        #  "faded" = fade uz probehl dnes (max 1x na stranu)
        self.brk = {1: None, -1: None}
        self.open_trades = []

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
        if not (571 <= mend <= 960):
            return

        # ---------- 1) stavba range 9:30-9:45 ----------
        if mend <= 585:
            self.rh = bar.High if self.rh is None else max(self.rh, bar.High)
            self.rl = bar.Low if self.rl is None else min(self.rl, bar.Low)
            return
        if self.rh is None or self.rl is None:
            return
        R = self.rh - self.rl
        if R <= 0:
            return

        # ---------- 2) sprava otevrenych obchodu (1min close-based) ----------
        for tr in self.open_trades:
            if tr["done"]:
                continue
            if tr["skip"]:                          # vstupni bar se nepocita
                tr["skip"] = False
                continue
            dirn = tr["dir"]
            fav = (bar.High - tr["entry"]) if dirn == 1 else (tr["entry"] - bar.Low)
            adv = (tr["entry"] - bar.Low) if dirn == 1 else (bar.High - tr["entry"])
            tr["mfe"] = max(tr["mfe"], fav)
            tr["mae"] = max(tr["mae"], adv)

            # rozhodnuti CLOSE-BASED (konzervativne: kdyz obe padly v teze minute, SL)
            close_fav = (bar.Close - tr["entry"]) if dirn == 1 else (tr["entry"] - bar.Close)
            close_adv = -close_fav
            tp_hit = close_fav >= tr["tp_dist"]
            sl_hit = close_adv >= tr["sl_dist"]
            exit_reason = None
            exit_px = None
            if sl_hit:
                exit_reason = "S" if not tp_hit else "A"
                exit_px = bar.Close
            elif tp_hit:
                exit_reason = "T"
                exit_px = bar.Close
            elif mend == 959:
                exit_reason = "E"
                exit_px = bar.Close

            if exit_reason:
                pnl = dirn * (exit_px - tr["entry"])
                self._emit(f"OF,{d.strftime('%Y-%m-%d')},{dirn},{R:.2f},{tr['entry']:.2f},"
                           f"{tr['tp_dist']:.2f},{tr['sl_dist']:.2f},{tr['tmin']},"
                           f"{tr['mfe']:.2f},{tr['mae']:.2f},{exit_px:.2f},{pnl:.2f},"
                           f"{exit_reason}")
                tr["done"] = True

        # ---------- 3) detekce fade setupu (1min close) ----------
        if mend > ENTRY_CUTOFF:
            return
        c = bar.Close

        # up-side (breakout nahoru -> fade short)
        if self.brk[1] != "faded":
            if self.brk[1] is None:
                if c > self.rh:
                    self.brk[1] = "out"
            elif self.brk[1] == "out":
                if c <= self.rh:                    # reclaim -> fade short
                    self.open_trades.append(dict(
                        dir=-1, entry=c, tp_dist=0.5 * R, sl_dist=0.5 * R,
                        tmin=mend - 570, skip=True, done=False, mfe=0.0, mae=0.0))
                    self.brk[1] = "faded"

        # down-side
        if self.brk[-1] != "faded":
            if self.brk[-1] is None:
                if c < self.rl:
                    self.brk[-1] = "out"
            elif self.brk[-1] == "out":
                if c >= self.rl:                    # reclaim -> fade long
                    self.open_trades.append(dict(
                        dir=1, entry=c, tp_dist=0.5 * R, sl_dist=0.5 * R,
                        tmin=mend - 570, skip=True, done=False, mfe=0.0, mae=0.0))
                    self.brk[-1] = "faded"

    def OnEndOfAlgorithm(self):
        self.Log(f"OF_TAGS={self.n_tags}")
