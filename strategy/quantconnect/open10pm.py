# region imports
from AlgorithmImports import *
# endregion

# "10 p.m. open" retest strategie (video #3)
#
# Pravidla:
#   1. Anchor = OPEN ceny 22:00 ET svicky (ne knot, open).
#   2. Breakout: 1m close >= BREAK_PTS bodu za urovni (prvni smer vyhrava).
#   3. Vstup: limit na urovni openu (retest), ve smeru breakoutu
#      (break dolu -> sell limit na openu, break nahoru -> buy limit).
#   4. SL 15 bodu, TP 45 bodu (3:1). 1 obchod/noc.
#   5. Vstupni okno 22:01-01:00 ET; nevyplneny limit se rusi v 01:00.
#      Pozice drzena max do 09:25 ET (flat pred RTH).
#
# Realne ordery, 1 kontrakt NQ, $100k, 2018-2025. Tag na vstupu:
#   TN,date,dir,open=...

BREAK_PTS = 10.0
SL_PTS = 15.0
TP_PTS = 45.0
FILL_WINDOW = 180     # minut od 22:00 (do 01:00 ET)
FLAT_AT = 685         # minut od 22:00 = 09:25 ET


class NQOpen10pm(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(100_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        self.night = None
        self.en_t = None
        self.tp_t = None
        self.sl_t = None

    @staticmethod
    def _tick(px):
        return round(px * 4) / 4.0

    def _cancel(self, tkt):
        if tkt is not None and tkt.Status not in (OrderStatus.Filled, OrderStatus.Canceled, OrderStatus.Invalid):
            tkt.Cancel()

    def _cleanup(self, flatten, why):
        self._cancel(self.en_t)
        self._cancel(self.tp_t)
        self._cancel(self.sl_t)
        if flatten and self.Portfolio.Invested:
            self.Liquidate(tag=why)

    def OnOrderEvent(self, e):
        if e.Status != OrderStatus.Filled:
            return
        if self.en_t is not None and e.OrderId == self.en_t.OrderId and self.night:
            side = self.night["armed"]
            px = e.FillPrice
            sym = e.Symbol
            self.tp_t = self.LimitOrder(sym, -side, self._tick(px + side * TP_PTS), tag="TP")
            self.sl_t = self.StopMarketOrder(sym, -side, self._tick(px - side * SL_PTS), tag="SL")
            self.night["filled"] = True
        elif self.tp_t is not None and e.OrderId == self.tp_t.OrderId:
            self._cancel(self.sl_t)
        elif self.sl_t is not None and e.OrderId == self.sl_t.OrderId:
            self._cancel(self.tp_t)

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        mend = t.hour * 60 + t.minute
        m22 = (mend - 1320) % 1440   # minuty od 22:00 ET (konec baru)

        # novy night anchor: bar koncici 22:01 -> jeho Open = 22:00 open
        if m22 == 1:
            self._cleanup(True, "NewNight")
            self.night = {"open": bar.Open, "armed": 0, "filled": False, "done": False,
                          "date": t.strftime("%Y-%m-%d")}
            self.en_t = self.tp_t = self.sl_t = None
            return
        if self.night is None or self.night["done"]:
            return

        # rano: flat a konec noci
        if m22 >= FLAT_AT:
            self._cleanup(True, "MorningFlat")
            self.night["done"] = True
            return

        # po vyplneni vstupu exity resi bracket u brokera
        if self.night["filled"]:
            return

        lvl = self.night["open"]

        # konec vstupniho okna -> zrusit nevyplneny limit
        if m22 > FILL_WINDOW:
            if self.en_t is not None:
                self._cancel(self.en_t)
            self.night["done"] = True
            return

        # detekce breakoutu (prvni smer vyhrava)
        if self.night["armed"] == 0:
            sym = self.future.Mapped
            if sym is None or sym not in self.Securities or self.Securities[sym].Price <= 0:
                return
            if bar.Close <= lvl - BREAK_PTS:
                self.night["armed"] = -1
                tag = f"TN,{self.night['date']},S,open={lvl:.2f}"
                self.en_t = self.LimitOrder(sym, -1, self._tick(lvl), tag=tag)
            elif bar.Close >= lvl + BREAK_PTS:
                self.night["armed"] = +1
                tag = f"TN,{self.night['date']},L,open={lvl:.2f}"
                self.en_t = self.LimitOrder(sym, 1, self._tick(lvl), tag=tag)
