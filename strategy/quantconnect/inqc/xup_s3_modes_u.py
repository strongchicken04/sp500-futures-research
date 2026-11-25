# region imports
from AlgorithmImports import *
from datetime import date as _date, timedelta
import hashlib, re, bisect, math, time as _time
import numpy as np
import pandas as pd
from xup_s3_const import *
# endregion


class ModesU:
    # ---------------- MODE: UNIV (Stage 3C, 2006-2020 only) ----------------
    VARS = [("H1", "lmcap", "B", -1), ("H1s", "lds", "B", -1), ("H2", "rvol20", "A", 1), ("H2s", "rvol5", "A", 1),
            ("H3", "si_ds", "D", 1), ("H3s", "dtc", "D", 1), ("H4", "lfloat", "C", -1), ("H4s", "float_ds", "C", -1),
            ("H5", "atr_p", "A", 1), ("H5s", "rv20", "A", 1), ("H6", "gap", "A", 0), ("H6s", "intraday", "A", 0),
            ("H7", "r20", "A", 1), ("H7s", "r5", "A", 1), ("H8", "lpx", "A", -1), ("H8s", "lpx_prev", "A", -1),
            ("H9", "ldv", "A", 0), ("H9s", "rdv20", "A", 0)]

    def _deciles(self, x, mo):
        """monthly cross-sectional percentile rank -> decile 0..9; NaN -> 10 (missing bin)"""
        df = pd.DataFrame({"x": x, "m": mo})
        pr = df.groupby("m")["x"].rank(pct=True, method="average").values
        dec = np.where(np.isfinite(pr), np.minimum((pr * 10).astype(int) - (pr * 10 == np.floor(pr * 10)).astype(int) * 0, 9), 10)
        dec = np.where(np.isfinite(pr), np.clip(np.ceil(pr * 10).astype(int) - 1, 0, 9), 10)
        return dec, pr

    def mode_univ(self):
        S = self.set_runtime_statistic
        rng = np.random.RandomState(2026)
        L, F = self.L, self.F
        mo = self._month()
        dev = self.Y <= 2020
        prim = L[:, PRIMARY]
        nsec = int(self.SID.max()) + 1
        W = rng.poisson(1.0, size=(200, nsec)).astype(np.float32)   # Poisson cluster-bootstrap weights by security
        res = []
        sec_lines = []
        for hid, var, uni, sign in self.VARS:
            m = self.U[uni] & dev & (prim >= 0)
            x = F[m, FI[var]]
            dec, pr = self._deciles(x, mo[m])
            y = (prim[m] == 1).astype(np.float32)
            sid = self.SID[m]
            # per-security x decile counts
            key = sid.astype(np.int64) * 11 + dec
            n_c = np.bincount(key, minlength=nsec * 11).reshape(nsec, 11).astype(np.float32)
            p_c = np.bincount(key, weights=y, minlength=nsec * 11).reshape(nsec, 11).astype(np.float32)
            N = n_c.sum(0); P = p_c.sum(0)
            rate = P / np.maximum(N, 1)
            BN = W @ n_c; BP = W @ p_c
            brate = BP / np.maximum(BN, 1)
            top, bot = 9, 0
            rr = rate[top] / max(rate[bot], 1e-12)
            orr = (rate[top] / max(1 - rate[top], 1e-12)) / max(rate[bot] / max(1 - rate[bot], 1e-12), 1e-12)
            brr = np.log(np.maximum(brate[:, top], 1e-9) / np.maximum(brate[:, bot], 1e-9))
            bor = np.log(np.maximum(brate[:, top] / np.maximum(1 - brate[:, top], 1e-9), 1e-9) / np.maximum(brate[:, bot] / np.maximum(1 - brate[:, bot], 1e-9), 1e-9))
            p = max(2 * min((brr <= 0).mean(), (brr >= 0).mean()), 1.0 / 200)
            # slope of logit(rate) on decile index (weighted LS) + bootstrap
            d = np.arange(10)

            def slope(rt, nn):
                lr_ = np.log(np.maximum(rt[:10], 1e-7) / np.maximum(1 - rt[:10], 1e-7))
                w = nn[:10]
                xm = (w * d).sum() / max(w.sum(), 1)
                ym = (w * lr_).sum() / max(w.sum(), 1)
                return ((w * (d - xm) * (lr_ - ym)).sum()) / max((w * (d - xm) ** 2).sum(), 1e-9)
            sl = slope(rate, N)
            bsl = np.array([slope(brate[i], BN[i]) for i in range(200)])
            rk = pd.Series(rate[:10]).rank().values
            spear = np.corrcoef(rk, d)[0, 1]
            # AUC of the monthly percentile rank, events vs non-events, with cluster-bootstrap
            fin = np.isfinite(pr)
            o = np.argsort(pr[fin], kind="mergesort")
            ys = y[fin][o]; ss = sid[fin][o]
            def wauc(w):
                wp = w * ys; wn = w * (1 - ys)
                cn = np.cumsum(wn) - wn
                return float((wp * cn).sum() / max(wp.sum() * wn.sum(), 1e-9))
            auc = wauc(np.ones(len(ys), dtype=np.float32))
            bauc = np.array([wauc(W[i][ss]) for i in range(60)])
            q = lambda a: (np.percentile(a, 2.5), np.percentile(a, 97.5))
            # block consistency of the top/bottom RR (2006-09, 2010-14, 2015-19, 2020)
            brr_blocks = []
            for bi in range(4):
                mb = (self.BL[m] == bi) if bi < 3 else (self.Y[m] == 2020)
                nb = np.bincount(dec[mb], minlength=11); pb = np.bincount(dec[mb], weights=y[mb], minlength=11)
                rb = pb / np.maximum(nb, 1)
                brr_blocks.append(rb[top] / max(rb[bot], 1e-12) if rb[bot] > 0 else np.inf)
            res.append(dict(hid=hid, var=var, uni=uni, sign=sign, rr=rr, rrci=np.exp(q(brr)), orr=orr, orci=np.exp(q(bor)), diff=(rate[top] - rate[bot]) * 100,
                            sl=sl, slci=q(bsl), spear=spear, auc=auc, aucci=q(bauc), p=p, blocks=brr_blocks, N=N, P=P, rate=rate))
            self.lg(f"{hid} {var} [{uni}] deciles rate%/rows k/pos: " + " ".join(f"d{k + 1} {rate[k] * 100:.3f}/{N[k] / 1000:.0f}/{int(P[k])}" for k in range(10)) + f" | miss {rate[10] * 100:.3f}/{N[10] / 1000:.0f}/{int(P[10])}")
            # secondary endpoints: top/bottom RR for all 27 targets (point + bootstrap p)
            parts = []
            for (f, h, t) in TGT:
                li = TI[(f, h, t)]
                mm = self.U[uni] & dev & (L[:, li] >= 0)
                if li == PRIMARY:
                    parts.append(((f, h), "P"))
                    continue
                dd, _ = self._deciles(F[mm, FI[var]], mo[mm])
                yy = (L[mm, li] == 1).astype(np.float32)
                ss2 = self.SID[mm]
                k2 = ss2.astype(np.int64) * 11 + dd
                n2 = np.bincount(k2, minlength=nsec * 11).reshape(nsec, 11).astype(np.float32)[:, [0, 9]]
                p2 = np.bincount(k2, weights=yy, minlength=nsec * 11).reshape(nsec, 11).astype(np.float32)[:, [0, 9]]
                r2 = p2.sum(0) / np.maximum(n2.sum(0), 1)
                b2 = (W @ p2) / np.maximum(W @ n2, 1)
                l2 = np.log(np.maximum(b2[:, 1], 1e-9) / np.maximum(b2[:, 0], 1e-9))
                p2v = max(2 * min((l2 <= 0).mean(), (l2 >= 0).mean()), 1.0 / 200)
                parts.append(((f, h), f"{r2[1] / max(r2[0], 1e-12):.2f}{'*' if p2v < 0.01 else ''}"))
                sec_lines.append(p2v)
            grp = {}
            for k, v in parts:
                grp.setdefault(k, []).append(v)
            self.lg(f"{hid} RR top/bot +50/100/200 (*p<.01): " + " ".join(f"{f}{h} " + "/".join(v) for (f, h), v in grp.items()))
        # Benjamini-Hochberg over the 18 primary-endpoint tests
        ps = np.array([r["p"] for r in res])
        o = np.argsort(ps)
        qv = np.empty(len(ps))
        mn = 1.0
        for rank in range(len(ps) - 1, -1, -1):
            mn = min(mn, ps[o[rank]] * len(ps) / (rank + 1))
            qv[o[rank]] = mn
        for r, qq in zip(res, qv):
            bl = "/".join(f"{x:.2f}" if np.isfinite(x) else "inf" for x in r["blocks"])
            S(f"U {r['hid']} {r['var']} [{r['uni']}]", f"RR {r['rr']:.2f} [{r['rrci'][0]:.2f},{r['rrci'][1]:.2f}] OR {r['orr']:.2f} diff {r['diff']:+.3f}pp | slope {r['sl']:+.3f} [{r['slci'][0]:+.3f},{r['slci'][1]:+.3f}] rho {r['spear']:+.2f} | AUC {r['auc']:.3f} [{r['aucci'][0]:.3f},{r['aucci'][1]:.3f}] | p {r['p']:.3f} q {qq:.3f} | blocks {bl}"[:198])
        # secondary family BH count
        sp = np.sort(np.array(sec_lines))
        thr = np.nonzero(sp <= 0.05 * (np.arange(1, len(sp) + 1)) / len(sp))[0]
        S("U secondary-endpoint family", f"{len(sp)} tests (18 variables x 26 targets): BH q<0.05 significant {thr[-1] + 1 if len(thr) else 0}")
        # H10: quintile x quintile tables and additive-logit expectation for the joint top cell
        for (va, vb, uni) in (("lpx", "rvol20", "A"), ("r20", "rvol20", "A"), ("atr_p", "lpx", "A"), ("lmcap", "rvol20", "B")):
            m = self.U[uni] & dev & (prim >= 0)
            da, _ = self._deciles(F[m, FI[va]], mo[m]); db, _ = self._deciles(F[m, FI[vb]], mo[m])
            ok = (da < 10) & (db < 10)
            qa, qb = da[ok] // 2, db[ok] // 2
            yy = (prim[m][ok] == 1).astype(float)
            n = np.bincount(qa * 5 + qb, minlength=25).reshape(5, 5); p = np.bincount(qa * 5 + qb, weights=yy, minlength=25).reshape(5, 5)
            rt = p / np.maximum(n, 1)
            lo = lambda z: np.log(np.maximum(z, 1e-7) / np.maximum(1 - z, 1e-7))
            ra = p.sum(1) / np.maximum(n.sum(1), 1); rb = p.sum(0) / np.maximum(n.sum(0), 1); r0 = p.sum() / max(n.sum(), 1)
            cells = []
            for (i, j) in ((4, 4), (0, 0), (4, 0), (0, 4)):
                exp = 1 / (1 + np.exp(-(lo(ra[i]) + lo(rb[j]) - lo(r0))))
                cells.append(f"q{i + 1}{j + 1} obs {rt[i, j] * 100:.2f}% exp-add {exp * 100:.2f}% (n {int(n[i, j] / 1000)}k pos {int(p[i, j])})")
            S(f"U H10 {va} x {vb} [{uni}]", " | ".join(cells)[:198])
            self.lg(f"H10 {va}(rows q1..q5) x {vb}(cols) rate%: " + " ; ".join(" ".join(f"{rt[i, j] * 100:.2f}" for j in range(5)) for i in range(5)))

