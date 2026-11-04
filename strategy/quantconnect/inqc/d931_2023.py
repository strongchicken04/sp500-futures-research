# region imports
from AlgorithmImports import *
import math
# endregion
#
# REAL ORDER-FLOW DELTA BEFORE THE OPEN -> 09:31 SPRINT DIRECTION, computed
# INSIDE QuantConnect (owner request 2026-11-04: "prior-day delta, premarket,
# Asia, London"; rules fixed before results). Exports no market data: only
# aggregate statistics per year as runtime statistics.
#
# Aggressive delta D = (buy - sell) / (buy + sell) of the aggressive volume in a
# window (trade close vs quote mid, tick rule at the mid - as the other in-QC
# studies), NQ front contract, 1-second bars, extended hours:
#   PD    prior RTH day 09:30-16:00          PDLH  prior day 15:00-16:00
#   ON    whole overnight 18:00-09:30        ASIA  18:00-00:00
#   LDN   London 02:00-05:00                 PRE   premarket 08:00-09:30
# Trade: entry at the 09:31:00 close, bracket +0.20% / -0.40% (Lucid 7),
# first touch on 1-second highs / lows from the next second, stop first if
# both; unresolved -> flat 15:55. For every window: FOLLOW (side = sign D)
# and FADE (side = -sign D), for any |D| > 0 and for a strong |D| (PD / ON
# >= 0.02, the shorter windows >= 0.05). Controls: LONG (always long), SHORT.
# Output per (year, group): resolved wins / resolved (random 66.7%), mean
# gross bp of all trades incl. unresolved / t / n.

YEAR = 2023
TGT, STP = 0.0020, 0.0040
WIN = ("PD", "PDLH", "ON", "ASIA", "LDN", "PRE")
STRONG = {"PD": 0.02, "ON": 0.02, "PDLH": 0.05, "ASIA": 0.05, "LDN": 0.05, "PRE": 0.05}


class Delta931InQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(YEAR - 1, 12, 26)
        self.set_end_date(YEAR, 12, 31)
        self.set_cash(1_000_000)
        self.nq = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.SECOND,
                                  data_normalization_mode=DataNormalizationMode.RAW,
                                  data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                  contract_depth_offset=0, extended_market_hours=True)
        self.nq.set_filter(0, 180)
        self.agg = {}
        self.acc = {w: [0.0, 0.0] for w in WIN}        # running buy / sell volume per window
        self.prev = {}                                  # finished windows of the last session
        self.last = None
        self.side = 0
        self.day = None
        self.tr = None                                  # today's long / short trades
        self.fired = False

    # ------------------------------------------------------------ helpers
    def _add(self, g, res, x):
        a = self.agg.setdefault((self.day.year, g), [0, 0, 0, 0.0, 0.0])
        a[0] += 1
        a[1] += 1 if res == 1 else 0
        a[2] += 1 if res != 0 else 0
        a[3] += x
        a[4] += x * x

    def _close_trades(self):
        if self.tr is None or self.last is None:
            return
        for d, t in self.tr["legs"].items():
            if t["res"] is None:
                t["res"], t["x"] = 0, d * (self.last / self.tr["e"] - 1.0) * 1e4
        if self.day is not None and self.day.year == YEAR:
            L, S = self.tr["legs"][1], self.tr["legs"][-1]
            self._add("LONG", L["res"], L["x"])
            self._add("SHORT", S["res"], S["x"])
            for w, D in self.tr["D"].items():
                sd = 1 if D > 0 else (-1 if D < 0 else 0)
                if sd == 0:
                    continue
                for mode, s in (("FOL", sd), ("FAD", -sd)):
                    t = self.tr["legs"][s]
                    self._add(f"{w} {mode}", t["res"], t["x"])
                    if abs(D) >= STRONG[w]:
                        self._add(f"{w} {mode} strong", t["res"], t["x"])
        self.tr = None

    def _d(self, w):
        b, s = self.acc[w]
        return (b - s) / (b + s) if b + s > 0 else None

    def _reset(self, w):
        self.acc[w] = [0.0, 0.0]

    # ------------------------------------------------------------ data
    def on_data(self, data: Slice):
        bar = data.bars.get(self.nq.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        sec = m * 60 + t.second
        c, h, l, v = float(bar.close), float(bar.high), float(bar.low), float(bar.volume)

        # session boundaries (bar end times, ET)
        if m >= 18 * 60 and self.prev.get("_on_started") != t.date():
            # a new overnight session: close windows of the RTH day, start the overnight ones
            self.prev["_on_started"] = t.date()
            for w in ("ON", "ASIA", "LDN", "PRE"):
                self._reset(w)
        if self.day != t.date():
            self.day = t.date()
            self.fired = False

        # open trades: first touch
        if self.tr is not None and 9 * 3600 + 31 * 60 < sec <= 15 * 3600 + 55 * 60:
            e = self.tr["e"]
            for d, tr in self.tr["legs"].items():
                if tr["res"] is not None:
                    continue
                if (d == 1 and l <= e * (1 - STP)) or (d == -1 and h >= e * (1 + STP)):
                    tr["res"], tr["x"] = -1, -STP * 1e4
                elif (d == 1 and h >= e * (1 + TGT)) or (d == -1 and l <= e * (1 - TGT)):
                    tr["res"], tr["x"] = 1, TGT * 1e4
        if self.tr is not None and sec > 15 * 3600 + 55 * 60:
            self._close_trades()

        # aggressor side
        sd = 0
        if v > 0:
            q = data.quote_bars.get(self.nq.symbol)
            if q is not None and q.bid is not None and q.ask is not None and q.bid.close > 0 and q.ask.close > 0:
                mid = (float(q.bid.close) + float(q.ask.close)) / 2.0
                sd = 1 if c > mid else (-1 if c < mid else 0)
            if sd == 0 and self.last is not None:
                sd = 1 if c > self.last else (-1 if c < self.last else self.side)
            self.side = sd or self.side
        live = []
        if 9 * 3600 + 30 * 60 < sec <= 16 * 3600:
            live = ["PD"] + (["PDLH"] if sec > 15 * 3600 else [])
        elif sec > 18 * 3600 or sec <= 9 * 3600 + 30 * 60:
            live = ["ON"]
            if sec > 18 * 3600:
                live.append("ASIA")
            if 2 * 3600 < sec <= 5 * 3600:
                live.append("LDN")
            if 8 * 3600 < sec <= 9 * 3600 + 30 * 60:
                live.append("PRE")
        if v > 0 and sd != 0:
            for w in live:
                self.acc[w][0 if sd > 0 else 1] += v
        self.last = c

        # RTH open: the RTH day accumulators start fresh (previous day's values kept)
        if sec > 9 * 3600 + 30 * 60 and sec <= 9 * 3600 + 31 * 60 and self.prev.get("_rth") != t.date():
            self.prev["_rth"] = t.date()
            self.prev["PD"], self.prev["PDLH"] = self.prev.get("PD_cur"), self.prev.get("PDLH_cur")
            for w in ("ON", "ASIA", "LDN", "PRE"):
                self.prev[w] = self._d(w)
            # the first RTH second already went to PD (today): restart it cleanly
            self._reset("PD")
            self._reset("PDLH")
            if v > 0 and sd != 0:
                self.acc["PD"][0 if sd > 0 else 1] += v
        if sec >= 16 * 3600 and self.prev.get("_rthend") != t.date():
            self.prev["_rthend"] = t.date()
            self.prev["PD_cur"], self.prev["PDLH_cur"] = self._d("PD"), self._d("PDLH")

        # entry at 09:31:00 (or the first bar after it)
        if not self.fired and 9 * 3600 + 31 * 60 <= sec < 9 * 3600 + 32 * 60:
            self.fired = True
            D = {w: self.prev.get(w) for w in WIN}
            D = {w: x for w, x in D.items() if x is not None}
            self.tr = {"e": c, "D": D, "legs": {1: {"res": None, "x": 0.0}, -1: {"res": None, "x": 0.0}}}

    def on_end_of_algorithm(self):
        self._close_trades()
        for (y, g), (n, w, r, s1, s2) in sorted(self.agg.items()):
            if n < 2 or y != YEAR:
                continue
            mu = s1 / n
            var = max(0.0, s2 / n - mu * mu)
            tt = mu / math.sqrt(var / n) if var > 0 else 0.0
            self.set_runtime_statistic(f"{y} D {g}", f"win {w}/{r} {mu:+.1f}bp/{tt:+.1f}/{n}")
