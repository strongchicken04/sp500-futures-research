# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# LUCID 25K CAREER CHAIN (owner 2026-11-14: "Vault Break blows the funded account on every losing trade -
# 20 days and a lot of money lost"). One continuous chain over the last 6 years: buy an eval ($60) -> pass
# with strategy E -> trade the funded account with strategy F until it breaches -> buy a new eval the next
# day. Net $ per year = payouts kept (90%) - eval fees. INSIDE QuantConnect, aggregates only.
# Signals (fixed, as tested before), both re-scaled to today's NQ (28,530) like the PCT runs:
#   VAULT  midnight CT + 0.30 x ATR15, VWAP from midnight CT, first 30-min close above both from the
#          candle opening 10:00 CT, long, TP 40 / SL 75 pt (0.140% / 0.263%), flat 14:30 CT, 1 a day.
#   ORB    overnight bias ORB v3, SL = 30% of SMA15 of daily ATR(14), TP 3x, flat 14:30 CT, 1 a day.
#   Same-day trades are applied in exit-time order (closed-trade breach check).
# Eval: +$1,250, DD $1,000 EOD trailing locking +$100 at $1,100, best day <= 50%, >= 2 days, fee $60.
# Funded: DD as eval, locked at +$100 after the first payout; payout = min(50% of balance, $1,000) when
#   5 days >= $100 since the last payout and >= $500 is available; 90% kept; no activation fee assumed.
# MNQ $2/pt, $2.50 per round trip. Chains start every 20 trading days of the window and run to its end.
# E: V6 / O1 / OR350 (ORB sized floor(350 / stop $ per MNQ)). F: V3 V4 V6 O1 O2 OR350 V3+O1 V4+O1 V6+O1.

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE = 28530.0
WIN0 = date(2020, 8, 10)


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



class WATR:
    def __init__(self, n):
        self.n = n
        self.pc = None
        self.v = None
        self.k = 0

    def update(self, h, l, c):
        tr = h - l if self.pc is None else max(h - l, abs(h - self.pc), abs(l - self.pc))
        self.v = tr if self.v is None else self.v + (tr - self.v) / self.n
        self.pc = c
        self.k += 1



class Chain(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.days = {}                     # date -> list of (exit minute, kind, pts_scaled, stop_scaled)
        self.cal = []
        self.mapped = None
        # ORB state
        self.adx15 = ADX(14)
        self.datr = WATR(14)
        self.datr_hist = deque(maxlen=15)
        self.sess = None
        self.b15 = None
        self.odate = None
        self.o_pend = None
        self.o_pos = None
        self.o_done = False
        # VAULT state
        self.vdate = None
        self.ranges = []
        self.mid = self.hi = self.lo = None
        self.pv = self.vv = 0.0
        self.c30 = None
        self.v_pos = None
        self.v_done = False
        self._o_new()

    def _o_new(self):
        self.onh = self.onl = None
        self.or15 = None
        self.ropen = None

    def _rec(self, t, kind, pos, px):
        sc = PRICE / pos["e"]
        pts = (px - pos["e"]) * pos["d"] * sc
        self.days.setdefault(t.date(), []).append((t.hour * 60 + t.minute, kind, pts, pos["risk"] * sc))

    def _manage(self, pos, o, h, l, c, m):
        if pos["d"] == 1:
            if l <= pos["sl"]:
                return min(pos["sl"], o)
            if h >= pos["tp"]:
                return max(pos["tp"], o)
        else:
            if h >= pos["sl"]:
                return max(pos["sl"], o)
            if l <= pos["tp"]:
                return min(pos["tp"], o)
        if m >= 15 * 60 + 30:
            return c
        return None

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        rolled = self.mapped is not None and self.f.mapped != self.mapped
        self.mapped = self.f.mapped
        if rolled:
            if self.o_pos is not None:
                self._rec(t, "O", self.o_pos, c)
                self.o_pos = None
            if self.v_pos is not None:
                self._rec(t, "V", self.v_pos, c)
                self.v_pos = None
            self.o_pend = None
            self.o_done = self.v_done = True
        # ---------------- daily ATR on Globex sessions
        if m > 18 * 60 or m <= 17 * 60:
            if m > 18 * 60 and self.sess is not None and self.sess[3] != t.date():
                self.datr.update(self.sess[0], self.sess[1], self.sess[2])
                if self.datr.k >= 14:
                    self.datr_hist.append(self.datr.v)
                self.sess = None
            self.sess = [h, l, c, t.date()] if self.sess is None else [max(self.sess[0], h), min(self.sess[1], l), c, self.sess[3]]
        b = self.b15
        self.b15 = [o, h, l, c] if b is None else [b[0], max(b[1], h), min(b[2], l), c]
        close15 = (m % 15 == 0)
        if close15:
            bb = self.b15
            self.adx15.update(bb[1], bb[2], bb[3])
            self.b15 = None
        # ---------------- ORB (day from 00:00 ET = 23:00 CT)
        if 0 < m <= 17 * 60 and self.odate != t.date():
            self.odate = t.date()
            self._o_new()
            self.o_pend = None
            self.o_done = False
        if self.odate == t.date() and 0 < m <= 17 * 60:
            if m <= 9 * 60 + 30:
                self.onh = h if self.onh is None else max(self.onh, h)
                self.onl = l if self.onl is None else min(self.onl, l)
            if 9 * 60 + 30 < m <= 16 * 60:
                if self.ropen is None:
                    self.ropen = o
                    if t.date() >= WIN0:
                        self.cal.append(t.date())
                if m <= 9 * 60 + 45:
                    self.or15 = [h, l] if self.or15 is None else [max(self.or15[0], h), min(self.or15[1], l)]
            if self.o_pend is not None and self.o_pos is None:
                d, sld = self.o_pend
                self.o_pend = None
                self.o_pos = {"d": d, "e": o, "sl": o - d * sld, "tp": o + d * 3 * sld, "risk": sld}
            if self.o_pos is not None:
                px = self._manage(self.o_pos, o, h, l, c, m)
                if px is not None:
                    self._rec(t, "O", self.o_pos, px)
                    self.o_pos = None
            if (not self.o_done and self.o_pos is None and close15 and 9 * 60 + 45 < m <= 15 * 60 + 15
                    and self.or15 is not None and self.ropen is not None and self.onh is not None and len(self.datr_hist) == 15):
                hi, lo = self.onh, self.onl
                q = (self.ropen - lo) / (hi - lo) if hi > lo else 0.5
                bias = 1 if q >= 2 / 3 else (-1 if q <= 1 / 3 else 0)
                if bias == 0:
                    self.o_done = True
                elif self.adx15.ready() and self.adx15.adx >= 20:
                    d = 1 if (bias == 1 and c > self.or15[0]) else (-1 if (bias == -1 and c < self.or15[1]) else 0)
                    if d != 0:
                        self.o_pend = (d, 0.30 * sum(self.datr_hist) / 15.0)
                        self.o_done = True
        # ---------------- VAULT (day from 01:00 ET = midnight CT)
        if 60 < m <= 18 * 60 and self.vdate != t.date():
            if self.vdate is not None and self.hi is not None:
                self.ranges.append(self.hi - self.lo)
                if len(self.ranges) > 15:
                    self.ranges.pop(0)
            self.vdate = t.date()
            self.mid, self.hi, self.lo = o, h, l
            self.pv = self.vv = 0.0
            self.c30 = None
            self.v_done = False
        if self.vdate == t.date() and 60 < m <= 18 * 60:
            self.hi, self.lo = max(self.hi, h), min(self.lo, l)
            self.pv += (h + l + c) / 3.0 * v
            self.vv += v
            vwap = self.pv / self.vv if self.vv > 0 else c
            if self.v_pos is not None:
                px = self._manage(self.v_pos, o, h, l, c, m)
                if px is not None:
                    self._rec(t, "V", self.v_pos, px)
                    self.v_pos = None
            a = self.c30
            self.c30 = [o, h, l, c] if a is None else [a[0], max(a[1], h), min(a[2], l), c]
            if m % 30 == 0:
                cc = self.c30[3]
                self.c30 = None
                if (not self.v_done and self.v_pos is None and len(self.ranges) == 15 and 11 * 60 + 30 <= m <= 15 * 60
                        and cc > self.mid + 0.30 * sum(self.ranges) / 15.0 and cc > vwap):
                    tpd, sld = cc * 40.0 / PRICE, cc * 75.0 / PRICE
                    self.v_pos = {"d": 1, "e": cc, "tp": cc + tpd, "sl": cc - sld, "risk": sld}
                    self.v_done = True

    # ------------------------------------------------------------------ chain sim
    def _size(self, spec, kind, stop):
        # spec like {"V": 6, "O": 1} or {"O": "R350"}
        n = spec.get(kind)
        if n is None:
            return 0
        if isinstance(n, str):
            n = int(float(n[1:]) / (stop * 2.0 + 2.5))
        return max(1, min(20, n))

    def _day_pnl_path(self, trades, spec):
        path = []
        for tm, kind, pts, stop in sorted(trades):
            n = self._size(spec, kind, stop)
            if n:
                path.append(pts * 2.0 * n - 2.5 * n)
        return path

    def _chain(self, seq, s0, E, F):
        i = s0
        fees = paid = 0.0
        evals = funded = npay = 0
        life = []
        mode = "E"
        fees += 60.0
        evals += 1
        bal = peak = best = 0.0
        td = wd = 0
        locked = False
        fstart = 0
        while i < len(seq):
            day = seq[i]
            i += 1
            spec = E if mode == "E" else F
            line = 100.0 if (locked or peak >= 1100.0) else peak - 1000.0
            run = bal
            dead = False
            traded = False
            for u in self._day_pnl_path(day, spec):
                traded = True
                run += u
                if run <= line:
                    dead = True
                    break
            if dead:
                if mode == "F":
                    life.append(i - fstart)
                mode = "E"
                fees += 60.0
                evals += 1
                bal = peak = best = 0.0
                td = wd = 0
                locked = False
                continue
            dp = run - bal
            bal = run
            peak = max(peak, bal)
            if mode == "E":
                if traded:
                    td += 1
                best = max(best, dp)
                if bal >= 1250.0 and best <= 0.5 * bal and td >= 2:
                    mode = "F"
                    funded += 1
                    fstart = i
                    bal = peak = 0.0
                    wd = 0
                    locked = False
            else:
                if dp >= 100.0:
                    wd += 1
                if peak >= 1100.0:
                    locked = True
                amt = min(0.5 * bal, 1000.0)
                if wd >= 5 and amt >= 500.0:
                    bal -= amt
                    paid += 0.9 * amt
                    npay += 1
                    wd = 0
                    locked = True
        yrs = (len(seq) - s0) / 252.0
        return (paid - fees) / yrs, npay / yrs, evals / yrs, funded / yrs, (sum(life) / len(life) if life else 0.0)

    def on_end_of_algorithm(self):
        cal = sorted(set(self.cal))
        seq = [self.days.get(d, []) for d in cal]
        nv = sum(1 for d in seq for x in d if x[1] == "V")
        no = sum(1 for d in seq for x in d if x[1] == "O")
        self.set_runtime_statistic("CH info", f"{cal[0]}..{cal[-1]} {len(cal)} days, vault {nv} orb {no} trades")
        Es = {"V6": {"V": 6}, "O1": {"O": 1}, "OR350": {"O": "R350"}}
        Fs = {"V3": {"V": 3}, "V4": {"V": 4}, "V6": {"V": 6}, "O1": {"O": 1}, "O2": {"O": 2}, "OR350": {"O": "R350"},
              "V3+O1": {"V": 3, "O": 1}, "V4+O1": {"V": 4, "O": 1}, "V6+O1": {"V": 6, "O": 1}}
        starts = range(0, max(1, len(seq) - 252), 20)
        for en, E in Es.items():
            for fn, F in Fs.items():
                res = [self._chain(seq, s0, E, F) for s0 in starts]
                k = len(res)
                self.set_runtime_statistic(f"CH E {en} F {fn}",
                    f"net ${sum(r[0] for r in res) / k:+,.0f}/y | payouts {sum(r[1] for r in res) / k:.1f}/y | evals {sum(r[2] for r in res) / k:.1f}/y"
                    f" | funded {sum(r[3] for r in res) / k:.1f}/y | funded life {sum(r[4] for r in res) / k:.0f} d")
