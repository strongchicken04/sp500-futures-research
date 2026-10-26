# region imports
from AlgorithmImports import *
from collections import defaultdict
# endregion
#
# BARS5 EXPORTER: a compact NQ day panel for offline idea testing (level lab).
# For every RTH session it emits
#   H,<yyyymmdd>,<contract expiry yymmdd>,<onh>,<onl>,<onpoc>,<onvol>,<poc>,<vah>,<val>,<rthvol>,<base>,
#     <asia high>,<asia low>,<london high>,<london low>
#     (Asia = bars ending 18:01..00:00 ET, London = 02:01..05:00 ET)
#     overnight (18:00 previous evening .. 09:30) high / low / POC / volume and
#     the RTH volume profile of THIS session from 1-minute bars (hlc3 volume
#     into 1-point bins; value area = 70% around the POC); base = RTH open
#   B,<yyyymmdd>,<chunk>,<bars>
#     13 five-minute RTH bars per chunk (chunk 0 = bars ending 09:35..10:35),
#     each "o:h:l:c:v" with prices as ticks (0.25 pt) relative to base,
#     bars separated by "/".
# Levels of the PRIOR session are applied offline (scripts/level_lab.py);
# a contract change between two sessions is visible from the expiry field.

START, END = 2010, 2013
TICKER = Futures.Indices.SP_500_E_MINI   # ES panel for the RS spread check (2026-10-26)
VA_SHARE = 0.70


class Bars5Exporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(START, 1, 1)
        self.SetEndDate(END, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.fut = self.AddFuture(TICKER, Resolution.Minute,
                                  dataNormalizationMode=DataNormalizationMode.Raw,
                                  dataMappingMode=DataMappingMode.OpenInterest,
                                  contractDepthOffset=0, extendedMarketHours=True)
        self.fut.SetFilter(0, 180)
        self._reset_on()
        self.rth = None

    def _reset_on(self):
        self.on = {"h": None, "l": None, "v": 0.0, "prof": defaultdict(float),
                   "ah": None, "al": None, "lh": None, "ll": None}

    def _emit(self, tag):
        try:
            sym = self.fut.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    mpv = float(self.Securities[sym].SymbolProperties.MinimumPriceVariation)
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5 / mpv) * mpv, tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as ex:
            self.Debug(f"tag fail: {ex}")

    @staticmethod
    def _va(prof):
        if not prof:
            return 0.0, 0.0, 0.0
        px = sorted(prof)
        tot = sum(prof.values())
        poc = max(px, key=lambda k: prof[k])
        i = j = px.index(poc)
        acc = prof[poc]
        while acc < VA_SHARE * tot and (i > 0 or j < len(px) - 1):
            up = prof[px[j + 1]] if j < len(px) - 1 else -1
            dn = prof[px[i - 1]] if i > 0 else -1
            if up >= dn:
                j += 1
                acc += prof[px[j]]
            else:
                i -= 1
                acc += prof[px[i]]
        return poc, px[j], px[i]

    def _flush(self):
        r = self.rth
        self.rth = None
        if r is None or not r["bars"]:
            return
        ds = r["day"].strftime("%Y%m%d")
        base = r["base"]
        onpoc = self._va(r["on"]["prof"])[0] if r["on"]["prof"] else 0.0
        poc, vah, val = self._va(r["prof"])
        onh = r["on"]["h"] or 0.0
        onl = r["on"]["l"] or 0.0
        self._emit(f"H,{ds},{r['exp']},{onh:.2f},{onl:.2f},{onpoc:.0f},{r['on']['v']:.0f},"
                   f"{poc:.0f},{vah:.0f},{val:.0f},{r['vol']:.0f},{base:.2f},"
                   f"{r['on']['ah'] or 0:.2f},{r['on']['al'] or 0:.2f},{r['on']['lh'] or 0:.2f},{r['on']['ll'] or 0:.2f}")
        tk = lambda p: int(round((p - base) * 4))
        bars = r["bars"]
        for k in range(0, len(bars), 13):
            chunk = "/".join(f"{tk(o)}:{tk(h)}:{tk(l)}:{tk(c)}:{int(v)}" for (o, h, l, c, v) in bars[k:k + 13])
            self._emit(f"B,{ds},{k // 13},{chunk}")

    def OnData(self, slice):
        if slice.Bars is None:
            return
        bar = slice.Bars.get(self.fut.Symbol)
        if bar is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute                      # bar END minute, ET
        o, h, l, c, v = (float(bar.Open), float(bar.High), float(bar.Low),
                         float(bar.Close), float(bar.Volume))
        rth = 9 * 60 + 30 < hm <= 16 * 60 and t.weekday() < 5
        if self.rth is not None and (not rth or self.rth["day"] != t.date()):
            self._flush()
            self._reset_on()
        if not rth:
            if hm > 18 * 60 or hm <= 9 * 60 + 30:
                s = self.on
                s["h"] = h if s["h"] is None else max(s["h"], h)
                s["l"] = l if s["l"] is None else min(s["l"], l)
                s["v"] += v
                s["prof"][round((h + l + c) / 3.0)] += v
                for lo_, hi_, kh, kl in ((18 * 60, 24 * 60, "ah", "al"), (-1, 0, "ah", "al"), (2 * 60, 5 * 60, "lh", "ll")):
                    if lo_ < hm <= hi_:
                        s[kh] = h if s[kh] is None else max(s[kh], h)
                        s[kl] = l if s[kl] is None else min(s[kl], l)
            return
        if self.rth is None:
            m = self.fut.Mapped
            self.rth = {"day": t.date(), "base": o, "on": self.on, "prof": defaultdict(float), "vol": 0.0,
                        "bars": [], "cur": None, "exp": m.ID.Date.strftime("%y%m%d") if m is not None else "0"}
        r = self.rth
        r["prof"][round((h + l + c) / 3.0)] += v
        r["vol"] += v
        b = r["cur"]
        if b is None:
            b = [o, h, l, c, v]
        else:
            b[1] = max(b[1], h)
            b[2] = min(b[2], l)
            b[3] = c
            b[4] += v
        r["cur"] = b
        if (hm - (9 * 60 + 30)) % 5 == 0:
            r["bars"].append(tuple(b))
            r["cur"] = None

    def OnEndOfAlgorithm(self):
        self._flush()
        self.Log(f"TAGS={self.n_tags}")
