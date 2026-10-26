# region imports
from AlgorithmImports import *
# endregion
#
# CROSS-ASSET EXPORTER: two literature edges outside equity indices.
#
#   CLE0 / CLE1  Crude oil on EIA Wednesdays (Wen, Indriawan, Lien & Xu,
#                Energy Journal 2023): the half-hour around the 10:30 ET
#                inventory release predicts the last half-hour. Sign of the
#                10:00-10:30 (CLE0) or 10:30-11:00 (CLE1) return, if larger
#                than 0.15%, is traded from 14:00 to 14:30.
#   GCA3 / GCA8  Gold long through Asian hours (Blose & Gondhalekar 2014;
#                Blose, Gondhalekar & Kort 2018): buy at the 18:00 ET
#                session open, exit at 03:00 (GCA3) or 08:20 (GCA8). Same
#                CME session, so flat before the next settlement.
#
# Everything runs on 1-minute bars. Entry is at the close of the entry
# minute and tracking starts on the following minute, so no part of the fill
# minute can count toward a stop or a target.
#
# Tag: C,<sig>,<yyyymmddHHMM>,<dir>,<entry>,<s x5>,<t x5>,<exit_pts>

CL_GRID = [0.0010, 0.0020, 0.0030, 0.0050, 0.0080]
GC_GRID = [0.0005, 0.0010, 0.0020, 0.0035, 0.0060]
CL_MIN_MOVE = 0.0015


class CrossAssetExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.cl = self._add(Futures.Energies.CRUDE_OIL_WTI)
        self.gc = self._add(Futures.Metals.GOLD)
        self.marks = {}
        self.open = []
        self.cl_day = None

    def _add(self, ticker):
        f = self.AddFuture(
            ticker, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 180)
        return f

    def OnData(self, slice):
        if slice.Bars is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute          # bar end time, ET
        for fut, key in ((self.cl, 'CL'), (self.gc, 'GC')):
            bar = slice.Bars.get(fut.Symbol)
            if bar is None:
                continue
            h, l, c = float(bar.High), float(bar.Low), float(bar.Close)
            self._track(key, h, l, c, hm, t)
            if key == 'CL':
                self._cl_logic(c, hm, t)
            else:
                self._gc_logic(c, hm, t)

    # ------------------------------------------------------------------
    def _cl_logic(self, c, hm, t):
        if t.weekday() != 2:
            return
        d = t.date()
        if self.cl_day != d:
            self.cl_day = d
            self.marks = {}
        for name, m in (('p1000', 10 * 60), ('p1030', 10 * 60 + 30),
                        ('p1100', 11 * 60)):
            if hm == m:
                self.marks[name] = c
        if hm == 14 * 60:
            mk = self.marks
            for sig, a, b in (('CLE0', 'p1000', 'p1030'),
                              ('CLE1', 'p1030', 'p1100')):
                if a in mk and b in mk and mk[a] > 0:
                    r = mk[b] / mk[a] - 1.0
                    if abs(r) > CL_MIN_MOVE:
                        self._open(sig, 'CL', 1 if r > 0 else -1, c, t,
                                   exit_hm=14 * 60 + 30, grid=CL_GRID)

    def _gc_logic(self, c, hm, t):
        # session reopens at 18:00; first bar ends 18:01. Sun-Thu evenings.
        if hm == 18 * 60 + 1 and t.weekday() in (6, 0, 1, 2, 3):
            self._open('GCA3', 'GC', 1, c, t, exit_hm=3 * 60, grid=GC_GRID,
                       overnight=True)
            self._open('GCA8', 'GC', 1, c, t, exit_hm=8 * 60 + 20,
                       grid=GC_GRID, overnight=True)

    # ------------------------------------------------------------------
    def _open(self, sig, inst, direction, price, t, exit_hm, grid,
              overnight=False):
        self.open.append({
            'sig': sig, 'inst': inst, 'dir': direction, 'e': price,
            'k': 0, 'exit': exit_hm, 'grid': grid, 'ov': overnight,
            'crossed': False,
            'sb': [-1] * len(grid), 'tb': [-1] * len(grid),
            'dt': t.strftime('%Y%m%d%H%M'),
        })

    def _track(self, inst, h, l, c, hm, t):
        keep = []
        for s in self.open:
            if s['inst'] != inst:
                keep.append(s)
                continue
            s['k'] += 1
            e = s['e']
            adv = (e - l) if s['dir'] == 1 else (h - e)
            fav = (h - e) if s['dir'] == 1 else (e - l)
            for i, p in enumerate(s['grid']):
                if s['sb'][i] < 0 and adv >= e * p:
                    s['sb'][i] = s['k']
                if s['tb'][i] < 0 and fav >= e * p:
                    s['tb'][i] = s['k']
            # overnight trades must pass midnight before the exit time counts
            if s['ov'] and hm < 12 * 60:
                s['crossed'] = True
            due = (s['crossed'] and hm >= s['exit']) if s['ov'] \
                else hm >= s['exit']
            if due or s['k'] > 900:
                self._emit_sig(s, s['dir'] * (c - e))
            else:
                keep.append(s)
        self.open = keep

    def _emit_sig(self, s, pnl):
        sb = ",".join(str(x) for x in s['sb'])
        tb = ",".join(str(x) for x in s['tb'])
        self._emit(f"C,{s['sig']},{s['dt']},{s['dir']},{s['e']:.4f},"
                   f"{sb},{tb},{pnl:.4f}")

    def _emit(self, tag):
        try:
            sym = self.gc.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5, 1),
                                          tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
