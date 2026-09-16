# region imports
from AlgorithmImports import *
from collections import deque, defaultdict
# endregion

# GC "4 positive-delta bars + VA retest long" test.
# 2018-2025. Timeframe from parameter (1/3/5 min).
#
# Setup:
#   - 4 consecutive bars with close > open (bullish body = positive delta proxy)
#   - Compute volume profile of those 4 bars ($0.5 bin size)
#   - Extract VAH, POC, VAL via 68% expansion around POC
#   - Zone = [VAL, POC]
#
# Entry:
#   - After cluster completes, wait up to MAX_WAIT bars for retest
#   - Retest bar: bar low <= POC (entered zone from above)
#   - Confirmation: bar close >= VAL (did NOT close below zone)
#   - Long at entry_bar close
#
# Exit tracked as MFE/MAE for post-hoc TP variant analysis:
#   - Track max high & min low reached over the trade
#   - SL hit if low <= VAL_at_entry
#   - Exit when: SL hit, or opposite bearish "4 in a row", or MAX_HOLD reached
#   - Also emit per-bar MFE-vs-VA-width so we can compute win rates for
#     any TP = k * VA_width or absolute pts
#
# Emit per trade:
#   G4D,tf,date_time,entry_px,val,poc,vah,exit_px,exit_reason,pnl,mfe,mae,bars_held
#     exit_reason: L (SL hit) | O (opposite pattern) | M (max hold)

TF_MIN = 5              # timeframe in minutes (change for 1/3)
SETUP_MODE = "SHORT_BREAK"  # "LONG_HOLD" (original) | "SHORT_BREAK" (inverted)
BIN_SIZE = 0.5          # $ bin for VP
VA_PCT = 0.68
MIN_VA_WIDTH = 1.0      # min VAH-VAL to accept setup (pts)
MAX_WAIT = 20           # bars to wait for retest after cluster
MAX_HOLD = 60           # bar cap after entry


class GC4PosVARetest(QCAlgorithm):

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
        # tf bar builder
        self.bar_o = None
        self.bar_h = None
        self.bar_l = None
        self.bar_c = None
        self.bar_v = 0.0
        self.bar_start = None
        # rolling last 4 completed TF bars
        self.hist = deque(maxlen=4)  # each: dict {o,h,l,c,v}
        # pending setup after cluster
        self.pending = None  # {'val','poc','vah','bars_waited'}
        # active trade
        self.trade = None    # {'entry_px','val','poc','vah','entry_bar','mfe','mae','bars'}
        self.bar_count = 0
        self.total_setups = 0

    # ---------- TF bar builder ----------
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
                self._on_tf_bar({
                    'o': self.bar_o, 'h': self.bar_h, 'l': self.bar_l,
                    'c': self.bar_c, 'v': self.bar_v, 't': self.bar_start})
            self.bar_o = bar.Open
            self.bar_h = bar.High
            self.bar_l = bar.Low
            self.bar_c = bar.Close
            self.bar_v = bar.Volume
            self.bar_start = bs
        else:
            self.bar_h = max(self.bar_h, bar.High)
            self.bar_l = min(self.bar_l, bar.Low)
            self.bar_c = bar.Close
            self.bar_v += bar.Volume

    # ---------- VA computation ----------
    def _compute_va(self, bars):
        bins = defaultdict(float)
        for b in bars:
            rng = b['h'] - b['l']
            if rng <= 0 or b['v'] <= 0:
                key = int(b['c'] / BIN_SIZE)
                bins[key] += max(b['v'], 1.0)
                continue
            n_bins = max(1, int(rng / BIN_SIZE))
            vpb = b['v'] / n_bins
            for i in range(n_bins):
                price = b['l'] + (i + 0.5) * BIN_SIZE
                key = int(price / BIN_SIZE)
                bins[key] += vpb
        if not bins:
            return None
        poc_key = max(bins.keys(), key=lambda k: bins[k])
        total = sum(bins.values())
        target = VA_PCT * total
        lo, hi = poc_key, poc_key
        acc = bins[poc_key]
        while acc < target:
            has_up = (hi + 1) in bins
            has_dn = (lo - 1) in bins
            if not has_up and not has_dn:
                break
            up = bins.get(hi + 1, 0.0)
            dn = bins.get(lo - 1, 0.0)
            if (has_up and not has_dn) or (has_up and has_dn and up >= dn):
                hi += 1; acc += up
            else:
                lo -= 1; acc += dn
        vah = (hi + 1) * BIN_SIZE
        val = lo * BIN_SIZE
        poc = (poc_key + 0.5) * BIN_SIZE
        return (val, poc, vah)

    # ---------- TF bar handler ----------
    def _on_tf_bar(self, b):
        self.bar_count += 1
        self.hist.append(b)

        # ---- active trade management ----
        if self.trade is not None:
            tr = self.trade
            tr['bars'] += 1
            # MFE = in favor, MAE = adverse. Track relative to direction.
            if tr['dir'] == 1:
                tr['mfe'] = max(tr['mfe'], b['h'] - tr['entry_px'])
                tr['mae'] = min(tr['mae'], b['l'] - tr['entry_px'])
            else:
                tr['mfe'] = max(tr['mfe'], tr['entry_px'] - b['l'])
                tr['mae'] = min(tr['mae'], tr['entry_px'] - b['h'])
            done = False; ex_px = None; reason = None
            # SL check (SL_px is always the opposite VA edge)
            if tr['dir'] == 1 and b['l'] <= tr['sl_px']:
                done, ex_px, reason = True, tr['sl_px'], 'L'
            elif tr['dir'] == -1 and b['h'] >= tr['sl_px']:
                done, ex_px, reason = True, tr['sl_px'], 'L'
            # opposite pattern (4 opposite bars in a row) — quick invalidation
            if not done and len(self.hist) == 4:
                if tr['dir'] == 1 and all(x['c'] < x['o'] for x in self.hist):
                    done, ex_px, reason = True, b['c'], 'O'
                elif tr['dir'] == -1 and all(x['c'] > x['o'] for x in self.hist):
                    done, ex_px, reason = True, b['c'], 'O'
            # max hold
            if not done and tr['bars'] >= MAX_HOLD:
                done, ex_px, reason = True, b['c'], 'M'
            if done:
                pnl = tr['dir'] * (ex_px - tr['entry_px'])
                self._emit(f"G4D,{TF_MIN},{tr['dir']},{b['t'].strftime('%Y-%m-%d %H:%M')},"
                           f"{tr['entry_px']:.2f},{tr['val']:.2f},{tr['poc']:.2f},{tr['vah']:.2f},"
                           f"{ex_px:.2f},{reason},{pnl:.2f},{tr['mfe']:.2f},{tr['mae']:.2f},{tr['bars']}")
                self.trade = None

        # ---- pending setup: waiting for retest ----
        if self.trade is None and self.pending is not None:
            self.pending['bars_waited'] += 1
            if self.pending['bars_waited'] > MAX_WAIT:
                self.pending = None
            else:
                low = b['l']; close = b['c']
                val = self.pending['val']; poc = self.pending['poc']; vah = self.pending['vah']
                if low <= poc:  # retest of zone
                    if SETUP_MODE == "LONG_HOLD" and close >= val:
                        # LONG entry: SL = VAL
                        self.trade = {'dir': 1, 'entry_px': close, 'val': val, 'poc': poc, 'vah': vah,
                                      'sl_px': val, 'entry_bar': self.bar_count,
                                      'mfe': 0.0, 'mae': 0.0, 'bars': 0}
                        self.pending = None
                    elif SETUP_MODE == "SHORT_BREAK" and close < val:
                        # SHORT entry: SL = POC (top of zone)
                        self.trade = {'dir': -1, 'entry_px': close, 'val': val, 'poc': poc, 'vah': vah,
                                      'sl_px': poc, 'entry_bar': self.bar_count,
                                      'mfe': 0.0, 'mae': 0.0, 'bars': 0}
                        self.pending = None
                    elif SETUP_MODE == "LONG_HOLD" and close < val:
                        # LONG failed — cancel setup
                        self.pending = None
                    elif SETUP_MODE == "SHORT_BREAK" and close >= val:
                        # keep waiting for the break — no cancel
                        pass

        # ---- new setup detection: 4 bullish in a row ----
        if len(self.hist) == 4 and self.trade is None and self.pending is None:
            if all(x['c'] > x['o'] for x in self.hist):
                va = self._compute_va(list(self.hist))
                if va is not None:
                    val, poc, vah = va
                    if (vah - val) >= MIN_VA_WIDTH:
                        self.pending = {'val': val, 'poc': poc, 'vah': vah, 'bars_waited': 0}
                        self.total_setups += 1

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
        self._emit(f"G4D_STATS,{TF_MIN},setups,{self.total_setups},tags,{self.n_tags}")
        self.Log(f"setups={self.total_setups} tags={self.n_tags}")
