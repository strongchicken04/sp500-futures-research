# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# TradeX ORB Sniper V3 - druha iterace rekonstrukce.
#
# Nove info z vendor popisu + strategy reportu (Oct 2022 - Sep 2025):
#   888 obchodu, win 75.23 %, PF 1.256 -> avgWin/avgLoss = 0.41
#   => STOP je ~2.4x SIRSI nez TP (vysoka win rate, zaporny skew)
#   "ATR volatility framework", "minimum threshold 11 points"
#
# Proto: (a) SIROKA mrizka stopu 0.6-2.0 x R (predchozi koncila na 0.5R),
#        (b) zaznam ATR(14) pro ATR-kotvene varianty,
#        (c) KLICOVE: obe intrabar konvence pro kazdy stop:
#            p{k} = MFE pred barem, kde stop padl  (konzervativni: stop vyhrava)
#            i{k} = MFE vcetne toho baru           (optimisticka: TP vyhrava)
#            Rozdil p vs i = presne to, co TradingView hada.
#
# Range/vstup shodne s v1: 9:30-9:45 ET, close 5m svicky za range,
# max 1 long + 1 short/den, vstupy do 15:00, EOD 16:00.
# Tag: OS,date,dir,R,atr,entry,tmin,p06,p09,p12,p15,p20,i06,i09,i12,i15,i20,mae,eod

SLS = (0.6, 0.9, 1.2, 1.5, 2.0)
ENTRY_CUTOFF = 900


class NQOrbSniperV2(QCAlgorithm):

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
        self.tr_hist = deque(maxlen=14)     # true range poslednich 14 RTH dni
        self.prev_close = None
        self.d_hi = None
        self.d_lo = None
        self.atr = 0.0
        self._reset_day()

    def _reset_day(self):
        self.rh = None
        self.rl = None
        self.taken = {1: False, -1: False}
        self.open_trades = []

    def _roll_atr(self):
        # uzavri predchozi den do ATR historie
        if self.d_hi is not None and self.d_lo is not None:
            if self.prev_close is None:
                tr = self.d_hi - self.d_lo
            else:
                tr = max(self.d_hi - self.d_lo,
                         abs(self.d_hi - self.prev_close),
                         abs(self.d_lo - self.prev_close))
            self.tr_hist.append(tr)
            if len(self.tr_hist) == 14:
                self.atr = sum(self.tr_hist) / 14.0
        self.d_hi = None
        self.d_lo = None

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
            self._roll_atr()                 # ATR z dokonceneho dne (past-only)
            self.cur_date = d
            self._reset_day()

        mend = t.hour * 60 + t.minute
        if not (571 <= mend <= 960):
            return

        # denni H/L/C pro ATR
        self.d_hi = bar.High if self.d_hi is None else max(self.d_hi, bar.High)
        self.d_lo = bar.Low if self.d_lo is None else min(self.d_lo, bar.Low)
        if mend == 960:
            self.prev_close = bar.Close

        # ---------- 1) range 9:30-9:45 ----------
        if mend <= 585:
            self.rh = bar.High if self.rh is None else max(self.rh, bar.High)
            self.rl = bar.Low if self.rl is None else min(self.rl, bar.Low)
            return
        if self.rh is None or self.rl is None:
            return
        R = self.rh - self.rl
        if R <= 0:
            return

        # ---------- 2) sprava otevrenych obchodu ----------
        for tr in self.open_trades:
            if tr["done"]:
                continue
            if tr["skip"]:
                tr["skip"] = False
                continue
            dirn = tr["dir"]
            fav = (bar.High - tr["entry"]) if dirn == 1 else (tr["entry"] - bar.Low)
            adv = (tr["entry"] - bar.Low) if dirn == 1 else (bar.High - tr["entry"])
            tr["mae"] = max(tr["mae"], adv)
            for k in SLS:
                if not tr["hit"][k]:
                    if adv >= k * R:
                        tr["hit"][k] = True
                        # optimisticka verze: zapocti i favorable z TOHOTO baru
                        tr["inc"][k] = max(tr["inc"][k], fav)
                    else:
                        tr["pre"][k] = max(tr["pre"][k], fav)
                        tr["inc"][k] = max(tr["inc"][k], fav)
            if mend == 960:
                eod = dirn * (bar.Close - tr["entry"])
                p = tr["pre"]; i = tr["inc"]
                self._emit(
                    f"OS,{d.strftime('%Y-%m-%d')},{dirn},{R:.2f},{self.atr:.2f},"
                    f"{tr['entry']:.2f},{tr['tmin']},"
                    f"{p[0.6]:.2f},{p[0.9]:.2f},{p[1.2]:.2f},{p[1.5]:.2f},{p[2.0]:.2f},"
                    f"{i[0.6]:.2f},{i[0.9]:.2f},{i[1.2]:.2f},{i[1.5]:.2f},{i[2.0]:.2f},"
                    f"{tr['mae']:.2f},{eod:.2f}")
                tr["done"] = True

        # ---------- 3) vstup na close 5m svicky ----------
        if (mend - 570) % 5 != 0 or mend > ENTRY_CUTOFF:
            return
        c5 = bar.Close
        side = 1 if c5 > self.rh else (-1 if c5 < self.rl else 0)
        if side != 0 and not self.taken[side]:
            self.taken[side] = True
            self.open_trades.append(dict(
                dir=side, entry=c5, tmin=mend - 570, skip=True, done=False, mae=0.0,
                pre={k: 0.0 for k in SLS}, inc={k: 0.0 for k in SLS},
                hit={k: False for k in SLS}))

    def OnEndOfAlgorithm(self):
        self.Log(f"OS_TAGS={self.n_tags}")
