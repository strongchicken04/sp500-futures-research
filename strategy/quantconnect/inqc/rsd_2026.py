# region imports
from AlgorithmImports import *
import math
# endregion
#
# RS SIGNAL x REAL ORDER FLOW, computed INSIDE QuantConnect (day shift
# 2026-10-26, rules fixed before results). Exports no market data: only
# aggregate statistics per year as runtime statistics.
#
# RS signal (live rule, Lucid 8): at the 10:00 / 11:00 / 13:00 / 14:30 ET
# checks, rs = NQ return since the 09:30 open - ES return since the open;
# long if rs > +0.15% and NQ above the session VWAP, short mirror; first
# signal of the day only.
# Order flow: aggressive buy / sell volume of NQ per 1-second bar (trade close
# vs quote mid, tick rule at the mid). D = (buy - sell) / (buy + sell) since
# 09:30 up to the check.  Groups: AGREE (D in the signal direction, |D| >=
# 0.05), AGAINST (opposite, |D| >= 0.05), NEUTRAL.
# Outcomes from the check price: funded leg +/-1.25% bracket (first touch on
# 1-second highs / lows, stop first if both in one second, else 15:55 close),
# and the sprint 0.20 / 0.30 bracket (resolved win rate). Gross bp.

START = (2026, 1, 1)
END = (2026, 7, 31)
CHECKS = (600, 660, 780, 870)        # minutes after midnight, bar end
EOD = 955
TH = 0.0015


class RSDeltaInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        kw = dict(data_normalization_mode=DataNormalizationMode.RAW,
                  data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                  contract_depth_offset=0, extended_market_hours=False)
        self.nq = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.SECOND, **kw)
        self.es = self.add_future(Futures.Indices.SP_500_E_MINI, Resolution.MINUTE, **kw)
        self.nq.set_filter(0, 180)
        self.es.set_filter(0, 180)
        self.agg = {}      # (year, group, kind) -> [n, sum, sumsq, wins, resolved]
        self.day = None
        self._new_day()

    def _new_day(self):
        self.o_nq = self.o_es = None
        self.es_last = None
        self.buy = self.sell = 0.0
        self.pv = self.vv = 0.0
        self.last_px = None
        self.last_side = 0
        self.done = False
        self.open_trades = []   # dicts: dir, e, group, legs state

    def _add(self, year, group, kind, x, win=None):
        a = self.agg.setdefault((year, group, kind), [0, 0.0, 0.0, 0, 0])
        a[0] += 1
        a[1] += x
        a[2] += x * x
        if win is not None:
            a[3] += 1 if win else 0
            a[4] += 1

    def _finish(self, tr, px_close):
        y = self.day.year
        for kind, (tp, sp) in (("leg", (125, 125)), ("sprint", (20, 30))):
            st = tr[kind]
            if st is None:
                x = tr["d"] * (px_close / tr["e"] - 1.0) * 1e4
                x = max(-sp, x)
                self._add(y, tr["g"], kind, x)
            else:
                self._add(y, tr["g"], kind, st, win=(st > 0))

    def on_data(self, data: Slice):
        t = self.time
        if self.day != t.date():
            self.day = t.date()
            self._new_day()
        hm = t.hour * 60 + t.minute
        eb = data.bars.get(self.es.symbol)
        if eb is not None:
            self.es_last = float(eb.close)
            if self.o_es is None and hm == 9 * 60 + 31:
                self.o_es = float(eb.open)
        bar = data.bars.get(self.nq.symbol)
        if bar is None:
            return
        secs = t.hour * 3600 + t.minute * 60 + t.second - (9 * 3600 + 30 * 60)
        if secs <= 0 or secs > 23400:
            return
        c, h, l, v = float(bar.close), float(bar.high), float(bar.low), float(bar.volume)
        if self.o_nq is None:
            self.o_nq = float(bar.open)
        # open trades: bracket checks on this second
        for tr in self.open_trades:
            for kind, (tp, sp) in (("leg", (125, 125)), ("sprint", (20, 30))):
                if tr[kind] is not None:
                    continue
                d, e = tr["d"], tr["e"]
                stop = e * (1 - d * sp / 1e4)
                tgt = e * (1 + d * tp / 1e4)
                if (d == 1 and l <= stop) or (d == -1 and h >= stop):
                    tr[kind] = -float(sp)
                elif (d == 1 and h >= tgt) or (d == -1 and l <= tgt):
                    tr[kind] = float(tp)
        if hm >= EOD and self.open_trades:
            for tr in self.open_trades:
                self._finish(tr, c)
            self.open_trades = []
        if v > 0:
            q = data.quote_bars.get(self.nq.symbol)
            side = 0
            if q is not None and q.bid is not None and q.ask is not None and q.bid.close > 0 and q.ask.close > 0:
                mid = (float(q.bid.close) + float(q.ask.close)) / 2.0
                side = 1 if c > mid else (-1 if c < mid else 0)
            if side == 0 and self.last_px is not None:
                side = 1 if c > self.last_px else (-1 if c < self.last_px else self.last_side)
            if side > 0:
                self.buy += v
            elif side < 0:
                self.sell += v
            self.last_side = side or self.last_side
            self.last_px = c
            self.pv += (h + l + c) / 3.0 * v
            self.vv += v
        if t.second == 0 and hm in CHECKS and not self.done and self.o_es and self.es_last and self.vv > 0:
            rs = (c / self.o_nq - 1.0) - (self.es_last / self.o_es - 1.0)
            vw = self.pv / self.vv
            d = 1 if (rs > TH and c > vw) else (-1 if (rs < -TH and c < vw) else 0)
            if d != 0:
                self.done = True
                tot = self.buy + self.sell
                dd = (self.buy - self.sell) / tot if tot > 0 else 0.0
                g = "agree" if d * dd >= 0.05 else ("against" if d * dd <= -0.05 else "neutral")
                for grp in (g, "all"):
                    self.open_trades.append({"d": d, "e": c, "g": grp, "leg": None, "sprint": None})

    def on_end_of_algorithm(self):
        out = {}
        for (y, g, kind), (n, s1, s2, w, r) in sorted(self.agg.items()):
            if n < 2:
                continue
            m = s1 / n
            var = max(0.0, s2 / n - m * m)
            tt = m / math.sqrt(var / n) if var > 0 else 0.0
            txt = f"{kind} {m:+.1f}/{tt:+.1f}/{n}" + (f" win {w}/{r}" if r else "")
            out.setdefault(f"{y} {g}", []).append(txt)
        for k, parts in out.items():
            self.set_runtime_statistic(k, " | ".join(parts))
