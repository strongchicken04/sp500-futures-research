# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# EXIT VARIANTS (owner 2026-11-24: "yes, test those entries and exits") for the entry below, first signal a day:
#   LIT (5-candle target / 20-candle stop), R1 / R15 / R2 (20-candle stop, TP 1 / 1.5 / 2 x risk), T1 / T2 (stop
#   1 tick beyond the pullback extreme since the VWAP touch, TP 1 / 2 x risk), HOLD (20-candle stop, no TP, flat
#   15:55), NOSTOP (no stop / TP, flat 15:55); VWAP 18:00 ET and 09:30 ET; Lucid 25K eval with MNQ sized to $300
#   risk (floor(300 / (risk pt x 2 + 2.5)), 1..20; NOSTOP: 2 MNQ), last 6 years.
# --- entry: OR BREAK -> VWAP PULLBACK -> ADX NOT RISING, LONG + SHORT (owner 2026-11-24; MNQ 1-min chart). NQ minute
# 2010-2026 INSIDE QuantConnect, aggregates only. Rules (owner) + details FIXED BEFORE RESULTS (ET clock):
#   OR = 09:30-10:00. A 1-min close above the OR high -> long setup, below the OR low -> short setup (the latest
#   break defines the side; switching side resets the setup). Then price must TOUCH the VWAP (low <= VWAP for a
#   long, high >= VWAP for a short; the close may be beyond it). After the touch, the first 1-min candle that
#   closes back on our side of the VWAP with ADX(14) <= the previous candle's ADX -> signal; if the ADX rises,
#   keep waiting while closes stay on our side; a close beyond the VWAP just waits for the next close back.
#   Entry at the next minute's open; TP = high of the last 5 candles (long) / low of the last 5 (short), SL = low
#   of the last 20 (long) / high of the last 20 (short), set at the signal candle; skip if the entry is already
#   beyond the TP or the SL. Stop first if both in one minute; gaps at the open. Flat 15:55; signals until 15:50.
#   Variants: VWAP anchored at 18:00 ET (Globex session = TradingView default on CME futures) or 09:30 ET;
#   max trades a day 1 / 3 (a new trade needs a new VWAP touch); control NOADX = same without the ADX rule.
#   Costs: NQ 0.75 pt ($15) and MNQ 1.25 pt ($2.50) per round trip. Points re-scaled to today's NQ (28,530).
#   Stats: trades / yr, win (gross), gross pt / trade, net R (NQ / MNQ cost), $ per MNQ trade, t, long / short,
#   eras 2010-13 / 14-17 / 18-21 / 22-26, last 6 years.

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE = 28530.0
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))
RECENT = date(2020, 11, 24)
EXITS = ("LIT", "R1", "R15", "R2", "T1", "T2", "HOLD", "NOSTOP")
VARS = tuple((a, 1, True, ex) for a in ("ETH", "RTH") for ex in EXITS)


def era_of(y):
    for i, (a, b) in enumerate(ERAS):
        if a <= y <= b:
            return i
    return None


class ADX:
    def __init__(self, n):
        self.n = n
        self.ph = self.pl = self.pc = None
        self.tr = self.pdm = self.ndm = None
        self.adx = None
        self.prev = None
        self.k = 0

    def update(self, h, l, c):
        if self.pc is None:
            self.ph, self.pl, self.pc = h, l, c
            return
        tr = max(h - l, abs(h - self.pc), abs(l - self.pc))
        up, dn = h - self.ph, self.pl - l
        pdm = up if (up > dn and up > 0) else 0.0
        ndm = dn if (dn > up and dn > 0) else 0.0
        n = self.n
        if self.tr is None:
            self.tr, self.pdm, self.ndm = tr, pdm, ndm
        else:
            self.tr += (tr - self.tr) / n
            self.pdm += (pdm - self.pdm) / n
            self.ndm += (ndm - self.ndm) / n
        if self.tr > 0:
            pdi, ndi = 100 * self.pdm / self.tr, 100 * self.ndm / self.tr
            dx = 100 * abs(pdi - ndi) / (pdi + ndi) if pdi + ndi > 0 else 0.0
            self.prev = self.adx
            self.adx = dx if self.adx is None else self.adx + (dx - self.adx) / n
            self.k += 1
        self.ph, self.pl, self.pc = h, l, c

    def ready(self):
        return self.k > 3 * self.n



class V:
    def __init__(self, key):
        self.key = key
        self.reset_day()
        self.trades = []     # (gross_pts_scaled, risk_scaled, dir, year, date)

    def reset_day(self):
        self.side = 0
        self.touched = False
        self.pbx = None
        self.pending = None
        self.pos = None
        self.n = 0


class ORVwapADX(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.adx = ADX(14)
        self.hh = deque(maxlen=20)
        self.ll = deque(maxlen=20)
        self.vars = [V(k) for k in VARS]
        self.mapped = None
        self.day = None
        self.eth = [0.0, 0.0]
        self.eth_date = None
        self.rth = [0.0, 0.0]
        self.orh = self.orl = None
        self.bad = False

    def _book(self, v, px, t):
        p = v.pos
        sc = PRICE / p["e"]
        v.trades.append(((px - p["e"]) * p["d"] * sc, p["risk"] * sc, p["d"], t.year, t.date()))
        v.pos = None

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c, vol = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        prev_adx = self.adx.adx
        self.adx.update(h, l, c)
        cur_adx = self.adx.adx
        self.hh.append(h)
        self.ll.append(l)
        rolled = self.mapped is not None and self.f.mapped != self.mapped
        self.mapped = self.f.mapped
        # Globex session VWAP from 18:00 ET
        if m > 18 * 60 and self.eth_date != t.date():
            self.eth = [0.0, 0.0]
            self.eth_date = t.date()
        tp_ = (h + l + c) / 3.0
        self.eth[0] += tp_ * vol
        self.eth[1] += vol
        if not (9 * 60 + 30 < m <= 16 * 60):
            return
        if self.day != t.date():
            for v in self.vars:
                if v.pos is not None:
                    self._book(v, o, t)
                v.reset_day()
            self.day = t.date()
            self.rth = [0.0, 0.0]
            self.orh = self.orl = None
            self.bad = False
        if rolled:
            self.bad = True
            for v in self.vars:
                if v.pos is not None:
                    self._book(v, c, t)
                v.pending = None
        self.rth[0] += tp_ * vol
        self.rth[1] += vol
        if m <= 10 * 60:
            self.orh = h if self.orh is None else max(self.orh, h)
            self.orl = l if self.orl is None else min(self.orl, l)
        for v in self.vars:
            anchor, maxt, use_adx, ex = v.key
            # entry at this minute's open
            if v.pending is not None and v.pos is None:
                d, exx, t5, sl20, slpb = v.pending
                v.pending = None
                sl = slpb if exx in ("T1", "T2") else (None if exx == "NOSTOP" else sl20)
                ok = not self.bad and (sl is None or (o - sl) * d > 0)
                risk = (o - sl) * d if sl is not None else max(1.0, (o - sl20) * d)
                tp = None
                if exx == "LIT":
                    tp = t5
                    ok = ok and (tp - o) * d > 0
                elif exx in ("R1", "T1"):
                    tp = o + d * risk
                elif exx == "R15":
                    tp = o + d * 1.5 * risk
                elif exx in ("R2", "T2"):
                    tp = o + d * 2.0 * risk
                if ok:
                    v.pos = {"d": d, "e": o, "tp": tp, "sl": sl, "risk": risk}
                    v.n += 1
            p = v.pos
            if p is not None:
                if p["d"] == 1:
                    if p["sl"] is not None and l <= p["sl"]:
                        self._book(v, min(p["sl"], o), t)
                    elif p["tp"] is not None and h >= p["tp"]:
                        self._book(v, max(p["tp"], o), t)
                else:
                    if p["sl"] is not None and h >= p["sl"]:
                        self._book(v, max(p["sl"], o), t)
                    elif p["tp"] is not None and l <= p["tp"]:
                        self._book(v, min(p["tp"], o), t)
                if v.pos is not None and m >= 15 * 60 + 55:
                    self._book(v, c, t)
            if self.bad or m <= 10 * 60 or m > 15 * 60 + 50 or self.orh is None or v.pos is not None or v.pending is not None or v.n >= maxt:
                continue
            vw_ = self.eth if anchor == "ETH" else self.rth
            if vw_[1] <= 0:
                continue
            vwap = vw_[0] / vw_[1]
            if c > self.orh and v.side != 1:
                v.side, v.touched = 1, False
            elif c < self.orl and v.side != -1:
                v.side, v.touched = -1, False
            if v.side == 0:
                continue
            d = v.side
            if (d == 1 and l <= vwap) or (d == -1 and h >= vwap):
                if not v.touched:
                    v.pbx = l if d == 1 else h
                v.touched = True
            if not v.touched:
                continue
            v.pbx = min(v.pbx, l) if d == 1 else max(v.pbx, h)
            ours = (c > vwap) if d == 1 else (c < vwap)
            if not ours:
                continue
            if use_adx and (prev_adx is None or cur_adx is None or not self.adx.ready() or cur_adx > prev_adx):
                continue
            hs, ls = list(self.hh), list(self.ll)
            h5, l5, h20, l20 = max(hs[-5:]), min(ls[-5:]), max(hs), min(ls)
            sl20 = l20 if d == 1 else h20
            slpb = (v.pbx - 0.25) if d == 1 else (v.pbx + 0.25)
            v.pending = (d, ex, h5 if d == 1 else l5, sl20, slpb)
            v.touched = False

    def _eval(self, seq, s0, fixed):
        i, ev = s0, 1
        bal = peak = best = 0.0
        td = 0
        while i < len(seq) and i - s0 < 250:
            x = seq[i]
            i += 1
            if x is None:
                continue
            pts, risk = x
            n = fixed if fixed else max(1, min(20, int(300.0 / (risk * 2.0 + 2.5))))
            line = 100.0 if peak >= 1100.0 else peak - 1000.0
            run = bal + pts * 2.0 * n - 2.5 * n
            if run <= line:
                ev += 1
                bal = peak = best = 0.0
                td = 0
                continue
            td += 1
            best = max(best, run - bal)
            bal = run
            peak = max(peak, bal)
            if bal >= 1250.0 and best <= 0.5 * bal and td >= 2:
                return i - s0, ev, True
        return i - s0, ev, False

    def on_end_of_algorithm(self):
        cal_days = sorted(set(x[4] for v in self.vars for x in v.trades if x[4] >= RECENT))
        for v in self.vars:
            tr = v.trades
            n = len(tr)
            if n < 20:
                continue
            anchor, maxt, use_adx, ex = v.key
            yrs = max(1.0, len(set(x[3] for x in tr)))
            rn = [(x[0] - 0.75) / x[1] for x in tr if x[1] > 0]
            usd = [x[0] * 2.0 - 2.5 for x in tr]
            mu = sum(usd) / n
            sd = math.sqrt(sum((x - mu) ** 2 for x in usd) / (n - 1))
            lo = [x[0] * 2.0 - 2.5 for x in tr if x[2] == 1]
            sh = [x[0] * 2.0 - 2.5 for x in tr if x[2] == -1]
            era = " ".join(f"{sum(x[0] * 2.0 - 2.5 for x in tr if era_of(x[3]) == i) / max(1, sum(1 for x in tr if era_of(x[3]) == i)):+.1f}" for i in range(len(ERAS)))
            byd = {x[4]: (x[0], x[1]) for x in tr if x[4] >= RECENT}
            seq = [byd.get(d) for d in cal_days]
            res = [self._eval(seq, s0, 2 if ex == "NOSTOP" else 0) for s0 in range(0, max(1, len(seq) - 120))]
            okk = [r for r in res if r[2]]
            evs = f"{len(okk) / sum(r[1] for r in res) * 100:.0f}%/{sum(r[0] for r in okk) / len(okk):.0f}d" if okk else "0%"
            self.set_runtime_statistic(f"VX {anchor} {ex}",
                f"{n / yrs:.0f}/y win {sum(1 for x in tr if x[0] > 0) / n * 100:.0f}% gross {sum(x[0] for x in tr) / n:+.2f}pt R(NQ) {sum(rn) / max(1, len(rn)):+.3f} $/MNQ {mu:+.2f} t{mu / (sd / math.sqrt(n)):+.1f}"
                f" | L {sum(lo) / max(1, len(lo)):+.2f} S {sum(sh) / max(1, len(sh)):+.2f} | era {era} | eval25 {evs}")
