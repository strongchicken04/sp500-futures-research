# region imports
from AlgorithmImports import *
# endregion
#
# ON FADE FILL TEST: does the overnight-level fade survive honest fills?
#
# The preregistered fade (first RTH touch of overnight high -> short, low ->
# long, midpoint -> toward the RTH open, 1:1 bracket, overnight range >= 65)
# was backtested with a resting limit filled exactly at the level on first
# touch. An exact touch that reverses is the case most likely to go unfilled
# live and the case most likely to win, so that assumption flatters it. Each
# level is therefore evaluated under three fill rules at once:
#
#   T  touch  - fill at the level on first touch (the original assumption)
#   X  thru   - fill at the level only once price trades 1 tick beyond it,
#               which guarantees a resting limit would have filled
#   C  close  - fill at the close of the first touching 1-minute bar
#
# On the fill bar only adverse movement counts; favourable movement inside
# that bar is ignored because its order relative to the fill is unknown.
# Brackets are tracked on 1-minute bars; a bar touching both sides is a stop.
#
# Tag: OC,<yyyymmdd>,<leg>,<dir>,<onrange>,
#      <for each mode T,X,C: fillmin,entry,r10,r15,r20,eodpts>
#   r = T target first / S stop first / E neither by 15:59 / N no fill

BRACKETS = [10.0, 15.0, 20.0]
TICK = 0.25
LAST_ENTRY = 15 * 60
EOD = 15 * 60 + 59
MODES = ("T", "X", "C")


class OnFadeFillTest(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 180)
        self.future = f
        self.cont = f.Symbol
        self.n_tags = 0
        self.onh = None
        self.onl = None
        self.cur_date = None
        self.legs = None
        self.rth_open = None
        self.last_close = None

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        # minute bars are stamped at their close; use the bar's start minute
        em = t.hour * 60 + t.minute - 1
        h, l, c = float(bar.High), float(bar.Low), float(bar.Close)

        if em >= 18 * 60 or em < 9 * 60 + 30:
            if em >= 18 * 60 and self.legs is not None:
                self._flush()
            if self.onh is None or (em >= 18 * 60 and self._fresh_on):
                self.onh, self.onl = h, l
                self._fresh_on = False
            else:
                self.onh = max(self.onh, h)
                self.onl = min(self.onl, l)
            return
        if em >= 16 * 60:
            self._fresh_on = True
            return

        d = t.date()
        if self.cur_date != d:
            self.cur_date = d
            self._start_day(float(bar.Open))
        if self.legs is None:
            return
        for leg in self.legs.values():
            self._step_leg(leg, em, h, l, c)
        if em >= EOD:
            self._flush()

    # ------------------------------------------------------------------
    _fresh_on = True

    def _start_day(self, rth_open):
        self.legs = None
        if self.onh is None or self.onl is None:
            return
        onh, onl = self.onh, self.onl
        onm = (onh + onl) / 2.0
        if rth_open > onm:
            mdir = 1
        elif rth_open < onm:
            mdir = -1
        else:
            mdir = 0
        self.legs = {}
        self.legs['H'] = self._new_leg('H', onh, -1, onh - onl)
        self.legs['L'] = self._new_leg('L', onl, 1, onh - onl)
        if mdir != 0:
            self.legs['M'] = self._new_leg('M', onm, mdir, onh - onl)
        self._fresh_on = True

    def _new_leg(self, name, level, direction, onrange):
        modes = {}
        for m in MODES:
            modes[m] = {'filled': False, 'fmin': -1, 'e': 0.0,
                        'res': {b: None for b in BRACKETS}, 'last': 0.0}
        return {'name': name, 'lvl': level, 'dir': direction,
                'rng': onrange, 'touched': False, 'modes': modes,
                'done': False}

    def _touch(self, leg, h, l):
        lvl = leg['lvl']
        if leg['name'] == 'M':
            return h >= lvl and l <= lvl
        return h >= lvl if leg['dir'] == -1 else l <= lvl

    def _through(self, leg, h, l):
        lvl = leg['lvl']
        if leg['name'] == 'M':
            # midpoint: the fade direction decides which side must trade
            return (l <= lvl - TICK) if leg['dir'] == 1 else (h >= lvl + TICK)
        return (h >= lvl + TICK) if leg['dir'] == -1 else (l <= lvl - TICK)

    def _step_leg(self, leg, em, h, l, c):
        if leg['done']:
            return
        d = leg['dir']
        for m, st in leg['modes'].items():
            if st['filled']:
                self._advance(st, d, h, l, c, fill_bar=False)
                continue
            if em > LAST_ENTRY:
                continue
            fill = False
            price = leg['lvl']
            if m == 'T' and self._touch(leg, h, l):
                fill = True
            elif m == 'X' and self._through(leg, h, l):
                fill = True
            elif m == 'C' and self._touch(leg, h, l):
                fill = True
                price = c
            if fill:
                st['filled'] = True
                st['fmin'] = em - (9 * 60 + 30)
                st['e'] = price
                if m != 'C':
                    self._advance(st, d, h, l, c, fill_bar=True)
                st['last'] = c

    def _advance(self, st, d, h, l, c, fill_bar):
        e = st['e']
        adv = (e - l) if d == 1 else (h - e)
        fav = (h - e) if d == 1 else (e - l)
        for b in BRACKETS:
            if st['res'][b] is not None:
                continue
            a_hit = adv >= b
            f_hit = (not fill_bar) and fav >= b
            if a_hit:
                st['res'][b] = 'S'
            elif f_hit:
                st['res'][b] = 'T'
        st['last'] = c

    def _flush(self):
        if self.legs is None:
            return
        for leg in self.legs.values():
            parts = []
            for m in MODES:
                st = leg['modes'][m]
                if not st['filled']:
                    parts.append("-1,0,N,N,N,0")
                    continue
                rs = [st['res'][b] or 'E' for b in BRACKETS]
                eod = leg['dir'] * (st['last'] - st['e'])
                parts.append(f"{st['fmin']},{st['e']:.2f},"
                             f"{rs[0]},{rs[1]},{rs[2]},{eod:.2f}")
            if all(p.startswith("-1") for p in parts):
                continue
            ds = self.cur_date.strftime('%Y%m%d')
            self._emit(f"OC,{ds},{leg['name']},{leg['dir']},"
                       f"{leg['rng']:.2f}," + ",".join(parts))
        self.legs = None

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5, 2),
                                          tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
