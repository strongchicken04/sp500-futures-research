# region imports
from AlgorithmImports import *
from collections import deque
# endregion
#
# MULTI-FEATURE EXPORTER + YM / RTY relative strength (day shift 2026-10-26):
# features _a / _b = NQ return since the open minus YM (Dow) / RTY (Russell)
# return since the open (0.0 when that market has no bar yet).
# MULTI-FEATURE EXPORTER: NQ at fixed decision times with VIX, VWAP, RSI,
# EMAs, prior-day volume profile, relative strength against ES and relative
# volume, plus the bracket grid both ways, so indicator-based rules (long and
# short) can be built and tested offline.
#
# Decision times (bar end, ET): CHECKS. At each, with everything known then:
#   ret     NQ return since the 09:30 open
#   rs      NQ return since the open minus ES return since the open
#   vwapd   (price - session VWAP) / price, bp
#   rsi14 / rsi2   RSI of 5-minute closes
#   e9, e21, e50   (price - EMA of 5-minute closes) / price, bp
#   vix, vixchg, vixrel   VIX level, change since its prior close (%), level
#                         over its 20-day average of daily closes
#   poc, vah, val  (price - prior session POC / value-area high / low), bp
#   rvol30   volume of the last 30 minutes / its 20-day average at this time
# Then the first minute each LEVELS bp move up and down is reached, to 15:55.
#
# Tag: M,<yyyymmdd>,<hhmm>,<price>,<17 features>,<up x13>,<dn x13>,<eod pts>

START, END = 2025, 2026
CHECKS = [10 * 60, 11 * 60, 13 * 60, 14 * 60 + 30]
LEVELS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150]
EOD = 15 * 60 + 55


class MultiFeatureExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(START, 1, 1)
        self.SetEndDate(END, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.nq = self._fut(Futures.Indices.NASDAQ_100_E_MINI)
        self.es = self._fut(Futures.Indices.SP_500_E_MINI)
        self.ym = self._fut(Futures.Indices.DOW_30_E_MINI)
        self.rty = self._fut(Futures.Indices.RUSSELL_2000_E_MINI)
        self.vix_sym = None
        try:
            self.vix_sym = self.AddIndex("VIX", Resolution.Minute).Symbol
        except Exception as ex:
            self.Debug(f"VIX index unavailable: {ex}")
        self.vix_last = None
        self.vix_prev_close = None
        self.vix_closes = deque(maxlen=20)
        self.ema = {9: None, 21: None, 50: None}
        self.c5 = deque(maxlen=15)
        self.vol_hist = {}
        self.day = None
        self.trk = []
        self.va = None
        self._reset()

    def _fut(self, ticker):
        f = self.AddFuture(ticker, Resolution.Minute,
                           dataNormalizationMode=DataNormalizationMode.Raw,
                           dataMappingMode=DataMappingMode.OpenInterest,
                           contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 180)
        return f

    def _reset(self):
        self.o_nq = self.o_es = None
        self.es_last = None
        self.o_x = {"ym": None, "rty": None}
        self.x_last = {"ym": None, "rty": None}
        self.pv = self.vol = 0.0
        self.prof = {}
        self.b5 = None
        self.vol_win = deque(maxlen=30)

    @staticmethod
    def _rsi(closes, n):
        if len(closes) < n + 1:
            return 50.0
        xs = list(closes)[-(n + 1):]
        g = sum(max(0.0, xs[i] - xs[i - 1]) for i in range(1, len(xs)))
        l = sum(max(0.0, xs[i - 1] - xs[i]) for i in range(1, len(xs)))
        return 100.0 if l == 0 else 100.0 - 100.0 / (1.0 + g / l)

    def OnData(self, slice):
        if slice.Bars is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute          # bar end time, ET
        if self.vix_sym is not None and slice.Bars.ContainsKey(self.vix_sym):
            self.vix_last = float(slice.Bars[self.vix_sym].Close)
            if hm == 16 * 60 + 15 or hm == 16 * 60:
                self.vix_eod = self.vix_last
        eb = slice.Bars.get(self.es.Symbol)
        if eb is not None:
            self.es_last = float(eb.Close)
            if hm == 9 * 60 + 31:
                self.o_es = float(eb.Open)
        for nm, fu in (("ym", self.ym), ("rty", self.rty)):
            xb = slice.Bars.get(fu.Symbol)
            if xb is not None:
                self.x_last[nm] = float(xb.Close)
                if hm == 9 * 60 + 31:
                    self.o_x[nm] = float(xb.Open)
        bar = slice.Bars.get(self.nq.Symbol)
        if bar is None:
            return
        o, h, l, c, v = (float(bar.Open), float(bar.High), float(bar.Low),
                         float(bar.Close), float(bar.Volume))
        if self.day != t.date():
            for tr in self.trk:
                self._emit(tr)
            self.trk = []
            self.day = t.date()
            self._reset()
        self._track(h, l, c, hm)
        if t.weekday() >= 5 or not (9 * 60 + 30 < hm <= 16 * 60):
            return
        if hm == 9 * 60 + 31:
            self.o_nq = o
        if self.o_nq is None:
            return
        self.pv += (h + l + c) / 3.0 * v
        self.vol += v
        vwap = self.pv / self.vol if self.vol > 0 else c
        key = round((h + l + c) / 3.0)
        self.prof[key] = self.prof.get(key, 0.0) + v
        self.vol_win.append(v)

        b = self.b5
        if b is None:
            self.b5 = b = [c]
        else:
            b[0] = c
        if hm % 5 == 0:
            self.b5 = None
            self.c5.append(c)
            for n in self.ema:
                k = 2.0 / (n + 1)
                self.ema[n] = c if self.ema[n] is None else c * k + self.ema[n] * (1 - k)

        if hm in CHECKS and self.va is not None and self.o_es and self.es_last and self.vix_last \
                and self.vix_prev_close and len(self.vix_closes) == 20 and None not in self.ema.values():
            hist = self.vol_hist.setdefault(hm, deque(maxlen=20))
            v30 = sum(self.vol_win)
            rv30 = v30 / (sum(hist) / len(hist)) if len(hist) >= 10 and sum(hist) > 0 else 1.0
            poc, vah, val = self.va
            bp = lambda x: (c - x) / c * 1e4
            f = (c / self.o_nq - 1.0, (c / self.o_nq - 1.0) - (self.es_last / self.o_es - 1.0), bp(vwap),
                 self._rsi(self.c5, 14), self._rsi(self.c5, 2),
                 bp(self.ema[9]), bp(self.ema[21]), bp(self.ema[50]),
                 self.vix_last, self.vix_last / self.vix_prev_close - 1.0,
                 self.vix_last / (sum(self.vix_closes) / 20.0),
                 bp(poc), bp(vah), bp(val), rv30, self._xrs("ym", c), self._xrs("rty", c))
            self.trk.append({"ctx": f"M,{t.strftime('%Y%m%d')},{hm},{c:.2f}," + ",".join(f"{x:.5f}" for x in f),
                             "e": c, "k": 0, "up": [-1] * len(LEVELS), "dn": [-1] * len(LEVELS), "last": 0.0})
        if hm in CHECKS:
            self.vol_hist.setdefault(hm, deque(maxlen=20)).append(sum(self.vol_win))

        if hm == 16 * 60:
            self._value_area()
            if self.vix_last:
                if self.vix_prev_close is not None:
                    self.vix_closes.append(self.vix_last)
                self.vix_prev_close = self.vix_last

    def _xrs(self, nm, c):
        if not self.o_x[nm] or not self.x_last[nm]:
            return 0.0
        return (c / self.o_nq - 1.0) - (self.x_last[nm] / self.o_x[nm] - 1.0)

    def _value_area(self):
        if not self.prof:
            return
        px = sorted(self.prof)
        tot = sum(self.prof.values())
        poc = max(px, key=lambda k: self.prof[k])
        i = j = px.index(poc)
        acc = self.prof[poc]
        while acc < 0.7 * tot and (i > 0 or j < len(px) - 1):
            lo = self.prof[px[i - 1]] if i > 0 else -1
            hi = self.prof[px[j + 1]] if j < len(px) - 1 else -1
            if hi >= lo:
                j += 1
                acc += hi
            else:
                i -= 1
                acc += lo
        self.va = (poc, px[j], px[i])

    def _track(self, h, l, c, hm):
        keep = []
        for tr in self.trk:
            tr["k"] += 1
            e = tr["e"]
            for i, bpv in enumerate(LEVELS):
                d = e * bpv / 10000.0
                if tr["up"][i] < 0 and h - e >= d:
                    tr["up"][i] = tr["k"]
                if tr["dn"][i] < 0 and e - l >= d:
                    tr["dn"][i] = tr["k"]
            tr["last"] = c - e
            if EOD <= hm <= 16 * 60:
                self._emit(tr)
            else:
                keep.append(tr)
        self.trk = keep

    def _emit(self, tr):
        tag = (tr["ctx"] + "," + ",".join(str(x) for x in tr["up"]) + ","
               + ",".join(str(x) for x in tr["dn"]) + f",{tr['last']:.2f}")
        try:
            sym = self.nq.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5, 0), tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as ex:
            self.Debug(f"tag fail: {ex}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags} VIX={'yes' if self.vix_sym else 'no'}")
