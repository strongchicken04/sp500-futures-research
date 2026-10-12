# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# TradeAxis DOL v4 — PULLBACK entry trigger on NQ 5min 2018-2025.
#
# Hypothesis: hit-rate edge is real (v2 proved +30pp above base rate at
# score>=65). Previous entries failed because entry close is often near
# a local extreme (price moved to generate the pivot). Fix: wait for
# price to pull BACK AWAY from DOL first, then enter when it resumes.
#
# Rules:
#   1. Primary target emerges with score >= MIN_SCORE  -> create pending setup
#   2. Store entry_close + DOL + ATR + direction
#   3. Wait up to WAIT_BARS for a pullback bar:
#         LONG:  close drops at least PB_ATR * atr below emergence close
#         SHORT: close rises at least PB_ATR * atr above emergence close
#   4. On that pullback bar, enter at close
#   5. SL = pullback bar low (long) / high (short) minus 0.1*atr buffer
#      Capped to max SL_CAP_ATR
#   6. TP = DOL price
#   7. Timeout: MAX_HOLD bars after entry
#   8. If primary becomes swept or score drops below CANCEL_SCORE -> cancel setup
#
# Emit: DOL4,dt_entry,side,entry,sl,tp,exit,reason,pnl,bars_held,bars_waited,
#       score,atr_dist,rr

TF_MIN       = 15          # 15min bars — less noise, cleaner SL survival
ATR_LEN      = 14
MAX_ATR_DIST = 4.0
HALF_LIFE    = 50
PIVOT_LEN    = 5
ZONE_FRAC    = 0.10
MIN_SCORE    = 70.0        # only the better bucket
CANCEL_SCORE = 55.0
MAX_HOLD     = 20
HTF_LEN      = 50
WAIT_BARS    = 6
PB_ATR       = 0.4
SL_CAP_ATR   = 0.75
RR_MIN       = 1.5
LONG_ONLY    = True
START_YEAR   = 2018
END_YEAR     = 2025


class TradeAxisDOLv4(QCAlgorithm):

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
        self.hist = deque(maxlen=max(200, MAX_HOLD + HTF_LEN + 5))
        self.bi = 0
        self.tr_q = deque(maxlen=ATR_LEN)
        self.atr = None
        self.ema_htf = None; self.k_htf = 2.0 / (HTF_LEN + 1)
        self.levels = []
        self.cur_date = None
        self.day_h = None; self.day_l = None; self.day_c = None
        self.pdh = None; self.pdl = None; self.pdc = None
        self.trade = None
        self.pending = None  # {'side','dol_px','dol_kind','emerge_close','atr','emerge_bi','score','atr_dist'}

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

        if self.ema_htf is None:
            self.ema_htf = b['c']
        else:
            self.ema_htf = b['c'] * self.k_htf + self.ema_htf * (1 - self.k_htf)

        if self.atr is None or self.pdh is None:
            return

        # manage active trade
        if self.trade is not None:
            self._manage_trade(b)

        self._detect_levels(b)
        self._mark_swept(b)

        # try to activate pending setup
        if self.pending is not None and self.trade is None:
            self._try_pullback_entry(b)

        # create new pending setup if none
        if self.pending is None and self.trade is None:
            self._try_create_pending(b)

        if len(self.levels) > 300:
            self.levels = self.levels[-300:]

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

    def _try_create_pending(self, b):
        close_px = b['c']
        bsl = self._primary(above=True)
        ssl = self._primary(above=False)

        cand = None
        if bsl is not None and bsl['score'] >= MIN_SCORE:
            cand = ('LONG', bsl)
        if ssl is not None and ssl['score'] >= MIN_SCORE:
            if cand is None or ssl['score'] > cand[1]['score']:
                cand = ('SHORT', ssl)
        if cand is None:
            return
        side, lv = cand

        if LONG_ONLY and side != 'LONG':
            return

        # HTF bias filter
        if side == 'LONG' and close_px <= self.ema_htf:
            return
        if side == 'SHORT' and close_px >= self.ema_htf:
            return

        self.pending = {
            'side': side, 'dol_px': lv['px'], 'dol_kind': lv['kind'],
            'emerge_close': close_px, 'atr_at': self.atr,
            'emerge_bi': self.bi, 'score': lv['score'], 'atr_dist': lv['atr_dist'],
            'emerge_dt': b['t'].strftime('%Y-%m-%d %H:%M'),
        }

    def _try_pullback_entry(self, b):
        p = self.pending
        close_px = b['c']
        age = self.bi - p['emerge_bi']

        # cancel if waited too long
        if age > WAIT_BARS:
            self.pending = None
            return

        # cancel if DOL swept
        for lv in self.levels:
            if lv['px'] == p['dol_px'] and lv['kind'] == p['dol_kind'] and lv['swept']:
                self.pending = None
                return

        # cancel if score dropped
        if p['side'] == 'LONG':
            curr_bsl = self._primary(above=True)
            if curr_bsl is None or curr_bsl['px'] != p['dol_px']:
                # DOL changed — cancel, let new primary form a new setup next bar
                self.pending = None
                return
            if curr_bsl['score'] < CANCEL_SCORE:
                self.pending = None
                return
        else:
            curr_ssl = self._primary(above=False)
            if curr_ssl is None or curr_ssl['px'] != p['dol_px']:
                self.pending = None
                return
            if curr_ssl['score'] < CANCEL_SCORE:
                self.pending = None
                return

        # pullback check
        pb_dist = PB_ATR * p['atr_at']
        if p['side'] == 'LONG':
            if close_px > p['emerge_close'] - pb_dist:
                return  # not pulled back enough
            # entry: this bar's close is at least PB_ATR below emergence
            entry_px = close_px
            sl = min(b['l'] - 0.1 * p['atr_at'], entry_px - SL_CAP_ATR * p['atr_at'])
            if sl >= entry_px:
                return
            tp = p['dol_px']
            if tp <= entry_px:
                self.pending = None
                return
            rr = (tp - entry_px) / (entry_px - sl)
        else:
            if close_px < p['emerge_close'] + pb_dist:
                return
            entry_px = close_px
            sl = max(b['h'] + 0.1 * p['atr_at'], entry_px + SL_CAP_ATR * p['atr_at'])
            if sl <= entry_px:
                return
            tp = p['dol_px']
            if tp >= entry_px:
                self.pending = None
                return
            rr = (entry_px - tp) / (sl - entry_px)

        if rr < RR_MIN:
            self.pending = None
            return

        self.trade = {
            'side': p['side'], 'entry_px': entry_px, 'tp': tp, 'sl': sl,
            'entry_bi': self.bi, 'score': p['score'], 'atr_dist': p['atr_dist'],
            'date_time': b['t'].strftime('%Y-%m-%d %H:%M'),
            'bars_waited': age, 'rr': rr,
        }
        self.pending = None

    def _manage_trade(self, b):
        tr = self.trade
        age = self.bi - tr['entry_bi']
        half = ZONE_FRAC * self.atr
        if tr['side'] == 'LONG':
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
        self._emit(f"DOL4,{tr['date_time']},{tr['side']},"
                   f"{tr['entry_px']:.2f},{tr['sl']:.2f},{tr['tp']:.2f},"
                   f"{ex:.2f},{reason},{pnl:.2f},{age},{tr['bars_waited']},"
                   f"{tr['score']:.2f},{tr['atr_dist']:.2f},{tr['rr']:.2f}")
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
