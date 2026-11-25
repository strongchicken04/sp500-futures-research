# region imports
from AlgorithmImports import *
from datetime import date as _date, timedelta
from collections import deque
import random, math
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 2 VALIDATION 1: UNIVERSE, ATTRITION, SELECTION BIAS, REPRESENTATIVENESS
# (owner 2026-11-24). Runs INSIDE QuantConnect; returns aggregates only (counts, shares, medians, a handful of
# ticker examples for classification). No predictive test, no feature selection.
#
# Sequential filter chain (category = first filter a security fails):
#   N  no fundamental data (ETF/ETN/ADR/units/warrants/new listings without Morningstar coverage)
#   O  fundamental but security type != common (ST00000001): preferred etc.
#   F  common but common_share_sub_type = Closed End Fund
#   S  not the primary share class
#   X  exchange not Nasdaq / NYSE / NYSE American (OTCM, Arca, ...)
#   P  SPAC heuristic: standard name contains "Acquisition" and raw price 9.0-10.8
#   K  core final universe (B-core)
# Universes: A = traded (price>0, volume>0, everything delivered); B = K; C = K with Morningstar float > 0;
# D = K that also appears in FINRA short interest on that date (>= 2018-01).
# Checks:
#   R  15 random dates (3 per block 2006-09, 2010-14, 2015-19, 2020-22, 2023-26, seed 2026): attrition counts,
#      C/D sizes, is_primary None count, ADR flag count, median 20d volatility K vs N
#   X  per block: profile of N (no fundamentals) names on the random dates: price / dollar volume, ticker patterns
#   Q  per block on a quarterly grid (Jan/Apr/Jul/Oct): A vs K price and dollar-volume mix, K share of A count and
#      of A dollar volume
#   M  per block on the grid: fundamental-all vs K exchange mix and market-cap mix
#   K  known tickers (ADR / ETF / ETN / CEF / leveraged ETF) on 2016-01-04 and 2024-01-02: category
#   S  SPAC heuristic: counts, Morningstar industry codes of heuristic SPACs
#   L  fundamentals lag: days from a symbol's first appearance (after 2006-02) to first has_fundamental_data
#   E  close-based (adjusted) event-start counts +50%/5d, +100%/10d, +200%/20d by category at the start date:
#      start-days and non-overlapping episodes -> how many events each filter removes (descriptive, not predictive)
#   Z  events whose window contains a split (raw/adj ratio mismatch > 1.5x) or a zero-volume day

BLOCKS = [("06-09", _date(2006, 1, 3), _date(2009, 12, 31)), ("10-14", _date(2010, 1, 1), _date(2014, 12, 31)),
          ("15-19", _date(2015, 1, 1), _date(2019, 12, 31)), ("20-22", _date(2020, 1, 1), _date(2022, 12, 31)),
          ("23-26", _date(2023, 1, 1), _date(2026, 11, 13))]
KNOWN = ["BABA", "TSM", "NVO", "BIDU", "TM", "SPY", "QQQ", "IWM", "GLD", "TQQQ", "VXX", "TVIX", "PDI", "ADX", "GOF", "UTF", "BRK.B", "GOOG"]
CATS = "KNOFSXP"
MAJOR = ("NAS", "NYS", "NYSE", "ASE", "AMEX")
LABELS = ((5, 1.5), (10, 2.0), (20, 3.0))


def _blk(d):
    for name, a, b in BLOCKS:
        if a <= d <= b:
            return name
    return None


class XupS2Universe(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2006, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        rng = random.Random(2026)
        self.rand_targets = []
        for name, a, b in BLOCKS:
            span = (b - a).days
            ds = sorted(a + timedelta(days=rng.randint(0, span - 25)) for _ in range(3))
            self.rand_targets += ds
        self.rand_done = []          # actual selector dates
        self.rand_pending = list(self.rand_targets)
        self.grid_done = set()
        self.hist = {}               # sid -> deque of (adj, raw, vol, cat)
        self.cat = {}                # sid -> cached category (refreshed monthly)
        self.cat_month = None
        self.first_seen = {}
        self.first_fund = {}
        self.ev = {}                 # (h, cat) -> [start_days, episodes]
        self.last_ev = {}            # (h, sid) -> index of last episode start
        self.zstat = {}
        self.day_idx = 0
        self.agg = {}
        self.si_sets = {}
        self.k_sets = {}
        self.known = {}
        self.spac_ind = {}
        self.err = []
        self.add_universe(self._select)
        try:
            self.add_universe(FINRAShortInterestUniverse, self._si)
        except Exception as e:
            self.err.append("si " + str(e)[:80])

    def _g(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _cat(self, x, px):
        if not x.has_fundamental_data:
            return "N"
        sr = self._g(lambda: x.security_reference)
        if sr is None:
            return "N"
        if self._g(lambda: str(sr.security_type), "") != "ST00000001":
            return "O"
        if "closed" in self._g(lambda: str(sr.common_share_sub_type), "").lower():
            return "F"
        pr = self._g(lambda: sr.is_primary_share, None)
        if pr is not None and not pr:
            return "S"
        if self._g(lambda: str(sr.exchange_id), "?") not in MAJOR:
            return "X"
        nm = self._g(lambda: str(x.company_reference.standard_name), "") or ""
        if "acquisition" in nm.lower() and 9.0 <= px <= 10.8:
            return "P"
        return "K"

    def _si(self, data):
        d = self.time.date()
        if any(abs((d - t).days) <= 4 for t in self.rand_targets) and d >= _date(2018, 1, 1):
            s = set()
            for x in data:
                s.add(x.symbol.value)
            self.si_sets[d] = s
        return []

    def _add(self, key, k, v=1):
        dct = self.agg.setdefault(key, {})
        dct[k] = dct.get(k, 0) + v

    def _select(self, fundamental):
        d = self.time.date()
        self.day_idx += 1
        mkey = (d.year, d.month)
        refresh = mkey != self.cat_month
        self.cat_month = mkey
        is_rand = bool(self.rand_pending) and d >= self.rand_pending[0]
        if is_rand:
            self.rand_pending.pop(0)
        is_grid = d.month in (1, 4, 7, 10) and mkey not in self.grid_done
        if is_grid:
            self.grid_done.add(mkey)
        is_known = (d >= _date(2016, 1, 4) and "k16" not in self.known) or (d >= _date(2024, 1, 2) and "k24" not in self.known)
        blk = _blk(d)
        rows = []  # for sample dates: (sid, tk, cat, px, dv, x)
        for x in fundamental:
            sid = str(x.symbol.id)
            px = float(x.price)
            vol = float(x.volume)
            adj = self._g(lambda: float(x.adjusted_price), px)
            fund = bool(x.has_fundamental_data)
            if sid not in self.first_seen:
                self.first_seen[sid] = d
            if fund and sid not in self.first_fund:
                self.first_fund[sid] = d
            c = self.cat.get(sid)
            if refresh or c is None or (fund and c == "N") or (not fund and c != "N"):
                c = self._cat(x, px)
                self.cat[sid] = c
            h = self.hist.get(sid)
            if h is None:
                h = deque(maxlen=21)
                self.hist[sid] = h
            h.append((adj, px, vol, c))
            # backward-looking event detection: each start day is evaluated once, when its window completes
            n = len(h)
            if n >= 6:
                hl = [r[0] for r in h]
                for hz, mult in LABELS:
                    if n < hz + 1:
                        break
                    st = h[-1 - hz]
                    if st[0] <= 0 or st[2] <= 0:
                        continue
                    mx = max(hl[-hz:])
                    if mx < mult * st[0]:
                        continue
                    key = (hz, st[3])
                    e = self.ev.setdefault(key, [0, 0])
                    e[0] += 1
                    lk = (hz, sid)
                    start_idx = self.day_idx - hz
                    if lk not in self.last_ev or start_idx - self.last_ev[lk] >= hz:
                        e[1] += 1
                        self.last_ev[lk] = start_idx
                        w = list(h)[-hz:]
                        rr = max(r[1] for r in w) / st[1] if st[1] > 0 else 0
                        ra = mx / st[0]
                        z = self.zstat.setdefault(hz, [0, 0, 0])
                        z[0] += 1
                        if rr > 0 and (ra / rr > 1.5 or rr / ra > 1.5):
                            z[1] += 1
                        if any(r[2] <= 0 for r in w):
                            z[2] += 1
            if is_rand or is_grid or is_known:
                rows.append((sid, x.symbol.value, c, px, float(self._g(lambda: x.dollar_volume, px * vol)), x, vol, h))
        if is_rand:
            self._rand(d, rows)
        if is_grid and blk:
            self._grid(blk, rows)
        if is_known:
            tag = "k16" if "k16" not in self.known else "k24"
            m = {r[1]: r for r in rows}
            self.known[tag] = " ".join(f"{t}:{m[t][2] if t in m else '-'}" for t in KNOWN)
        return []

    def _vol20(self, h):
        p = [r[0] for r in h]
        if len(p) < 21 or min(p) <= 0:
            return None
        lr = [math.log(p[i] / p[i - 1]) for i in range(1, len(p))]
        m = sum(lr) / len(lr)
        return math.sqrt(sum((v - m) ** 2 for v in lr) / (len(lr) - 1))

    def _rand(self, d, rows):
        self.rand_done.append(d)
        cnt = {c: 0 for c in CATS}
        traded = 0
        prim_none = 0
        adr = 0
        flt = 0
        kt = set()
        vols = {"K": [], "N": []}
        blk = _blk(d)
        for sid, tk, c, px, dv, x, vol, h in rows:
            if px <= 0 or vol <= 0:
                continue
            traded += 1
            cnt[c] += 1
            if c != "N":
                if self._g(lambda: x.security_reference.is_primary_share, None) is None:
                    prim_none += 1
                if self._g(lambda: bool(x.security_reference.is_depositary_receipt), False):
                    adr += 1
            if c == "K":
                kt.add(tk)
                if self._g(lambda: float(x.company_profile.float), 0.0) > 0:
                    flt += 1
            if c in vols:
                v = self._vol20(h)
                if v is not None:
                    vols[c].append(v)
            if c == "N" and blk:
                self._add(("X", blk), "n")
                self._add(("X", blk), "dv<100k", 1 if dv < 1e5 else 0)
                self._add(("X", blk), "px<1", 1 if px < 1 else 0)
                self._add(("X", blk), "dot", 1 if ("." in tk or " " in tk) else 0)
                if len(tk) == 5:
                    self._add(("X5", blk), tk[-1])
                self._add(("XL", blk), len(tk) if len(tk) < 6 else 6)
                ex = self.agg.setdefault(("XE", blk), [])
                if len(tk) == 5 and tk[-1] in "WURY" and len(ex) < 4:
                    ex.append(tk)
            if c == "P":
                ic = self._g(lambda: str(x.asset_classification.morningstar_industry_code), "?")
                self.spac_ind[ic] = self.spac_ind.get(ic, 0) + 1
            if c == "O" and blk:
                ex = self.agg.setdefault(("OE", "all"), [])
                if len(ex) < 6 and tk not in ex:
                    ex.append(tk)
        self.k_sets[d] = kt
        med = lambda a: sorted(a)[len(a) // 2] * 100 if a else 0
        n_all = len(rows)
        c_f = traded - cnt["N"]
        c_c = c_f - cnt["O"]
        c_nc = c_c - cnt["F"]
        c_pr = c_nc - cnt["S"]
        c_ex = c_pr - cnt["X"]
        c_k = c_ex - cnt["P"]
        self.rand_stats = getattr(self, "rand_stats", {})
        self.rand_stats[d] = [n_all, traded, c_f, c_c, c_nc, c_pr, c_ex, c_k, flt, prim_none, adr, med(vols["K"]), med(vols["N"])]

    def _grid(self, blk, rows):
        tot_dv = 0.0
        k_dv = 0.0
        for sid, tk, c, px, dv, x, vol, h in rows:
            if px <= 0 or vol <= 0:
                continue
            pb = "<1" if px < 1 else "1-5" if px < 5 else "5-20" if px < 20 else ">20"
            db = "<100k" if dv < 1e5 else "100k-1M" if dv < 1e6 else "1-10M" if dv < 1e7 else ">10M"
            self._add(("QA", blk), pb)
            self._add(("QAd", blk), db)
            self._add(("QA", blk), "n")
            tot_dv += dv
            if c == "K":
                self._add(("QK", blk), pb)
                self._add(("QKd", blk), db)
                self._add(("QK", blk), "n")
                k_dv += dv
            if c != "N":
                ex = self._g(lambda: str(x.security_reference.exchange_id), "?")
                mc = self._g(lambda: float(x.market_cap), 0.0)
                mb = "na" if mc <= 0 else "<50M" if mc < 5e7 else "50-300M" if mc < 3e8 else "0.3-2B" if mc < 2e9 else ">2B"
                self._add(("MF", blk), ex if ex in ("NAS", "NYS", "NYSE", "ASE", "AMEX", "OTCM") else "oth")
                self._add(("MFm", blk), mb)
                self._add(("MF", blk), "n")
                if c == "K":
                    self._add(("MK", blk), ex)
                    self._add(("MKm", blk), mb)
                    self._add(("MK", blk), "n")
        self._add(("DV", blk), "A", tot_dv)
        self._add(("DV", blk), "K", k_dv)

    def _pct(self, dct, keys):
        n = max(1, dct.get("n", 0))
        return " ".join(f"{k} {100.0 * dct.get(k, 0) / n:.0f}" for k in keys)

    def on_end_of_algorithm(self):
        S = self.set_runtime_statistic
        # R
        for d in sorted(getattr(self, "rand_stats", {})):
            n_all, tr, f, c, nc, pr, ex, k, flt, pn, adr, vk, vn = self.rand_stats[d]
            sd = None
            for t in sorted(self.si_sets):
                if abs((t - d).days) <= 4:
                    sd = t
                    break
            dd = len(self.k_sets[d] & self.si_sets[sd]) if sd else "-"
            S(f"R {d}", f"all {n_all} traded {tr} fund {f} common {c} notCEF {nc} primary {pr} majorEx {ex} notSPAC(B) {k} | C float {flt} D SI {dd} | primNone {pn} ADRflag {adr} | vol20 med K {vk:.1f}% N {vn:.1f}%")
        # X
        for name, a, b in BLOCKS:
            x = self.agg.get(("X", name), {})
            n = max(1, x.get("n", 0))
            x5 = self.agg.get(("X5", name), {})
            xl = self.agg.get(("XL", name), {})
            top5 = " ".join(f"{k}:{v}" for k, v in sorted(x5.items(), key=lambda kv: -kv[1])[:6])
            lens = " ".join(f"{k}:{v}" for k, v in sorted(xl.items()))
            S(f"X {name} no-fund", f"n {x.get('n', 0)} dv<100k {100.0 * x.get('dv<100k', 0) / n:.0f}% px<1 {100.0 * x.get('px<1', 0) / n:.0f}% dot {x.get('dot', 0)} | len {lens} | 5ch last {top5} | ex {' '.join(self.agg.get(('XE', name), []))}"[:198])
        # Q and M
        for name, a, b in BLOCKS:
            qa = self.agg.get(("QA", name), {})
            qk = self.agg.get(("QK", name), {})
            qad = self.agg.get(("QAd", name), {})
            qkd = self.agg.get(("QKd", name), {})
            qad["n"] = qa.get("n", 0)
            qkd["n"] = qk.get("n", 0)
            dv = self.agg.get(("DV", name), {})
            pk = ["<1", "1-5", "5-20", ">20"]
            dk = ["<100k", "100k-1M", "1-10M", ">10M"]
            S(f"Q {name} A vs K", f"K/A n {100.0 * qk.get('n', 0) / max(1, qa.get('n', 0)):.0f}% dv {100.0 * dv.get('K', 0) / max(1, dv.get('A', 1)):.0f}% | px A {self._pct(qa, pk)} K {self._pct(qk, pk)} | dv A {self._pct(qad, dk)} K {self._pct(qkd, dk)}"[:198])
            mf = self.agg.get(("MF", name), {})
            mk = self.agg.get(("MK", name), {})
            mfm = self.agg.get(("MFm", name), {})
            mkm = self.agg.get(("MKm", name), {})
            mfm["n"] = mf.get("n", 0)
            mkm["n"] = mk.get("n", 0)
            exs = sorted(set(list(mf.keys()) + list(mk.keys())) - {"n"})
            mks = ["na", "<50M", "50-300M", "0.3-2B", ">2B"]
            S(f"M {name} fund vs K", f"ex F {self._pct(mf, exs)} K {self._pct(mk, exs)} | mcap F {self._pct(mfm, mks)} K {self._pct(mkm, mks)}"[:198])
        # K known
        for tag in ("k16", "k24"):
            S(f"K known {tag}", self.known.get(tag, "-")[:198])
        S("K O-type examples", " ".join(self.agg.get(("OE", "all"), [])))
        # S spac
        S("S SPAC industry codes", " ".join(f"{k}:{v}" for k, v in sorted(self.spac_ind.items(), key=lambda kv: -kv[1])[:6]))
        # L lag
        lags = []
        never = 0
        newc = 0
        byblk = {}
        for sid, fs in self.first_seen.items():
            if fs < _date(2006, 2, 1) or fs > _date(2026, 9, 1):
                continue
            newc += 1
            ff = self.first_fund.get(sid)
            if ff is None:
                never += 1
                continue
            lg = (ff - fs).days
            lags.append(lg)
            b = _blk(fs) or "?"
            byblk.setdefault(b, []).append(lg)
        lags.sort()
        q = lambda a, p: a[int(p * (len(a) - 1))] if a else 0
        S("L fund lag", (f"new {newc} never {never} | lag p50 {q(lags, .5)} p75 {q(lags, .75)} p90 {q(lags, .9)} | 0d {100.0 * sum(1 for v in lags if v == 0) / max(1, len(lags)):.0f}% >5d {100.0 * sum(1 for v in lags if v > 5) / max(1, len(lags)):.0f}% >30d {100.0 * sum(1 for v in lags if v > 30) / max(1, len(lags)):.0f}% | blk p50/p90 "
                          + " ".join(f"{b}:{q(sorted(v), .5)}/{q(sorted(v), .9)}" for b, v in sorted(byblk.items())))[:198])
        # E events
        for hz, mult in LABELS:
            parts = []
            for c in CATS:
                e = self.ev.get((hz, c), [0, 0])
                parts.append(f"{c} {e[0]}/{e[1]}")
            z = self.zstat.get(hz, [0, 0, 0])
            S(f"E +{int((mult - 1) * 100)}%/{hz}d close starts/episodes", " ".join(parts) + f" | Z episodes {z[0]} split-in-window {z[1]} zero-vol-day {z[2]}")
        if self.err:
            S("ERR", " | ".join(self.err)[:198])
