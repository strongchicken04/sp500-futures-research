# region imports
from AlgorithmImports import *
import math
# endregion
#
# CZECH MIDNIGHT OPEN, round 5 - ANCHOR CONTROL for the round-4 candidate (E15 BIG:
# +2.1 / +1.1 / +5.7 / +3.3 bp, t 3.2 on NQ). Same trade (entry 15:00 close, exit 15:59, no
# stop / 0.5% stop), the anchor varied: O18 (18:00 ET), RTH 09:30 open, prior 16:00 close,
# 00:00 ET open; size filter |price / anchor - 1| >= 0.25 / 0.50 / 1.00%; yearly line and
# worst trade for O18 0.50% no stop. Is it the Czech midnight open or late momentum on
# a trending day? Fixed before results.
# (round 4 header kept below)
# CZECH MIDNIGHT OPEN, round 4 - the late-day continuation as a TRADE (round 3:
# the side of the 15:00 price vs the 18:00 ET open predicted 15:00 -> 16:00 in
# all eras on NQ (+0.2..+3.2 bp, t 2.8) and ES (t 2.4), slightly better than the
# same from the 09:30 open). Rules FIXED BEFORE RESULTS:
#   Entry at the close of the 15:00 bar (E15) or the 15:30 bar (E1530) in the
#   direction of sign(price - O18); exit at the 15:59 bar close (prop: flat
#   before 16:00 close auction risk); optional stop 0.30% / 0.50% from the entry
#   (minute lows / highs, filled at the worse of stop and the minute open).
#   Filters: ALL; BIG (|price / O18 - 1| >= 0.50%); AGREE (O18 side = side vs
#   the 09:30 open = side vs the RTH VWAP); BIG+AGREE.
#   Results: gross bp per trade by era, t, win %, and net bp at TODAY's price
#   (NQ 1.25 pt / 28,530; ES 0.5 pt / 6,800 per round trip) - the cost in bp of
#   2010 prices is not today's cost; $ per year at 3 MNQ / 3 MES at today's price.
# Verdict: CANDIDATE if gross > 0 in all four eras, t >= 3 pooled, net > 0.

START = (2010, 1, 1)
END = (2026, 12, 31)
MARKET = "ES"
ERAS = (("10-13", 2010, 2013), ("14-17", 2014, 2017), ("18-21", 2018, 2021), ("22-26", 2022, 2026))
PRICE = {"NQ": 28530.0, "ES": 6800.0}
COSTPT = {"NQ": 1.25, "ES": 0.5}
PV = {"NQ": 2.0, "ES": 5.0}


def era_of(y):
    for i, (_, a, b) in enumerate(ERAS):
        if a <= y <= b:
            return i
    return None


def tstat(v):
    n = len(v)
    if n < 3:
        return 0.0
    mu = sum(v) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in v) / (n - 1))
    return mu / (sd / math.sqrt(n)) if sd > 0 else 0.0


class MidnightLateInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        tk = {"NQ": Futures.Indices.NASDAQ_100_E_MINI, "ES": Futures.Indices.SP_500_E_MINI}[MARKET]
        self.f = self.add_future(tk, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.o18 = self.d18 = self.map18 = None
        self.o00 = None
        self.pdc = None
        self.rday = None
        self.trades = {}        # key -> list of (era, bp)
        self.open = []          # live trades of today

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        if 18 * 60 < m <= 18 * 60 + 15 and self.d18 != t.date():
            self.o18, self.d18, self.map18 = o, t.date(), self.f.mapped
            self.o00 = None
        if 0 < m <= 15 and self.o00 is None and self.o18 is not None:
            self.o00 = o
        if m == 16 * 60:
            self.pdc_next = c
        if not (9 * 60 + 30 < m <= 16 * 60):
            return
        if self.rday != t.date():
            self.rday = t.date()
            self.ropen = o
            self.pdc = getattr(self, "pdc_next", None)
            self.pv = self.vv = 0.0
            self.open = []
        self.pv += (h + l + c) / 3.0 * v
        self.vv += v
        # manage open trades
        for tr in self.open:
            if tr["done"]:
                continue
            d, e, sp = tr["d"], tr["e"], tr["sp"]
            if sp:
                stop = e * (1 - d * sp)
                if (d == 1 and l <= stop) or (d == -1 and h >= stop):
                    px = min(stop, o) if d == 1 else max(stop, o)
                    self._book(tr, px, t)
                    continue
            if m >= 15 * 60 + 59:
                self._book(tr, c, t)
        if self.o18 is None or self.f.mapped != self.map18 or (t.date() - self.d18).days > 4:
            return
        if m == 15 * 60:
            for an, X in (("O18", self.o18), ("OPEN", self.ropen), ("PDC", self.pdc), ("O00", self.o00)):
                if X is None:
                    continue
                d = 1 if c > X else (-1 if c < X else 0)
                if d == 0:
                    continue
                mv = abs(c / X - 1)
                for th in (0.0025, 0.005, 0.01):
                    if mv < th:
                        continue
                    for sp in (0.0, 0.005):
                        self.open.append({"key": (an, th, sp), "d": d, "e": c, "sp": sp, "done": False})

    def _book(self, tr, px, t):
        tr["done"] = True
        bp = tr["d"] * (px / tr["e"] - 1) * 1e4
        self.trades.setdefault(tr["key"], []).append((era_of(t.year), bp, t.year))

    def on_end_of_algorithm(self):
        cost_bp = COSTPT[MARKET] / PRICE[MARKET] * 1e4
        for key in sorted(self.trades):
            tr = self.trades[key]
            per = [[x[1] for x in tr if x[0] == i] for i in range(len(ERAS))]
            allv = [x[1] for x in tr]
            n = len(allv)
            mu = sum(allv) / n
            an, th, sp = key
            self.set_runtime_statistic(f"ML5 {MARKET} {an} >={th * 100:.2f}% sl{sp * 100:.1f}",
                                       " ".join(f"{sum(p) / len(p):+.2f}" if p else "-" for p in per)
                                       + f" | {mu:+.2f}bp t{tstat(allv):+.1f} net {mu - cost_bp:+.2f} n{n}")
            if key == ("O18", 0.005, 0.0):
                ys = sorted(set(x[2] for x in tr))
                self.set_runtime_statistic(f"ML5 {MARKET} O18 0.5% years", " ".join(
                    f"{y % 100}:{sum(x[1] for x in tr if x[2] == y) / max(1, sum(1 for x in tr if x[2] == y)):+.1f}" for y in ys))
                self.set_runtime_statistic(f"ML5 {MARKET} O18 0.5% worst/best", f"{min(allv):.0f} / {max(allv):.0f} bp; "
                                           f"share < -50bp {sum(1 for x in allv if x < -50) / n * 100:.1f}%")
