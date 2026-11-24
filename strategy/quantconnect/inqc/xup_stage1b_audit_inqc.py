# region imports
from AlgorithmImports import *
import AlgorithmImports as AI
from datetime import date as _date
import random
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 1b AUDIT (owner 2026-11-24). Aggregates only.
#   C  alt-data class names in the runtime filtered to: FINRA, Regalytics, Short, Tiingo, Benzinga, SEC, Halt,
#      Quiver, SmartInsider, Insider, ExtractAlpha, Kavout, Brain, CrunchDAO, Estimize, Analyst, Earnings
#   FL Morningstar CompanyProfile.Float: coverage (> 0) per January 2006-2026; float / shares outstanding ratio
#      distribution; point-in-time behaviour: for 300 random fundamental stocks fixed on 2012-01-03, the number of
#      distinct float values over 2012-2016 monthly (a static back-filled field would give 1), the share that change
#      within 12 months, and whether float jumps line up with shares-outstanding changes; float around the AAPL
#      2020-08-31 4:1 split and the GE 2021-08-02 1:8 reverse split (split-adjusted or raw?)
#   ST security type codes / depositary receipt flag / share class status / common share sub type distribution
#      among fundamental securities on 2016-01-04 and 2026-01-02

KW = ("FINRA", "Regalytics", "Short", "Tiingo", "Benzinga", "SEC", "Halt", "Quiver", "SmartInsider", "Insider",
      "ExtractAlpha", "Kavout", "Brain", "CrunchDAO", "Estimize", "Analyst", "EODHD", "Earnings")
EXCL = ("Statement", "BalanceSheet", "IncomeStatement", "CashFlow", "Securities", "Security", "ShortName", "ShortTerm")


class XupAudit1b(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2006, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        self.add_universe(self._select)
        self.done = set()
        self.panel = None          # set of symbol ids followed 2012-2016
        self.ftrack = {}           # id -> list of (month, float, shares)
        self.pit = {}
        random.seed(7)

    def _g(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _select(self, fundamental):
        d = self.time.date()
        mkey = (d.year, d.month)
        # panel tracking monthly 2012-2016
        if self.panel is not None and 2012 <= d.year <= 2016 and mkey not in self.done:
            self.done.add(mkey)
            for x in fundamental:
                sid = str(x.symbol.id)
                if sid in self.panel:
                    fl = self._g(lambda: float(x.company_profile.float), 0.0)
                    so = self._g(lambda: float(x.company_profile.shares_outstanding), 0.0)
                    self.ftrack.setdefault(sid, []).append((mkey, fl, so))
        if self.panel is None and d >= _date(2012, 1, 3):
            wf = [x for x in fundamental if x.has_fundamental_data and self._g(lambda: float(x.company_profile.float), 0.0) > 0]
            pick = random.sample(wf, min(300, len(wf)))
            self.panel = set(str(x.symbol.id) for x in pick)
            self.done.add(mkey)
            for x in pick:
                self.ftrack[str(x.symbol.id)] = [(mkey, float(x.company_profile.float), self._g(lambda: float(x.company_profile.shares_outstanding), 0.0))]
        # split checks
        for tk, dd in (("AAPL", (_date(2020, 8, 3), _date(2020, 10, 1))), ("GE", (_date(2021, 7, 1), _date(2021, 9, 1))),
                       ("GME", (_date(2020, 6, 1), _date(2021, 1, 4), _date(2021, 6, 1), _date(2022, 9, 1)))):
            for k, cd in enumerate(dd):
                key = (tk, k)
                if key not in self.pit and d >= cd and (d - cd).days < 10:
                    for x in fundamental:
                        if x.symbol.value == tk:
                            self.pit[key] = (str(d), self._g(lambda: float(x.company_profile.float), 0.0),
                                             self._g(lambda: float(x.company_profile.shares_outstanding), 0.0), float(x.price),
                                             self._g(lambda: float(x.market_cap), 0.0))
                            break
        # January coverage + type mix
        jkey = ("J", d.year)
        if d.month == 1 and jkey not in self.done:
            self.done.add(jkey)
            wf = [x for x in fundamental if x.has_fundamental_data]
            fl = [self._g(lambda: float(x.company_profile.float), 0.0) for x in wf]
            so = [self._g(lambda: float(x.company_profile.shares_outstanding), 0.0) for x in wf]
            cov = 100.0 * sum(1 for v in fl if v > 0) / max(1, len(wf))
            ratios = sorted(f / s for f, s in zip(fl, so) if f > 0 and s > 0)
            q = (lambda p: ratios[int(p * (len(ratios) - 1))]) if ratios else (lambda p: 0)
            small = [f for f in fl if 0 < f < 5e6]
            self.set_runtime_statistic(f"FL {d.year}", f"float>0 {cov:.0f}% of {len(wf)} | float/SO p10 {q(0.1):.2f} p50 {q(0.5):.2f} p90 {q(0.9):.2f} >1.01: {100.0 * sum(1 for r in ratios if r > 1.01) / max(1, len(ratios)):.0f}% | float<5M {len(small)}")
            if d.year in (2016, 2026):
                def dist(fn):
                    c = {}
                    for x in wf:
                        v = str(self._g(lambda: fn(x), "?"))
                        c[v] = c.get(v, 0) + 1
                    return " ".join(f"{k}:{v}" for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:6])
                self.set_runtime_statistic(f"ST {d.year} type", dist(lambda x: x.security_reference.security_type)[:190])
                self.set_runtime_statistic(f"ST {d.year} DR/status", ("DR " + dist(lambda x: x.security_reference.is_depositary_receipt) + " | status " + dist(lambda x: x.security_reference.share_class_status))[:190])
                self.set_runtime_statistic(f"ST {d.year} subtype", dist(lambda x: x.security_reference.common_share_sub_type)[:190])
        return []

    def on_end_of_algorithm(self):
        names = sorted(set(n for n in dir(AI) if any(k.lower() in n.lower() for k in KW) and not any(e in n for e in EXCL)))
        txt = ", ".join(names)
        for j in range(0, min(len(txt), 950), 190):
            self.set_runtime_statistic(f"C classes {j // 190}", txt[j:j + 190])
        # panel PIT behaviour
        nd, ch12, aligned, tot = [], 0, 0, 0
        for sid, rows in self.ftrack.items():
            fl = [r[1] for r in rows if r[1] > 0]
            if len(fl) < 12:
                continue
            tot += 1
            nd.append(len(set(fl)))
            if len(set(fl[:13])) > 1:
                ch12 += 1
            # do float changes coincide with shares-outstanding changes?
            fch = [i for i in range(1, len(rows)) if rows[i][1] != rows[i - 1][1]]
            sch = set(i for i in range(1, len(rows)) if rows[i][2] != rows[i - 1][2])
            if fch and sum(1 for i in fch if i in sch) / len(fch) > 0.5:
                aligned += 1
        nd.sort()
        if nd:
            self.set_runtime_statistic("FL panel 2012-2016", f"stocks {tot} | distinct float values per stock p10 {nd[int(0.1 * (len(nd) - 1))]} p50 {nd[len(nd) // 2]} p90 {nd[int(0.9 * (len(nd) - 1))]} | changed within 12m {100.0 * ch12 / tot:.0f}% | changes mostly with SO {100.0 * aligned / tot:.0f}%")
        self.set_runtime_statistic("FL splits", " | ".join(f"{a}{b} {v[0]} FL {v[1] / 1e6:.0f}M SO {v[2] / 1e6:.0f}M px {v[3]:.1f} MC {v[4] / 1e9:.1f}B" for (a, b), v in sorted(self.pit.items()))[:198])
