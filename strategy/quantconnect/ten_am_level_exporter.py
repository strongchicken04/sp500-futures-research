# region imports
from AlgorithmImports import *
# endregion

# 10:00 open level test (napad uzivatele) - reaktivita a prediktivni sila
# openu 1m svicky 10:00 ET vs placebo urovne (open 9:45 a open 10:15 svicky,
# stejne "stari" urovne pri startu sledovani).
#
# Pro kazdy den a uroven (M=10:00, A=9:45, B=10:15) sledujeme od nasledujici
# minuty do 16:00:
#   ncross    = pocet zmen znamenka (close - lvl)  ... hruba reaktivita
#   minsAbove = minut s close > lvl
#   prvni navrat po vzdaleni >= 20 bps: strana prichodu, vynos 15 a 30 minut
#     po doteku VE SMERU odrazu (kladne = uroven drzela)
#   pos1030   = znamenko (close 10:30 - lvl), retC = vynos 10:30 -> close
# Tag: OT,date,which,lvl,ncross,minsAbove,ftSide,ftF15,ftF30,pos1030,retC

DEPART_BPS = 20.0


class NQTenAmLevel(QCAlgorithm):

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
        # konfigurace: which -> (minuta konce level baru); level bar 10:00-10:01 konci 601
        self.trk = {"M": {"m0": 601}, "A": {"m0": 586}, "B": {"m0": 616}}
        for k in self.trk:
            self.trk[k].update(lvl=None, ncross=0, above=0, prev_sign=0,
                               departed=False, ft_side=0, ft_idx=None,
                               ft_f15=None, ft_f30=None, bars=0)
        self.c1030 = None
        self.c_eod = None

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

        if mend == 630:
            self.c1030 = bar.Close
        self.c_eod = bar.Close

        for k, s in self.trk.items():
            if mend == s["m0"]:
                s["lvl"] = bar.Open
                s["prev_sign"] = 1 if bar.Close > bar.Open else (-1 if bar.Close < bar.Open else 0)
                continue
            if s["lvl"] is None or mend <= s["m0"]:
                continue
            lvl = s["lvl"]
            s["bars"] += 1
            sign = 1 if bar.Close > lvl else (-1 if bar.Close < lvl else 0)
            if sign != 0 and s["prev_sign"] != 0 and sign != s["prev_sign"]:
                s["ncross"] += 1
            if sign != 0:
                s["prev_sign"] = sign
            if bar.Close > lvl:
                s["above"] += 1
            # odchod a prvni navrat
            dist = abs(bar.Close / lvl - 1.0) * 1e4
            if not s["departed"]:
                if dist >= DEPART_BPS:
                    s["departed"] = True
                    s["dep_side"] = 1 if bar.Close > lvl else -1
            elif s["ft_idx"] is None:
                if bar.Low <= lvl <= bar.High:
                    s["ft_side"] = s["dep_side"]       # +1 = prichod shora (support test)
                    s["ft_idx"] = s["bars"]
                    s["ft_px"] = bar.Close
            if s["ft_idx"] is not None:
                if s["ft_f15"] is None and s["bars"] == s["ft_idx"] + 15:
                    s["ft_f15"] = (bar.Close / lvl - 1.0) * 1e4 * s["ft_side"]
                if s["ft_f30"] is None and s["bars"] == s["ft_idx"] + 30:
                    s["ft_f30"] = (bar.Close / lvl - 1.0) * 1e4 * s["ft_side"]

        if mend == 960:
            for k, s in self.trk.items():
                if s["lvl"] is None:
                    continue
                pos = 0
                retc = 0.0
                if self.c1030 is not None and self.c_eod is not None:
                    pos = 1 if self.c1030 > s["lvl"] else (-1 if self.c1030 < s["lvl"] else 0)
                    retc = (self.c_eod / self.c1030 - 1.0) * 1e4
                f15 = s["ft_f15"] if s["ft_f15"] is not None else -9999
                f30 = s["ft_f30"] if s["ft_f30"] is not None else -9999
                tag = (f"OT,{d.strftime('%Y-%m-%d')},{k},{s['lvl']:.2f},{s['ncross']},"
                       f"{s['above']},{s['ft_side']},{f15:.1f},{f30:.1f},{pos},{retc:.1f}")
                self._emit(tag)

    def OnEndOfAlgorithm(self):
        self.Log(f"OT_TAGS={self.n_tags}")
