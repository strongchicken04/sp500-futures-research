# region imports
from AlgorithmImports import *
import AlgorithmImports as AI
from datetime import date as _date
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 1 DATA FEASIBILITY AUDIT (owner 2026-11-24). Runs INSIDE QuantConnect and returns
# aggregates only (counts, coverage shares, field / class names); no security-level data leaves QC.
# Checks:
#   U  universe coverage on the first trading day of each January 2006-2026 (+ 2026-11): number of securities passed
#      to the Fundamental universe, share with fundamentals, security type / ADR / exchange mix, price and market-cap
#      buckets, coverage of shares outstanding and market cap
#   D  survivorship: are known later-delisted / bankrupt / acquired names present before their exit; share of 2008
#      symbols that no longer exist in 2026
#   F  fundamental field names that mention float / short / shares / outstanding / market cap / delist / ipo / file
#      date (what Morningstar exposes in QC)
#   P  point-in-time check of shares outstanding around known share-count changes (AAPL 4:1 split 2020-08-31,
#      GE 1:8 reverse split 2021-08-02)
#   A  alternative-data classes available in the QC runtime (names containing Short / FINRA / RegSHO / Float / News
#      / Tiingo / Benzinga / SEC / Insider / Halt / Earnings / Estimize)
#   I  intraday + pre-market minute data for a small / volatile name (AMC 2021-01-26/27), split events for GE 2021

KNOWN = {  # ticker -> (check date, event)
    "LEH": (_date(2008, 1, 2), "bankrupt 2008-09"),
    "WM": (_date(2008, 1, 2), "bank failure 2008-09"),
    "BSC": (_date(2008, 1, 2), "acquired 2008-05"),
    "CIT": (_date(2008, 1, 2), "bankrupt 2009-11"),
    "RSH": (_date(2014, 1, 2), "bankrupt 2015-02"),
    "SHLD": (_date(2017, 1, 3), "bankrupt 2018-10"),
    "HTZ": (_date(2019, 1, 2), "bankrupt 2020-05 (relisted)"),
    "BBBY": (_date(2022, 1, 3), "bankrupt 2023-04"),
    "SIVB": (_date(2022, 1, 3), "bank failure 2023-03"),
    "FRC": (_date(2022, 1, 3), "bank failure 2023-05"),
}
KEYWORDS = ("float", "short", "share", "outstanding", "market_cap", "marketcap", "delist", "ipo", "file_date", "filedate", "insider")


class XupAudit(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2006, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        self.add_universe(self._select)
        self.done = set()
        self.syms_2008 = None
        self.syms_last = None
        self.all_syms = set()
        self.field_names = None
        self.known_hits = {}
        self.pit = {}

    def _safe(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _fields(self, f):
        out = {}
        for part in ("company_profile", "security_reference", "company_reference", "earning_reports", "valuation_ratios",
                     "operation_ratios", "financial_statements", "asset_classification"):
            obj = self._safe(lambda: getattr(f, part))
            if obj is None:
                continue
            names = [n for n in dir(obj) if not n.startswith("_") and any(k in n.lower() for k in KEYWORDS)]
            out[part] = names
        return out

    def _select(self, fundamental):
        d = self.time.date()
        for x in fundamental:
            self.all_syms.add(str(x.symbol.id))
        # survivorship checks
        for tk, (cd, ev) in KNOWN.items():
            if tk not in self.known_hits and d >= cd and (d - cd).days < 10:
                self.known_hits[tk] = any(x.symbol.value == tk for x in fundamental)
        # point-in-time shares outstanding checks
        for tk, dd in (("AAPL", (_date(2020, 8, 3), _date(2020, 10, 1), _date(2020, 12, 1))),
                       ("GE", (_date(2021, 7, 1), _date(2021, 9, 1), _date(2021, 11, 1)))):
            for k, cd in enumerate(dd):
                key = (tk, k)
                if key not in self.pit and d >= cd and (d - cd).days < 10:
                    for x in fundamental:
                        if x.symbol.value == tk:
                            so = self._safe(lambda: float(x.company_profile.shares_outstanding), 0.0)
                            mc = self._safe(lambda: float(x.market_cap), 0.0)
                            self.pit[key] = (str(d), so, mc, float(x.price))
                            break
        key = (d.year, d.month)
        sample = (d.month == 1 and (d.year, 1) not in self.done) or (d.year == 2026 and d.month == 11 and (2026, 11) not in self.done)
        if not sample:
            return []
        self.done.add(key)
        n = len(fundamental)
        wf = [x for x in fundamental if x.has_fundamental_data]
        def share(cond, base):
            return 100.0 * sum(1 for x in base if self._safe(lambda: cond(x), False)) / max(1, len(base))
        st_common = share(lambda x: x.security_reference.security_type == "ST00000001", wf)
        adr = share(lambda x: bool(x.security_reference.is_depositary_receipt), wf)
        exch = {}
        for x in wf:
            e = self._safe(lambda: str(x.security_reference.exchange_id), "?")
            exch[e] = exch.get(e, 0) + 1
        top_ex = " ".join(f"{k}:{v}" for k, v in sorted(exch.items(), key=lambda kv: -kv[1])[:5])
        p1 = share(lambda x: x.price < 1, fundamental)
        p5 = share(lambda x: 1 <= x.price < 5, fundamental)
        mc = [self._safe(lambda: float(x.market_cap), 0.0) for x in wf]
        mcp = [m for m in mc if m > 0]
        def mshare(lo, hi):
            return 100.0 * sum(1 for m in mcp if lo <= m < hi) / max(1, len(mcp))
        so_cov = share(lambda x: float(x.company_profile.shares_outstanding) > 0, wf)
        mc_cov = 100.0 * len(mcp) / max(1, len(wf))
        self.set_runtime_statistic(f"U {d}",
            f"n {n} fund {len(wf)} | common {st_common:.0f}% ADR {adr:.0f}% | ex {top_ex} | px<1 {p1:.0f}% 1-5 {p5:.0f}%"
            f" | mcap<10M {mshare(0, 1e7):.0f}% 10-50M {mshare(1e7, 5e7):.0f}% 50-300M {mshare(5e7, 3e8):.0f}% >1B {mshare(1e9, 1e15):.0f}% | SO {so_cov:.0f}% MC {mc_cov:.0f}%")
        cur = set(str(x.symbol.id) for x in fundamental)
        if d.year == 2008:
            self.syms_2008 = cur
        self.syms_last = cur
        if self.field_names is None and wf:
            self.field_names = self._fields(wf[0])
        return []

    def on_end_of_algorithm(self):
        # D: survivorship
        hits = " ".join(f"{k}:{'Y' if v else 'N'}" for k, v in self.known_hits.items())
        self.set_runtime_statistic("D known delisted present", hits)
        if self.syms_2008 and self.syms_last:
            gone = len(self.syms_2008 - self.syms_last)
            self.set_runtime_statistic("D 2008 symbols gone by last sample", f"{gone}/{len(self.syms_2008)} ({100.0 * gone / len(self.syms_2008):.0f}%) | unique symbols seen 2006-2026 {len(self.all_syms)}")
        # F: fields
        if self.field_names:
            k = 0
            for part, names in self.field_names.items():
                if names:
                    self.set_runtime_statistic(f"F {part}", ", ".join(names)[:190])
                    k += 1
        # P: point in time
        self.set_runtime_statistic("P shares outstanding", " | ".join(f"{a}{b}: {v[0]} SO {v[1] / 1e6:.0f}M MC {v[2] / 1e9:.1f}B px {v[3]:.1f}" for (a, b), v in sorted(self.pit.items()))[:195])
        # A: alt-data classes in the runtime
        kws = ("Short", "FINRA", "RegSHO", "Float", "News", "Tiingo", "Benzinga", "SEC", "Insider", "Halt", "Earnings", "Estimize", "Quiver", "Fundamental")
        names = sorted(set(n for n in dir(AI) if any(k.lower() in n.lower() for k in kws)))
        txt = ", ".join(names)
        for j in range(0, min(len(txt), 760), 190):
            self.set_runtime_statistic(f"A classes {j // 190}", txt[j:j + 190])
        # I: intraday / pre-market + splits
        try:
            amc = self.add_equity("AMC", Resolution.MINUTE, extended_market_hours=True).symbol
            h = self.history(amc, datetime(2021, 1, 27, 4, 0), datetime(2021, 1, 27, 20, 0), Resolution.MINUTE, extended_market_hours=True)
            if h is None or h.empty:
                self.set_runtime_statistic("I AMC 2021-01-27 minute", "no data")
            else:
                ts = [ix[1] if isinstance(ix, tuple) else ix for ix in h.index]
                pre = sum(1 for t in ts if t.hour < 9 or (t.hour == 9 and t.minute <= 30))
                post = sum(1 for t in ts if t.hour >= 16 and not (t.hour == 16 and t.minute == 0))
                self.set_runtime_statistic("I AMC 2021-01-27 minute", f"bars {len(ts)} pre-market {pre} after-hours {post} volume {float(h['volume'].sum()) / 1e6:.0f}M")
        except Exception as e:
            self.set_runtime_statistic("I AMC 2021-01-27 minute", f"error {str(e)[:150]}")
        try:
            ge = self.add_equity("GE", Resolution.DAILY).symbol
            hs = self.history(Split, ge, datetime(2021, 1, 1), datetime(2021, 12, 31))
            self.set_runtime_statistic("I GE 2021 splits", f"{0 if hs is None else len(hs)} split rows: {str(hs.tail(2).to_dict()) [:150] if hs is not None and len(hs) else ''}")
        except Exception as e:
            self.set_runtime_statistic("I GE 2021 splits", f"error {str(e)[:150]}")
