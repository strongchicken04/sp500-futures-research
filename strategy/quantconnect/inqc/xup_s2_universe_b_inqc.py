# region imports
from AlgorithmImports import *
from datetime import date as _date
from collections import deque
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 2 VALIDATION 1b: WHAT ARE THE EXCLUDED GROUPS? (owner 2026-11-24). Aggregates only.
# Validation 1 showed: ADRs (BABA, TSM, BIDU, TM) are NOT flagged by is_depositary_receipt but fail is_primary_share
# (category S, together with secondary share classes such as BRK.B / GOOG); ETFs / ETNs / CEFs (SPY, VXX, PDI)
# have no fundamentals (category N), as do warrants / units / rights (5-letter W/U/R) and OTC ADRs (5-letter Y/F).
# Here the groups are split further and close-based (adjusted) event episodes are counted per sub-group and block:
#   Sf / Su  non-primary share, company country != USA (ADR-like) / USA (secondary class)
#   Nw / Ny / N4 / No  no fundamentals: 5-letter ending W/U/R or '.' (derivative-like) / 5-letter ending Y/F (OTC
#   ADR / foreign) / <= 4 letters (ETF, ETN, CEF, uncovered stocks) / other
#   Xo / Xa  fundamental common primary but exchange OTCM / other (Arca etc.)
#   K  core; O F P as before
# Snapshots 2010-06, 2018-06, 2024-06: counts and a few ticker examples per sub-group.

MAJOR = ("NAS", "NYS", "NYSE", "ASE", "AMEX")
SNAP = [_date(2010, 6, 1), _date(2018, 6, 1), _date(2024, 6, 3)]
BLK = [(2006, 2009), (2010, 2014), (2015, 2019), (2020, 2022), (2023, 2026)]


class XupS2UniverseB(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2006, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        self.add_universe(self._select)
        self.cat = {}
        self.cm = None
        self.hist = {}
        self.last_ev = {}
        self.day = 0
        self.ev = {}
        self.snap = {}
        self.snap_pending = list(SNAP)

    def _g(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _cat(self, x, px, tk):
        if not x.has_fundamental_data:
            if "." in tk or (len(tk) == 5 and tk[-1] in "WUR"):
                return "Nw"
            if len(tk) == 5 and tk[-1] in "YF":
                return "Ny"
            if len(tk) <= 4:
                return "N4"
            return "No"
        sr = self._g(lambda: x.security_reference)
        if sr is None:
            return "No"
        if self._g(lambda: str(sr.security_type), "") != "ST00000001":
            return "O"
        if "closed" in self._g(lambda: str(sr.common_share_sub_type), "").lower():
            return "F"
        if self._g(lambda: sr.is_primary_share, None) is False:
            c = self._g(lambda: str(x.company_reference.country_id), "?")
            return "Su" if c == "USA" else "Sf"
        ex = self._g(lambda: str(sr.exchange_id), "?")
        if ex not in MAJOR:
            return "Xo" if ex == "OTCM" else "Xa"
        nm = self._g(lambda: str(x.company_reference.standard_name), "") or ""
        if "acquisition" in nm.lower() and 9.0 <= px <= 10.8:
            return "P"
        return "K"

    def _select(self, fundamental):
        d = self.time.date()
        self.day += 1
        mkey = (d.year, d.month)
        refresh = mkey != self.cm
        self.cm = mkey
        snap = bool(self.snap_pending) and d >= self.snap_pending[0]
        if snap:
            self.snap_pending.pop(0)
            cnt, exs = {}, {}
        b = next(i for i, (a, z) in enumerate(BLK) if a <= d.year <= z)
        for x in fundamental:
            sid = str(x.symbol.id)
            px = float(x.price)
            vol = float(x.volume)
            adj = self._g(lambda: float(x.adjusted_price), px)
            fund = bool(x.has_fundamental_data)
            c = self.cat.get(sid)
            if refresh or c is None or (fund == c.startswith("N")):
                c = self._cat(x, px, x.symbol.value)
                self.cat[sid] = c
            h = self.hist.get(sid)
            if h is None:
                h = deque(maxlen=11)
                self.hist[sid] = h
            h.append((adj, vol, c))
            n = len(h)
            for hz, mult in ((5, 1.5), (10, 2.0)):
                if n < hz + 1:
                    break
                st = h[-1 - hz]
                if st[0] <= 0 or st[1] <= 0:
                    continue
                if max(r[0] for r in list(h)[-hz:]) < mult * st[0]:
                    continue
                lk = (hz, sid)
                si = self.day - hz
                if lk not in self.last_ev or si - self.last_ev[lk] >= hz:
                    self.last_ev[lk] = si
                    k = (hz, st[2], b)
                    self.ev[k] = self.ev.get(k, 0) + 1
            if snap and px > 0 and vol > 0:
                cnt[c] = cnt.get(c, 0) + 1
                lst = exs.setdefault(c, [])
                if c in ("Sf", "Su", "N4", "No", "Xa", "O") and len(lst) < 6:
                    if c != "N4" or px * vol > 1e6:
                        lst.append(x.symbol.value)
        if snap:
            self.snap[d] = (cnt, exs)
        return []

    def on_end_of_algorithm(self):
        S = self.set_runtime_statistic
        cats = ["K", "Sf", "Su", "Nw", "Ny", "N4", "No", "Xo", "Xa", "O", "F", "P"]
        for hz, lab in ((5, "+50%/5d"), (10, "+100%/10d")):
            tot = {c: sum(self.ev.get((hz, c, b), 0) for b in range(5)) for c in cats}
            S(f"EV {lab} episodes by group", " ".join(f"{c} {tot[c]}" for c in cats))
            for c in ("K", "Sf", "Nw", "N4"):
                S(f"EV {lab} {c} by block", " ".join(f"{BLK[b][0]}-{BLK[b][1] % 100:02d}:{self.ev.get((hz, c, b), 0)}" for b in range(5)))
        for d, (cnt, exs) in sorted(self.snap.items()):
            S(f"SN {d} counts", " ".join(f"{c} {cnt.get(c, 0)}" for c in cats))
            S(f"SN {d} examples", " | ".join(f"{c}: {' '.join(exs.get(c, []))}" for c in ("Sf", "Su", "N4", "No", "Xa", "O"))[:198])
