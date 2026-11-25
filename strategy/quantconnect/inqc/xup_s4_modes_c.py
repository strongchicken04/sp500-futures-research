# region imports
from AlgorithmImports import *
import hashlib, time as _time
from datetime import datetime as _dt, timedelta as _td, date as _date
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s3_modes_m import FULL_A
from xup_s4_core import *
# endregion
#
# Stage 4D: tradability strata (S4TRAD), conservative liquidity filters on validation + test (S4FILT),
# execution-data availability audit with minute trade / quote bars (S4EXEC). Aggregates only.


class S4ModesC:

    def _dec_cut(self, x, m):
        v = x[m & np.isfinite(x)]
        return np.percentile(v, np.arange(10, 100, 10)) if len(v) else np.zeros(9)

    def _tr_line(self, m, tv, testrows, fl, ev, tsel, aid, capd):
        prim = self.L[:, PRIMARY]
        rows = tv & m
        n = int(rows.sum()); pos = int((rows & (prim == 1)).sum())
        ps = []
        for k in (0.01, 0.05, 0.10):
            f = fl[k] & rows
            ps.append(f"{100 * (prim[f] == 1).mean() if f.any() else 0:.1f}")
        es = tsel & m[ev["start"]]
        ne = int(es.sum())
        cs = []
        for k in (0.01, 0.05, 0.10):
            c = capd[k]
            cs.append(f"{100 * c[es[tsel]].mean() if ne else 0:.0f}")
        ep = []
        for k in (0.01, 0.05):
            f = fl[k] & testrows & m
            ep.append(f"{100 * (aid[f] >= 0).mean() if f.any() else 0:.0f}")
        nsel = int((fl[0.01] & rows).sum())
        Fm = self.F[rows][:, [FI[c] for c in FULL_A]] if n else np.zeros((0, 1))
        miss = 100 * np.isnan(Fm).any(axis=1).mean() if n else 0
        mna = 100 * np.isnan(self.F[rows, FI["lmcap"]]).mean() if n else 0
        return (f"rows {n} pos {pos} base {100 * pos / max(n, 1):.2f}% ev {ne} | P@1/5/10 {'/'.join(ps)}% (sel1 {nsel}) | cap1/5/10 {'/'.join(cs)}% | evprec1/5 {'/'.join(ep)}%"
                f" | px {np.median(self.PX[rows]) if n else 0:.2f} $vol {np.median(self.DV[rows]) / 1e3 if n else 0:.0f}k | missFULL {miss:.1f}% mcapNA {mna:.0f}%")

    def mode_s4trad(self):
        S = self.set_runtime_statistic
        self._s4_finish()
        sc = self._s4_score(["fullA RF", "volume LR"], True)
        scored = self.U["A"] & (self.D >= SCORE_START)
        testrows = scored & (self.D >= T0) & (self.D <= T1)
        tv = testrows & (self.L[:, PRIMARY] >= 0)
        ev = self._s4_events(PRIMARY, "E1")
        aid, ain = self._s4_assoc(ev)
        tsel = (ev["date"] >= T0) & (ev["date"] <= T1)
        dev = self.U["A"] & (self.D < T0)
        atr, rv, mc = self.F[:, FI["atr_p"]], self.F[:, FI["rv20"]], self.F[:, FI["lmcap"]]
        ca, cr, cm = self._dec_cut(atr, dev), self._dec_cut(rv, dev), self._dec_cut(mc, dev)
        PX, DV = self.PX, self.DV
        pxs, dvs = self._strata_px(PX), self._strata_dv(DV)
        comb = [("px<1 & $vol<100k", (PX < 1) & (DV < 1e5)), ("px<1 & $vol>=100k", (PX < 1) & (DV >= 1e5)), ("px1-5 & $vol<100k", (PX >= 1) & (PX < 5) & (DV < 1e5)),
                ("px1-5 & $vol>=100k", (PX >= 1) & (PX < 5) & (DV >= 1e5)), ("px>=5 & $vol>=100k", (PX >= 5) & (DV >= 1e5)), ("px>=5 & $vol>=1M", (PX >= 5) & (DV >= 1e6))]
        for nm in ("fullA RF", "volume LR"):
            fl, pr = self._s4_flags(sc[nm], scored)
            capd = {}
            for k in (0.01, 0.05, 0.10):
                c = self._s4_capture(ev, tsel, fl[k])
                capd[k] = (c["pre"] + c["dur"]) > 0
            tg = SHORT[nm]
            if nm == "fullA RF":
                S("T0 RF all test", self._tr_line(np.ones(len(self.D), dtype=bool), tv, testrows, fl, ev, tsel, aid, capd)[:198])
                for i, lab in enumerate(PX_LAB):
                    S(f"T1 RF px {i} {lab}", self._tr_line(pxs == i, tv, testrows, fl, ev, tsel, aid, capd)[:198])
                for i, lab in enumerate(DV_LAB):
                    S(f"T2 RF $vol {i} {lab}", self._tr_line(dvs == i, tv, testrows, fl, ev, tsel, aid, capd)[:198])
                for nmx, x, cut in (("ATR", atr, ca), ("RV20", rv, cr), ("MCAP", mc, cm)):
                    d = np.where(np.isfinite(x), np.searchsorted(cut, x, side="right"), 10)
                    for j in range(11 if nmx == "MCAP" else 10):
                        lab = f"d{j + 1}" if j < 10 else "missing"
                        self.lg(f"T4 RF {nmx} {lab} (cut {f'{cut[j - 1]:.4g}' if 0 < j < 10 else '-'}): " + self._tr_line(d == j, tv, testrows, fl, ev, tsel, aid, capd))
            for lab, m in comb:
                S(f"T3 {tg} {lab}", self._tr_line(m, tv, testrows, fl, ev, tsel, aid, capd)[:198])
        self.lg("CHECK " + self.s4_check)

    def _filt_eval(self, sc, scored, prow, ev, aid, pmin, dmin, e0, e1):
        prim = self.L[:, PRIMARY]
        fm = (self.PX >= pmin) & (self.DV >= dmin)
        fl, pr = self._s4_flags(sc, scored & fm)
        rows = prow & fm
        valid = rows & (prim >= 0)
        nall = int(prow.sum())
        base = (prim[valid] == 1).mean() if valid.any() else np.nan
        P = [(prim[fl[k] & valid] == 1).mean() if (fl[k] & valid).any() else np.nan for k in (0.01, 0.05, 0.10)]
        es_all = (ev["date"] >= e0) & (ev["date"] <= e1)
        es = es_all & fm[ev["start"]]
        ne = int(es.sum())
        cap1 = self._s4_capture(ev, es, fl[0.01]); cap5 = self._s4_capture(ev, es, fl[0.05])
        c1 = ((cap1["pre"] + cap1["dur"]) > 0); c5 = ((cap5["pre"] + cap5["dur"]) > 0)
        sig1 = fl[0.01] & rows
        a1 = aid[sig1]
        return dict(rows=100 * rows.sum() / max(nall, 1), ev=100 * ne / max(es_all.sum(), 1), ne=ne, base=base, P=P,
                    cap1=c1.mean() if ne else np.nan, cap5=c5.mean() if ne else np.nan, pre5=(cap5["pre"] > 0).mean() if ne else np.nan,
                    prec1=(a1 >= 0).mean() if len(a1) else np.nan, sig1=int(sig1.sum()), ev1=len(np.unique(a1[a1 >= 0])),
                    px=np.median(self.PX[sig1]) if sig1.any() else np.nan, dv=np.median(self.DV[sig1]) if sig1.any() else np.nan)

    def _filt_txt(self, r):
        P = "/".join(f"{100 * x:.1f}" for x in r["P"])
        return (f"rows {r['rows']:.1f}% ev {r['ev']:.1f}% ({r['ne']}) base {100 * r['base']:.2f}% | P@1/5/10 {P}% lift1 {r['P'][0] / max(r['base'], 1e-9):.1f} | cap1/5 {100 * r['cap1']:.0f}/{100 * r['cap5']:.0f}% pre5 {100 * r['pre5']:.0f}%"
                f" evprec1 {100 * r['prec1']:.0f}% | sig1 {r['sig1']} ev1 {r['ev1']} | px {r['px']:.2f} $vol {r['dv'] / 1e3:.0f}k")

    def mode_s4filt(self):
        S = self.set_runtime_statistic
        self._s4_finish()
        ev = self._s4_events(PRIMARY, "E1")
        aid, ain = self._s4_assoc(ev)
        scV = self._s4_score(["fullA RF"], False, VSCORE, V1)["fullA RF"]
        scT = self._s4_score(["fullA RF"], True)["fullA RF"]
        A = self.U["A"]
        per = {"V": (scV, A & (self.D >= VSCORE) & (self.D <= V1), A & (self.D >= V0) & (self.D <= V1), V0, V1),
               "T": (scT, A & (self.D >= SCORE_START) & (self.D <= T1), A & (self.D >= T0) & (self.D <= T1), T0, T1)}
        grid = [(0, 0)] + [(p, 0) for p in (0.10, 0.50, 1, 2, 5)] + [(0, d) for d in (1e5, 2.5e5, 5e5, 1e6, 5e6)] + [(p, d) for p in (0.10, 0.50, 1, 2, 5) for d in (1e5, 2.5e5, 5e5, 1e6, 5e6)]
        res = {}
        for tag, (sc, scored, prow, e0, e1) in per.items():
            for p, d in grid:
                r = self._filt_eval(sc, scored, prow, ev, aid, p, d, e0, e1)
                res[(tag, p, d)] = r
                lab = f"p{p:g} d{d / 1e3:g}k"
                if tag == "T":
                    S(f"F T {lab}", self._filt_txt(r)[:198])
                else:
                    self.lg(f"F V {lab}: " + self._filt_txt(r))
        for seg, p, d in (("S0", 1, 1e5), ("S1", 1, 5e5), ("S2", 5, 1e6)):
            v, t = res[("V", p, d)], res[("T", p, d)]
            lv, lt = v["P"][0] / max(v["base"], 1e-9), t["P"][0] / max(t["base"], 1e-9)
            ok = (lv >= 3) and (lt >= 3) and (t["ne"] >= 100) and (t["cap5"] >= 0.30)
            S(f"C6 {seg} p>={p} $vol>={d / 1e3:g}k", f"lift1 valid {lv:.2f} test {lt:.2f} | test E1 events {t['ne']} | test cap5 {100 * t['cap5']:.1f}% | P@1 test {100 * t['P'][0]:.2f}% base {100 * t['base']:.3f}% -> {'PASS' if ok else 'FAIL'}")
        self.lg("CHECK " + self.s4_check)

    # ---------------- execution data availability (minute trade / quote bars) ----------------
    def _hsel(self, idx, n, salt):
        keys = [hashlib.md5(f"{salt}|{self.sid_list[self.SID[i]]}|{self.D[i]}".encode()).hexdigest() for i in idx]
        o = np.argsort(keys)
        return idx[o[:n]]

    def _minute(self, sym, d):
        t0 = _dt.combine(_date.fromordinal(int(d)), _dt.min.time())
        tb = self.history(sym, t0, t0 + _td(days=1), Resolution.MINUTE, fill_forward=False, extended_market_hours=True, data_normalization_mode=DataNormalizationMode.RAW)
        try:
            qb = self.history(QuoteBar, sym, t0, t0 + _td(days=1), Resolution.MINUTE, fill_forward=False, extended_market_hours=True)
        except Exception:
            qb = None
        return tb, qb

    def _mstats(self, tb, qb):
        out = {}
        if tb is None or len(tb) == 0:
            return out
        df = tb.reset_index() if "time" not in getattr(tb, "columns", []) else tb
        tcol = "time" if "time" in df.columns else df.columns[1]
        tt = pd.to_datetime(df[tcol])
        mins = tt.dt.hour * 60 + tt.dt.minute
        reg = (mins > 570) & (mins <= 960)
        pre = mins <= 570
        post = mins > 960
        hi, cl, vo = df["high"].values, df["close"].values, df["volume"].values
        out["n_reg"] = int(reg.sum()); out["n_pre"] = int(pre.sum()); out["n_post"] = int(post.sum())
        if reg.any():
            hr = hi[reg.values].max()
            out["dv_reg"] = float((cl[reg.values] * vo[reg.values]).sum())
            f30 = reg & (mins <= 600)
            out["dv_30"] = float((cl[f30.values] * vo[f30.values]).sum())
            out["ext_high"] = float(hi[(pre | post).values].max() > hr * 1.001) if (pre | post).any() else 0.0
            out["near_hi"] = int((hi[reg.values] >= 0.95 * hr).sum())
            vr = vo[reg.values]
            out["vol_at_hi"] = float(vr[cl[reg.values] >= 0.9 * hr].sum() / max(vr.sum(), 1e-9))
        if qb is not None and len(qb) > 0:
            dq = qb.reset_index()
            qt = pd.to_datetime(dq["time"]) if "time" in dq.columns else pd.to_datetime(dq.iloc[:, 1])
            qm = qt.dt.hour * 60 + qt.dt.minute
            qreg = ((qm > 570) & (qm <= 960)).values
            if "bidclose" in dq.columns and "askclose" in dq.columns:
                b, a = dq["bidclose"].values, dq["askclose"].values
                ok = qreg & (b > 0) & (a > 0) & (a >= b)
                out["n_q"] = int(ok.sum())
                if ok.any():
                    sp = (a[ok] - b[ok]) / ((a[ok] + b[ok]) / 2)
                    out["spr"] = float(np.median(sp))
                    f30 = ok & (qm.values <= 600)
                    out["spr30"] = float(np.median((a[f30] - b[f30]) / ((a[f30] + b[f30]) / 2))) if f30.any() else np.nan
                    out["spr5"] = float((sp > 0.05).mean())
        return out

    def mode_s4exec(self):
        S = self.set_runtime_statistic
        self._s4_finish()
        t_start = _time.time()
        sc = self._s4_score(["fullA RF"], True)["fullA RF"]
        scored = self.U["A"] & (self.D >= SCORE_START)
        testrows = scored & (self.D >= T0) & (self.D <= T1)
        fl, pr = self._s4_flags(sc, scored)
        nxt_ok = np.zeros(len(self.D), dtype=bool)
        nxt_ok[:-1] = self.GS[1:] == self.GS[:-1]
        sig_idx = np.nonzero(fl[0.01] & testrows & nxt_ok)[0]
        ev3 = self._s4_events(PRIMARY, "E3")
        t3 = (ev3["date"] >= T0) & (ev3["date"] <= T1)
        mv_idx = ev3["start"][t3]
        ctl_idx = np.nonzero(testrows & ~fl[0.10] & nxt_ok)[0]
        samples = [("SIGNAL entry day t+1", self._hsel(sig_idx, 120, "s"), 1), ("MOVE day (E3)", self._hsel(mv_idx, 120, "m"), 0), ("CONTROL entry day t+1", self._hsel(ctl_idx, 60, "c"), 1)]
        S("X0 samples", f"RF top-1% test signals {len(sig_idx)}, E3 test move days {len(mv_idx)}, control rows {len(ctl_idx)}; hash samples 120 / 120 / 60; minute history with extended hours, RAW")
        errs = {}
        for name, idx, off in samples:
            rec = []
            for i in idx:
                if _time.time() - t_start > 40 * 60:
                    break
                j = i + off
                sym = self.syms.get(self.sid_list[self.SID[j]])
                if sym is None:
                    errs["nosym"] = errs.get("nosym", 0) + 1
                    continue
                try:
                    tb, qb = self._minute(sym, self.D[j])
                    st = self._mstats(tb, qb)
                    st["px"] = self.PX[j]
                    rec.append(st)
                except Exception as e:
                    kname = type(e).__name__
                    errs[kname] = errs.get(kname, 0) + 1
            n = len(rec)
            g = lambda k: np.array([r.get(k, np.nan) for r in rec], dtype=float)
            has_t = np.array([r.get("n_reg", 0) > 0 for r in rec]); has_q = np.array([r.get("n_q", 0) > 0 for r in rec]); has_p = np.array([r.get("n_pre", 0) > 0 for r in rec])
            S(f"X1 {name}", (f"done {n}/{len(idx)} | minute trades {int(has_t.sum())} premarket bars {int(has_p.sum())} quotes {int(has_q.sum())} | reg minutes with trades {q(g('n_reg'), (25, 50, 75))}"
                             f" | $vol reg {q(g('dv_reg') / 1e3, (25, 50, 75))}k first30 {q(g('dv_30') / 1e3, (25, 50, 75))}k")[:198])
            S(f"X2 {name}", (f"spread med (quote minutes) p25/50/75 {q(100 * g('spr'), (25, 50, 75))}% first30 {q(100 * g('spr30'), (25, 50, 75))}% | share min spread>5% med {np.nanmedian(g('spr5')) * 100 if has_q.any() else np.nan:.0f}%"
                             f" | high outside reg hours {np.nanmean(g('ext_high')) * 100:.0f}% | minutes >=95% of high med {np.nanmedian(g('near_hi')):.0f} | vol share at >=90% of high med {100 * np.nanmedian(g('vol_at_hi')):.0f}%")[:198])
            pxs = g("px")
            for lo_, hi_, lab in ((0, 1, "<$1"), (1, 5, "$1-5"), (5, 1e9, ">=$5")):
                m = (pxs >= lo_) & (pxs < hi_)
                if m.any():
                    self.lg(f"X3 {name} {lab}: n {int(m.sum())} quotes {int(has_q[m].sum())} spread med {np.nanmedian(100 * g('spr')[m]):.2f}% first30 {np.nanmedian(100 * g('spr30')[m]):.2f}% $vol reg med {np.nanmedian(g('dv_reg')[m]) / 1e3:.0f}k minutes med {np.nanmedian(g('n_reg')[m]):.0f}")
        S("X4 errors", ("none" if not errs else " ".join(f"{k} {v}" for k, v in errs.items())) + f" | runtime {(_time.time() - t_start) / 60:.1f} min")
        self.lg("CHECK " + self.s4_check)
