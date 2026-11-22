# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# INTRADAY TREND / MOMENTUM FOLLOWER, LONG AND SHORT (owner 2026-11-22: "NQ fell 5% on Friday, we are in a big
# downtrend - develop a good trend / momentum follower, not only long but short too"). NQ minute 2010-2026
# INSIDE QuantConnect, aggregates only, 1 NQ, $15 per trade, flat every day. FIXED BEFORE RESULTS:
#   Noise Area (Zarattini-Aziz-Barbon 2024): sigma(m) = mean over the last 14 days of |close(m)/O - 1| at the
#     same minute m (O = RTH open); UB(m) = max(O, prevC) x (1 + sigma), LB(m) = min(O, prevC) x (1 - sigma).
#   NA30      checks at 10:00, 10:30, ..., 15:30 ET (bar-end clock): flat & p > UB -> long, p < LB -> short;
#             long exits when p < max(UB, VWAP), short when p > min(LB, VWAP) (checked at the same marks, may
#             re-enter / reverse at a mark); fills at the mark minute's close; flat at the 15:59 close.
#   NA30M     the same, but the trailing stop is checked on every minute close
#   NA30-R50  NA30, daily regime: previous RTH close above its 50-day SMA -> long only, below -> short only
#   NA30-R20  NA30, regime = sign of the 20-day return (prevC / C[-20])
#   ORBV      opening range 09:30-10:00; a 5-min close above its high -> long, below its low -> short (from the
#             10:05 close, last entry 15:00); exit on a 5-min close back through the RTH VWAP; max one entry
#             per side a day; flat 15:55
#   ORBV-R50  ORBV with the SMA50 regime
# Output: trades / yr, win, $ per trade (per NQ at today's price 28,530), t, $ / yr, max DD; long and short
#   split; eras 2010-13 / 14-17 / 18-21 / 22-26; $ per year on DOWN-regime days (prevC < SMA50) vs UP days;
#   2022 (bear year) and the last 6 years; per-year $ for the main variants.

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE, PV, COST = 28530.0, 20.0, 15.0
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))
VARS = ("NA30", "NA30M", "NA30-R50", "NA30-R20", "ORBV", "ORBV-R50")
MARKS = set(range(10 * 60, 15 * 60 + 31, 30))


def era_of(y):
    for i, (a, b) in enumerate(ERAS):
        if a <= y <= b:
            return i
    return None


class V:
    def __init__(self, k):
        self.k = k
        self.pos = None
        self.trades = []        # (usd, dir, era, year, down_regime, date)
        self.used = set()


class TrendFollow(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.v = {k: V(k) for k in VARS}
        self.hist = {}          # minute -> deque(14) of |c/O - 1|
        self.closes = deque(maxlen=60)
        self.mapped = None
        self.day = None
        self.prevC = None
        self.days = []
        self._new()

    def _new(self):
        self.O = None
        self.pv = self.vv = 0.0
        self.today = {}
        self.orh = self.orl = None
        self.c5 = None
        self.lastC = None
        self.bad = False
        self.reg50 = self.reg20 = 0

    def _book(self, v, px, t):
        p = v.pos
        usd = (px - p["e"]) * p["d"] * PRICE / p["e"] * PV - COST
        v.trades.append((usd, p["d"], era_of(t.year), t.year, self.reg50 == -1, t.date()))
        v.pos = None

    def _end_day(self):
        if self.day is None or self.O is None:
            return
        if not self.bad:
            for mm, x in self.today.items():
                self.hist.setdefault(mm, deque(maxlen=14)).append(x)
            if self.lastC is not None:
                self.closes.append(self.lastC)
                self.prevC = self.lastC
        else:
            self.prevC = None

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c, vol = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        rolled = self.mapped is not None and self.f.mapped != self.mapped
        self.mapped = self.f.mapped
        if not (9 * 60 + 30 < m <= 16 * 60):
            return
        if self.day != t.date():
            for v in self.v.values():
                if v.pos is not None:
                    self._book(v, self.lastC if self.lastC else o, t)
            self._end_day()
            self.day = t.date()
            self._new()
            if len(self.closes) >= 50 and self.prevC is not None:
                sma = sum(list(self.closes)[-50:]) / 50.0
                self.reg50 = 1 if self.prevC > sma else -1
                self.reg20 = 1 if self.prevC > list(self.closes)[-21] else -1
            for v in self.v.values():
                v.used = set()
        if rolled:
            self.bad = True
            for v in self.v.values():
                if v.pos is not None:
                    self._book(v, c, t)
        if self.O is None:
            self.O = o
        self.lastC = c
        self.pv += (h + l + c) / 3.0 * vol
        self.vv += vol
        vw = self.pv / self.vv if self.vv > 0 else c
        self.today[m] = abs(c / self.O - 1.0)
        if m <= 10 * 60:
            self.orh = h if self.orh is None else max(self.orh, h)
            self.orl = l if self.orl is None else min(self.orl, l)
        if self.bad or self.prevC is None:
            return
        hq = self.hist.get(m)
        ub = lb = None
        if hq is not None and len(hq) == 14:
            s = sum(hq) / 14.0
            ub = max(self.O, self.prevC) * (1 + s)
            lb = min(self.O, self.prevC) * (1 - s)
        # ---------------- Noise Area variants
        for k in ("NA30", "NA30M", "NA30-R50", "NA30-R20"):
            v = self.v[k]
            if ub is None:
                continue
            if v.pos is not None:
                if m >= 15 * 60 + 59:
                    self._book(v, c, t)
                    continue
                if k == "NA30M" or m in MARKS:
                    p = v.pos
                    if (p["d"] == 1 and c < max(ub, vw)) or (p["d"] == -1 and c > min(lb, vw)):
                        self._book(v, c, t)
            if v.pos is None and m in MARKS:
                d = 1 if c > ub else (-1 if c < lb else 0)
                if k == "NA30-R50" and d != self.reg50:
                    d = 0
                if k == "NA30-R20" and d != self.reg20:
                    d = 0
                if d != 0:
                    v.pos = {"d": d, "e": c}
        # ---------------- ORB + VWAP variants (5-min closes)
        if m % 5 == 0 and m > 10 * 60:
            for k in ("ORBV", "ORBV-R50"):
                v = self.v[k]
                if v.pos is not None:
                    p = v.pos
                    if m >= 15 * 60 + 55 or (p["d"] == 1 and c < vw) or (p["d"] == -1 and c > vw):
                        self._book(v, c, t)
                if v.pos is None and m <= 15 * 60 and self.orh is not None:
                    d = 1 if c > self.orh else (-1 if c < self.orl else 0)
                    if k == "ORBV-R50" and d != self.reg50:
                        d = 0
                    if d != 0 and d not in v.used:
                        v.pos = {"d": d, "e": c}
                        v.used.add(d)

    def on_end_of_algorithm(self):
        def st(tr):
            n = len(tr)
            if n < 10:
                return "n<10"
            yrs = max(1.0, len(set(x[3] for x in tr)))
            u = [x[0] for x in tr]
            mu = sum(u) / n
            sd = math.sqrt(sum((x - mu) ** 2 for x in u) / (n - 1))
            cum = pk = mdd = 0.0
            for x in u:
                cum += x
                pk = max(pk, cum)
                mdd = min(mdd, cum - pk)
            return f"{n / yrs:.0f}/y win {sum(1 for x in u if x > 0) / n * 100:.0f}% ${mu:+.0f}/tr t{mu / (sd / math.sqrt(n)):+.1f} ${sum(u) / yrs:+,.0f}/y DD ${mdd:,.0f}"
        for k, v in self.v.items():
            tr = v.trades
            if len(tr) < 20:
                continue
            yrs = max(1.0, len(set(x[3] for x in tr)))
            era = " ".join(f"{sum(x[0] for x in tr if x[2] == i) / max(1, sum(1 for x in tr if x[2] == i)):+.0f}" for i in range(len(ERAS)))
            self.set_runtime_statistic(f"TF {k}", st(tr) + f" | $/tr era {era}")
            lo = [x for x in tr if x[1] == 1]
            sh = [x for x in tr if x[1] == -1]
            dn = [x for x in tr if x[4]]
            up = [x for x in tr if not x[4]]
            y22 = [x for x in tr if x[3] == 2022]
            rec = [x for x in tr if x[5] >= date(2020, 11, 20)]
            self.set_runtime_statistic(f"TF {k} split",
                f"L {sum(x[0] for x in lo) / max(1, len(lo)):+.0f}/tr ${sum(x[0] for x in lo) / yrs:+,.0f}/y | S {sum(x[0] for x in sh) / max(1, len(sh)):+.0f}/tr ${sum(x[0] for x in sh) / yrs:+,.0f}/y"
                f" | DOWN-reg ${sum(x[0] for x in dn) / yrs:+,.0f}/y ({sum(x[0] for x in dn) / max(1, len(dn)):+.0f}/tr) UP-reg ${sum(x[0] for x in up) / yrs:+,.0f}/y"
                f" | 2022 ${sum(x[0] for x in y22):+,.0f} | last6y ${sum(x[0] for x in rec) / 6:+,.0f}/y")
            if k in ("NA30", "NA30M", "NA30-R50", "ORBV"):
                ys = sorted(set(x[3] for x in tr))
                self.set_runtime_statistic(f"TF {k} years k$", " ".join(f"{y % 100}:{sum(x[0] for x in tr if x[3] == y) / 1000:+.0f}" for y in ys))
