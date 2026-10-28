# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion
#
# Z LEG (Lucid 6 noise momentum) x REAL ORDER FLOW, computed INSIDE
# QuantConnect (night 2026-10-27/28, rules fixed before results). Exports no
# market data: only aggregate statistics per year as runtime statistics.
# Z is flat since 2025 (STATE item 18); can a flow filter keep its good trades?
#
# Z rules (AUTOMATION_SPEC): decisions at :00 / :30 from 10:00 to 15:30 on the
# close at that time. sigma(t) = mean over the last 14 sessions of |price at t /
# 09:30 open - 1|. Upper = max(open, prior RTH close) x (1 + sigma), lower =
# min(open, prior close) x (1 - sigma). close > upper -> long, close < lower ->
# short, an opposite signal reverses; a long exits at a decision when the close
# is below max(upper, VWAP), a short when above min(lower, VWAP). Hard stop
# 0.50% from the entry (1-second highs / lows after the entry), flat 15:55.
# Entry needs close > max(upper, VWAP) (short: < min(lower, VWAP)) so that an
# entry never meets the exit rule at the same decision.
# (No vol gate here - the comparison is between flow groups on the same trades.)
# Flow of an entry: I = (buy - sell) / (buy + sell) of aggressive volume in the
# 30 min before the entry decision (trade close vs quote mid, tick rule at the
# mid), x the trade direction. Groups: POS (I > 0) / NEG (I <= 0), C02 / A02
# (I >= +0.02 / <= -0.02), C05 / A05 (+/-0.05).
# Per year: points per trade mean / t / n / wins per group, and the RISK view
# (sum, max drawdown of cumulative points, worst 20-day sum) for ALL vs C02 vs POS.

START = (2020, 1, 1)
END = (2020, 12, 31)
STOP = 0.005
EOD = 23100                                  # 15:55 in seconds after 09:30
DEC = list(range(1800, 21601, 1800))         # 10:00 .. 15:30


class ZFlowInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.nq = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.SECOND,
                                  data_normalization_mode=DataNormalizationMode.RAW,
                                  data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                  contract_depth_offset=0, extended_market_hours=False)
        self.nq.set_filter(0, 180)
        self.hist = {s: deque(maxlen=14) for s in DEC}
        self.agg = {}
        self.path = {"ALL": [], "C02": [], "POS": []}
        self.pclose = None
        self.day = None
        self._new_day()

    def _new_day(self):
        self.op = None
        self.pv = self.vv = 0.0
        self.b = self.s = 0.0
        self.last = None
        self.side = 0
        self.pos = None                          # dict d, e, g
        self.dmove = {}
        self.dpl = {}

    def _add(self, key, x):
        a = self.agg.setdefault(key, [0, 0.0, 0.0, 0])
        a[0] += 1; a[1] += x; a[2] += x * x; a[3] += 1 if x > 0 else 0

    def _exit(self, x):
        y = self.day.year
        for g in self.pos["g"]:
            self._add((y, g), x)
            if g in self.path:
                self.dpl[g] = self.dpl.get(g, 0.0) + x
        self.pos = None

    def _close_day(self):
        if self.day is None:
            return
        if self.pos is not None and self.last is not None:
            self._exit(self.pos["d"] * (self.last - self.pos["e"]))
        if self.op is not None:
            for s, mv in self.dmove.items():
                self.hist[s].append(mv)
            for k in self.path:
                self.path[k].append((self.day.year, self.dpl.get(k, 0.0)))
        if self.last is not None:
            self.pclose = self.last

    def on_data(self, data: Slice):
        t = self.time
        if self.day != t.date():
            self._close_day()
            self.day = t.date()
            self._new_day()
        bar = data.bars.get(self.nq.symbol)
        if bar is None:
            return
        secs = t.hour * 3600 + t.minute * 60 + t.second - (9 * 3600 + 30 * 60)
        if secs <= 0 or secs > 23400:
            return
        c, h, l, v = float(bar.close), float(bar.high), float(bar.low), float(bar.volume)
        if self.op is None:
            self.op = float(bar.open)
        if self.pos is not None:
            d, e = self.pos["d"], self.pos["e"]
            if (d == 1 and l <= e * (1 - STOP)) or (d == -1 and h >= e * (1 + STOP)):
                self._exit(-STOP * e)
            elif secs >= EOD:
                self._exit(d * (c - e))
        if v > 0:
            q = data.quote_bars.get(self.nq.symbol)
            sd = 0
            if q is not None and q.bid is not None and q.ask is not None and q.bid.close > 0 and q.ask.close > 0:
                mid = (float(q.bid.close) + float(q.ask.close)) / 2.0
                sd = 1 if c > mid else (-1 if c < mid else 0)
            if sd == 0 and self.last is not None:
                sd = 1 if c > self.last else (-1 if c < self.last else self.side)
            if sd > 0:
                self.b += v
            elif sd < 0:
                self.s += v
            self.side = sd or self.side
            self.pv += (h + l + c) / 3.0 * v
            self.vv += v
        self.last = c
        if secs in self.hist:
            self.dmove[secs] = abs(c / self.op - 1.0)
            hs = self.hist[secs]
            tot = self.b + self.s
            imb = (self.b - self.s) / tot if tot > 0 else 0.0
            self.b = self.s = 0.0
            if len(hs) < 14 or self.pclose is None or self.vv <= 0 or secs >= EOD:
                return
            sig = sum(hs) / len(hs)
            up = max(self.op, self.pclose) * (1 + sig)
            dn = min(self.op, self.pclose) * (1 - sig)
            vw = self.pv / self.vv
            want = 1 if c > max(up, vw) else (-1 if c < min(dn, vw) else 0)   # entry must not meet the exit rule
            if self.pos is not None:
                d = self.pos["d"]
                if want == -d or (d == 1 and c < max(up, vw)) or (d == -1 and c > min(dn, vw)):
                    self._exit(d * (c - self.pos["e"]))
            if self.pos is None and want != 0:
                fi = want * imb
                g = ["ALL", "POS" if fi > 0 else "NEG"]
                if fi >= 0.02:
                    g.append("C02")
                if fi <= -0.02:
                    g.append("A02")
                if fi >= 0.05:
                    g.append("C05")
                if fi <= -0.05:
                    g.append("A05")
                self.pos = {"d": want, "e": c, "g": g}

    def on_end_of_algorithm(self):
        self._close_day()
        for k, p in self.path.items():
            by = {}
            for y, x in p:
                by.setdefault(y, []).append(x)
            for y, xs in by.items():
                cum = peak = dd = 0.0
                for x in xs:
                    cum += x
                    peak = max(peak, cum)
                    dd = max(dd, peak - cum)
                w20 = min(sum(xs[i:i + 20]) for i in range(max(1, len(xs) - 19))) if xs else 0.0
                self.set_runtime_statistic(f"{y} ZR {k}", f"sum {cum:+.0f}pt maxDD {dd:.0f}pt worst20d {w20:+.0f}pt days {len(xs)}")
        for (y, g), (n, s1, s2, w) in sorted(self.agg.items()):
            if n < 2:
                continue
            m = s1 / n
            var = max(0.0, s2 / n - m * m)
            tt = m / math.sqrt(var / n) if var > 0 else 0.0
            self.set_runtime_statistic(f"{y} Z {g}", f"{m:+.1f}pt/{tt:+.1f}/{n} wins {w}")
