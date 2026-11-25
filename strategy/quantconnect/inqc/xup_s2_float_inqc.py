# region imports
from AlgorithmImports import *
from datetime import date as _date, timedelta
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 2 VALIDATION 3: DERIVED POINT-IN-TIME FLOAT (owner 2026-11-24). Aggregates only.
# Stage 1 found Morningstar SharesOutstanding (SO) and Float restated to today's split basis; proposed
#   PIT shares  DS = MarketCap / raw price          PIT float = Float x DS / SO
# Alternative PIT share estimate: SO x split_factor (factor-file split factor, today's basis).
# Universe: fundamental, security type common, 2011-01 .. 2026-11.
#   FS  every split detected from day-over-day changes in the factor-file split factor (true ex-dates): does DS
#       jump by the split ratio on the ex-date (lag 0) or later (stale market cap -> derived float wrong by the split
#       ratio for that many days)? Market-cap continuity on the ex-date. Forward vs reverse, low-priced reverse.
#   FA  agreement of DS with SO x split_factor on January snapshots (two independent PIT share estimates)
#   FT  staleness (weekly sampling): float changes per stock-year, weeks between changes, share of float changes in
#       weeks with an SO change, share of SO changes that also change the Float/SO ratio, age of the current float
#       value on 2016-01 and 2024-01 snapshots
#   FP  point-in-time test: share of weekly observations whose earning_reports.file_date lies in the future
#       (look-ahead signature); SO changes vs latest file date
#   FX  examples (issuance AMC / GME 2020-2022, buybacks AAPL): DS and SO x split_factor on fixed dates

EX = {"AMC": [_date(2020, 6, 1), _date(2021, 1, 4), _date(2021, 7, 1), _date(2022, 7, 1), _date(2023, 9, 1)],
      "GME": [_date(2020, 6, 1), _date(2021, 7, 1), _date(2022, 6, 1), _date(2022, 8, 1)],
      "AAPL": [_date(2012, 1, 3), _date(2016, 1, 4), _date(2020, 1, 2), _date(2024, 1, 2)]}


class XupS2Float(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2011, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        self.add_universe(self._select)
        self.common = {}       # sid -> bool (refreshed monthly)
        self.cm = None
        self.prev = {}         # sid -> (sf, price, mc)
        self.pending = []      # [sid, ratio, ds_before, mc_before, k, pre_price, done]
        self.lags = {}         # bucket -> counts
        self.lagstat = {"fwd": [], "rev": [], "revlow": []}
        self.mccont = [0, 0]
        self.nsplit = {"fwd": 0, "rev": 0}
        self.week = None
        self.wk = {}           # sid -> (so, fl, ratio, last_change_date)
        self.ft = {"obs": 0, "flch": 0, "flch_with_so": 0, "soch": 0, "soch_ratio": 0, "future_fd": 0, "fd_obs": 0}
        self.flchg_dates = {}  # sid -> list of dates float changed
        self.so_fd_lag = []
        self.age = {}
        self.fa = {}
        self.ex = {}
        self.jan = set()

    def _g(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _select(self, fundamental):
        d = self.time.date()
        mkey = (d.year, d.month)
        refresh = mkey != self.cm
        self.cm = mkey
        wkey = d.isocalendar()[:2]
        weekly = wkey != self.week
        self.week = wkey
        jan = d.month == 1 and d.year not in self.jan
        if jan:
            self.jan.add(d.year)
        exd = [(tk, k) for tk, ds in EX.items() for k, cd in enumerate(ds) if (tk, k) not in self.ex and d >= cd]
        pend = {}
        for p in self.pending:
            pend.setdefault(p[0], []).append(p)
        fa_rows = []
        age_tag = "2016" if (d >= _date(2016, 1, 4) and "2016" not in self.age) else "2024" if (d >= _date(2024, 1, 2) and "2024" not in self.age) else None
        ages = []
        for x in fundamental:
            if not x.has_fundamental_data:
                continue
            sid = str(x.symbol.id)
            c = self.common.get(sid)
            if refresh or c is None:
                c = self._g(lambda: str(x.security_reference.security_type), "") == "ST00000001"
                self.common[sid] = c
            if not c:
                continue
            px = float(x.price)
            sf = self._g(lambda: float(x.split_factor), 0.0)
            mc = self._g(lambda: float(x.market_cap), 0.0)
            if px <= 0 or sf <= 0:
                continue
            ds = mc / px if mc > 0 else 0.0
            # pending split checks
            if sid in pend:
                for p in pend[sid]:
                    p[4] += 1
                    if ds > 0 and p[2] > 0 and not p[6]:
                        r = ds / p[2]
                        if abs(r / p[1] - 1) < 0.10:
                            p[6] = True
                            self._lag(p, p[4] - 1)
                    if p[4] == 1 and p[3] > 0 and mc > 0:
                        self.mccont[1] += 1
                        if abs(mc / p[3] - 1) < 0.05:
                            self.mccont[0] += 1
                    if p[4] >= 31 and not p[6]:
                        p[6] = True
                        self._lag(p, 999)
            pv = self.prev.get(sid)
            if pv is not None and pv[0] > 0:
                ratio = sf / pv[0]
                if abs(ratio - 1) > 0.02 and pv[1] > 0:
                    # split ratio in share terms: forward 4:1 -> sf 0.25 -> 1.0 -> ratio 4
                    kind = "fwd" if ratio > 1 else "rev"
                    self.nsplit[kind] += 1
                    dsb = pv[2] / pv[1] if pv[2] > 0 else 0.0
                    p = [sid, ratio, dsb, pv[2], 0, pv[1], False, kind]
                    self.pending.append(p)
                    # evaluate today's bar immediately (k = 0)
                    p[4] = 1
                    if mc > 0 and pv[2] > 0:
                        self.mccont[1] += 1
                        if abs(mc / pv[2] - 1) < 0.05:
                            self.mccont[0] += 1
                    if ds > 0 and dsb > 0 and abs((ds / dsb) / ratio - 1) < 0.10:
                        p[6] = True
                        self._lag(p, 0)
            self.prev[sid] = (sf, px, mc)
            if weekly:
                so = self._g(lambda: float(x.company_profile.shares_outstanding), 0.0)
                fl = self._g(lambda: float(x.company_profile.float), 0.0)
                fd = self._g(lambda: x.earning_reports.file_date.value, None)
                if fd is not None:
                    self.ft["fd_obs"] += 1
                    fdd = self._g(lambda: fd.date(), None)
                    if fdd is not None and fdd > d:
                        self.ft["future_fd"] += 1
                if so > 0 and fl > 0:
                    rt = fl / so
                    w = self.wk.get(sid)
                    self.ft["obs"] += 1
                    if w is not None:
                        soch = abs(so / w[0] - 1) > 1e-6
                        flch = abs(fl / w[1] - 1) > 1e-6
                        if soch:
                            self.ft["soch"] += 1
                            if abs(rt / w[2] - 1) > 0.005:
                                self.ft["soch_ratio"] += 1
                            fdd = self._g(lambda: fd.date(), None) if fd is not None else None
                            if fdd is not None:
                                self.so_fd_lag.append((d - fdd).days)
                        if flch:
                            self.ft["flch"] += 1
                            if soch:
                                self.ft["flch_with_so"] += 1
                            self.flchg_dates.setdefault(sid, []).append(d)
                        lc = d if flch else w[3]
                    else:
                        lc = None
                    self.wk[sid] = (so, fl, rt, lc)
                    if age_tag and lc is not None:
                        ages.append((d - lc).days)
            if jan:
                so = self._g(lambda: float(x.company_profile.shares_outstanding), 0.0)
                if so > 0 and ds > 0:
                    fa_rows.append(ds / (so * sf))
            if exd and x.symbol.value in EX:
                for tk, k in exd:
                    if tk == x.symbol.value:
                        so = self._g(lambda: float(x.company_profile.shares_outstanding), 0.0)
                        fl = self._g(lambda: float(x.company_profile.float), 0.0)
                        self.ex[(tk, k)] = (str(d), ds, so * sf, fl * ds / so if so > 0 else 0.0, px)
        self.pending = [p for p in self.pending if not p[6]]
        if jan and fa_rows:
            n = len(fa_rows)
            self.fa[d.year] = (n, 100.0 * sum(1 for r in fa_rows if abs(r - 1) <= 0.05) / n, 100.0 * sum(1 for r in fa_rows if abs(r - 1) <= 0.20) / n,
                               100.0 * sum(1 for r in fa_rows if r > 1.5 or r < 0.67) / n)
        if age_tag and ages:
            ages.sort()
            self.age[age_tag] = (len(ages), ages[len(ages) // 2], ages[int(0.9 * (len(ages) - 1))])
        return []

    def _lag(self, p, k):
        kind = p[7]
        b = "0" if k == 0 else "1-2" if k <= 2 else "3-5" if k <= 5 else "6-30" if k <= 30 else "none30"
        self.lags.setdefault(kind, {})
        self.lags[kind][b] = self.lags[kind].get(b, 0) + 1
        if kind == "rev" and p[5] < 1.0:
            self.lags.setdefault("revlow", {})
            self.lags["revlow"][b] = self.lags["revlow"].get(b, 0) + 1

    def on_end_of_algorithm(self):
        S = self.set_runtime_statistic
        order = ["0", "1-2", "3-5", "6-30", "none30"]
        for kind in ("fwd", "rev", "revlow"):
            dct = self.lags.get(kind, {})
            n = max(1, sum(dct.values()))
            S(f"FS {kind} split DS lag", f"n {sum(dct.values())} | " + " ".join(f"{b}:{100.0 * dct.get(b, 0) / n:.0f}%" for b in order))
        S("FS detected / mcap continuity", f"fwd {self.nsplit['fwd']} rev {self.nsplit['rev']} | mcap within 5% across ex-date {100.0 * self.mccont[0] / max(1, self.mccont[1]):.0f}% of {self.mccont[1]}")
        S("FA DS vs SO*sf (n, within5%, within20%, off>1.5x)", " | ".join(f"{y}: {v[0]} {v[1]:.0f}% {v[2]:.0f}% {v[3]:.0f}%" for y, v in sorted(self.fa.items()) if y in (2011, 2013, 2016, 2019, 2021, 2023, 2025, 2026))[:198])
        ft = self.ft
        gaps = []
        per_year = []
        for sid, ds in self.flchg_dates.items():
            for i in range(1, len(ds)):
                gaps.append((ds[i] - ds[i - 1]).days)
        gaps.sort()
        q = lambda a, p: a[int(p * (len(a) - 1))] if a else 0
        S("FT staleness", f"weekly obs {ft['obs']} | float changes {ft['flch']} with SO change {100.0 * ft['flch_with_so'] / max(1, ft['flch']):.0f}% | SO changes {ft['soch']} that change Float/SO ratio {100.0 * ft['soch_ratio'] / max(1, ft['soch']):.0f}% | days between float changes p25 {q(gaps, .25)} p50 {q(gaps, .5)} p90 {q(gaps, .9)}"[:198])
        S("FT float age", " | ".join(f"{k}: n {v[0]} age p50 {v[1]}d p90 {v[2]}d" for k, v in sorted(self.age.items())))
        lg = sorted(self.so_fd_lag)
        S("FP point-in-time", f"file_date in future {100.0 * ft['future_fd'] / max(1, ft['fd_obs']):.2f}% of {ft['fd_obs']} | SO change minus latest file_date days p10 {q(lg, .1)} p50 {q(lg, .5)} p90 {q(lg, .9)} | <0 {100.0 * sum(1 for v in lg if v < 0) / max(1, len(lg)):.1f}% <=7 {100.0 * sum(1 for v in lg if 0 <= v <= 7) / max(1, len(lg)):.0f}%")
        for tk in EX:
            S(f"FX {tk}", " | ".join(f"{v[0]} DS {v[1] / 1e6:.0f}M SOsf {v[2] / 1e6:.0f}M FLpit {v[3] / 1e6:.0f}M px {v[4]:.2f}" for (t, k), v in sorted(self.ex.items()) if t == tk)[:198])
