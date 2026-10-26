# region imports
from AlgorithmImports import *
# endregion

# TradeX ORB Sniper (rekonstrukce rodiny) - 15min opening range breakout.
#
# Pravidla odvozena ze screenshotu + popisu indikatoru:
#   range  = high/low prvnich 15 min RTH (9:30-9:45 ET, tri 5m svicky)
#   vstup  = CLOSE 5m svicky za range (nad = long, pod = short), od 9:45
#   limit  = max 1 long + 1 short za den, vstupy do 15:00, EOD exit 16:00
#   TP/SL  = nasobky velikosti range R (vendor konstanty neznamy ->
#            testujeme celou rodinu)
#
# Pro kazdy obchod zaznamename MFE dosazene PRED zasahem daneho SL
# (konzervativne: bar, ve kterem SL padne, se do MFE nepocita) pro
# SL v {0.15, 0.25, 0.35, 0.50} x R. Lokalne pak vyhodnotime libovolne
# TP: vyhra <=> mfe_pre[SL] >= TP.
# Tag: OB,date,dir,R,entry,tmin,m15,m25,m35,m50,mae,eod   (body)

SLS = (0.15, 0.25, 0.35, 0.50)
ENTRY_CUTOFF = 900          # posledni vstup 15:00 (minuta konce baru)


class NQOrbSniper(QCAlgorithm):

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
        self.taken = {1: False, -1: False}
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

        # ---------- 2) sprava otevrenych obchodu (1min rozliseni) ----------
        for tr in self.open_trades:
            if tr["done"]:
                continue
            if tr["skip"]:                      # vstupni bar se nepocita
                tr["skip"] = False
                continue
            dirn = tr["dir"]
            fav = (bar.High - tr["entry"]) if dirn == 1 else (tr["entry"] - bar.Low)
            adv = (tr["entry"] - bar.Low) if dirn == 1 else (bar.High - tr["entry"])
            tr["mae"] = max(tr["mae"], adv)
            for k in SLS:
                if not tr["sl_hit"][k]:
                    if adv >= k * R:
                        tr["sl_hit"][k] = True      # MFE zamrzne pred timto barem
                    else:
                        tr["mfe"][k] = max(tr["mfe"][k], fav)
            if mend == 960:
                eod = dirn * (bar.Close - tr["entry"])
                self._emit(f"OB,{d.strftime('%Y-%m-%d')},{dirn},{R:.2f},{tr['entry']:.2f},"
                           f"{tr['tmin']},{tr['mfe'][0.15]:.2f},{tr['mfe'][0.25]:.2f},"
                           f"{tr['mfe'][0.35]:.2f},{tr['mfe'][0.50]:.2f},"
                           f"{tr['mae']:.2f},{eod:.2f}")
                tr["done"] = True

        # ---------- 3) vstupy na close 5m svicky ----------
        if (mend - 570) % 5 != 0 or mend > ENTRY_CUTOFF:
            return
        c5 = bar.Close
        side = 0
        if c5 > self.rh:
            side = 1
        elif c5 < self.rl:
            side = -1
        if side != 0 and not self.taken[side]:
            self.taken[side] = True
            self.open_trades.append(dict(
                dir=side, entry=c5, tmin=mend - 570, skip=True, done=False,
                mae=0.0, mfe={k: 0.0 for k in SLS}, sl_hit={k: False for k in SLS}))

    def OnEndOfAlgorithm(self):
        self.Log(f"OB_TAGS={self.n_tags}")
