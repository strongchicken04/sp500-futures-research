# region imports
from AlgorithmImports import *
from datetime import date as _date
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s3_modes_m import _split
from xup_s4_core import *
# endregion
#
# Stage 4E statistical robustness: paired bootstrap model comparisons, period stability (S4BOOT);
# Stage 4F calibration, ranking stability and a frozen calibration experiment (S4CALIB).

PAIRS = [("fullA RF", "volume LR"), ("fullA LR", "volume LR"), ("fullA GBM", "volume LR"), ("fullA RF", "price LR"), ("fullA LR", "price LR"),
         ("fullA GBM", "price LR"), ("fullA RF", "momentum LR"), ("fullA LR", "momentum LR"), ("fullA GBM", "momentum LR")]


class S4ModesD:

    def _evalset(self, lo, hi):
        prim = self.L[:, PRIMARY]
        m = self.U["A"] & (self.D >= lo) & (self.D <= hi) & (prim >= 0)
        return m, (prim[m] == 1).astype(np.float64)

    def _ap(self, s, y):
        o = np.argsort(-s, kind="mergesort")
        return self._ap_sorted(y[o], np.ones(len(y)))

    def mode_s4boot(self):
        S = self.set_runtime_statistic
        self._s4_finish()
        sc = self._s4_score(MN, True)
        nsec = int(self.SID.max()) + 1
        em, y = self._evalset(T0, T1)
        sid = self.SID[em]; D = self.D[em]
        du, di = np.unique(D, return_inverse=True)
        B1, B2 = 2000, 1000
        Ws = self._boot_W(B1, 11, nsec)
        Ws2 = self._boot_W(B2, 12, nsec); Wd2 = self._boot_W(B2, 13, len(du))
        srt, ysrt, ap0, flg, num, den = {}, {}, {}, {}, {}, {}
        for nm in MN:
            s = sc[nm][em]
            o = np.argsort(-s, kind="mergesort")
            srt[nm] = o
            ysrt[nm] = y[o]
            ap0[nm] = self._ap_sorted(y[o], np.ones(len(y)))
            pr = self._dayrank(s, D)
            for k in (0.01, 0.05, 0.10):
                f = (pr <= k).astype(np.float64)
                flg[(nm, k)] = f
                num[(nm, k)] = np.bincount(sid, weights=y * f, minlength=nsec)
                den[(nm, k)] = np.bincount(sid, weights=f, minlength=nsec)
        bap = {nm: np.empty(B1) for nm in MN}
        for b in range(B1):
            w = Ws[b][sid]
            for nm in MN:
                o = srt[nm]
                bap[nm][b] = self._ap_sorted(ysrt[nm], w[o])
        bap2 = {nm: np.empty(B2) for nm in MN}
        bp2 = {nm: np.empty(B2) for nm in MN}
        for b in range(B2):
            w = Ws2[b][sid] * Wd2[b][di]
            for nm in MN:
                o = srt[nm]
                bap2[nm][b] = self._ap_sorted(ysrt[nm], w[o])
                f = flg[(nm, 0.01)]
                bp2[nm][b] = (w * y * f).sum() / max((w * f).sum(), 1e-9)
        bP = {key: (Ws @ num[key]) / np.maximum(Ws @ den[key], 1e-9) for key in num}
        P0 = {key: num[key].sum() / max(den[key].sum(), 1e-9) for key in num}
        for nm in MN:
            S(f"M {SHORT[nm]}", (f"PR-AUC {ap0[nm]:.4f} {self._ci(bap[nm])} two-way {self._ci(bap2[nm])} | P@1 {100 * P0[(nm, 0.01)]:.2f}% {self._ci(100 * bP[(nm, 0.01)], 2)}"
                                 f" P@5 {100 * P0[(nm, 0.05)]:.2f}% {self._ci(100 * bP[(nm, 0.05)], 2)} P@10 {100 * P0[(nm, 0.10)]:.2f}%")[:198])
        for a, b in PAIRS:
            d = bap[a] - bap[b]
            parts = [f"dPR-AUC {ap0[a] - ap0[b]:+.4f} {self._ci(d)} p {self._pval(d):.4f}"]
            for k in (0.01, 0.05, 0.10):
                dk = 100 * (bP[(a, k)] - bP[(b, k)])
                parts.append(f"dP@{int(k * 100)} {100 * (P0[(a, k)] - P0[(b, k)]):+.2f}pp {self._ci(dk, 2)} p {self._pval(dk):.3f}")
            S(f"D {SHORT[a]}-{SHORT[b]}", " | ".join(parts)[:198])
        for a, b in PAIRS[:3]:
            d = bap2[a] - bap2[b]; d1 = 100 * (bp2[a] - bp2[b])
            S(f"D2 {SHORT[a]}-{SHORT[b]} two-way", f"security x date bootstrap ({B2}): dPR-AUC {self._ci(d)} p {self._pval(d):.4f} | dP@1 {self._ci(d1, 2)}pp p {self._pval(d1):.3f}")
        # event-level paired comparisons (E1 test events, S4-rank flags), bootstrap by security
        scored = self.U["A"] & (self.D >= SCORE_START)
        testrows = scored & (self.D >= T0) & (self.D <= T1)
        ev = self._s4_events(PRIMARY, "E1")
        aid, ain = self._s4_assoc(ev)
        tsel = (ev["date"] >= T0) & (ev["date"] <= T1)
        esid = ev["sid"][tsel]
        Ne = np.bincount(esid, minlength=nsec).astype(np.float64)
        bNe = Ws @ Ne
        capA, capP, eprec = {}, {}, {}
        fls = {}
        for nm in MN:
            fl, pr = self._s4_flags(sc[nm], scored)
            fls[nm] = fl
            for k in (0.01, 0.05, 0.10):
                c = self._s4_capture(ev, tsel, fl[k])
                capA[(nm, k)] = np.bincount(esid, weights=((c["pre"] + c["dur"]) > 0).astype(float), minlength=nsec)
                capP[(nm, k)] = np.bincount(esid, weights=(c["pre"] > 0).astype(float), minlength=nsec)
                sg = fl[k] & testrows
                eprec[(nm, k)] = (np.bincount(self.SID[sg], weights=(aid[sg] >= 0).astype(float), minlength=nsec), np.bincount(self.SID[sg], minlength=nsec).astype(float))
        for a, b in PAIRS:
            parts = []
            for k in (0.01, 0.05):
                da = 100 * (Ws @ (capA[(a, k)] - capA[(b, k)])) / np.maximum(bNe, 1e-9)
                dp = 100 * (Ws @ (capP[(a, k)] - capP[(b, k)])) / np.maximum(bNe, 1e-9)
                pa = 100 * (capA[(a, k)].sum() - capA[(b, k)].sum()) / Ne.sum(); pp = 100 * (capP[(a, k)].sum() - capP[(b, k)].sum()) / Ne.sum()
                ea = (Ws @ eprec[(a, k)][0]) / np.maximum(Ws @ eprec[(a, k)][1], 1e-9) - (Ws @ eprec[(b, k)][0]) / np.maximum(Ws @ eprec[(b, k)][1], 1e-9)
                e0 = eprec[(a, k)][0].sum() / max(eprec[(a, k)][1].sum(), 1) - eprec[(b, k)][0].sum() / max(eprec[(b, k)][1].sum(), 1)
                parts.append(f"k{int(k * 100)} dcap {pa:+.1f}pp {self._ci(da, 1)} dpre {pp:+.1f}pp {self._ci(dp, 1)} devprec {100 * e0:+.1f}pp {self._ci(100 * ea, 1)}")
            self.lg(f"DE {SHORT[a]}-{SHORT[b]} (E1 test events {int(Ne.sum())}): " + " | ".join(parts))
        for nm in ("fullA RF", "volume LR"):
            parts = []
            for k in (0.01, 0.05, 0.10):
                ca = 100 * (Ws @ capA[(nm, k)]) / np.maximum(bNe, 1e-9); cp = 100 * (Ws @ capP[(nm, k)]) / np.maximum(bNe, 1e-9)
                ep = 100 * (Ws @ eprec[(nm, k)][0]) / np.maximum(Ws @ eprec[(nm, k)][1], 1e-9)
                parts.append(f"k{int(k * 100)} cap {100 * capA[(nm, k)].sum() / Ne.sum():.1f}% {self._ci(ca, 1)} pre {100 * capP[(nm, k)].sum() / Ne.sum():.1f}% {self._ci(cp, 1)} evprec {100 * eprec[(nm, k)][0].sum() / max(eprec[(nm, k)][1].sum(), 1):.1f}% {self._ci(ep, 1)}")
            self.lg(f"EV {SHORT[nm]}: " + " | ".join(parts))
        # deduplication difference (RF, k 5): C10 vs N0, bootstrap by security
        for k in (0.01, 0.05):
            res = {}
            for rule in ("N0", "C10"):
                kept = self._s4_dedup(fls["fullA RF"][k], rule, aid, scored)
                sg = kept & testrows
                c = self._s4_capture(ev, tsel, kept)
                res[rule] = (np.bincount(self.SID[sg], weights=(aid[sg] >= 0).astype(float), minlength=nsec), np.bincount(self.SID[sg], minlength=nsec).astype(float),
                             np.bincount(esid, weights=((c["pre"] + c["dur"]) > 0).astype(float), minlength=nsec))
            pe = lambda r: (Ws @ r[0]) / np.maximum(Ws @ r[1], 1e-9)
            dprec = 100 * (pe(res["C10"]) - pe(res["N0"]))
            dcap = 100 * (Ws @ (res["C10"][2] - res["N0"][2])) / np.maximum(bNe, 1e-9)
            self.lg(f"DD RF k{int(k * 100)} C10-N0: devprec {100 * (res['C10'][0].sum() / max(res['C10'][1].sum(), 1) - res['N0'][0].sum() / max(res['N0'][1].sum(), 1)):+.1f}pp {self._ci(dprec, 1)}"
                    f" dcap {100 * (res['C10'][2].sum() - res['N0'][2].sum()) / Ne.sum():+.1f}pp {self._ci(dcap, 1)} | signals {int(res['N0'][1].sum())} -> {int(res['C10'][1].sum())}")
        # tradability category difference: RF top-1 % precision for price >= 1 vs price < 1 (S4-rank flags, valid test rows)
        prim = self.L[:, PRIMARY]
        f1 = fls["fullA RF"][0.01] & testrows & (prim >= 0)
        out = []
        for lab, m in (("px<1", self.PX < 1), ("px>=1", self.PX >= 1)):
            g = f1 & m
            out.append((np.bincount(self.SID[g], weights=(prim[g] == 1).astype(float), minlength=nsec), np.bincount(self.SID[g], minlength=nsec).astype(float)))
        pa = (Ws @ out[1][0]) / np.maximum(Ws @ out[1][1], 1e-9) - (Ws @ out[0][0]) / np.maximum(Ws @ out[0][1], 1e-9)
        self.lg(f"DT RF top-1% precision px>=1 minus px<1: {100 * (out[1][0].sum() / max(out[1][1].sum(), 1) - out[0][0].sum() / max(out[0][1].sum(), 1)):+.2f}pp {self._ci(100 * pa, 2)} (n {int(out[1][1].sum())} / {int(out[0][1].sum())})")
        # period stability
        Wp = self._boot_W(1000, 21, nsec)
        for tag, lo, hi in (("2021-22", T0, _date(2022, 12, 31).toordinal()), ("2023-25", _date(2023, 1, 1).toordinal(), T1), ("2026YTD", Y0, Y1)):
            m, yy = self._evalset(lo, hi)
            sd = self.SID[m]; dd = self.D[m]
            esel = (ev["date"] >= lo) & (ev["date"] <= hi)
            rowsp = scored & (self.D >= lo) & (self.D <= hi)
            res = {}
            for nm in ("fullA RF", "volume LR"):
                s = sc[nm][m]
                o = np.argsort(-s, kind="mergesort")
                apb = np.array([self._ap_sorted(yy[o], Wp[b][sd][o]) for b in range(300)])
                res[nm] = (self._ap_sorted(yy[o], np.ones(len(yy))), apb)
                pr = self._dayrank(s, dd)
                P = [100 * yy[pr <= k].mean() for k in (0.01, 0.05, 0.10)]
                c = self._s4_capture(ev, esel, fls[nm][0.05])
                sg = fls[nm][0.05] & rowsp
                f1 = fls[nm][0.01] & rowsp
                S(f"P {tag} {SHORT[nm]}", (f"base {100 * yy.mean():.3f}% n {len(yy)} secs {len(np.unique(sd))} | PR-AUC {res[nm][0]:.4f} {self._ci(apb)} | P@1/5/10 {P[0]:.2f}/{P[1]:.2f}/{P[2]:.2f}%"
                                           f" | E1 ev {int(esel.sum())} cap5 {100 * ((c['pre'] + c['dur']) > 0).mean():.1f}% pre5 {100 * (c['pre'] > 0).mean():.1f}% evprec5 {100 * (aid[sg] >= 0).mean():.1f}%"
                                           f" | top1 <$1 {100 * (self.PX[f1] < 1).mean():.0f}% $vol {np.median(self.DV[f1]) / 1e3:.0f}k")[:198])
            d = res["fullA RF"][1] - res["volume LR"][1]
            self.lg(f"P {tag} RF-VOL dPR-AUC {res['fullA RF'][0] - res['volume LR'][0]:+.4f} {self._ci(d)} p {self._pval(d):.3f} (300 security resamples)")
        self.lg("CHECK " + self.s4_check)

    # ---------------- calibration and ranking stability ----------------
    def _calstats(self, p, y, nb=10):
        p = np.clip(p, 1e-7, 1 - 1e-7)
        o = np.argsort(p, kind="mergesort")
        bins = np.array_split(o, nb)
        ece = sum(len(b) * abs(p[b].mean() - y[b].mean()) for b in bins) / len(p)
        ll = -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
        return dict(brier=np.mean((p - y) ** 2), ll=ll, ece=ece, cil=p.sum() / max(y.sum(), 1e-9), rel=[(p[b].mean(), y[b].mean()) for b in bins])

    def _caltxt(self, c):
        return f"Brier {c['brier'] * 1e3:.3f}e-3 logloss {c['ll']:.4f} ECE10 {100 * c['ece']:.3f}pp pred/obs {c['cil']:.2f}"

    def mode_s4calib(self):
        S = self.set_runtime_statistic
        self._s4_finish()
        names = ["fullA RF", "volume LR", "fullA LR", "fullA GBM", "price LR", "momentum LR"]
        sc = self._s4_score(names, True)
        em, y = self._evalset(T0, T1)
        D = self.D[em]; sid = self.SID[em]
        for nm in names[:4]:
            p = sc[nm][em]
            c = self._calstats(p, y); c20 = self._calstats(p, y, 20)
            top = np.argsort(-p)[:max(1, len(p) // 100)]
            S(f"K {SHORT[nm]}", f"{self._caltxt(c)} ECE20 {100 * c20['ece']:.3f}pp | top1% pred {100 * p[top].mean():.2f}% obs {100 * y[top].mean():.2f}% | AUC-free")
            self.lg(f"REL {SHORT[nm]} deciles pred/obs %: " + " ".join(f"{100 * a:.2f}/{100 * b:.2f}" for a, b in c["rel"]))
        # drift (RF): year, price, $vol, ATR tercile, SPY-vol regime tercile, monthly base-rate link
        p = sc["fullA RF"][em]
        yrs = self.Y[em]
        parts = []
        for yr in range(2021, 2026):
            m = yrs == yr
            parts.append(f"{yr} base {100 * y[m].mean():.2f}% pred/obs {p[m].sum() / max(y[m].sum(), 1):.2f} ECE {100 * self._calstats(p[m], y[m])['ece']:.2f}")
        em26, y26 = self._evalset(Y0, Y1)
        p26 = sc["fullA RF"][em26]
        parts.append(f"2026 base {100 * y26.mean():.2f}% pred/obs {p26.sum() / max(y26.sum(), 1):.2f}")
        S("K2 RF drift by year", " | ".join(parts)[:198])
        px, dv = self.PX[em], self.DV[em]
        self.lg("K3 RF pred/obs by price stratum: " + " ".join(f"{PX_LAB[i]} {p[self._strata_px(px) == i].sum() / max(y[self._strata_px(px) == i].sum(), 1):.2f}" for i in range(7)))
        self.lg("K3 RF pred/obs by $vol stratum: " + " ".join(f"{DV_LAB[i]} {p[self._strata_dv(dv) == i].sum() / max(y[self._strata_dv(dv) == i].sum(), 1):.2f}" for i in range(6)))
        devm = self.U["A"] & (self.D < T0)
        atr = self.F[:, FI["atr_p"]]
        cut = np.nanpercentile(atr[devm], [33.33, 66.67])
        at = np.searchsorted(cut, atr[em])
        self.lg("K3 RF pred/obs by ATR tercile (2006-2020 cut-offs): " + " ".join(f"T{j + 1} base {100 * y[at == j].mean():.2f}% {p[at == j].sum() / max(y[at == j].sum(), 1):.2f}" for j in range(3)))
        spl = np.log(self.spy_c)
        spr = np.concatenate([[np.nan], np.diff(spl)])
        vol20 = pd.Series(spr).rolling(20, min_periods=20).std().values
        rv = vol20[np.clip(self.MDX, 0, len(vol20) - 1)]
        dmask = devm & np.isfinite(rv)
        vc = np.nanpercentile(rv[dmask], [33.33, 66.67])
        rt = np.searchsorted(vc, rv[em])
        self.lg("K3 RF pred/obs by SPY 20d vol tercile (2006-2020 cut-offs): " + " ".join(f"T{j + 1} base {100 * y[rt == j].mean():.2f}% {p[rt == j].sum() / max(y[rt == j].sum(), 1):.2f} ECE {100 * self._calstats(p[rt == j], y[rt == j])['ece']:.2f}" for j in range(3) if (rt == j).any()))
        mo = (self.Y[em].astype(int) * 12 + pd.to_datetime(pd.Series(D).map(lambda x: _date.fromordinal(int(x)))).dt.month.values)
        g = pd.DataFrame({"m": mo, "p": p, "y": y}).groupby("m").sum()
        ratio = g["y"] / g["p"]
        cnt = pd.Series(mo).value_counts().sort_index()
        base = g["y"] / cnt.values
        self.lg(f"K3 RF monthly: corr(base rate, obs/pred) {base.corr(ratio):+.3f} over {len(g)} months; obs/pred p10/50/90 {q(ratio.values, (10, 50, 90))}")
        # ranking stability
        rng = np.random.RandomState(5)
        sub = rng.choice(len(y), size=min(300000, len(y)), replace=False)
        R = {nm: pd.Series(sc[nm][em][sub]).rank().values for nm in names}
        sp = [f"{SHORT[a]}-{SHORT[b]} {np.corrcoef(R[a], R[b])[0, 1]:.3f}" for i, a in enumerate(names) for b in names[i + 1:]]
        S("K4 Spearman pooled", " ".join(sp[:9])[:198])
        self.lg("K4 Spearman pooled (all pairs): " + " ".join(sp))
        prR = {nm: self._dayrank(sc[nm][em], D) for nm in names}
        self.lg(f"K4 within-day rank correlation RF-VOL {np.corrcoef(prR['fullA RF'], prR['volume LR'])[0, 1]:.3f} RF-LR {np.corrcoef(prR['fullA RF'], prR['fullA LR'])[0, 1]:.3f} RF-GBM {np.corrcoef(prR['fullA RF'], prR['fullA GBM'])[0, 1]:.3f}")
        scored = self.U["A"] & (self.D >= SCORE_START)
        testrows = scored & (self.D >= T0) & (self.D <= T1)
        fl = {nm: self._s4_flags(sc[nm], scored)[0] for nm in names}
        for k in (0.01, 0.05, 0.10):
            a = fl["fullA RF"][k] & testrows
            S(f"K5 top{int(k * 100)} overlap", ("share of RF selections also selected by: " + " ".join(f"{SHORT[nm]} {100 * (a & fl[nm][k]).sum() / max(a.sum(), 1):.0f}%" for nm in names[1:]))[:198])
        prev = np.zeros(len(self.D), dtype=bool)
        for nm in ("fullA RF", "volume LR"):
            for k in (0.01, 0.05):
                f = fl[nm][k]
                prev[:] = False
                prev[1:] = f[:-1] & (self.GS[1:] == self.GS[:-1])
                a = f & testrows
                self.lg(f"K6 persistence {SHORT[nm]} top{int(k * 100)}: share of selections whose previous session was also selected {100 * (a & prev).sum() / max(a.sum(), 1):.1f}%")
        pr = self._s4_flags(sc["fullA RF"], scored)[1]
        t1 = testrows & (self.D <= _date(2022, 12, 31).toordinal()); t2 = testrows & (self.D >= _date(2023, 1, 1).toordinal())
        m1 = pd.Series(1 - pr[t1]).groupby(self.SID[t1]).mean(); m2 = pd.Series(1 - pr[t2]).groupby(self.SID[t2]).mean()
        jj = m1.index.intersection(m2.index)
        self.lg(f"K6 RF security-level mean percentile, 2021-22 vs 2023-25: Spearman {m1[jj].rank().corr(m2[jj].rank()):.3f} over {len(jj)} securities")
        # is the RF advantage driven by a few securities / extreme rows?
        prim = self.L[:, PRIMARY]
        npos = np.bincount(sid, weights=y, minlength=int(self.SID.max()) + 1)
        order = np.argsort(-npos)
        nact = int((npos > 0).sum())
        parts = []
        for lab, m in (("all", np.ones(len(y), dtype=bool)), ("ex top1% secs", ~np.isin(sid, order[:max(1, nact // 100)])), ("ex top5% secs", ~np.isin(sid, order[:max(1, nact // 20)])),
                       ("ex px<0.10", px >= 0.10), ("px<1", px < 1), ("px>=1", px >= 1)):
            a = self._ap(sc["fullA RF"][em][m], y[m]); b = self._ap(sc["volume LR"][em][m], y[m])
            parts.append(f"{lab}: RF {a:.4f} VOL {b:.4f} d {a - b:+.4f} (pos {int(y[m].sum())})")
        S("K7 RF-VOL advantage", " | ".join(parts[:3])[:198])
        self.lg("K7 RF-VOL advantage: " + " | ".join(parts))
        # frozen calibration experiment: MODEL-split RF, Platt and isotonic fitted on validation 2017-2020 only
        from sklearn.linear_model import LogisticRegression
        from sklearn.isotonic import IsotonicRegression
        scM = self._s4_score(["fullA RF"], False, V0, Y1)["fullA RF"]
        vm, yv = self._evalset(V0, V1)
        pv = np.clip(scM[vm], 1e-7, 1 - 1e-7)
        lg = lambda x: np.log(np.clip(x, 1e-7, 1 - 1e-7) / (1 - np.clip(x, 1e-7, 1 - 1e-7)))
        platt = LogisticRegression(C=1e6, max_iter=500).fit(lg(pv)[:, None], yv)
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(pv, yv)
        for tag, (m, yy) in (("test 2021-25", (em, y)), ("2026 YTD", (em26, y26))):
            pm = scM[m]
            rows = [("TEST-refit RF raw", sc["fullA RF"][m]), ("MODEL RF raw", pm), ("MODEL RF + Platt(valid)", platt.predict_proba(lg(pm)[:, None])[:, 1]), ("MODEL RF + isotonic(valid)", iso.predict(pm))]
            for lab, pp in rows:
                self.lg(f"CAL {tag} {lab}: {self._caltxt(self._calstats(pp, yy))} | PR-AUC {self._ap(pp, yy):.4f}")
        S("K8 calibration experiment", f"Platt slope {platt.coef_[0][0]:.3f} intercept {platt.intercept_[0]:.3f} fitted on validation rows {len(yv)} (positives {int(yv.sum())}); results in log lines CAL")
        self.lg("CHECK " + self.s4_check)
