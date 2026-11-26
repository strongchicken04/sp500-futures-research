# region imports
from AlgorithmImports import *
from datetime import date as _date
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s4_core import *
from xup_s4_core import _o
from xup_s45_core import *
# endregion
#
# Stage 4.5: S45MODEL (timing models vs the frozen-state baseline, C2) and S45PLACEBO (within-security placebo,
# membership-matched, C3). Primary population S1-P5, target ONSET_3 (E1), signals = per-day top 10 % of the
# conditional population, rolling-origin folds a (2021-22), b (2023-25), c (2026 diagnostic).

P21 = (T0, _o(2022, 12, 31)); P23 = (_o(2023, 1, 1), T1)


class S45ModesB:

    def _s45_primary(self, uname="S1", kst=0.05, defn="E1", k=3, rule="trail"):
        exante, lab, st = self._s45_pop(uname, kst, defn, k, rule)
        mv = self._s45_mv(defn)
        eh = self._s45_evhist(self._s45_mv("E1"))
        if not hasattr(self, "hp45"):
            e0, l0, s0 = self._s45_pop("S1", 0.05, "E1", 3, "trail")
            self._s45_hp(e0, l0, s0, eh)
        return exante, lab, st, mv, eh

    def _s45_specs(self):
        logo = [(f"L2_no{g}", "l2", [f for f in FULL45 if f == "rf" or f not in GROUPS[g]]) for g in GROUPS]
        return [("STATE", "state", []), ("LR_VACC", "lr", G_STATE + G_VACC), ("LR_VOLU", "lr", G_STATE + G_VOLU), ("LR_PATH", "lr", G_STATE + G_PATH),
                ("LR_TRANS", "lr", G_TRANS), ("L2_FULL", "l2", FULL45), ("RF_FULL", "rf", FULL45)] + logo

    def _s45_rowm(self, s, y, d):
        o = np.argsort(-s, kind="mergesort")
        ys = y[o]
        ap = self._ap_sorted(ys, np.ones(len(ys)))
        n = len(ys)
        pp = [ys[:max(1, int(np.ceil(k * n)))].mean() for k in (0.01, 0.05, 0.10)]
        return ap, pp

    def _s45_evstats(self, mv, sel, sig, popev, lab, k=3):
        elig, cap, lead, sid = self._s45_capture(mv, sel, sig, popev, k)
        sg = sig & popev
        npos = int((lab[sg] == 1).sum())
        nsig = int(sg.sum())
        ns = np.bincount(self.SID[sg])
        return dict(elig=elig, cap=cap, lead=lead, sid=sid, nsig=nsig, prec=npos / max(nsig, 1), capn=int(cap[elig].sum()), eln=int(elig.sum()),
                    fpc=(nsig - npos) / max(int(cap[elig].sum()), 1), sps=float(ns[ns > 0].mean()) if (ns > 0).any() else 0.0)

    def _s45_pairboot(self, a, b, sid, dates=None, B=2000, seeds=(4501, 4502, 4503)):
        """paired difference of event-level means (a - b) with security and two-way (security x date) bootstrap"""
        nsec = int(self.SID.max()) + 1
        Ws = self._boot_W(B, seeds[0], nsec)
        d = (a - b).astype(np.float64)
        num = np.bincount(sid, weights=d, minlength=nsec); den = np.bincount(sid, minlength=nsec).astype(np.float64)
        bs = (Ws @ num) / np.maximum(Ws @ den, 1e-9)
        out = {"d": d.mean() if len(d) else np.nan, "cs": self._ci(100 * bs, 1), "ps": self._pval(bs), "lo_s": np.percentile(bs, 2.5)}
        if dates is not None:
            du, di = np.unique(dates, return_inverse=True)
            W1 = self._boot_W(B, seeds[1], nsec); W2 = self._boot_W(B, seeds[2], len(du))
            bt = np.array([(W1[i][sid] * W2[i][di] * d).sum() / max((W1[i][sid] * W2[i][di]).sum(), 1e-9) for i in range(B)])
            out.update({"ct": self._ci(100 * bt, 1), "pt": self._pval(bt), "lo_t": np.percentile(bt, 2.5)})
        return out

    def mode_s45model(self):
        S = self.set_runtime_statistic
        self._s45_finish()
        exante, lab, st, mv, eh = self._s45_primary()
        hp = self.hp45
        S("M0 hyperparameters (train 2017-19, validate 2020)", f"L2 C={hp['l2']} (grid PR-AUC {hp['l2_grid']}) | RF leaf={hp['rf']} ({hp['rf_grid']}) | {hp['n']}"[:198])
        specs = self._s45_specs()
        sc = self._s45_models(exante, lab, st, eh, specs, folds=("a", "b", "c"))
        test = (self.D >= T0) & (self.D <= T1)
        popev = exante & np.isfinite(sc["L2_FULL"]) & test
        ev = popev & (lab >= 0)
        y = (lab[ev] == 1).astype(float)
        sel = (mv["date"] >= T0) & (mv["date"] <= T1)
        allev = int((sel & st["umask"][np.maximum(mv["t1"] - 1, 0)]).sum())
        res = {}
        for nm, kind, feats in specs:
            s = sc[nm]
            ap, pp = self._s45_rowm(s[ev], y, self.D[ev])
            sig10 = self._s45_signals(s, popev, 0.10); sig25 = self._s45_signals(s, popev, 0.25)
            e10 = self._s45_evstats(mv, sel, sig10, popev, lab)
            p25 = (lab[sig25 & ev] == 1).mean() if (sig25 & ev).any() else np.nan
            extra = ""
            if kind != "state":
                p = np.clip(s[ev], 1e-6, 1 - 1e-6)
                extra = f" | Brier {np.mean((p - y) ** 2) * 1e3:.2f}e-3 LL {-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)):.4f}"
            res[nm] = (s, sig10, e10)
            S(f"M1 {nm}", (f"PR-AUC {ap:.4f} | pool P@1/5/10 {100 * pp[0]:.1f}/{100 * pp[1]:.1f}/{100 * pp[2]:.1f}% | day-top10 P {100 * e10['prec']:.2f}% ({e10['nsig']}) top25 {100 * p25:.2f}%"
                              f" lift10 {e10['prec'] / max(y.mean(), 1e-9):.2f} | cap {100 * e10['capn'] / max(e10['eln'], 1):.1f}% ({e10['capn']}/{e10['eln']}){extra}")[:198])
        S("M2 test population", f"S1-P5 2021-25 valid rows {int(ev.sum())} pos {int(y.sum())} base {100 * y.mean():.3f}% | eligible E1 events {res['STATE'][2]['eln']} of {allev} test move days in S1 | secs {len(np.unique(self.SID[ev]))}")
        # C2: pre-event capture, L2_FULL - STATE
        eS, eL = res["STATE"][2], res["L2_FULL"][2]
        el = eS["elig"]
        a, b = eL["cap"][el].astype(float), eS["cap"][el].astype(float)
        sid = eS["sid"][el]
        dts = mv["date"][sel][el]
        pb = self._s45_pairboot(a, b, sid, dts)
        per = {}
        for tag, (lo, hi) in (("21-22", P21), ("23-25", P23)):
            m = (dts >= lo) & (dts <= hi)
            per[tag] = (a[m].mean() - b[m].mean()) if m.any() else np.nan
        logo = {nm: res[nm][2]["cap"][el].mean() - b.mean() for nm, _, _ in specs if nm.startswith("L2_no")}
        c2 = (pb["lo_s"] > 0) and (pb["lo_t"] > 0) and all(v > 0 for v in per.values()) and all(v > 0 for v in logo.values())
        S("C2 capture L2_FULL-STATE", f"{100 * a.mean():.1f}% vs {100 * b.mean():.1f}% d {100 * pb['d']:+.1f}pp sec {pb['cs']} p {pb['ps']:.4f} | two-way {pb['ct']} p {pb['pt']:.4f} -> {'PASS' if c2 else 'FAIL'}")
        S("C2 periods / LOGO", ("21-22 " + f"{100 * per['21-22']:+.1f}pp 23-25 {100 * per['23-25']:+.1f}pp | LOGO vs STATE " + " ".join(f"{k[5:]} {100 * v:+.1f}" for k, v in logo.items()))[:198])
        # other paired capture comparisons and PR-AUC difference
        parts = []
        for nm in ("RF_FULL", "LR_VACC", "LR_VOLU", "LR_PATH", "LR_TRANS"):
            bb = self._s45_pairboot(a, res[nm][2]["cap"][el].astype(float), sid, None, B=2000)
            parts.append(f"L2-{nm} {100 * bb['d']:+.1f}{bb['cs']}")
        S("M3 capture L2_FULL vs others (sec boot)", " | ".join(parts)[:198])
        nsec = int(self.SID.max()) + 1
        W = self._boot_W(2000, 4505, nsec)
        sidr = self.SID[ev]
        oL = np.argsort(-res["L2_FULL"][0][ev], kind="mergesort"); oS = np.argsort(-res["STATE"][0][ev], kind="mergesort")
        yL, yS = y[oL], y[oS]
        d0 = self._ap_sorted(yL, np.ones(len(y))) - self._ap_sorted(yS, np.ones(len(y)))
        bd = np.array([self._ap_sorted(yL, W[i][sidr][oL]) - self._ap_sorted(yS, W[i][sidr][oS]) for i in range(2000)])
        S("M4 PR-AUC L2_FULL-STATE", f"{d0:+.4f} {self._ci(bd)} p {self._pval(bd):.4f} (security bootstrap 2000, rows {len(y)})")
        for nm in ("STATE", "L2_FULL"):
            e = res[nm][2]
            ld = e["lead"][e["cap"] & e["elig"]]
            self.lg(f"EV {nm}: captured {e['capn']}/{e['eln']} eligible ({100 * e['capn'] / max(allev, 1):.1f}% of {allev} all S1 test move days) | signals {e['nsig']} event precision {100 * e['prec']:.2f}% false/captured {e['fpc']:.1f}"
                    f" signals/security {e['sps']:.1f} | first-signal lead 1/2/3: {(ld == 1).sum()}/{(ld == 2).sum()}/{(ld == 3).sum()}")
        # run-up already in progress at the signal (Amendment 1): xr = HIGH(t) / min OPEN(t-9..t) - 1 at the first signal row
        xr = self.OUT[:, OI["xr"]]
        for nm in ("STATE", "L2_FULL"):
            e = res[nm][2]
            cp = e["cap"] & e["elig"]
            t1 = mv["t1"][sel][cp]; ld = e["lead"][cp]
            xs = xr[t1 - ld]
            self.lg(f"RUNUP {nm}: run-up at first signal (xr) p25/50/75 {q(100 * xs, (25, 50, 75))}% | share xr>=30% {100 * np.mean(xs >= 0.3):.0f}% xr>=50% {100 * np.mean(xs >= 0.5):.0f}% (captured {len(xs)})")
        strict = popev & (np.nan_to_num(xr, nan=0) < 0.5)
        caps = {}
        for nm in ("STATE", "L2_FULL"):
            caps[nm] = self._s45_evstats(mv, sel, self._s45_signals(res[nm][0], strict, 0.10), strict, lab)
        els = caps["STATE"]["elig"]
        bs_ = self._s45_pairboot(caps["L2_FULL"]["cap"][els].astype(float), caps["STATE"]["cap"][els].astype(float), caps["STATE"]["sid"][els], None, B=2000)
        S("M7 strict pre-move (xr<50% at t)", f"eligible events {int(els.sum())} | cap STATE {100 * caps['STATE']['cap'][els].mean():.1f}% L2 {100 * caps['L2_FULL']['cap'][els].mean():.1f}% d {100 * bs_['d']:+.1f}pp {bs_['cs']} | P10 STATE {100 * caps['STATE']['prec']:.2f}% L2 {100 * caps['L2_FULL']['prec']:.2f}%")
        # calibration of the primary model
        p = res["L2_FULL"][0][ev]
        o = np.argsort(p); bins = np.array_split(o, 10)
        self.lg("CAL L2_FULL deciles pred/obs %: " + " ".join(f"{100 * p[bb].mean():.2f}/{100 * y[bb].mean():.2f}" for bb in bins))
        # 2026 diagnostic (fold c)
        y26 = (self.D >= Y0)
        pe26 = exante & np.isfinite(sc["L2_FULL"]) & y26
        ev26 = pe26 & (lab >= 0)
        s26 = (mv["date"] >= Y0)
        parts = []
        for nm in ("STATE", "L2_FULL"):
            yy = (lab[ev26] == 1).astype(float)
            ap, pp = self._s45_rowm(sc[nm][ev26], yy, self.D[ev26])
            e = self._s45_evstats(mv, s26, self._s45_signals(sc[nm], pe26, 0.10), pe26, lab)
            parts.append(f"{nm} PR-AUC {ap:.4f} cap {e['capn']}/{e['eln']} P10 {100 * e['prec']:.1f}%")
        S("M5 2026 YTD diagnostic (fold c)", (f"rows {int(ev26.sum())} pos {int((lab[ev26] == 1).sum())} | " + " | ".join(parts))[:198])
        # secondary horizons
        for k in (1, 2, 5):
            ex2, lab2, st2 = self._s45_pop("S1", 0.05, "E1", k)
            sc2 = self._s45_models(ex2, lab2, st2, eh, [("STATE", "state", []), ("L2_FULL", "l2", FULL45)], folds=("a", "b"))
            pe = ex2 & np.isfinite(sc2["L2_FULL"]) & test
            evk = pe & (lab2 >= 0)
            yk = (lab2[evk] == 1).astype(float)
            out = {}
            for nm in ("STATE", "L2_FULL"):
                ap, pp = self._s45_rowm(sc2[nm][evk], yk, self.D[evk])
                out[nm] = (ap, self._s45_evstats(mv, sel, self._s45_signals(sc2[nm], pe, 0.10), pe, lab2, k))
            el2 = out["STATE"][1]["elig"]
            bb = self._s45_pairboot(out["L2_FULL"][1]["cap"][el2].astype(float), out["STATE"][1]["cap"][el2].astype(float), out["STATE"][1]["sid"][el2], None, B=1000)
            S(f"M6 ONSET_{k}", (f"base {100 * yk.mean():.2f}% | PR-AUC STATE {out['STATE'][0]:.4f} L2 {out['L2_FULL'][0]:.4f} | cap STATE {100 * out['STATE'][1]['cap'][el2].mean():.1f}% L2 {100 * out['L2_FULL'][1]['cap'][el2].mean():.1f}%"
                                f" d {100 * bb['d']:+.1f}pp {bb['cs']} (events {int(el2.sum())})")[:198])
        self._s45_end()

    # ---------------- placebo ----------------
    def _s45_memcount(self, member, mv, sel, a, b):
        t1 = mv["t1"][sel]
        lo, hi = np.maximum(t1 - b, 0), np.maximum(t1 - a, 0)
        cm = np.concatenate([[0], np.cumsum(member)])
        return cm[hi + 1] - cm[lo]

    def mode_s45placebo(self):
        S = self.set_runtime_statistic
        self._s45_finish()
        exante, lab, st, mv, eh = self._s45_primary()
        specs = [("STATE", "state", []), ("L2_FULL", "l2", FULL45), ("RF_FULL", "rf", FULL45)]
        sc = self._s45_models(exante, lab, st, eh, specs, folds=("a", "b"))
        test = (self.D >= T0) & (self.D <= T1)
        popev = exante & np.isfinite(sc["L2_FULL"]) & test
        member = st["umask"]
        sigs = {nm: self._s45_signals(sc[nm], popev, 0.10) for nm, _, _ in specs}
        nsec = int(self.SID.max()) + 1
        W = self._boot_W(2000, 4506, nsec)
        verdict = {}
        for defn in ("E1", "E2", "E3", "B", "M"):
            mvd = self._s45_mv(defn)
            sel = (mvd["date"] >= T0) & (mvd["date"] <= T1)
            wins = [(1, 3, 31, 33), (1, 5, 41, 45), (1, 3, 61, 63)] if defn == "E1" else [(1, 3, 31, 33)]
            for nm in (("L2_FULL", "STATE", "RF_FULL") if defn == "E1" else ("L2_FULL", "STATE")):
                sig = sigs[nm]
                for (a, b, pa, pb) in wins:
                    okA, detA = self._s45_window(mvd, sel, sig, a, b)
                    okB, detB = self._s45_window(mvd, sel, sig, pa, pb)
                    mA = self._s45_memcount(member, mvd, sel, a, b); mB = self._s45_memcount(member, mvd, sel, pa, pb)
                    okAm, _ = self._s45_window(mvd, sel, sig, a, b, member=member)
                    okBm, _ = self._s45_window(mvd, sel, sig, pa, pb, member=member)
                    sid = mvd["sid"][sel]
                    lines = []
                    for tag, use in (("unmatched", okA & okB & (mA > 0) & (mB > 0)), ("matched", okAm & okBm)):
                        x, z, s_ = detA[use].astype(float), detB[use].astype(float), sid[use]
                        if len(x) == 0:
                            lines.append(f"{tag} n 0"); continue
                        num = np.bincount(s_, weights=x - z, minlength=nsec); den = np.bincount(s_, minlength=nsec).astype(float)
                        bd = 100 * (W @ num) / np.maximum(W @ den, 1e-9)
                        r = x.mean() / max(z.mean(), 1e-9)
                        ok = (r >= 1.5) and (np.percentile(bd, 2.5) > 0)
                        verdict[(defn, nm, a, b, pa, pb, tag)] = ok
                        lines.append(f"{tag} n {len(x)}: {100 * x.mean():.1f}/{100 * z.mean():.1f}% d {100 * (x.mean() - z.mean()):+.1f}{self._ci(bd, 1)} r {r:.2f}{' *' if ok else ''}")
                    txt = f"pre {a}-{b} vs placebo {pa}-{pb} | " + " | ".join(lines)
                    if nm == "L2_FULL" and (a, b, pa, pb) == (1, 3, 31, 33):
                        S(f"P {defn} {nm}", txt[:198])
                    self.lg(f"P {defn} {nm}: {txt}")
        e1 = verdict.get(("E1", "L2_FULL", 1, 3, 31, 33, "unmatched"), False) and verdict.get(("E1", "L2_FULL", 1, 3, 31, 33, "matched"), False)
        alt = verdict.get(("E2", "L2_FULL", 1, 3, 31, 33, "matched"), False) or verdict.get(("E3", "L2_FULL", 1, 3, 31, 33, "matched"), False)
        S("C3 verdict", f"E1 unmatched+matched {'PASS' if e1 else 'FAIL'} | E2 or E3 matched {'PASS' if alt else 'FAIL'} -> C3 {'PASS' if (e1 and alt) else 'FAIL'}")
        self._s45_end()
