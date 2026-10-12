# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion

# TradeAxis DOL — hit-rate test on NQ 2018-2025, 5min bars.
#
# Replicates the public 4-pillar scoring recipe (we can't see the source):
#   Score (0..100) = Proximity(0..40) + Freshness(0..25) + Confluence(0..20) + Density(0..15)
# Level pool: BSL (swing high), SSL (swing low), bullish FVG mid, bearish FVG mid.
#
# Signal := bar where the "primary" (highest-scored, non-swept, within max ATR)
#          level ABOVE price (BSL/bullFVG) or BELOW price (SSL/bearFVG) CHANGES
#          vs previous bar.
#
# Measurement: within next N_LOOK (20) bars, is target zone touched?
#   zone = target_px +- 0.10 * ATR
# Hit = 1 if touched, 0 if not. If still open at end of data, drop.
#
# Base rate: for every signal, also pick a RANDOM level at the same ATR
#   distance in the same direction (seeded by bar_index) and record its hit.
#
# Emit tags: DOL,date_time,side,kind,px,atr,atr_dist,score,hit,bars_to_touch,
#            rand_px,rand_hit
# Score bucket analysis is done post-hoc on the dump.

TF_MIN       = 5
ATR_LEN      = 14
MAX_ATR_DIST = 4.0
HALF_LIFE    = 50
PIVOT_LEN    = 5
N_LOOK       = 20            # measurement horizon
ZONE_FRAC    = 0.10          # zone width = 0.10 * ATR

START_YEAR   = 2018
END_YEAR     = 2025


class TradeAxisDOLHitRate(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(START_YEAR, 1, 1)
        self.SetEndDate(END_YEAR, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=False)
        f.SetFilter(0, 180)
        self.future = f
        self.cont = f.Symbol
        self.n_tags = 0

        # bar builder
        self.bar_o = None; self.bar_h = None; self.bar_l = None
        self.bar_c = None; self.bar_start = None
        # history for pivots, FVG, density, ATR
        self.hist = deque(maxlen=max(200, N_LOOK + PIVOT_LEN * 4))
        # bar index counter
        self.bi = 0
        # ATR
        self.tr_q = deque(maxlen=ATR_LEN)
        self.atr = None
        # level pool: list of dicts {px, birth, kind, swept}
        # kind: 1=BSL, 2=SSL, 3=bullFVG, 4=bearFVG
        self.levels = []
        # previous primary targets (to detect "change" signal)
        self.prev_bsl = None
        self.prev_ssl = None
        # pending measurements: list of dicts to resolve as new bars arrive
        self.pending = []  # {'side','kind','px','atr','atr_dist','score','start_bi','rand_px','done','hit','bars','rand_hit','rand_done','date_time'}
        # PDH/PDL
        self.cur_date = None
        self.day_h = None; self.day_l = None; self.day_c = None
        self.pdh = None; self.pdl = None; self.pdc = None

    def _bucket_start(self, t):
        m = (t.minute // TF_MIN) * TF_MIN
        return t.replace(minute=m, second=0, microsecond=0)

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        bs = self._bucket_start(t)
        if self.bar_start != bs:
            if self.bar_o is not None:
                self._on_bar({'o': self.bar_o, 'h': self.bar_h, 'l': self.bar_l,
                              'c': self.bar_c, 't': self.bar_start})
            self.bar_o = bar.Open; self.bar_h = bar.High
            self.bar_l = bar.Low;  self.bar_c = bar.Close
            self.bar_start = bs
        else:
            self.bar_h = max(self.bar_h, bar.High)
            self.bar_l = min(self.bar_l, bar.Low)
            self.bar_c = bar.Close

    def _on_bar(self, b):
        self.bi += 1
        self.hist.append(b)

        # daily rollover for PDH/PDL
        d = b['t'].date()
        if self.cur_date != d:
            if self.day_h is not None:
                self.pdh = self.day_h; self.pdl = self.day_l; self.pdc = self.day_c
            self.cur_date = d
            self.day_h = b['h']; self.day_l = b['l']; self.day_c = b['c']
        else:
            self.day_h = max(self.day_h, b['h'])
            self.day_l = min(self.day_l, b['l'])
            self.day_c = b['c']

        # ATR update
        if len(self.hist) >= 2:
            prev = self.hist[-2]
            tr = max(b['h'] - b['l'],
                     abs(b['h'] - prev['c']),
                     abs(b['l'] - prev['c']))
            self.tr_q.append(tr)
            if len(self.tr_q) == ATR_LEN:
                self.atr = sum(self.tr_q) / ATR_LEN

        if self.atr is None or self.pdh is None:
            return

        # resolve pending measurements
        self._resolve_pending(b)

        # detect new levels (confirmed pivots require PIVOT_LEN bars after)
        self._detect_levels(b)

        # mark swept
        self._mark_swept(b)

        # compute primary
        bsl = self._primary(above=True)
        ssl = self._primary(above=False)

        # signal = primary CHANGE
        if bsl is not None:
            key_bsl = (bsl['kind'], round(bsl['px'], 2))
            if key_bsl != self.prev_bsl:
                self._emit_signal('BSL', bsl, b)
                self.prev_bsl = key_bsl
        if ssl is not None:
            key_ssl = (ssl['kind'], round(ssl['px'], 2))
            if key_ssl != self.prev_ssl:
                self._emit_signal('SSL', ssl, b)
                self.prev_ssl = key_ssl

        # cull old swept levels (keep pool bounded)
        if len(self.levels) > 300:
            self.levels = [lv for lv in self.levels[-300:]]

    def _detect_levels(self, b):
        # pivot high/low: index -PIVOT_LEN-1 is the pivot center
        n = len(self.hist)
        if n < 2 * PIVOT_LEN + 1:
            return
        c = n - PIVOT_LEN - 1
        center = self.hist[c]
        is_ph = all(center['h'] >= self.hist[i]['h'] for i in range(c - PIVOT_LEN, c + PIVOT_LEN + 1) if i != c)
        is_pl = all(center['l'] <= self.hist[i]['l'] for i in range(c - PIVOT_LEN, c + PIVOT_LEN + 1) if i != c)
        center_bi = self.bi - PIVOT_LEN
        if is_ph:
            self.levels.append({'px': center['h'], 'birth': center_bi, 'kind': 1, 'swept': False})
        if is_pl:
            self.levels.append({'px': center['l'], 'birth': center_bi, 'kind': 2, 'swept': False})
        # FVG on the just-confirmed bar: look at hist[-3], [-2], [-1]
        if n >= 3:
            b0 = self.hist[-1]; b2 = self.hist[-3]
            if b0['l'] > b2['h']:  # bull FVG
                self.levels.append({'px': (b0['l'] + b2['h']) / 2, 'birth': self.bi, 'kind': 3, 'swept': False})
            if b0['h'] < b2['l']:  # bear FVG
                self.levels.append({'px': (b0['h'] + b2['l']) / 2, 'birth': self.bi, 'kind': 4, 'swept': False})

    def _mark_swept(self, b):
        for lv in self.levels:
            if lv['swept']:
                continue
            k = lv['kind']
            if (k == 1 or k == 3) and b['h'] >= lv['px']:
                lv['swept'] = True
            if (k == 2 or k == 4) and b['l'] <= lv['px']:
                lv['swept'] = True

    def _score(self, lv, close_px):
        d_atr = abs(close_px - lv['px']) / max(self.atr, 1e-6)
        prox = 0.0 if d_atr > MAX_ATR_DIST else (1.0 - d_atr / MAX_ATR_DIST) * 40.0
        age = self.bi - lv['birth']
        fresh = (0.5 ** (age / max(HALF_LIFE, 1))) * 25.0
        tol = 0.2 * self.atr
        conf = 0.0
        if abs(lv['px'] - self.pdh) <= tol: conf += 10
        if abs(lv['px'] - self.pdl) <= tol: conf += 10
        if abs(lv['px'] - self.pdc) <= tol: conf += 6
        pdEq = (self.pdh + self.pdl) / 2
        if abs(lv['px'] - pdEq) <= tol: conf += 4
        conf = min(conf, 20)
        # density: equal highs/lows within tolD over last 20 bars
        tolD = 0.1 * self.atr
        dens = 0.0
        for i in range(max(0, len(self.hist) - 20), len(self.hist)):
            bb = self.hist[i]
            if abs(bb['h'] - lv['px']) <= tolD or abs(bb['l'] - lv['px']) <= tolD:
                dens += 2.0
        dens = min(dens, 15)
        return prox + fresh + conf + dens

    def _primary(self, above):
        close_px = self.hist[-1]['c']
        best = None; best_sc = -1.0
        for lv in self.levels:
            if lv['swept']:
                continue
            if above and (lv['px'] <= close_px or lv['kind'] not in (1, 3)):
                continue
            if not above and (lv['px'] >= close_px or lv['kind'] not in (2, 4)):
                continue
            d_atr = abs(close_px - lv['px']) / max(self.atr, 1e-6)
            if d_atr > MAX_ATR_DIST:
                continue
            sc = self._score(lv, close_px)
            if sc > best_sc:
                best_sc = sc; best = lv
        if best is None:
            return None
        return {'px': best['px'], 'kind': best['kind'], 'score': best_sc,
                'atr_dist': abs(close_px - best['px']) / self.atr}

    def _emit_signal(self, side, lv, b):
        # random comparison level: same ATR distance in same direction,
        # seeded deterministically on bar_index for reproducibility
        rng_seed = (self.bi * 2654435761) & 0xFFFFFFFF
        # pseudo-random in [0.5, maxAtrDist], mapped to atr distance
        u = ((rng_seed >> 8) & 0xFFFF) / 0xFFFF
        rand_dist_atr = 0.5 + u * (MAX_ATR_DIST - 0.5)
        close_px = b['c']
        if side == 'BSL':
            rand_px = close_px + rand_dist_atr * self.atr
        else:
            rand_px = close_px - rand_dist_atr * self.atr
        self.pending.append({
            'side': side, 'kind': lv['kind'], 'px': lv['px'], 'atr': self.atr,
            'atr_dist': lv['atr_dist'], 'score': lv['score'],
            'start_bi': self.bi, 'done': False, 'hit': 0, 'bars': -1,
            'rand_px': rand_px, 'rand_done': False, 'rand_hit': 0, 'rand_bars': -1,
            'date_time': b['t'].strftime('%Y-%m-%d %H:%M'),
        })

    def _resolve_pending(self, b):
        half = ZONE_FRAC * self.atr
        remaining = []
        for p in self.pending:
            age = self.bi - p['start_bi']
            # resolve target
            if not p['done']:
                lo = p['px'] - half; hi = p['px'] + half
                if b['l'] <= hi and b['h'] >= lo:
                    p['done'] = True; p['hit'] = 1; p['bars'] = age
                elif age >= N_LOOK:
                    p['done'] = True; p['hit'] = 0; p['bars'] = age
            # resolve random
            if not p['rand_done']:
                lo = p['rand_px'] - half; hi = p['rand_px'] + half
                if b['l'] <= hi and b['h'] >= lo:
                    p['rand_done'] = True; p['rand_hit'] = 1; p['rand_bars'] = age
                elif age >= N_LOOK:
                    p['rand_done'] = True; p['rand_hit'] = 0; p['rand_bars'] = age
            if p['done'] and p['rand_done']:
                self._emit(f"DOL,{p['date_time']},{p['side']},{p['kind']},"
                           f"{p['px']:.2f},{p['atr']:.2f},{p['atr_dist']:.2f},"
                           f"{p['score']:.2f},{p['hit']},{p['bars']},"
                           f"{p['rand_px']:.2f},{p['rand_hit']}")
            else:
                remaining.append(p)
        self.pending = remaining

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
