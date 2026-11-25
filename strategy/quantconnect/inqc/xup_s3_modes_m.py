# region imports
from AlgorithmImports import *
from datetime import date as _date, timedelta
import numpy as np
import pandas as pd
from xup_s3_const import *
# endregion
#
# Stage 3D-G: predictive models. MODEL = fit on development, evaluate on validation (selection allowed here only).
# TEST = frozen specification (FROZEN below), refit on development + validation, evaluate 2021-2025 ONCE and 2026 YTD
# separately. Universes / splits per research/extreme_upside/stage3/protocol.md.

G_PRICE = ["lpx", "lpx_prev", "pstrat"]
G_MOM = ["r1", "r2", "r3", "r5", "r10", "r20", "dhi5", "dhi10", "dhi20", "dhi60", "dlo5", "dlo20", "dlo60", "up_streak", "dn_streak"]
G_VOL = ["lvol", "rvol5", "rvol10", "rvol20", "ldv", "rdv20", "vtrend", "pv", "zero20", "miss20"]
G_VLT = ["rv5", "rv10", "rv20", "atr_p", "range_p", "gap", "intraday", "clv"]
G_FUND = ["lmcap", "lds", "dds250", "mstrat"]
G_SI = ["si_ds", "dtc", "si_chg", "si_age", "si_amb"]
G_FLT = ["lfloat", "float_ds", "fratio_age", "ds_mismatch", "f_implaus"]
FULL_A = G_PRICE + G_MOM + G_VOL + G_VLT

# (name, universe, features, model, split) ; split: "std" = train 2006-2016 / valid 2017-2020,
# "c" = train 2011-2016 / valid 2017-2020, "d" = train 2018-01-11..2019-12 / valid 2020 (SI exists only from 2018)
SPECS = [
    ("uncond", "A", [], "const", "std"),
    ("price LR", "A", G_PRICE, "lr", "std"),
    ("momentum LR", "A", G_MOM, "lr", "std"),
    ("volume LR", "A", G_VOL, "lr", "std"),
    ("price+mom LR", "A", G_PRICE + G_MOM, "lr", "std"),
    ("price+vol LR", "A", G_PRICE + G_VOL, "lr", "std"),
    ("price+volat LR", "A", G_PRICE + G_VLT, "lr", "std"),
    ("fullA LR", "A", FULL_A, "lr", "std"),
    ("fullA L2", "A", FULL_A, "l2", "std"),
    ("fullA RF", "A", FULL_A, "rf", "std"),
    ("fullA GBM", "A", FULL_A, "gbm", "std"),
    ("mcap+price+vol LR [B]", "B", G_FUND + G_PRICE + G_VOL, "lr", "std"),
    ("fullA GBM [B]", "B", FULL_A, "gbm", "std"),
    ("full+fund GBM [B]", "B", FULL_A + G_FUND, "gbm", "std"),
    ("fullA GBM [D]", "D", FULL_A, "gbm", "d"),
    ("full+SI GBM [D]", "D", FULL_A + G_SI, "gbm", "d"),
    ("fullA GBM [C]", "C", FULL_A + G_FUND, "gbm", "c"),
    ("full+float GBM [C]", "C", FULL_A + G_FUND + G_FLT, "gbm", "c"),
]
# Amendment 3 (protocol.md), committed before TEST: all 18 specifications ran in MODEL v1 -> all are frozen.
FROZEN = [sp[0] for sp in SPECS]
L2_C_FROZEN = 0.1   # chosen on validation in MODEL v1


def _split(alg, sp, test=False):
    d = alg.D
    o = lambda y, m, dd: _date(y, m, dd).toordinal()
    if not test:
        if sp == "std":
            tr = (d >= o(2006, 2, 1)) & (d <= o(2016, 12, 31) - 60)
            va = (d >= o(2017, 1, 1)) & (d <= o(2020, 12, 31))
        elif sp == "c":
            tr = (d >= o(2011, 1, 1)) & (d <= o(2016, 12, 31) - 60)
            va = (d >= o(2017, 1, 1)) & (d <= o(2020, 12, 31))
        else:
            tr = (d >= o(2018, 1, 11)) & (d <= o(2019, 12, 31) - 60)
            va = (d >= o(2020, 1, 1)) & (d <= o(2020, 12, 31))
        return tr, va, None
    lo = {"std": o(2006, 2, 1), "c": o(2011, 1, 1), "d": o(2018, 1, 11)}[sp]
    tr = (d >= lo) & (d <= o(2020, 12, 31) - 60)
    te = (d >= o(2021, 1, 1)) & (d <= o(2025, 12, 31))
    ytd = (d >= o(2026, 1, 1)) & (d <= DATA_END.toordinal())
    return tr, te, ytd


class ModesM:

    def _prep(self, X, st=None):
        """winsorise at train p1/p99, median-impute, missing indicators for columns with NaN in train, standardise"""
        if st is None:
            lo = np.nanpercentile(X, 1, axis=0); hi = np.nanpercentile(X, 99, axis=0); med = np.nanmedian(X, axis=0)
            lo = np.where(np.isfinite(lo), lo, 0); hi = np.where(np.isfinite(hi), hi, 0); med = np.where(np.isfinite(med), med, 0)
            miss = np.isnan(X).any(axis=0)
            Z = np.clip(np.where(np.isnan(X), med, X), lo, hi)
            mu = Z.mean(axis=0); sd = Z.std(axis=0) + 1e-9
            st = (lo, hi, med, miss, mu, sd)
        lo, hi, med, miss, mu, sd = st
        Z = (np.clip(np.where(np.isnan(X), med, X), lo, hi) - mu) / sd
        if miss.any():
            Z = np.hstack([Z, np.isnan(X[:, miss]).astype(np.float32)])
        return Z.astype(np.float32), st

    def _fit(self, kind, X, y, w, Xh=None, yh=None):
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
        if kind == "lr":
            Z, st = self._prep(X)
            m = LogisticRegression(C=1e4, max_iter=400).fit(Z, y, sample_weight=w)
            return lambda A: m.predict_proba(self._prep(A, st)[0])[:, 1], m
        if kind == "l2":
            Z, st = self._prep(X)
            best = None
            if Xh is None:   # TEST: C fixed to the value chosen on validation (L2_C_FROZEN)
                m = LogisticRegression(C=L2_C_FROZEN, max_iter=400).fit(Z, y, sample_weight=w)
                self.l2_C = L2_C_FROZEN
                return lambda A: m.predict_proba(self._prep(A, st)[0])[:, 1], m
            for C in (0.001, 0.01, 0.1, 1.0):
                m = LogisticRegression(C=C, max_iter=400).fit(Z, y, sample_weight=w)
                if Xh is not None:
                    from sklearn.metrics import average_precision_score
                    ap = average_precision_score(yh, m.predict_proba(self._prep(Xh, st)[0])[:, 1])
                    if best is None or ap > best[0]:
                        best = (ap, C, m)
            self.l2_C = best[1]
            m = best[2]
            return lambda A: m.predict_proba(self._prep(A, st)[0])[:, 1], m
        if kind == "rf":
            Z, st = self._prep(X)
            m = RandomForestClassifier(n_estimators=200, min_samples_leaf=200, max_features="sqrt", max_samples=0.5, n_jobs=1, random_state=7).fit(Z, y, sample_weight=w)
            return lambda A: m.predict_proba(self._prep(A, st)[0])[:, 1], m
        if kind == "gbm":
            # time-ordered internal holdout = last 10% of the training rows by date (rows arrive date-sorted per call)
            n = len(y)
            cut = int(n * 0.9)
            m = HistGradientBoostingClassifier(learning_rate=0.05, max_leaf_nodes=31, l2_regularization=0.1, max_iter=25, warm_start=True, early_stopping=False, random_state=7)
            best, best_it, bad = 1e9, 25, 0
            for it in range(25, 525, 25):
                m.set_params(max_iter=it)
                m.fit(X[:cut], y[:cut], sample_weight=w[:cut])
                p = np.clip(m.predict_proba(X[cut:])[:, 1], 1e-6, 1 - 1e-6)
                ll = -np.average(y[cut:] * np.log(p) + (1 - y[cut:]) * np.log(1 - p), weights=w[cut:])
                if ll < best - 1e-6:
                    best, best_it, bad = ll, it, 0
                else:
                    bad += 1
                    if bad >= 3:
                        break
            m2 = HistGradientBoostingClassifier(learning_rate=0.05, max_leaf_nodes=31, l2_regularization=0.1, max_iter=best_it, random_state=7).fit(X, y, sample_weight=w)
            self.gbm_iters = best_it
            return lambda A: m2.predict_proba(A)[:, 1], m2
        raise ValueError(kind)

    def _train_rows(self, mask, li):
        rng = np.random.RandomState(7)
        idx = np.nonzero(mask & (self.L[:, li] >= 0))[0]
        y = (self.L[idx, li] == 1)
        keep = y | (rng.rand(len(idx)) < 0.10)
        idx = idx[keep]
        o = np.argsort(self.D[idx], kind="mergesort")
        idx = idx[o]
        y = (self.L[idx, li] == 1).astype(int)
        w = np.where(y == 1, 1.0, 10.0)
        return idx, y, w

    def _metrics(self, s, y, d, sid, boot=60):
        """PR-AUC, precision / recall at top 1/5/10% ranked within each day (pooled), lift, Brier, ROC-AUC, CIs"""
        from sklearn.metrics import roc_auc_score
        n, pos = len(y), int(y.sum())
        base = pos / max(n, 1)
        pr = self._dayrank(s, d)
        o = np.argsort(-s, kind="mergesort")
        ys = y[o].astype(np.float64)

        def ap_w(w):
            wy = w * ys
            tp = np.cumsum(wy); cnt = np.cumsum(w)
            return float((wy * tp / np.maximum(cnt, 1e-9)).sum() / max(wy.sum(), 1e-9))
        ap = ap_w(np.ones(n))
        out = dict(n=n, pos=pos, base=base, ap=ap)
        for k in (0.01, 0.05, 0.10):
            sel = pr <= k
            out[f"p{int(k * 100)}"] = y[sel].mean() if sel.any() else 0
            out[f"r{int(k * 100)}"] = y[sel].sum() / max(pos, 1)
            out[f"n{int(k * 100)}"] = int(sel.sum()); out[f"k{int(k * 100)}"] = int(y[sel].sum())
        out["brier"] = float(np.mean((s - y) ** 2))
        out["auc"] = roc_auc_score(y, s) if 0 < pos < n else np.nan
        rng = np.random.RandomState(99)
        W = rng.poisson(1.0, size=(boot, int(sid.max()) + 1)).astype(np.float64)
        sel1 = pr <= 0.01
        bap, bp1 = [], []
        for i in range(boot):
            w = W[i][sid]
            bap.append(ap_w(w[o]))
            bp1.append((w[sel1] * y[sel1]).sum() / max(w[sel1].sum(), 1e-9))
        out["ap_ci"] = (np.percentile(bap, 2.5), np.percentile(bap, 97.5))
        out["p1_ci"] = (np.percentile(bp1, 2.5), np.percentile(bp1, 97.5))
        return out

    def _dayrank(self, s, d):
        """within-day rank r (1 = highest score, ties by row order) scaled so that 'top k' = r <= ceil(k * n_day):
        returns (r - 1) / n_day + tiny, so pr <= k selects exactly ceil(k * n_day) rows per day (at least 1)"""
        df = pd.DataFrame({"s": s, "d": d})
        r = df.groupby("d")["s"].rank(ascending=False, method="first").values
        n = df.groupby("d")["s"].transform("size").values
        return (r - 1) / n + 1e-12

    def _calib(self, s, y):
        b = np.minimum((pd.Series(s).rank(method="first").values - 1) * 10 // len(s), 9).astype(int)
        return " ".join(f"{np.mean(s[b == k]) * 100:.2f}/{np.mean(y[b == k]) * 100:.2f}" for k in range(10))

    def _run_specs(self, names, test=False):
        S = self.set_runtime_statistic
        li = PRIMARY
        results = {}
        for spec in SPECS:
            if names is not None and spec[0] not in names:
                continue
            import time as _t
            t0 = _t.time()
            try:
                self._one_spec(spec, test, results)
                if not test:
                    self.lg(f"TIME {spec[0]} {(_t.time() - t0) / 60:.1f} min")
            except Exception as e:
                import traceback
                S(f"{'T' if test else 'M'} {spec[0]}", ("ERROR " + str(e) + " | " + traceback.format_exc()[-120:])[:198])
        return results

    def _one_spec(self, spec, test, results):
        S = self.set_runtime_statistic
        li = PRIMARY
        name, uni, feats, kind, sp = spec
        if True:
            tr, ev, ytd = _split(self, sp, test)
            um = self.U[uni]
            idx, y, w = self._train_rows(um & tr, li)
            evm = um & ev & (self.L[:, li] >= 0)
            ye = (self.L[evm, li] == 1).astype(int)
            if kind == "const":
                f = lambda A, r=np.average(y, weights=w): np.full(len(A), r)
                X = np.zeros((len(idx), 1)); cols = [0]
            else:
                cols = [FI[c] for c in feats]
                X = self.F[idx][:, cols]
                Xh = self.F[evm][:, cols] if (kind == "l2" and not test) else None
                f, mdl = self._fit(kind, X, y, w, Xh, ye if Xh is not None else None)
                if kind == "gbm" and name == "fullA GBM":
                    self.gbm_main = (f, cols)
            se = f(self.F[evm][:, cols]) if kind != "const" else f(np.zeros(int(evm.sum())))
            mt = self._metrics(se, ye, self.D[evm], self.SID[evm])
            results[name] = (mt, se, evm)
            extra = f" C={self.l2_C}" if kind == "l2" else (f" it={self.gbm_iters}" if kind == "gbm" else "")
            S(f"{'T' if test else 'M'} {name}", (f"n {mt['n'] // 1000}k pos {mt['pos']} base {mt['base'] * 100:.3f}% | PR-AUC {mt['ap']:.4f} [{mt['ap_ci'][0]:.4f},{mt['ap_ci'][1]:.4f}] lift {mt['ap'] / max(mt['base'], 1e-9):.1f}"
                                                    f" | P@1% {mt['p1'] * 100:.2f}% [{mt['p1_ci'][0] * 100:.2f},{mt['p1_ci'][1] * 100:.2f}] ({mt['k1']}/{mt['n1']}) P@5 {mt['p5'] * 100:.2f} P@10 {mt['p10'] * 100:.2f}"
                                                    f" | R@1/5/10 {mt['r1'] * 100:.0f}/{mt['r5'] * 100:.0f}/{mt['r10'] * 100:.0f}% | Brier {mt['brier'] * 1e3:.3f}e-3 AUC {mt['auc']:.3f}{extra}")[:198])
            if kind in ("gbm", "l2", "lr") and name.startswith(("fullA", "full+")):
                self.lg(f"CALIB {name} (pred%/obs% by predicted decile): " + self._calib(se, ye))
            if test and ytd is not None and kind != "const":
                ym = um & ytd & (self.L[:, li] >= 0)
                if ym.sum() > 1000:
                    yy = (self.L[ym, li] == 1).astype(int)
                    m2 = self._metrics(f(self.F[ym][:, cols]), yy, self.D[ym], self.SID[ym], boot=30)
                    self.lg(f"YTD2026 {name}: n {m2['n']} pos {m2['pos']} base {m2['base'] * 100:.3f}% PR-AUC {m2['ap']:.4f} [{m2['ap_ci'][0]:.4f},{m2['ap_ci'][1]:.4f}] P@1% {m2['p1'] * 100:.2f}% ({m2['k1']}/{m2['n1']}) R@10 {m2['r10'] * 100:.0f}% AUC {m2['auc']:.3f}")

    def _importance(self, test=False):
        """permutation importance (PR-AUC drop) of the main GBM on a fixed evaluation subsample"""
        from sklearn.metrics import average_precision_score
        if not hasattr(self, "gbm_main"):
            return
        f, cols = self.gbm_main
        tr, ev, _ = _split(self, "std", test)
        evm = self.U["A"] & ev & (self.L[:, PRIMARY] >= 0)
        idx = np.nonzero(evm)[0]
        rng = np.random.RandomState(5)
        y = self.L[idx, PRIMARY] == 1
        sel = idx[y | (rng.rand(len(idx)) < 0.15)]
        X = self.F[sel][:, cols].copy(); yy = (self.L[sel, PRIMARY] == 1).astype(int)
        base = average_precision_score(yy, f(X))
        imp = []
        for j, c in enumerate(cols):
            Xp = X.copy(); Xp[:, j] = Xp[rng.permutation(len(Xp)), j]
            imp.append((base - average_precision_score(yy, f(Xp)), FEATS[c]))
        imp.sort(reverse=True)
        self.lg("IMPORTANCE fullA GBM (PR-AUC drop, subsample): " + " ".join(f"{n} {v:.4f}" for v, n in imp[:15]))

    def _secondary(self, test=False):
        """main GBM spec refit for selected secondary endpoints (same features, A)"""
        S = self.set_runtime_statistic
        tr, ev, _ = _split(self, "std", test)
        um = self.U["A"]
        cols = [FI[c] for c in FULL_A]
        parts = []
        for tg in (("A", 5, 0.5), ("A", 20, 2.0), ("B", 10, 1.0), ("M", 10, 1.0), ("A", 10, 0.5)):
            li = TI[tg]
            idx, y, w = self._train_rows(um & tr, li)
            f, _ = self._fit("gbm", self.F[idx][:, cols], y, w)
            evm = um & ev & (self.L[:, li] >= 0)
            ye = (self.L[evm, li] == 1).astype(int)
            mt = self._metrics(f(self.F[evm][:, cols]), ye, self.D[evm], self.SID[evm], boot=30)
            parts.append(f"{tg[0]}{tg[1]}/{int(tg[2] * 100)}: base {mt['base'] * 100:.2f}% AP {mt['ap']:.3f} (x{mt['ap'] / max(mt['base'], 1e-9):.1f}) P@1 {mt['p1'] * 100:.1f}% ({mt['k1']}) AUC {mt['auc']:.3f}")
        self.lg(("TEST " if test else "VALID ") + "secondary endpoints, fullA GBM: " + " | ".join(parts))

    def _tradability(self, res):
        """top 1% (within day) of the main GBM: price, dollar volume, flags, confirmation by B / B-max"""
        if "fullA GBM" not in res:
            return
        mt, se, evm = res["fullA GBM"]
        pr = self._dayrank(se, self.D[evm])
        sel = np.nonzero(evm)[0][pr <= 0.01]
        F = self.F
        px = np.exp(F[sel, FI["lpx"]]); dv = np.expm1(F[sel, FI["ldv"]])
        y = self.L[sel, PRIMARY] == 1
        b = self.L[sel, TI[("B", 10, 1.0)]] == 1; bm = self.L[sel, TI[("M", 10, 1.0)]] == 1
        self.set_runtime_statistic("T tradability top1% fullA GBM", (f"rows {len(sel)} events {int(y.sum())} | px med {np.nanmedian(px):.2f} <$1 {100 * np.mean(px < 1):.0f}% 1-5 {100 * np.mean((px >= 1) & (px < 5)):.0f}% | $vol med {np.nanmedian(dv) / 1e3:.0f}k <100k {100 * np.mean(dv < 1e5):.0f}%"
                                                                     f" | miss20 {100 * np.mean(F[sel, FI['miss20']] == 1):.0f}% | events confirmed by B {100 * b[y].mean() if y.any() else 0:.0f}% Bmax {100 * bm[y].mean() if y.any() else 0:.0f}% | A ret>200% {100 * np.mean(self.R[sel][y] > 2) if y.any() else 0:.0f}%")[:198])

    def mode_model(self):
        res = self._run_specs(None, test=False)
        mA, mG = res.get("fullA LR"), res.get("fullA GBM")
        if mA and mG:
            # H10: does the interaction-capable GBM beat the additive logistic model on validation? (bootstrap over securities)
            sA, sG, evm = mA[1], mG[1], mG[2]
            y = (self.L[evm, PRIMARY] == 1).astype(float); sid = self.SID[evm]
            rng = np.random.RandomState(3); W = rng.poisson(1.0, size=(60, int(sid.max()) + 1))
            def ap(s, w):
                o = np.argsort(-s, kind="mergesort"); wy = (w * y)[o]; ww = w[o]
                return (wy * np.cumsum(wy) / np.maximum(np.cumsum(ww), 1e-9)).sum() / max(wy.sum(), 1e-9)
            d = [ap(sG, W[i][sid].astype(float)) - ap(sA, W[i][sid].astype(float)) for i in range(60)]
            self.set_runtime_statistic("M H10 GBM minus additive LR PR-AUC", f"{mG[0]['ap'] - mA[0]['ap']:+.4f} [{np.percentile(d, 2.5):+.4f},{np.percentile(d, 97.5):+.4f}]")
        self._safe(self._importance, False)
        self._safe(self._secondary, False)

    def _safe(self, fn, *a):
        import time as _t, traceback
        t0 = _t.time()
        try:
            fn(*a)
        except Exception as e:
            self.lg(f"ERROR {fn.__name__}: {e} | {traceback.format_exc()[-150:]}")
        self.lg(f"TIME {fn.__name__} {(_t.time() - t0) / 60:.1f} min")

    def mode_test(self):
        if FROZEN is None:
            self.set_runtime_statistic("T ERROR", "FROZEN specification not set - refusing to touch the test period")
            return
        self._safe(self._univ_rep, 2021, 2025, "R")
        res = self._run_specs(FROZEN, test=True)
        self._safe(self._importance, True)
        self._safe(self._secondary, True)
        self._safe(self._tradability, res)
