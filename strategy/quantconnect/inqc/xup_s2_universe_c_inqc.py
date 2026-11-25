# region imports
from AlgorithmImports import *
from datetime import date as _date
from collections import deque
import hashlib
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 2 VALIDATION 1c (owner 2026-11-24). Aggregates + ticker examples only.
# Validation 1b showed two problems with the fundamental-based filters:
#   (a) is_primary_share = False for ordinary single-class US stocks (ACM, ACI, ACXM, ADS ...), not only for
#       secondary classes (BRK.B, GOOG) and foreign cross-listings / ADRs
#   (b) securities with <= 4-letter tickers and NO fundamentals include common stocks (AA 2010, ARNC 2018,
#       HWM 2024, AXAS, ABK), not only ETFs / ETNs / CEFs, and carry as many +100%/10d episodes as the core
# Here:
#   P1  on 2010-06 / 2018-06 / 2024-06: for each non-primary US security, does another share class of the same
#       Morningstar company_id with is_primary_share = True exist that day? (sibling -> genuine secondary class;
#       no sibling -> mis-flag); count of company_ids with > 1 security left in the core (class duplicates)
#   N1  +100%/10d close-based (adjusted) episodes among no-fundamental <= 4-letter tickers: number of securities
#       with >= 1 episode, and 48 tickers drawn by a fixed hash (with the event year) for manual classification
#       (ETF / ETN / CEF vs common stock)

MAJOR = ("NAS", "NYS", "NYSE", "ASE", "AMEX")
SNAP = [_date(2010, 6, 1), _date(2018, 6, 1), _date(2024, 6, 3)]


class XupS2UniverseC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2006, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        self.add_universe(self._select)
        self.isn4 = {}
        self.cm = None
        self.hist = {}
        self.last_ev = {}
        self.evsec = {}      # sid -> (ticker, year, count)
        self.day = 0
        self.snap = {}
        self.snap_pending = list(SNAP)

    def _g(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _select(self, fundamental):
        d = self.time.date()
        self.day += 1
        mkey = (d.year, d.month)
        refresh = mkey != self.cm
        self.cm = mkey
        snap = bool(self.snap_pending) and d >= self.snap_pending[0]
        if snap:
            self.snap_pending.pop(0)
            self._snapshot(d, fundamental)
        for x in fundamental:
            sid = str(x.symbol.id)
            f = self.isn4.get(sid)
            if refresh or f is None:
                f = (not x.has_fundamental_data) and len(x.symbol.value) <= 4
                self.isn4[sid] = f
            if not f:
                continue
            px = float(x.price)
            adj = self._g(lambda: float(x.adjusted_price), px)
            vol = float(x.volume)
            h = self.hist.get(sid)
            if h is None:
                h = deque(maxlen=11)
                self.hist[sid] = h
            h.append((adj, vol))
            if len(h) == 11:
                st = h[0]
                if st[0] > 0 and st[1] > 0 and max(r[0] for r in list(h)[1:]) >= 2.0 * st[0]:
                    si = self.day - 10
                    if sid not in self.last_ev or si - self.last_ev[sid] >= 10:
                        self.last_ev[sid] = si
                        e = self.evsec.get(sid)
                        self.evsec[sid] = (x.symbol.value, d.year, (e[2] if e else 0) + 1) if e is None else (e[0], e[1], e[2] + 1)
        return []

    def _snapshot(self, d, fundamental):
        prim_by_co = {}
        su = []
        core_by_co = {}
        for x in fundamental:
            if not x.has_fundamental_data or float(x.price) <= 0:
                continue
            sr = self._g(lambda: x.security_reference)
            if sr is None or self._g(lambda: str(sr.security_type), "") != "ST00000001":
                continue
            co = self._g(lambda: str(x.company_reference.company_id), "?")
            pr = self._g(lambda: sr.is_primary_share, None)
            ctry = self._g(lambda: str(x.company_reference.country_id), "?")
            ex = self._g(lambda: str(sr.exchange_id), "?")
            if pr is not False:
                prim_by_co[co] = prim_by_co.get(co, 0) + 1
                if ex in MAJOR:
                    core_by_co[co] = core_by_co.get(co, 0) + 1
            elif ctry == "USA":
                su.append((co, x.symbol.value))
        sib = [t for co, t in su if prim_by_co.get(co, 0) > 0]
        nosib = [t for co, t in su if prim_by_co.get(co, 0) == 0]
        dup = sum(1 for v in core_by_co.values() if v > 1)
        self.snap[d] = (len(su), len(sib), len(nosib), sib[:5], nosib[:6], dup, len(core_by_co))

    def on_end_of_algorithm(self):
        S = self.set_runtime_statistic
        for d, v in sorted(self.snap.items()):
            S(f"P1 {d} US non-primary", f"n {v[0]} with primary sibling {v[1]} ({' '.join(v[3])}) | no sibling {v[2]} ({' '.join(v[4])}) | core companies with >1 class {v[5]} of {v[6]}"[:198])
        n = len(self.evsec)
        tot = sum(v[2] for v in self.evsec.values())
        S("N1 no-fund <=4 letters +100%/10d", f"securities with >=1 episode {n}, episodes {tot}")
        pick = sorted(self.evsec.items(), key=lambda kv: hashlib.md5(kv[0].encode()).hexdigest())[:48]
        txt = " ".join(f"{v[0]}{str(v[1])[2:]}" for k, v in pick)
        for j in range(0, len(txt), 190):
            S(f"N1 sample {j // 190}", txt[j:j + 190])
        # securities with the most episodes (where most of the events are concentrated)
        top = sorted(self.evsec.values(), key=lambda v: -v[2])[:20]
        S("N1 top by episodes", " ".join(f"{v[0]}:{v[2]}" for v in top)[:198])
