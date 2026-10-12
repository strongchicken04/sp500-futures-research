# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# TradeAxis DOL — tradeable strategy on NQ 5min 2018-2025.
#
# Entry: when primary BSL (above) or SSL (below) emerges with score >= MIN_SCORE,
#        enter in the direction of DOL at close of bar.
#          BSL + score>=MIN_SCORE -> LONG targeting BSL
#          SSL + score>=MIN_SCORE -> SHORT targeting SSL
# TP: target = DOL price (zone midpoint; filled when high/low touches zone)
# SL: opposite-side "nearest" level — nearest live SSL below (for long) or BSL
#     above (for short). If none, fall back to recent swing low/high in hist.
# Timeout: if neither TP nor SL hit within MAX_HOLD bars, flat at close.
#
# One trade at a time. Score threshold filters volume to a manageable rate.
#
# Emit per trade:
#   DOL_TR,dt,side,entry_px,sl,tp,exit_px,exit_reason,pnl,bars,score,atr_dist
#     exit_reason: TP, SL, TIME

TF_MIN       = 5
ATR_LEN      = 14
MAX_ATR_DIST = 4.0
HALF_LIFE    = 50
PIVOT_LEN    = 5
ZONE_FRAC    = 0.10
MIN_SCORE    = 65.0        # tested threshold
MAX_HOLD     = 20
START_YEAR   = 2018
END_YEAR     = 2025


class TradeAxisDOLStrategy(QCAlgorithm):

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

        self.bar_o = None; self.bar_h = None; self.bar_l = None
        self.bar_c = None; self.bar_start = None
        self.hist = deque(maxlen=max(200, MAX_HOLD + PIVOT_LEN * 4))
        self.bi = 0
        self.tr_q = deque(maxlen=ATR_LEN)
        self.atr = None
        self.levels = []
        self.cur_date = None
        self.day_h = None; self.day_l = None; self.day_c = None
        self.pdh = None; self.pdl = None; self.pdc = None
        # active trade state
        self.trade = None
        self.prev_bsl = None
        self.prev_ssl = None

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

        if len(self.hist) >= 2:
            prev = self.hist[-2]
            tr = max(b['h'] - b['l'], abs(b['h'] - prev['c']), abs(b['l'] - prev['c']))
            self.tr_q.append(tr)
            if len(self.tr_q) == ATR_LEN:
                self.atr = sum(self.tr_q) / ATR_LEN

        if self.atr is None or self.pdh is None:
            return

        # resolve active trade FIRST (on this bar's H/L)
        if self.trade is not None:
            self._manage_trade(b)

        self._detect_levels(b)
        self._mark_swept(b)

        # entry only when no active trade
        if self.trade is None:
            bsl = self._primary(above=True)
            ssl = self._primary(above=False)
            # pick higher-scored side
            cand = None
            if bsl is not None and bsl['score'] >= MIN_SCORE:
                cand = ('BSL', bsl)
            if ssl is not None and ssl['score'] >= MIN_SCORE:
                if cand is None or ssl['score'] > cand[1]['score']:
                    cand = ('SSL', ssl)
            if cand is not None:
                side, lv = cand
                key = (lv['kind'], round(lv['px'], 2))
                prev = self.prev_bsl if side == 'BSL' else self.prev_ssl
                if key != prev:
                    self._enter(side, lv, b)
                    if side == 'BSL':
                        self.prev_bsl = key
                    else:
                        self.prev_ssl = key

        if len(self.levels) > 300:
            self.levels = [lv for lv in self.levels[-300:]]

    def _detect_levels(self, b):
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
        if n >= 3:
            b0 = self.hist[-1]; b2 = self.hist[-3]
            if b0['l'] > b2['h']:
                self.levels.append({'px': (b0['l'] + b2['h']) / 2, 'birth': self.bi, 'kind': 3, 'swept': False})
            if b0['h'] < b2['l']:
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

    def _nearest_opposite(self, side, entry_px):
        # SL anchor:
        #   long  -> nearest live SSL (pivL or bearFVG) BELOW entry
        #   short -> nearest live BSL (pivH or bullFVG) ABOVE entry
        best = None; best_d = 1e18
        for lv in self.levels:
            if lv['swept']:
                continue
            k = lv['kind']
            if side == 'LONG' and k in (2, 4) and lv['px'] < entry_px:
                d = entry_px - lv['px']
                if d < best_d:
                    best_d = d; best = lv['px']
            if side == 'SHORT' and k in (1, 3) and lv['px'] > entry_px:
                d = lv['px'] - entry_px
                if d < best_d:
                    best_d = d; best = lv['px']
        # fallback: use recent hist swing within last 20 bars
        if best is None:
            lookback = list(self.hist)[-20:]
            if side == 'LONG':
                best = min(bb['l'] for bb in lookback) - 0.1 * self.atr
            else:
                best = max(bb['h'] for bb in lookback) + 0.1 * self.atr
        return best

    def _enter(self, side_lbl, lv, b):
        close_px = b['c']
        if side_lbl == 'BSL':
            tr_side = 'LONG'
            tp = lv['px']
            sl = self._nearest_opposite('LONG', close_px)
            if sl >= close_px:  # safety
                sl = close_px - 0.5 * self.atr
        else:
            tr_side = 'SHORT'
            tp = lv['px']
            sl = self._nearest_opposite('SHORT', close_px)
            if sl <= close_px:
                sl = close_px + 0.5 * self.atr
        self.trade = {
            'side': tr_side, 'entry_px': close_px, 'tp': tp, 'sl': sl,
            'entry_bi': self.bi, 'score': lv['score'], 'atr_dist': lv['atr_dist'],
            'date_time': b['t'].strftime('%Y-%m-%d %H:%M'),
        }

    def _manage_trade(self, b):
        tr = self.trade
        age = self.bi - tr['entry_bi']
        half = ZONE_FRAC * self.atr
        if tr['side'] == 'LONG':
            # SL first (worst case assumption on same bar)
            if b['l'] <= tr['sl']:
                ex = tr['sl']; reason = 'SL'
            elif b['h'] >= tr['tp'] - half:
                ex = tr['tp'] - half; reason = 'TP'
            elif age >= MAX_HOLD:
                ex = b['c']; reason = 'TIME'
            else:
                return
            pnl = ex - tr['entry_px']
        else:
            if b['h'] >= tr['sl']:
                ex = tr['sl']; reason = 'SL'
            elif b['l'] <= tr['tp'] + half:
                ex = tr['tp'] + half; reason = 'TP'
            elif age >= MAX_HOLD:
                ex = b['c']; reason = 'TIME'
            else:
                return
            pnl = tr['entry_px'] - ex
        self._emit(f"DOL_TR,{tr['date_time']},{tr['side']},"
                   f"{tr['entry_px']:.2f},{tr['sl']:.2f},{tr['tp']:.2f},"
                   f"{ex:.2f},{reason},{pnl:.2f},{age},"
                   f"{tr['score']:.2f},{tr['atr_dist']:.2f}")
        self.trade = None

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
