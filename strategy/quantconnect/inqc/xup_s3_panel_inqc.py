# region imports
from AlgorithmImports import *
from datetime import date as _date, timedelta
import hashlib, re, bisect, math, time as _time
import numpy as np
import pandas as pd
from xup_ic_0 import DATA as _d0
from xup_ic_1 import DATA as _d1
from xup_ic_2 import DATA as _d2
from xup_ic_3 import DATA as _d3
from xup_ic_4 import DATA as _d4
from xup_s3_const import *
from xup_s3_const import _blk
from xup_s3_modes_ab import ModesAB
from xup_s3_modes_u import ModesU
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 3 PANEL (owner brief 2026-11-25). All security-level work stays inside QC; the
# output is aggregate statistics only (runtime statistics + <= 10 KB of log lines).
# One script, several MODEs (set by the runner): AUDIT | BASE | UNIV | MODEL | TEST. Every run rebuilds the same
# panel deterministically (Object Store reads are not permitted on this account).
#
# Universe / classification: Stage 2 option A rules (xup_s2_instr_class_inqc.py v3), weekly universe pass.
#   A        all securities not classified ETF / ETN / CEF / PREFERRED / PREF_OTHER / DEBT / WARRANT / RIGHT / UNIT / TEST
#   A-strict A without UNRESOLVED;  A-ex-ADR  A without ADR_FOREIGN;  A-fund  A minus UNRESOLVED days that are
#            fund-like by the point-in-time flag (trailing 120 sessions: idio vol vs SPY < 0.006 and share of
#            |r| > 8% <= 0.025)
#   B        Morningstar common (COMMON, COMMON_SECONDARY) with a fundamental snapshot <= 40 days old
#   C        B with Morningstar float (Float / SO ratio > 0), 2011 onward (uncertain)
#   D        A with a FINRA short-interest value: delivered (QC end_time) on/before t, value age <= 35 days,
#            not on a duplicate-record day, 2018-01-11 .. 2026-08-27
# Panel: security-days of a FIXED-HASH SAMPLE of securities (md5(security id) % SAMPLE_MOD == 0; same sample in
#   every run), all their eligible days. Eligible: real bar (fill-forward off), raw close > 0, >= 20 prior sessions
#   in the same segment (segments split at gaps > 10 market sessions), date 2006-02-01 .. 2026-08-27.
# Labels (Stage 2): reference adjusted OPEN(t+1); window = the security's next h sessions inside the segment;
#   A = max adj HIGH / ref - 1; B = adj CLOSE(t+h) / ref - 1; Bmax = max adj CLOSE / ref - 1; h = 5, 10, 20;
#   thresholds 50 / 100 / 200%; incomplete window (segment end / data end) -> label invalid (-1).
# Features: only data up to and including the close of t (see FEATS); leakage unit test in AUDIT.

MODE = "AUDIT"
class XupS3Panel(QCAlgorithm, ModesAB, ModesU):

    def initialize(self):
        self.t0 = _time.time()
        self.set_start_date(2006, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        self.logbuf = []
        self.err = []
        self.sec_etf, self.ncen, self.cur = {}, {}, {}
        for ln in "\n".join((_d0, _d1, _d2, _d3, _d4)).split("\n"):
            p = ln.split(" ")
            if len(p) < 4:
                continue
            if p[0] == "E":
                for tk in p[3].split(","):
                    self.sec_etf.setdefault(tk, []).append((_date(int(p[1]), 1, 1), _date(int(p[2]), 12, 31)))
            elif p[0] == "K" and len(p) >= 5:
                for tk in p[4].split(","):
                    self.ncen.setdefault(tk, []).append((_date(int(p[1]), 1, 1), _date(int(p[2]), 12, 31), p[3]))
            elif p[0] == "C":
                for tk in p[3].split(","):
                    if tk in self.cur and p[2] == "SECCTE":
                        continue
                    self.cur[tk] = p[1]
                    if p[1] == "TEST":
                        TESTS.add(tk)
        self.span, self.first, self.last, self.ms = {}, {}, {}, {}
        self.syms = {}
        self.snap = {}       # sampled sid -> list of (date, mc, raw px, so, float)
        self.si = {}         # sampled sid -> list of (date, si, prev_si, dtc, ambiguous)
        self.si_last = {}
        self.insample = {}
        self.week = None
        self.month = None
        self.add_universe(self._select)
        self.add_universe(FINRAShortInterestUniverse, self._si_sel)

    def _g(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _hs(self, sid):
        v = self.insample.get(sid)
        if v is None:
            v = int(hashlib.md5(sid.encode()).hexdigest()[:8], 16) % SAMPLE_MOD == 0
            self.insample[sid] = v
        return v

    # ---------------- universe pass ----------------
    def _select(self, fundamental):
        d = self.time.date()
        wk = d.isocalendar()[:2]
        if wk == self.week:
            return []
        self.week = wk
        mo = (d.year, d.month)
        monthly = mo != self.month
        self.month = mo
        prim_by_co, rows = {}, []
        for x in fundamental:
            sid = str(x.symbol.id)
            tk = x.symbol.value
            sp = self.span.get(sid)
            if sp is None:
                self.span[sid] = [[tk, d, d]]
                self.first[sid] = d
            elif sp[-1][0] != tk:
                sp.append([tk, d, d])
            else:
                sp[-1][2] = d
            self.last[sid] = d
            smp = self._hs(sid)
            if smp and sid not in self.syms:
                self.syms[sid] = x.symbol
            if not x.has_fundamental_data:
                continue
            if smp:
                mc = self._g(lambda: float(x.market_cap), 0.0)
                so = self._g(lambda: float(x.company_profile.shares_outstanding), 0.0)
                fl = self._g(lambda: float(x.company_profile.float), 0.0)
                self.snap.setdefault(sid, []).append((d, mc, float(x.price), so, fl))
            if monthly:
                sr = self._g(lambda: x.security_reference)
                if sr is None:
                    continue
                typ = self._g(lambda: str(sr.security_type), "")
                sub = self._g(lambda: str(sr.common_share_sub_type), "").lower()
                pr = self._g(lambda: sr.is_primary_share, None)
                co = self._g(lambda: str(x.company_reference.company_id), "?")
                ctry = self._g(lambda: str(x.company_reference.country_id), "?")
                if typ == "ST00000001" and pr is not False:
                    prim_by_co[co] = 1
                rows.append((sid, typ, sub, pr, co, ctry))
        for sid, typ, sub, pr, co, ctry in rows:
            if typ != "ST00000001":
                c = "PREF_OTHER"
            elif "closed" in sub:
                c = "CEF"
            elif pr is False and ctry != "USA":
                c = "ADR_FOREIGN"
            elif pr is False and prim_by_co.get(co):
                c = "COMMON_SECONDARY"
            else:
                c = "COMMON"
            m = self.ms.setdefault(sid, {})
            m[c] = m.get(c, 0) + 1
        return []

    def _si_sel(self, data):
        d = self.time.date()
        seen = {}
        for x in data:
            sid = str(x.symbol.id)
            if not self._hs(sid):
                continue
            try:
                v = (float(x.short_interest), float(x.previous_short_interest), float(x.days_to_cover))
            except Exception:
                continue
            if sid in seen:
                seen[sid] = None if seen[sid] != v else v
            else:
                seen[sid] = v
        for sid, v in seen.items():
            self.si_last[sid] = d
            lst = self.si.setdefault(sid, [])
            amb = v is None
            if not lst or lst[-1][4] != amb or (not amb and lst[-1][1] != v[0]):
                lst.append((d, None, None, None, True) if amb else (d, v[0], v[1], v[2], False))
        return []

    # ---------------- classification (Stage 2 option A, v3) ----------------
    def _rule(self, tk):
        if re.fullmatch(r"Z[A-Z]ZZT", tk) or tk in TESTS:
            return "TEST"
        if tk.endswith(".WS") or ".WS." in tk or tk.endswith(".W"):
            return "WARRANT"
        if tk.endswith(".U") or tk.endswith(".UN"):
            return "UNIT"
        if tk.endswith(".R") or tk.endswith(".RT"):
            return "RIGHT"
        if re.fullmatch(r"[A-Z]{4}[A-Z]", tk):
            return {"W": "WARRANT", "R": "RIGHT", "U": "UNIT", "P": "PREFERRED", "O": "PREFERRED", "N": "PREFERRED", "M": "PREFERRED",
                    "Y": "ADR_FOREIGN", "F": "ADR_FOREIGN", "A": "COMMON_NOFUND", "B": "COMMON_NOFUND", "Q": "COMMON_NOFUND"}.get(tk[-1])
        return None

    def _classify(self, sid):
        spans = self.span[sid]
        tks = [s[0] for s in spans]
        if any(self._rule(t) == "TEST" for t in tks):
            return "TEST"
        m = self.ms.get(sid)
        if m:
            return max(m, key=lambda k: m[k])
        for t, a, z in spans:
            for st, en in self.sec_etf.get(t, []):
                if a <= en and z >= st:
                    return "ETF"
        hits = set()
        for t, a, z in spans:
            for st, en, ty in self.ncen.get(t, []):
                if a <= en and z >= st:
                    hits.add(ty)
        for ty in ("ETF", "CEF", "PREFERRED", "DEBT", "WARRANT"):
            if ty in hits:
                return ty
        if self.last[sid] >= _date(2025, 6, 1):
            t = spans[-1][0]
            if t in self.cur:
                return {"COMMON": "COMMON_NOFUND", "ADR": "ADR_FOREIGN", "OTHER": "UNRESOLVED"}.get(self.cur[t], self.cur[t])
        for t in reversed(tks):
            r = self._rule(t)
            if r:
                return r
        return "UNRESOLVED"

    # ---------------- panel construction ----------------
    def _hist(self, syms, mode):
        h = self.history(syms, datetime(2005, 10, 1), datetime(2026, 8, 28), Resolution.DAILY, fill_forward=False, data_normalization_mode=mode)
        out = {}
        if h is None or h.empty:
            return out
        for s in syms:
            try:
                df = h.loc[s]
            except Exception:
                continue
            if df is None or len(df) < 30:
                continue
            ds = np.array([(t.date() if t.hour >= 9 else (t - timedelta(days=1)).date()).toordinal() for t in df.index], dtype=np.int64)
            cols = [df[c].values.astype(float) if c in df.columns else np.zeros(len(df)) for c in ("open", "high", "low", "close", "volume")]
            out[s] = (ds, *cols)
        return out

    def _security(self, sid, cls, adj, raw):
        ds, o, hi, lo, c, v = adj
        rds, ro, rh, rl, rc, rv = raw
        if len(ds) != len(rds) or not np.array_equal(ds, rds):
            m = {d: i for i, d in enumerate(rds)}
            idx = np.array([m.get(d, -1) for d in ds])
            ok = idx >= 0
            ds, o, hi, lo, c, v = ds[ok], o[ok], hi[ok], lo[ok], c[ok], v[ok]
            rc, rv = rc[idx[ok]], rv[idx[ok]]
        n = len(ds)
        if n < 30:
            return None
        md = np.array([self.mdi.get(int(d), -1) for d in ds])
        okm = md >= 0
        if not okm.all():
            ds, o, hi, lo, c, v, rc, rv, md = ds[okm], o[okm], hi[okm], lo[okm], c[okm], v[okm], rc[okm], rv[okm], md[okm]
            n = len(ds)
            if n < 30:
                return None
        seg = np.concatenate([[0], np.cumsum(np.diff(md) > 11)])
        F = np.full((n, len(FEATS)), np.nan, dtype=np.float32)
        L = np.full((n, len(TGT)), -1, dtype=np.int8)
        aret = np.full(n, np.nan, dtype=np.float32)
        elig = np.zeros(n, dtype=bool)
        for sg in np.unique(seg):
            ii = np.nonzero(seg == sg)[0]
            if len(ii) < 25:
                continue
            a, b = ii[0], ii[-1] + 1
            self._seg_feats(F, L, aret, elig, a, b, ds, o, hi, lo, c, v, rc, rv, md)
        # PIT fundamentals (B / C)
        self._fund_feats(sid, F, ds, c, rc, elig)
        self._si_feats(sid, F, ds, elig)
        dsel = (ds >= START.toordinal()) & (ds <= DATA_END.toordinal())
        elig &= dsel & (rc > 0) & (c > 0)
        keep = np.nonzero(elig)[0]
        if len(keep) == 0:
            return None
        return ds[keep].astype(np.int32), F[keep], L[keep], aret[keep]

    def _seg_feats(self, F, L, aret, elig, a, b, ds, o, hi, lo, c, v, rc, rv, md):
        S = slice(a, b)
        C = pd.Series(c[S]); H = pd.Series(hi[S]); Lo = pd.Series(lo[S]); O = pd.Series(o[S]); V = pd.Series(v[S])
        RC = pd.Series(rc[S]); RV = pd.Series(rv[S]); MD = md[S]
        lc = np.log(C.where(C > 0))
        lr = lc.diff()
        for k, nm in ((1, "r1"), (2, "r2"), (3, "r3"), (5, "r5"), (10, "r10"), (20, "r20")):
            F[S, FI[nm]] = (lc - lc.shift(k)).values
        for k in (5, 10, 20, 60):
            F[S, FI[f"dhi{k}"]] = (C / H.rolling(k, min_periods=k).max() - 1).values
        for k in (5, 20, 60):
            F[S, FI[f"dlo{k}"]] = (C / Lo.rolling(k, min_periods=k).min() - 1).values
        up = (lr > 0).astype(int).values
        dn = (lr < 0).astype(int).values
        us = np.zeros(len(up)); dsk = np.zeros(len(up))
        for i in range(1, len(up)):
            us[i] = us[i - 1] + 1 if up[i] else 0
            dsk[i] = dsk[i - 1] + 1 if dn[i] else 0
        F[S, FI["up_streak"]] = us
        F[S, FI["dn_streak"]] = dsk
        F[S, FI["gap"]] = (O / C.shift(1) - 1).values
        F[S, FI["intraday"]] = (C / O - 1).values
        rng = (H - Lo)
        F[S, FI["clv"]] = np.where(rng > 0, (C - Lo) / rng.where(rng > 0), 0.5)
        for k in (5, 10, 20):
            F[S, FI[f"rv{k}"]] = lr.rolling(k, min_periods=k).std().values
        tr = pd.concat([H - Lo, (H - C.shift(1)).abs(), (Lo - C.shift(1)).abs()], axis=1).max(axis=1)
        F[S, FI["atr_p"]] = (tr.rolling(14, min_periods=14).mean() / C).values
        F[S, FI["range_p"]] = (rng / C).values
        F[S, FI["lpx"]] = np.log(RC.where(RC > 0)).values
        F[S, FI["lpx_prev"]] = np.log(RC.where(RC > 0)).shift(1).values
        F[S, FI["lvol"]] = np.log1p(RV).values
        for k in (5, 10, 20):
            base = V.shift(1).rolling(k, min_periods=k).mean()
            F[S, FI[f"rvol{k}"]] = (V / base.where(base > 0)).values
        DV = RC * RV
        F[S, FI["ldv"]] = np.log1p(DV).values
        bd = DV.shift(1).rolling(20, min_periods=20).mean()
        F[S, FI["rdv20"]] = (DV / bd.where(bd > 0)).values
        m5 = V.rolling(5, min_periods=5).mean(); m20 = V.rolling(20, min_periods=20).mean()
        F[S, FI["vtrend"]] = (m5 / m20.where(m20 > 0)).values
        F[S, FI["pv"]] = (lr * np.log(pd.Series(F[S, FI["rvol20"]]).clip(lower=1e-3))).values
        F[S, FI["zero20"]] = (V <= 0).astype(float).rolling(20, min_periods=1).max().values
        mdd = pd.Series(np.concatenate([[0], np.diff(MD) - 1])).clip(lower=0)
        F[S, FI["miss20"]] = (mdd.rolling(20, min_periods=1).sum() > 0).astype(float).values
        F[S, FI["pstrat"]] = np.where(rc[S] < 1, 0, np.where(rc[S] < 5, 1, 2))
        # fund-like PIT flag (trailing 120 sessions vs SPY on the same session dates)
        spy_r = np.log(self.spy_c[MD[1:]] / self.spy_c[MD[:-1]])
        sr = pd.Series(np.concatenate([[np.nan], spy_r]))
        cov = lr.rolling(120, min_periods=120).cov(sr)
        vs = sr.rolling(120, min_periods=120).var()
        vr = lr.rolling(120, min_periods=120).var()
        idio = np.sqrt(np.maximum(vr - cov * cov / vs.where(vs > 0), 0))
        jump = (lr.abs() > 0.08).astype(float).rolling(120, min_periods=120).mean()
        F[S, FI["fundlike"]] = np.where(idio.notna() & jump.notna(), ((idio < 0.006) & (jump <= 0.025)).astype(float), np.nan)
        # labels
        n = b - a
        oo, hh, cc = o[S], hi[S], c[S]
        endm = self.mdi[DATA_END.toordinal()] if DATA_END.toordinal() in self.mdi else 10 ** 9
        for h in HZ:
            m = n - h
            if m <= 0:
                continue
            ref = oo[1:m + 1]
            mh = np.lib.stride_tricks.sliding_window_view(hh[1:], h)[:m].max(axis=1)
            mc = np.lib.stride_tricks.sliding_window_view(cc[1:], h)[:m].max(axis=1)
            ec = cc[h:h + m]
            okr = (ref > 0) & (MD[h:h + m] <= endm)
            with np.errstate(divide="ignore", invalid="ignore"):
                ra, rb, rm = mh / ref - 1, ec / ref - 1, mc / ref - 1
            for t in TH:
                for f, rr in (("A", ra), ("B", rb), ("M", rm)):
                    col = np.where(okr, (rr >= t).astype(np.int8), -1)
                    L[a:a + m, TI[(f, h, t)]] = col
            if h == 10:
                aret[a:a + m] = np.where(okr, ra, np.nan)
        e = np.zeros(n, dtype=bool)
        e[20:] = True
        elig[a:b] = e

    def _fund_feats(self, sid, F, ds, c, rc, elig):
        sn = self.snap.get(sid)
        if not sn:
            return
        sd = np.array([s[0].toordinal() for s in sn])
        j = np.searchsorted(sd, ds, side="right") - 1
        ok = (j >= 0)
        jj = np.where(ok, j, 0)
        age = ds - sd[jj]
        ok &= age <= 40
        # adjusted close of the last session before the snapshot date (snapshot is taken at 00:00 of its date)
        k = np.searchsorted(ds, sd, side="left") - 1
        cs = np.where(k >= 0, c[np.maximum(k, 0)], np.nan)
        mc = np.array([s[1] for s in sn]); so = np.array([s[3] for s in sn]); fl = np.array([s[4] for s in sn]); px = np.array([s[2] for s in sn])
        with np.errstate(divide="ignore", invalid="ignore"):
            mct = mc[jj] * c / cs[jj]
            dst = mct / rc
        good = ok & (mc[jj] > 0) & np.isfinite(mct) & (mct > 0)
        F[:, FI["lmcap"]] = np.where(good, np.log(np.where(good, mct, 1)), np.nan)
        F[:, FI["lds"]] = np.where(good, np.log(np.where(good & (dst > 0), dst, 1)), np.nan)
        F[:, FI["mstrat"]] = np.where(good, np.select([mct < 5e7, mct < 3e8, mct < 2e9], [0, 1, 2], 3), np.nan)
        # DS change vs ~250 sessions earlier
        dsl = pd.Series(np.where(good, dst, np.nan))
        F[:, FI["dds250"]] = (dsl / dsl.shift(250) - 1).values
        # float (C): ratio Float / SO from the snapshot, age of the ratio, mismatch / implausible flags
        ratio = np.where((so > 0) & (fl > 0), fl / np.maximum(so, 1), np.nan)
        rage = np.zeros(len(sn))
        last_change = sd[0]
        for i in range(len(sn)):
            if i > 0 and not (np.isnan(ratio[i]) and np.isnan(ratio[i - 1])) and (np.isnan(ratio[i - 1]) or abs(ratio[i] / ratio[i - 1] - 1) > 1e-4):
                last_change = sd[i]
            rage[i] = sd[i] - last_change
        dss = np.where(px > 0, mc / np.maximum(px, 1e-9), np.nan)
        mism = np.zeros(len(sn))
        for i in range(1, len(sn)):
            k0, k1 = k[i - 1], k[i]
            if k0 >= 0 and k1 >= 0 and rc[k0] > 0 and rc[k1] > 0 and c[k0] > 0 and c[k1] > 0 and dss[i - 1] > 0 and dss[i] > 0:
                spl = (rc[k1] / c[k1]) / (rc[k0] / c[k0])          # >1 forward split, <1 reverse split (dividends ~1)
                exp = dss[i - 1] / spl
                if abs(spl - 1) > 0.1 and abs(dss[i] / exp - 1) > 0.5:
                    mism[i] = 1
        r_t = ratio[jj]
        fok = good & np.isfinite(r_t) & (ds >= _date(2011, 1, 1).toordinal())
        F[:, FI["float_ds"]] = np.where(fok, r_t, np.nan)
        F[:, FI["lfloat"]] = np.where(fok, np.log(np.where(fok, r_t * np.where(dst > 0, dst, 1), 1)), np.nan)
        F[:, FI["fratio_age"]] = np.where(fok, rage[jj] + age, np.nan)
        F[:, FI["ds_mismatch"]] = np.where(fok, mism[jj], np.nan)
        F[:, FI["f_implaus"]] = np.where(fok, ((r_t < 0.1) | (r_t > 1.01)).astype(float), np.nan)

    def _si_feats(self, sid, F, ds, elig):
        lst = self.si.get(sid)
        lo, hi = _date(2018, 1, 11).toordinal(), DATA_END.toordinal()
        inwin = (ds >= lo) & (ds <= hi)
        F[:, FI["si_miss"]] = np.where(inwin, 1.0, np.nan)
        if not lst:
            return
        sd = np.array([x[0].toordinal() for x in lst])
        j = np.searchsorted(sd, ds, side="right") - 1
        ok = inwin & (j >= 0)
        jj = np.where(j >= 0, j, 0)
        amb = np.array([x[4] for x in lst])[jj]
        siv = np.array([np.nan if x[1] is None else x[1] for x in lst])[jj]
        psi = np.array([np.nan if x[2] is None else x[2] for x in lst])[jj]
        dtc = np.array([np.nan if x[3] is None else x[3] for x in lst])[jj]
        age = ds - sd[jj]
        lastdel = self.si_last.get(sid, _date(1990, 1, 1)).toordinal()
        stale = (age > 35) | (ds > lastdel + 5)
        F[:, FI["si_amb"]] = np.where(ok, amb.astype(float), np.nan)
        F[:, FI["si_age"]] = np.where(ok, age, np.nan)
        use = ok & ~amb & ~stale & np.isfinite(siv)
        F[:, FI["si_miss"]] = np.where(inwin, (~use).astype(float), np.nan)
        lds = F[:, FI["lds"]]
        with np.errstate(divide="ignore", invalid="ignore"):
            F[:, FI["si_ds"]] = np.where(use & np.isfinite(lds), siv / np.exp(lds), np.nan)
            F[:, FI["dtc"]] = np.where(use, dtc, np.nan)
            F[:, FI["si_chg"]] = np.where(use & (psi > 0), siv / psi - 1, np.nan)

    def _build(self):
        S = self.set_runtime_statistic
        cls = {sid: self._classify(sid) for sid in self.span}
        self.cls_all = cls
        spy = Symbol.create("SPY", SecurityType.EQUITY, Market.USA)
        sp = self._hist([spy], DataNormalizationMode.ADJUSTED).get(spy)
        self.mdi = {int(d): i for i, d in enumerate(sp[0])}
        self.spy_c = sp[4]
        sample = [sid for sid in self.span if self._hs(sid) and cls[sid] not in NONA and sid in self.syms]
        self.nsample = len(sample)
        parts = []
        sids = []
        for a in range(0, len(sample), 60):
            ch = sample[a:a + 60]
            syms = [self.syms[s] for s in ch]
            try:
                fa = self._hist(syms, DataNormalizationMode.ADJUSTED)
                fr = self._hist(syms, DataNormalizationMode.RAW)
            except Exception as e:
                self.err.append("hist " + str(e)[:60])
                continue
            for s, sid in zip(syms, ch):
                if s not in fa or s not in fr:
                    continue
                try:
                    r = self._security(sid, cls[sid], fa[s], fr[s])
                except Exception as e:
                    self.err.append("sec " + str(e)[:60])
                    continue
                if r is None:
                    continue
                parts.append(r)
                sids.append(sid)
        self.sid_list = sids
        self.D = np.concatenate([p[0] for p in parts])
        self.F = np.concatenate([p[1] for p in parts])
        self.L = np.concatenate([p[2] for p in parts])
        self.R = np.concatenate([p[3] for p in parts])
        self.SID = np.concatenate([np.full(len(p[0]), i, dtype=np.int32) for i, p in enumerate(parts)])
        self.CLS = np.array([CI.get(cls[s], -1) for s in sids], dtype=np.int8)[self.SID]
        yrs = np.array([_date.fromordinal(int(x)).year for x in np.unique(self.D)])
        ymap = dict(zip(np.unique(self.D), yrs))
        self.Y = np.vectorize(ymap.get)(self.D).astype(np.int16)
        self.BL = np.array([_blk(y) for y in range(2005, 2027)], dtype=np.int8)[self.Y - 2005]
        # universe masks
        F = self.F
        unres = self.CLS == CI["UNRESOLVED"]
        self.U = {
            "A": np.ones(len(self.D), dtype=bool),
            "A-strict": ~unres,
            "A-exADR": self.CLS != CI["ADR_FOREIGN"],
            "A-fund": ~(unres & (F[:, FI["fundlike"]] == 1)),
            "B": np.isin(self.CLS, [CI["COMMON"], CI["COMMON_SECONDARY"]]) & np.isfinite(F[:, FI["lmcap"]]),
            "C": np.isin(self.CLS, [CI["COMMON"], CI["COMMON_SECONDARY"]]) & np.isfinite(F[:, FI["float_ds"]]),
            "D": F[:, FI["si_miss"]] == 0,
        }
        self.build_secs = _time.time() - self.t0

    # ---------------- helpers for output ----------------
    def lg(self, s):
        self.logbuf.append(s)

    def flush(self):
        out = "\n".join(self.logbuf)
        if len(out) > 9800:
            out = out[:9800] + "\n...TRUNCATED"
        for ln in out.split("\n"):
            self.log(ln)

    def on_end_of_algorithm(self):
        S = self.set_runtime_statistic
        try:
            self._build()
        except Exception as e:
            import traceback
            S("ERR build", (str(e) + " | " + traceback.format_exc()[-150:])[:198])
            return
        S("P0 panel", f"mode {MODE} | sample securities {self.nsample} with data {len(self.sid_list)} | rows {len(self.D)} | build {self.build_secs / 60:.0f} min")
        try:
            getattr(self, "mode_" + MODE.lower())()
        except Exception as e:
            import traceback
            S("ERR mode", (str(e) + " | " + traceback.format_exc()[-150:])[:198])
        if self.err:
            S("ERR misc", f"{len(self.err)}: " + " | ".join(self.err[:3])[:180])
        self.flush()

