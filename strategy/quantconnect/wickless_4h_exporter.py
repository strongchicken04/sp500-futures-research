# region imports
from AlgorithmImports import *
# endregion

# Wickless 4H candle claim test (video strategie #2, ICT stylu)
#
# Claim z videa: 4H svicka BEZ SPODNIHO KNOTU je "temer vzdy pohlcena" -
# cena se vraci na jeji low ("no manipulation -> imbalance must be filled").
#
# Merime na realnem NQ (extended hours, 4H buckety kotvene 18:00 ET jako TV):
#   - event = dokonceny 4H bar s malym knotem (spodni i horni symetricky):
#       wick <= max(1 tick, WICK_FRAC * range)
#   - baseline = kazdy 10. dokonceny 4H bar (jeho low i high) - kontrola,
#     jestli wickless urovne pritahuji cenu VIC nez bezne urovne
#   - pro kazdy event sledujeme dalsich az HORIZON 4H baru:
#       touched? za kolik 4H baru? max utek ceny PROTI urovni (away)
#
# Exfiltrace: 1 canceled limit order / event, tag:
#   W4,date,hour,kind,dir,wick,frac,rng,touched,bars,away
#   kind: BW=bottom wick event, TW=top wick, LB=baseline low, LT=baseline high
#   dir:  U=bull svicka, D=bear svicka

WICK_FRAC = 0.03      # "bez knotu" = knot <= 3 % range (a vzdy tolerance 1 tick)
TICK = 0.25
HORIZON = 30          # sleduj max 30 4H baru (~5 obchodnich dni)
BASE_EVERY = 10       # baseline sampling: kazdy 10. bar


class NQWickless4H(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        self.epoch = datetime(2018, 1, 1)
        self.cur_bucket = None
        self.o = self.h = self.l = self.c = None
        self.n_bars = 0
        self.events = []          # aktivni sledovane urovne
        self.n_tags = 0

    def _bucket(self, t):
        # 4H bucket kotveny na 18:00 ET
        total_min = int((t - self.epoch).total_seconds() // 60)
        return (total_min - 1080) // 240

    def _emit(self, ev, touched, bars):
        tag = (f"W4,{ev['date']},{ev['hour']:02d},{ev['kind']},{ev['dir']},"
               f"{ev['wick']:.2f},{ev['frac']:.4f},{ev['rng']:.2f},"
               f"{int(touched)},{bars},{ev['away']:.2f}")
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def _register(self, kind, level, o, h, l, c, wick, t_end):
        rng = h - l
        self.events.append({
            "kind": kind, "level": level, "dir": "U" if c >= o else "D",
            "wick": wick, "frac": wick / rng if rng > 0 else 0.0, "rng": rng,
            "start": self.n_bars, "away": 0.0,
            "date": t_end.strftime("%Y-%m-%d"), "hour": t_end.hour})

    def _candle_done(self, t_end):
        o, h, l, c = self.o, self.h, self.l, self.c
        rng = h - l
        if rng <= 0:
            return
        self.n_bars += 1
        bot_wick = min(o, c) - l
        top_wick = h - max(o, c)
        thr = max(TICK + 1e-9, WICK_FRAC * rng)
        if bot_wick <= thr:
            self._register("BW", l, o, h, l, c, bot_wick, t_end)
        if top_wick <= thr:
            self._register("TW", h, o, h, l, c, top_wick, t_end)
        if self.n_bars % BASE_EVERY == 0:
            self._register("LB", l, o, h, l, c, bot_wick, t_end)
            self._register("LT", h, o, h, l, c, top_wick, t_end)

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        b = self._bucket(t)
        if self.cur_bucket is None:
            self.cur_bucket = b
        if b != self.cur_bucket:
            if self.o is not None:
                self._candle_done(t)
            self.cur_bucket = b
            self.o = self.h = self.l = self.c = None

        if self.o is None:
            self.o, self.h, self.l, self.c = bar.Open, bar.High, bar.Low, bar.Close
        else:
            self.h = max(self.h, bar.High)
            self.l = min(self.l, bar.Low)
            self.c = bar.Close

        # sledovani aktivnich urovni (minutova granularita)
        if not self.events:
            return
        done = []
        for ev in self.events:
            elapsed = self.n_bars - ev["start"]
            if ev["kind"] in ("BW", "LB"):
                ev["away"] = max(ev["away"], bar.High - ev["level"])
                hit = bar.Low <= ev["level"]
            else:
                ev["away"] = max(ev["away"], ev["level"] - bar.Low)
                hit = bar.High >= ev["level"]
            if hit:
                self._emit(ev, True, max(elapsed, 1))
                done.append(ev)
            elif elapsed > HORIZON:
                self._emit(ev, False, -1)
                done.append(ev)
        for ev in done:
            self.events.remove(ev)

    def OnEndOfAlgorithm(self):
        for ev in self.events:
            self._emit(ev, False, -1)   # nevyresene na konci (nepujdou emitnout, jen log)
        self.Log(f"W4_TAGS={self.n_tags} PENDING={len(self.events)} BARS={self.n_bars}")
