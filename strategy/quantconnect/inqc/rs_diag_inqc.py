# region imports
from AlgorithmImports import *
import math
# endregion
#
# v2: bracket bug fixed (see _outcome) + RS x O18 agreement (replaces the buggy round-2 G4).
# DIAGNOSTIC (2026-11-09 night): the RS sprint at the 10:00 check came out
# BELOW random in midnight_open2_inqc.py (-3..-8 pp vs 60%), against the
# earlier exports / in-QC runs (+2..+7 pp). Same rule computed three ways in
# one algorithm, NQ + ES minute bars 2010-2026:
#   A  the midnight_open2 code path (extended hours, RTH open = first bar
#      after 09:30, ES open = first ES RTH bar, VWAP from NQ RTH minutes,
#      bracket checked on later minute bars)
#   B  the reference logic (rs_delta_inqc.py: ES open = the open of the bar
#      ending 09:31, NQ open = first RTH bar, VWAP RTH, brackets from the next
#      bar), minute resolution
#   C  B but the bracket is evaluated on the minute CLOSES only (a check for
#      intrabar order effects)
# Output: resolved win rate minus 60% by era, n, and how often A and B fire
# the same side on the same day. Aggregates only.

START = (2010, 1, 1)
END = (2026, 12, 31)
ERAS = (("10-13", 2010, 2013), ("14-17", 2014, 2017), ("18-21", 2018, 2021), ("22-26", 2022, 2026))


class RSDiagInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        kw = dict(fill_forward=False, data_normalization_mode=DataNormalizationMode.RAW,
                  data_mapping_mode=DataMappingMode.OPEN_INTEREST, contract_depth_offset=0, extended_market_hours=True)
        self.nq = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, **kw)
        self.es = self.add_future(Futures.Indices.SP_500_E_MINI, Resolution.MINUTE, **kw)
        self.nq.set_filter(0, 180)
        self.es.set_filter(0, 180)
        self.day = None
        self.res = {"A": [[0, 0] for _ in ERAS], "B": [[0, 0] for _ in ERAS], "C": [[0, 0] for _ in ERAS]}
        self.same = [0, 0]
        self.o18 = None
        self.agree = {True: [[0, 0] for _ in ERAS], False: [[0, 0] for _ in ERAS]}
        self._new()

    def _new(self):
        self.o_nq = self.o_es_a = self.o_es_b = None
        self.es_last = None
        self.pv = self.vv = 0.0
        self.bars = []
        self.sig = {}
        self.o18_today = self.o18[0] if getattr(self, "o18", None) else None

    def _era(self, y):
        for i, (_, a, b) in enumerate(ERAS):
            if a <= y <= b:
                return i
        return None

    def _outcome(self, d, e, start, closes_only=False):
        # v2 FIX: the target is +0.20% in the trade direction and the stop -0.30% against it
        # (v1 used +0.20% up / -0.30% down for both sides -> shorts had a 40% random-walk rate)
        tgt = stp = None
        for i in range(start, len(self.bars)):
            h, l, c, m = self.bars[i]
            if m > 15 * 60 + 55:
                break
            hh, ll = (c, c) if closes_only else (h, l)
            if d == 1:
                if tgt is None and hh >= e * 1.002:
                    tgt = i
                if stp is None and ll <= e * 0.997:
                    stp = i
            else:
                if tgt is None and ll <= e * 0.998:
                    tgt = i
                if stp is None and hh >= e * 1.003:
                    stp = i
            if tgt is not None and stp is not None:
                break
        if stp is not None and (tgt is None or stp <= tgt):
            return -1
        return 1 if tgt is not None else 0

    def _close_day(self):
        if self.day is None or not self.bars:
            return
        k = self._era(self.day.year)
        if k is None:
            return
        for name, (d, e, i0) in self.sig.items():
            if name == "C":
                r = self._outcome(d, e, i0 + 1, closes_only=True)
            else:
                r = self._outcome(d, e, i0 + 1)
            if r != 0:
                self.res[name][k][0] += r == 1
                self.res[name][k][1] += 1
                if name == "B" and self.o18 is not None and self.o18_today is not None:
                    ag = (1 if e > self.o18_today else -1) == d
                    self.agree[ag][k][0] += r == 1
                    self.agree[ag][k][1] += 1
        if "A" in self.sig or "B" in self.sig:
            self.same[1] += 1
            if "A" in self.sig and "B" in self.sig and self.sig["A"][0] == self.sig["B"][0]:
                self.same[0] += 1

    def on_data(self, data: Slice):
        t = self.time
        m = t.hour * 60 + t.minute
        nb = data.bars.get(self.nq.symbol)
        if nb is not None and 18 * 60 < m <= 18 * 60 + 15 and (self.o18 is None or self.o18[1] != t.date()):
            self.o18 = (float(nb.open), t.date())
        if self.day != t.date() and 9 * 60 + 30 < m <= 16 * 60:
            self._close_day()
            self.day = t.date()
            self._new()
        eb = data.bars.get(self.es.symbol)
        if eb is not None and 9 * 60 + 30 < m <= 16 * 60:
            self.es_last = float(eb.close)
            if self.o_es_a is None:
                self.o_es_a = float(eb.open)
            if self.o_es_b is None and m == 9 * 60 + 31:
                self.o_es_b = float(eb.open)
        bar = data.bars.get(self.nq.symbol)
        if bar is None or not (9 * 60 + 30 < m <= 16 * 60) or self.day != t.date():
            return
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        if self.o_nq is None:
            self.o_nq = o
        self.bars.append((h, l, c, m))
        self.pv += (h + l + c) / 3.0 * v
        self.vv += v
        if m == 10 * 60 and self.vv > 0 and self.es_last:
            vw = self.pv / self.vv
            for name, oes in (("A", self.o_es_a), ("B", self.o_es_b)):
                if oes is None:
                    continue
                rs = (c / self.o_nq - 1.0) - (self.es_last / oes - 1.0)
                d = 1 if (rs > 0.0015 and c > vw) else (-1 if (rs < -0.0015 and c < vw) else 0)
                if d != 0:
                    self.sig[name] = (d, c, len(self.bars) - 1)
                    if name == "B":
                        self.sig["C"] = (d, c, len(self.bars) - 1)

    def on_end_of_algorithm(self):
        self._close_day()
        for name, per in self.res.items():
            w = sum(p[0] for p in per)
            n = sum(p[1] for p in per)
            z = (w - 0.6 * n) / math.sqrt(0.24 * n) if n else 0.0
            self.set_runtime_statistic(f"RSD {name}", " ".join(f"{(p[0] / p[1] - 0.6) * 100:+.1f}/{p[1]}" if p[1] else "-" for p in per) + f" z{z:+.1f}")
        self.set_runtime_statistic("RSD same side A=B", f"{self.same[0]}/{self.same[1]}")
        for ag, per in self.agree.items():
            w = sum(p[0] for p in per)
            n = sum(p[1] for p in per)
            z = (w - 0.6 * n) / math.sqrt(0.24 * n) if n else 0.0
            self.set_runtime_statistic(f"RSD B {'agree' if ag else 'against'} O18", " ".join(f"{(p[0] / p[1] - 0.6) * 100:+.1f}/{p[1]}" if p[1] else "-" for p in per) + f" z{z:+.1f}")
