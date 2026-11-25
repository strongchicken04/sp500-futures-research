# region imports
from AlgorithmImports import *
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s3_modes_m import SPECS, _split
# endregion
#
# Stage 3 deliverable 8 (protocol Amendment 4): robustness of the FROZEN models and of the univariate A-universe
# variables across A, A-strict, A-ex-ADR and A-fund, and across test sub-periods. No refit beyond the identical
# TEST refit, no selection, no new features or hyperparameters.

R_MODELS = ["price LR", "momentum LR", "volume LR", "fullA LR", "fullA RF", "fullA GBM"]
R_UNIS = ["A", "A-strict", "A-exADR", "A-fund"]
R_VARS = [("H2", "rvol20"), ("H5", "atr_p"), ("H6", "gap"), ("H7", "r20"), ("H8", "lpx"), ("H9", "ldv")]


class ModesR:

    def _rr_ci(self, m, var, W, nsec):
        mo = self._month()
        dec, _ = self._deciles(self.F[m, FI[var]], mo[m])
        y = (self.L[m, PRIMARY] == 1).astype(np.float32)
        key = self.SID[m].astype(np.int64) * 11 + dec
        n_c = np.bincount(key, minlength=nsec * 11).reshape(nsec, 11)[:, [0, 9]].astype(np.float32)
        p_c = np.bincount(key, weights=y, minlength=nsec * 11).reshape(nsec, 11)[:, [0, 9]].astype(np.float32)
        r = p_c.sum(0) / np.maximum(n_c.sum(0), 1)
        b = (W @ p_c) / np.maximum(W @ n_c, 1)
        lb = np.log(np.maximum(b[:, 1], 1e-9) / np.maximum(b[:, 0], 1e-9))
        return r[1] / max(r[0], 1e-12), np.exp(np.percentile(lb, 2.5)), np.exp(np.percentile(lb, 97.5)), int(y.sum())

    def mode_robust(self):
        S = self.set_runtime_statistic
        li = PRIMARY
        # ---- 1. univariate A-universe variables in the sensitivity universes, development years and test years
        nsec = int(self.SID.max()) + 1
        W = np.random.RandomState(2026).poisson(1.0, size=(200, nsec)).astype(np.float32)
        valid = self.L[:, li] >= 0
        for hid, var in R_VARS:
            parts = []
            for u in R_UNIS[1:]:
                for tag, per in (("dev", self.Y <= 2020), ("test", (self.Y >= 2021) & (self.Y <= 2025))):
                    rr, lo, hi, pos = self._rr_ci(self.U[u] & per & valid, var, W, nsec)
                    parts.append(f"{u} {tag} {rr:.2f} [{lo:.2f},{hi:.2f}]")
            self.lg(f"RU {hid} {var} top/bottom RR: " + " | ".join(parts))
        # ---- 2. frozen models (identical TEST refit on A), evaluated inside each sensitivity universe and sub-period
        tr, te, _ = _split(self, "std", True)
        evm = self.U["A"] & te & valid
        ye_all = (self.L[evm, li] == 1).astype(int)
        D, SID, Y = self.D[evm], self.SID[evm], self.Y[evm]
        sub = {u: self.U[u][evm] for u in R_UNIS}
        for spec in SPECS:
            name, uni, feats, kind, sp = spec
            if name not in R_MODELS:
                continue
            try:
                idx, y, w = self._train_rows(self.U["A"] & tr, li)
                cols = [FI[c] for c in feats]
                f, _m = self._fit(kind, self.F[idx][:, cols], y, w)
                se = f(self.F[evm][:, cols])
                for u in R_UNIS:
                    k = sub[u]
                    mt = self._metrics(se[k], ye_all[k], D[k], SID[k], boot=30)
                    S(f"X {name} {u}", f"2021-25 n {mt['n'] // 1000}k pos {mt['pos']} base {mt['base'] * 100:.3f}% | PR-AUC {mt['ap']:.4f} [{mt['ap_ci'][0]:.4f},{mt['ap_ci'][1]:.4f}] | P@1% {mt['p1'] * 100:.2f}% ({mt['k1']}/{mt['n1']}) R@10 {mt['r10'] * 100:.0f}% AUC {mt['auc']:.3f}"[:198])
                parts = []
                for tag, k in (("2021-22", Y <= 2022), ("2023-25", Y >= 2023)):
                    mt = self._metrics(se[k], ye_all[k], D[k], SID[k], boot=30)
                    parts.append(f"{tag}: base {mt['base'] * 100:.3f}% PR-AUC {mt['ap']:.4f} [{mt['ap_ci'][0]:.4f},{mt['ap_ci'][1]:.4f}] P@1% {mt['p1'] * 100:.2f}% ({mt['k1']}) AUC {mt['auc']:.3f}")
                self.lg(f"RP {name} [A]: " + " | ".join(parts))
            except Exception as e:
                import traceback
                S(f"X {name}", ("ERROR " + str(e) + " | " + traceback.format_exc()[-120:])[:198])
