# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion

# GC (Gold futures) ribbon-SHIFT + FVG reversal test, 2018-2025.
#
# Setup ("A + exit-na-key-zone"):
#   1) Solidni prior trend: ribbon (EMA20/34/50 na 5min) stejnym smerem
#      alespon MIN_TREND_BARS 5m barov s min. separaci ATR_MULT * ATR14
#   2) SHIFT: regime flip na opacny smer se stejnym filtrem
#   3) Rejection (A): po SHIFTu bar vlezl do FVG v novem smeru
#      (bar high >= bearish_fvg.bot pro short; bar low <= bull_fvg.top pro long)
#      a ZAVREL MIMO ve smeru tradu (close <= fvg.bot / close >= fvg.top)
#   4) Valid target: existuje nevyplneny FVG dal ve smeru tradu s vyskou
#      >= MIN_TARGET_H a strednim bodem >= MIN_TARGET_DIST od entry
#   5) Entry: close bar po rejection
#   6) Exit: dotyk BLIZSI HRANY target FVG (target_top pro short, target_bot pro long)
#           NEBO opacny SHIFT NEBO time-cap MAX_HOLD_BARS
#
# FVG: 3-svickovy Fair Value Gap na 5min
#   bull: high[-3] < low[-1]  -> gap [high[-3], low[-1]]
#   bear: low[-3]  > high[-1] -> gap [high[-1], low[-3]]
#
# Emit per trade:
#   GRS,ts,dir,entry_px,exit_px,exit_reason,pnl,age_bars
#     dir = +1/-1
#     exit_reason: T (target), S (opposite SHIFT), M (max hold)
#     pnl in POINTS (1 GC point = $100), bez costs

EMA_F, EMA_M, EMA_S = 20, 34, 50
ATR_LEN = 14
ATR_MULT = 0.15            # loosened (was 0.20)
MIN_TREND_BARS = 20        # prior trend must be >= this bars
MIN_FVG_H = 1.0            # pts, gold has small FVGs on 5m
MIN_TARGET_H = 3.0
MIN_TARGET_DIST = 20.0     # pts from entry to target mid
MAX_WAIT_AFTER_SHIFT = 40
MAX_HOLD_BARS = 120
FVG_KEEP = 400
REJ_WAIT_BARS = 3          # after FVG touch, how many bars to look for close-outside

# SL configuration
SL_MODE = "swing"          # "fvg" | "atr" | "swing"
SL_ATR_BUFFER = 0.30       # ATR multiple added beyond FVG edge (mode "atr")
SL_SWING_LOOKBACK = 5      # bars back for swing high/low (mode "swing")


class GCRibbonShiftFVG(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Metals.Gold, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 180)
        self.future = f
        self.cont = f.Symbol
        self.n_tags = 0

        # 5m bar builder
        self.b5 = None
        self.b5_start = None

        # 5m rolling data
        self.closes = deque(maxlen=64)
        self.highs = deque(maxlen=64)
        self.lows = deque(maxlen=64)

        # EMAs (recursive)
        self.ef = None; self.em = None; self.es = None
        self.kf = 2.0 / (EMA_F + 1)
        self.km = 2.0 / (EMA_M + 1)
        self.ks = 2.0 / (EMA_S + 1)

        # ATR (Wilder-ish)
        self.atr = None
        self.tr_hist = deque(maxlen=ATR_LEN)
        self.prev_close = None

        # regime state
        self.regime = 0
        self.regime_age = 0
        # last DIRECTIONAL regime (+1 or -1) and its final age when it ended
        self.last_dir_regime = 0
        self.last_dir_age_final = 0
        self.bar_5m = 0
        self.pending_shift = None
        self.trade = None
        self.trades_taken = 0

        # FVGs: list of dict {top,bot,is_bull,born,filled,touched_at}
        self.fvgs = []

        # diagnostic counters
        self.cnt_shifts = 0
        self.cnt_shifts_valid_prior = 0
        self.cnt_rejections = 0
        self.cnt_valid_target = 0
        self.cnt_trades = 0
        self.cur_year = None

    # ---------- 5m bar builder ----------
    def _bucket_start(self, t):
        m = (t.minute // 5) * 5
        return t.replace(minute=m, second=0, microsecond=0)

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        bs = self._bucket_start(t)
        if self.b5_start != bs:
            if self.b5 is not None:
                self._on_5m(self.b5)
            self.b5 = {'o': bar.Open, 'h': bar.High, 'l': bar.Low, 'c': bar.Close, 't': bs}
            self.b5_start = bs
        else:
            self.b5['h'] = max(self.b5['h'], bar.High)
            self.b5['l'] = min(self.b5['l'], bar.Low)
            self.b5['c'] = bar.Close

    # ---------- indicators ----------
    def _update_emas(self, c):
        if self.ef is None:
            if len(self.closes) >= EMA_S:
                cs = list(self.closes)
                self.ef = sum(cs[-EMA_F:]) / EMA_F
                self.em = sum(cs[-EMA_M:]) / EMA_M
                self.es = sum(cs[-EMA_S:]) / EMA_S
        else:
            self.ef = c * self.kf + self.ef * (1 - self.kf)
            self.em = c * self.km + self.em * (1 - self.km)
            self.es = c * self.ks + self.es * (1 - self.ks)

    def _update_atr(self, h, l, c):
        if self.prev_close is None:
            self.prev_close = c
            return
        tr = max(h - l, abs(h - self.prev_close), abs(l - self.prev_close))
        self.prev_close = c
        self.tr_hist.append(tr)
        if self.atr is None:
            if len(self.tr_hist) == ATR_LEN:
                self.atr = sum(self.tr_hist) / ATR_LEN
        else:
            self.atr = (self.atr * (ATR_LEN - 1) + tr) / ATR_LEN

    # ---------- FVG mgmt ----------
    def _detect_fvg(self, hh, ll):
        # hh, ll are lists of highs/lows
        if len(hh) < 3:
            return
        # bull: high[-3] < low[-1]
        if hh[-3] < ll[-1]:
            gtop = ll[-1]; gbot = hh[-3]
            if (gtop - gbot) >= MIN_FVG_H:
                self.fvgs.append({'top': gtop, 'bot': gbot, 'is_bull': True,
                                  'born': self.bar_5m, 'filled': False, 'touched': None})
        # bear: low[-3] > high[-1]
        if ll[-3] > hh[-1]:
            gtop = ll[-3]; gbot = hh[-1]
            if (gtop - gbot) >= MIN_FVG_H:
                self.fvgs.append({'top': gtop, 'bot': gbot, 'is_bull': False,
                                  'born': self.bar_5m, 'filled': False, 'touched': None})

    def _mark_filled(self, h, l):
        for f in self.fvgs:
            if f['filled']:
                continue
            if f['is_bull']:
                if l <= f['bot']:
                    f['filled'] = True
            else:
                if h >= f['top']:
                    f['filled'] = True

    def _prune_fvgs(self):
        self.fvgs = [f for f in self.fvgs if (self.bar_5m - f['born']) <= FVG_KEEP]

    def _find_target(self, direction, entry_px):
        best = None; bd = 1e18
        for f in self.fvgs:
            if f['filled']:
                continue
            if (f['top'] - f['bot']) < MIN_TARGET_H:
                continue
            mid = (f['top'] + f['bot']) / 2.0
            if direction == -1:
                if mid >= entry_px - MIN_TARGET_DIST:
                    continue
                d = entry_px - mid
            else:
                if mid <= entry_px + MIN_TARGET_DIST:
                    continue
                d = mid - entry_px
            if d < bd:
                bd = d; best = f
        return best

    # ---------- 5m handler ----------
    def _on_5m(self, b):
        self.bar_5m += 1
        c = b['c']; h = b['h']; l = b['l']
        self.closes.append(c); self.highs.append(h); self.lows.append(l)

        self._update_emas(c)
        self._update_atr(h, l, c)

        if self.ef is None or self.atr is None:
            return

        # ---- regime ----
        sep_min = ATR_MULT * self.atr
        up = (self.ef > self.em) and (self.em > self.es) and ((self.ef - self.es) > sep_min)
        dn = (self.ef < self.em) and (self.em < self.es) and ((self.es - self.ef) > sep_min)
        new_r = 1 if up else (-1 if dn else 0)

        if new_r == self.regime:
            self.regime_age += 1
        else:
            # regime changed. If leaving a DIRECTIONAL regime, remember it.
            if self.regime != 0:
                self.last_dir_regime = self.regime
                self.last_dir_age_final = self.regime_age
            # entering a directional regime opposite to last one -> SHIFT
            if new_r != 0 and self.last_dir_regime != 0 and new_r != self.last_dir_regime:
                self.cnt_shifts += 1
                if self.last_dir_age_final >= MIN_TREND_BARS:
                    self.cnt_shifts_valid_prior += 1
                    self.pending_shift = {'dir': new_r, 'bars_since': 0, 'shift_bar': self.bar_5m}
                # any SHIFT-worthy transition consumes the "last dir" so we
                # don't fire again on transient neutral flickers
                self.last_dir_regime = new_r
                self.last_dir_age_final = 0
            self.regime = new_r
            self.regime_age = 1

        # ---- FVG detection & maintenance ----
        self._detect_fvg(list(self.highs), list(self.lows))
        self._mark_filled(h, l)
        self._prune_fvgs()

        # ---- active trade exit ----
        if self.trade is not None:
            tr = self.trade
            age = self.bar_5m - tr['entry_bar']
            done = False; ex_px = None; reason = None
            # SL first (conservative same-bar priority)
            if tr['dir'] == -1:
                if h >= tr['sl']:
                    done = True; ex_px = tr['sl']; reason = 'L'
            else:
                if l <= tr['sl']:
                    done = True; ex_px = tr['sl']; reason = 'L'
            # Target
            if not done:
                if tr['dir'] == -1:
                    if l <= tr['target_top']:
                        done = True; ex_px = tr['target_top']; reason = 'T'
                else:
                    if h >= tr['target_bot']:
                        done = True; ex_px = tr['target_bot']; reason = 'T'
            if not done and new_r != 0 and new_r == -tr['dir']:
                done = True; ex_px = c; reason = 'S'
            if not done and age >= MAX_HOLD_BARS:
                done = True; ex_px = c; reason = 'M'
            if done:
                pnl = tr['dir'] * (ex_px - tr['entry_px'])
                self._emit(f"GRS,{b['t'].strftime('%Y-%m-%d %H:%M')},{tr['dir']},{tr['entry_px']:.2f},{ex_px:.2f},{reason},{pnl:.2f},{age}")
                self.trade = None

        # ---- look for entry ----
        if self.trade is None and self.pending_shift is not None:
            self.pending_shift['bars_since'] += 1
            if self.pending_shift['bars_since'] > MAX_WAIT_AFTER_SHIFT:
                self.pending_shift = None
            else:
                d = self.pending_shift['dir']
                shift_bar = self.pending_shift['shift_bar']
                cand = None
                # 1) update touched state for direction-appropriate FVGs
                for f in self.fvgs:
                    if f['filled']:
                        continue
                    if f['born'] < shift_bar - 3:
                        continue
                    if d == -1 and not f['is_bull']:
                        if f.get('touched') is None and h >= f['bot']:
                            f['touched'] = self.bar_5m
                    elif d == 1 and f['is_bull']:
                        if f.get('touched') is None and l <= f['top']:
                            f['touched'] = self.bar_5m
                # 2) check rejection = close outside FVG in trade direction, within REJ_WAIT_BARS of touch
                for f in self.fvgs:
                    if f['filled'] or f.get('touched') is None:
                        continue
                    if (self.bar_5m - f['touched']) > REJ_WAIT_BARS:
                        continue
                    if d == -1 and not f['is_bull'] and c <= f['bot']:
                        cand = f; break
                    if d == 1 and f['is_bull'] and c >= f['top']:
                        cand = f; break
                if cand is not None:
                    self.cnt_rejections += 1
                    tgt = self._find_target(d, c)
                    if tgt is not None:
                        self.cnt_valid_target += 1
                        # SL depending on mode
                        if SL_MODE == "fvg":
                            sl = cand['top'] if d == -1 else cand['bot']
                        elif SL_MODE == "atr":
                            base = cand['top'] if d == -1 else cand['bot']
                            buf = SL_ATR_BUFFER * self.atr
                            sl = base + buf if d == -1 else base - buf
                        elif SL_MODE == "swing":
                            k = SL_SWING_LOOKBACK
                            hh = list(self.highs)[-k:] if len(self.highs) >= k else list(self.highs)
                            ll = list(self.lows)[-k:] if len(self.lows) >= k else list(self.lows)
                            sl = max(hh) if d == -1 else min(ll)
                        else:
                            sl = cand['top'] if d == -1 else cand['bot']
                        self.trade = {'dir': d, 'entry_px': c, 'entry_bar': self.bar_5m,
                                      'target_top': tgt['top'], 'target_bot': tgt['bot'],
                                      'sl': sl, 'entry_ts': b['t']}
                        self.trades_taken += 1
                        self.cnt_trades += 1
                        cand['filled'] = True
                        self.pending_shift = None

        # ---- yearly diagnostic summary ----
        yr = b['t'].year
        if self.cur_year is None:
            self.cur_year = yr
        elif yr != self.cur_year:
            self._emit(f"DIAG,{self.cur_year},shifts,{self.cnt_shifts},priorOK,{self.cnt_shifts_valid_prior},"
                       f"rejections,{self.cnt_rejections},validTgt,{self.cnt_valid_target},trades,{self.cnt_trades}")
            self.cur_year = yr

    # ---------- tag exfil ----------
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
        self._emit(f"DIAG,{self.cur_year},shifts,{self.cnt_shifts},priorOK,{self.cnt_shifts_valid_prior},"
                   f"rejections,{self.cnt_rejections},validTgt,{self.cnt_valid_target},trades,{self.cnt_trades}")
        self.Log(f"TRADES={self.trades_taken}  TAGS={self.n_tags}")
