# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# MULTI-ACCOUNT OPERATION (owner 2026-11-14: "pass evals, then copy-trade e.g. 3 funded accounts - simulate
# it"). Lucid caps (third-party sources): 5 funded, 10 accounts total. Each SLOT runs the chain eval (Vault
# 6 MNQ, $60) -> funded (ORB n MNQ, payout only the full $1,000, rules as funded_plans_inqc.py) -> breach ->
# new eval next day. Plans FIXED BEFORE RESULTS:
#   ONE     1 slot (reference)
#   ALL5    5 copy-traded accounts = one slot x 5 (identical trades -> identical fate)
#   STAG21  5 independent slots started 0 / 21 / 42 / 63 / 84 trading days apart, then each restarts on its
#           own after a breach (same signals, different balances)
#   STAG10  the same 10 trading days apart
#   with ORB 1 MNQ and ORB 2 MNQ on the funded accounts.
# Cash flow = payouts kept (90%) - eval fees. Global starts every 20 trading days of the last 6 years,
# months = 21 trading-day blocks from the start (the start-up months included). Output: net $ / yr,
# monthly median / share of months below 0 / share with a payout, worst 3-month sum (mean of the worst
# per start, and the worst of all), longest run of months without a payout, days a year with >= 3 accounts
# breached the same day.
#
# (base: LUCID 25K CAREER CHAIN, owner 2026-11-14: "Vault Break blows the funded account on every losing trade -
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



class MultiAccount(QCAlgorithm):

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

    # ------------------------------------------------------------------ slot sim
    def _u(self, day, kind, n):
        for tm, k, pts, stop in day:
            if k == kind:
                return pts * 2.0 * n - 2.5 * n
        return None

    def _run(self, seq, g0, offsets, mult, on):
        L = len(seq) - g0
        cash = [0.0] * L
        pays = [0] * L
        breaches = [0] * L
        slots = [{"st": "W", "start": o} for o in offsets]
        for t in range(L):
            day = seq[g0 + t]
            for sl in slots:
                if sl["st"] == "W":
                    if t < sl["start"]:
                        continue
                    sl.update(st="E", bal=0.0, peak=0.0, best=0.0, td=0)
                    cash[t] -= 60.0 * mult
                if sl["st"] == "E":
                    u = self._u(day, "V", 6)
                    if u is None:
                        continue
                    line = 100.0 if sl["peak"] >= 1100.0 else sl["peak"] - 1000.0
                    run = sl["bal"] + u
                    if run <= line:
                        sl.update(st="E", bal=0.0, peak=0.0, best=0.0, td=0)
                        cash[t] -= 60.0 * mult
                        continue
                    sl["td"] += 1
                    sl["best"] = max(sl["best"], u)
                    sl["bal"] = run
                    sl["peak"] = max(sl["peak"], run)
                    if run >= 1250.0 and sl["best"] <= 0.5 * run and sl["td"] >= 2:
                        sl.update(st="F", bal=0.0, peak=0.0, locked=False, wd=0)
                    continue
                # funded
                line = 100.0 if sl["locked"] else sl["peak"] - 1000.0
                u = self._u(day, "O", on)
                run = sl["bal"] + (u or 0.0)
                if run <= line:
                    breaches[t] += mult
                    sl.update(st="E", bal=0.0, peak=0.0, best=0.0, td=0)
                    cash[t] -= 60.0 * mult      # new eval bought right away (trades from the next day)
                    continue
                if run - sl["bal"] >= 100.0:
                    sl["wd"] += 1
                sl["bal"] = run
                sl["peak"] = max(sl["peak"], run)
                if sl["peak"] >= 1100.0:
                    sl["locked"] = True
                amt = min(0.5 * run, 1000.0)
                if sl["wd"] >= 5 and amt >= 1000.0:
                    sl["bal"] -= amt
                    cash[t] += 0.9 * amt * mult
                    pays[t] += mult
                    sl["wd"] = 0
                    sl["locked"] = True
        return cash, pays, breaches

    def on_end_of_algorithm(self):
        cal = sorted(set(self.cal))
        seq = [self.days.get(d, []) for d in cal]
        plans = {"ONE": ([0], 1), "ALL5": ([0], 5), "STAG21": ([0, 21, 42, 63, 84], 1), "STAG10": ([0, 10, 20, 30, 40], 1)}
        starts = list(range(0, max(1, len(seq) - 252), 20))
        for on in (1, 2):
            for name, (offs, mult) in plans.items():
                yr, med, neg, withp, w3, w3min, dry, b3 = [], [], [], [], [], [], [], []
                for g0 in starts:
                    cash, pays, br = self._run(seq, g0, offs, mult, on)
                    L = len(cash)
                    months = [(sum(cash[i:i + 21]), sum(pays[i:i + 21])) for i in range(0, L - 20, 21)]
                    if len(months) < 4:
                        continue
                    yr.append(sum(cash) / (L / 252.0))
                    mv = sorted(x[0] for x in months)
                    med.append(mv[len(mv) // 2])
                    neg.append(sum(1 for x in months if x[0] < 0) / len(months))
                    withp.append(sum(1 for x in months if x[1] > 0) / len(months))
                    s3 = [sum(months[j][0] for j in range(i, i + 3)) for i in range(len(months) - 2)]
                    w3.append(min(s3))
                    run_ = best_ = 0
                    for x in months:
                        run_ = run_ + 1 if x[1] == 0 else 0
                        best_ = max(best_, run_)
                    dry.append(best_)
                    b3.append(sum(1 for x in br if x >= 3) / (L / 252.0))
                k = len(yr)
                self.set_runtime_statistic(f"MA O{on} {name}",
                    f"net ${sum(yr) / k:+,.0f}/y | month median ${sum(med) / k:+,.0f} below0 {sum(neg) / k * 100:.0f}% payout {sum(withp) / k * 100:.0f}%"
                    f" | worst 3m ${sum(w3) / k:+,.0f} (min ${min(w3):+,.0f}) | dry {sum(dry) / k:.1f}m (max {max(dry)}) | >=3 breach {sum(b3) / k:.1f}/y")
        self.set_runtime_statistic("MA info", f"{cal[0]}..{cal[-1]} {len(cal)} days, starts {len(starts)}")
