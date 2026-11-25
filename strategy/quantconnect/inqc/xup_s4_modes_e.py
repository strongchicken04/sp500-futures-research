# region imports
from AlgorithmImports import *
from datetime import date as _date
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s4_core import *
# endregion
#
# Stage 4G outcome / downside distributions (S4OUTC), Stage 4H universe + label robustness (S4ROBUST),
# Stage 4I concentration and regimes (S4CONC). Aggregates only.


class S4ModesE:

    def _out_lines(self, sel):
        O = self.OUT
        n = int(sel.sum())
        v10 = sel & np.isfinite(O[:, OI["mh10"]]); v20 = sel & np.isfinite(O[:, OI["c20"]])
        n10, n20 = int(v10.sum()), int(v20.sum())
        inc20 = sel & ~np.isfinite(O[:, OI["c20"]])
        segend = inc20 & (self.D[self.SEG1] < DATA_END.toordinal() - 7)
        g = lambda k, m: O[m, OI[k]]
        l1 = (f"n {n} valid10 {pct(n10, n)} valid20 {pct(n20, n)} incompl20 seg-end {int(segend.sum())} data-end {int((inc20 & ~segend).sum())}"
              f" | maxHIGH10 {q(100 * g('mh10', v10))}% | maxCLOSE10 {q(100 * g('mc10', v10))}%")
        l2 = f"close t+5 {q(100 * g('c5', sel & np.isfinite(O[:, OI['c5']])))}% | t+10 {q(100 * g('c10', v10))}% | t+20 {q(100 * g('c20', v20))}%"
        sh = lambda m, d: 100 * m.sum() / max(d, 1)
        t100 = g("t100", v10); tmx = g("tmax10", v10)
        l3 = (f"minLOW10 {q(100 * g('ml10', v10), (10, 25, 50))}% minLOW20 {q(100 * g('ml20', v20), (10, 25, 50))}% | hit50/100/200 {sh(g('t50', v10) > 0, n10):.1f}/{sh(t100 > 0, n10):.1f}/{sh(g('t200', v10) > 0, n10):.1f}%"
              f" close+100 {sh(g('mc10', v10) >= 1, n10):.1f}% | c10<0 {sh(g('c10', v10) < 0, n10):.0f}% c20<0 {sh(g('c20', v20) < 0, n20):.0f}% c20<=-50% {sh(g('c20', v20) <= -0.5, n20):.1f}%"
              f" c20<=-80% {sh(g('c20', v20) <= -0.8, n20):.1f}% low20<=-50% {sh(g('ml20', v20) <= -0.5, n20):.1f}% | t-max med {np.median(tmx) if len(tmx) else np.nan:.0f} t100 med {np.median(t100[t100 > 0]) if (t100 > 0).any() else np.nan:.0f}"
              f" | high-close gap med {np.median(100 * (g('mh10', v10) - g('mc10', v10))) if n10 else np.nan:.0f}pp")
        return l1, l2, l3

    def mode_s4outc(self):
        S = self.set_runtime_statistic
        self._s4_finish()
        sc = self._s4_score(["fullA RF", "price LR", "volume LR"], True)
        scored = self.U["A"] & (self.D >= SCORE_START)
        testrows = scored & (self.D >= T0) & (self.D <= T1)
        sets = [("UNCOND", testrows)]
        fl = {}
        for nm in ("fullA RF", "price LR", "volume LR"):
            fl[nm] = self._s4_flags(sc[nm], scored)[0]
            for k in (0.01, 0.05, 0.10):
                sets.append((f"{SHORT[nm]} top{int(k * 100)}", fl[nm][k] & testrows))
        for i, (lab, sel) in enumerate(sets):
            l1, l2, l3 = self._out_lines(sel)
            if lab in ("UNCOND", "RF top1", "RF top5", "VOL top1", "PRICE top1"):
                S(f"O{i:02d} {lab} a", l1[:198]); S(f"O{i:02d} {lab} b", l2[:198])
                self.lg(f"O{i:02d} {lab} c: {l3}")
            else:
                self.lg(f"O{i:02d} {lab} a: {l1}")
                self.lg(f"O{i:02d} {lab} b: {l2}")
                self.lg(f"O{i:02d} {lab} c: {l3}")
        prim = self.L[:, PRIMARY]
        O = self.OUT
        for lab, sel in (("RF top1 failures (A10/100 = 0)", fl["fullA RF"][0.01] & testrows & (prim == 0)), ("RF top1 successes (A10/100 = 1)", fl["fullA RF"][0.01] & testrows & (prim == 1)),
                         ("UNCOND failures", testrows & (prim == 0))):
            v20 = sel & np.isfinite(O[:, OI["c20"]]); v10 = sel & np.isfinite(O[:, OI["c10"]])
            S(f"O9 {lab}", (f"n {int(sel.sum())} | c10 med {100 * np.median(O[v10, OI['c10']]):.1f}% | c20 p5/25/50 {q(100 * O[v20, OI['c20']], (5, 25, 50))}% | c20<=-50% {100 * (O[v20, OI['c20']] <= -0.5).mean():.1f}%"
                            f" | c10>=+100% {100 * (O[v10, OI['c10']] >= 1).mean():.1f}%")[:198])
        # C7 flag: S1 segment, RF re-ranked inside S1
        s1 = (self.PX >= 1) & (self.DV >= 5e5)
        f1 = self._s4_flags(sc["fullA RF"], scored & s1)[0][0.01] & testrows
        v10 = f1 & np.isfinite(O[:, OI["c10"]])
        a = (O[v10, OI["c10"]] <= -0.5).mean(); b = (O[v10, OI["mc10"]] >= 1).mean()
        l1, l2, l3 = self._out_lines(f1)
        self.lg(f"O S1 RF top1 a: {l1}"); self.lg(f"O S1 RF top1 b: {l2}"); self.lg(f"O S1 RF top1 c: {l3}")
        S("C7 S1 RF top1", f"n {int(f1.sum())} valid10 {int(v10.sum())} | share close(t+10) <= -50% {100 * a:.2f}% vs share reaching +100% close in window {100 * b:.2f}% -> {'FLAG' if a > b else 'no flag'}")
        self.lg("CHECK " + self.s4_check)

    def mode_s4robust(self):
        S = self.set_runtime_statistic
        self._s4_finish()
        sc = self._s4_score(["fullA RF"], True)["fullA RF"]
        scoredA = self.U["A"] & (self.D >= SCORE_START)
        prim = self.L[:, PRIMARY]
        for u in ("A", "A-strict", "A-exADR", "A-fund", "B"):
            um = self.U[u]
            scored = scoredA & um
            testrows = scored & (self.D >= T0) & (self.D <= T1)
            fl, pr = self._s4_flags(sc, scored)
            for fam in ("A", "B", "M"):
                li = TI[(fam, 10, 1.0)]
                ev = self._s4_events(li, "E1", um)
                aid, ain = self._s4_assoc(ev)
                tsel = (ev["date"] >= T0) & (ev["date"] <= T1)
                for k in ((0.01, 0.05) if fam == "A" else (0.05,)):
                    c = self._s4_capture(ev, tsel, fl[k])
                    anyc = (c["pre"] + c["dur"]) > 0
                    pok = c["pok"]
                    sg = fl[k] & testrows
                    ld = c["lead"][c["lead"] > 0]
                    conf = ev["confM"][tsel][anyc].mean() if fam == "A" and anyc.any() else np.nan
                    S(f"R {u} {fam}10 k{int(k * 100)}", (f"ev {int(tsel.sum())} cap {100 * anyc.mean():.1f}% pre {100 * (c['pre'] > 0).mean():.1f}% placebo {100 * (c['plac'][pok] > 0).mean():.1f}% in-only {100 * ((c['pre'] == 0) & (c['dur'] > 0)).mean():.1f}%"
                                                         f" | evprec {100 * (aid[sg] >= 0).mean():.1f}% | lead med {np.median(ld) if len(ld) else np.nan:.0f} | conf(Bmax) {100 * conf:.0f}% | sel <$1 {100 * (self.PX[sg] < 1).mean():.0f}% $vol {np.median(self.DV[sg]) / 1e3:.0f}k")[:198])
            # S1 filter inside the universe (re-ranked), primary family
            s1 = (self.PX >= 1) & (self.DV >= 5e5)
            f1 = self._s4_flags(sc, scored & s1)
            ev = self._s4_events(PRIMARY, "E1", um)
            tsel = (ev["date"] >= T0) & (ev["date"] <= T1) & s1[ev["start"]]
            c5 = self._s4_capture(ev, tsel, f1[0][0.05])
            v = testrows & s1 & (prim >= 0)
            p1 = (prim[f1[0][0.01] & v] == 1).mean() if (f1[0][0.01] & v).any() else np.nan
            base = (prim[v] == 1).mean() if v.any() else np.nan
            self.lg(f"RS1 {u}: S1 base {100 * base:.3f}% P@1 {100 * p1:.2f}% lift {p1 / max(base, 1e-9):.2f} | S1 events {int(tsel.sum())} cap5 {100 * ((c5['pre'] + c5['dur']) > 0).mean():.1f}% pre5 {100 * (c5['pre'] > 0).mean():.1f}%")
        # incomplete-label sensitivity (A, primary)
        testA = scoredA & (self.D >= T0) & (self.D <= T1)
        fl, pr = self._s4_flags(sc, scoredA)
        for k in (0.01, 0.05):
            f = fl[k] & testA
            ex = (prim[f & (prim >= 0)] == 1).mean(); neg = (prim[f] == 1).sum() / max(f.sum(), 1)
            S(f"R incomplete k{int(k * 100)}", f"selected {int(f.sum())} invalid-label {int((f & (prim < 0)).sum())} | P excluding invalid {100 * ex:.2f}% | P invalid-as-negative {100 * neg:.2f}%")
        ev = self._s4_events(PRIMARY, "E1")
        tsel = (ev["date"] >= T0) & (ev["date"] <= T1)
        c = self._s4_capture(ev, tsel, fl[0.05])
        inc = ev["incomplete"][tsel]
        anyc = (c["pre"] + c["dur"]) > 0
        S("R incomplete events", f"test E1 events {int(tsel.sum())} incomplete {int(inc.sum())} | cap5 all {100 * anyc.mean():.1f}% complete-only {100 * anyc[~inc].mean():.1f}% incomplete-only {100 * anyc[inc].mean() if inc.any() else np.nan:.1f}%")
        # E2 / E3 in the sensitivity universes (RF, k 5)
        for u in ("A-strict", "A-exADR", "A-fund"):
            um = self.U[u]
            fl, pr = self._s4_flags(sc, scoredA & um)
            parts = []
            for rule in ("E2", "E3"):
                ev = self._s4_events(PRIMARY, rule, um)
                tsel = (ev["date"] >= T0) & (ev["date"] <= T1)
                c = self._s4_capture(ev, tsel, fl[0.05])
                parts.append(f"{rule} ev {int(tsel.sum())} cap {100 * ((c['pre'] + c['dur']) > 0).mean():.1f}% pre {100 * (c['pre'] > 0).mean():.1f}% placebo {100 * (c['plac'][c['pok']] > 0).mean():.1f}%")
            self.lg(f"RE {u} RF k5: " + " | ".join(parts))
        self.lg("CHECK " + self.s4_check)

    def mode_s4conc(self):
        S = self.set_runtime_statistic
        self._s4_finish()
        sc = self._s4_score(["fullA RF", "volume LR"], True)
        scored = self.U["A"] & (self.D >= SCORE_START)
        testrows = scored & (self.D >= T0) & (self.D <= T1)
        prim = self.L[:, PRIMARY]
        tv = testrows & (prim >= 0)
        fl = {nm: self._s4_flags(sc[nm], scored)[0] for nm in sc}
        du, dc = np.unique(self.D[testrows], return_counts=True)
        f1 = fl["fullA RF"][0.01] & testrows
        _, fc = np.unique(self.D[f1], return_counts=True)
        S("Q1 daily counts", f"test days {len(du)} | eligible rows/day p10/50/90 {q(dc, (10, 50, 90))} min {dc.min()} max {dc.max()} | RF top-1% selections/day p50 {np.median(fc):.0f} max {fc.max()} (20% sample of the universe)")
        dpos = pd.Series((prim[tv] == 1).astype(float)).groupby(self.D[tv]).agg(["sum", "count"])
        ps = np.sort(dpos["sum"].values)[::-1]
        tot = ps.sum()
        ev = self._s4_events(PRIMARY, "E1")
        tsel = (ev["date"] >= T0) & (ev["date"] <= T1)
        on = pd.Series(1, index=ev["date"][tsel]).groupby(level=0).sum().reindex(du, fill_value=0).values
        mu, var = on.mean(), on.var()
        rate = dpos["sum"] / dpos["count"]; pbar = dpos["sum"].sum() / dpos["count"].sum()
        vb = (pbar * (1 - pbar) / dpos["count"]).mean()
        icc = max((rate.var() - vb) / (pbar * (1 - pbar)), 0)
        S("Q2 date concentration", (f"share of positive rows on top 1% / 5% of days {100 * ps[:max(1, len(ps) // 100)].sum() / tot:.1f}% / {100 * ps[:max(1, len(ps) // 20)].sum() / tot:.1f}% | E1 onsets/day mean {mu:.2f} var {var:.2f} var/mean {var / max(mu, 1e-9):.2f}"
                                    f" days > mean+3sd {int((on > mu + 3 * np.sqrt(var)).sum())} | daily rate var obs/binomial {rate.var() / max(vb, 1e-12):.2f} ICC {icc:.4f}")[:198])
        nsec = int(self.SID.max()) + 1
        secs_rows = np.unique(self.SID[testrows])
        ec = np.bincount(ev["sid"][tsel], minlength=nsec)[secs_rows]
        fcs = np.bincount(self.SID[f1], minlength=nsec)[secs_rows]
        sh = lambda a, p: 100 * np.sort(a)[::-1][:max(1, int(round(len(a) * p)))].sum() / max(a.sum(), 1)
        S("Q3 security concentration", f"securities with test rows {len(secs_rows)}, with >=1 event {int((ec > 0).sum())} | share of events from top 1/5/10% securities {sh(ec, .01):.1f}/{sh(ec, .05):.1f}/{sh(ec, .10):.1f}% | RF top-1% selections from top 1/5/10% {sh(fcs, .01):.1f}/{sh(fcs, .05):.1f}/{sh(fcs, .10):.1f}%")
        # regimes (past-only variables, tercile cut-offs from 2006-2020)
        spl = np.log(self.spy_c)
        spr = np.concatenate([[np.nan], np.diff(spl)])
        vol20 = pd.Series(spr).rolling(20, min_periods=20).std().values
        mdx = np.clip(self.MDX, 0, len(vol20) - 1)
        reg = {"SPY 20d vol": vol20[mdx]}
        try:
            iwm = Symbol.create("IWM", SecurityType.EQUITY, Market.USA)
            h = self._hist([iwm], DataNormalizationMode.ADJUSTED).get(iwm)
            if h is not None:
                ser = pd.Series(h[4], index=h[0])
                r20 = np.log(ser / ser.shift(20))
                reg["IWM 20d return"] = r20.reindex(self.D.astype(np.int64)).values
        except Exception as e:
            self.lg("IWM history failed: " + type(e).__name__)
        A = self.U["A"]
        med = pd.Series(self.F[A, FI["r20"]]).groupby(self.D[A]).median()
        reg["panel median r20"] = med.reindex(self.D.astype(np.int64)).values
        dev = A & (self.D < T0)
        for name, x in reg.items():
            ok = dev & np.isfinite(x)
            dd = pd.Series(x[ok]).groupby(self.D[ok]).first()
            cut = np.percentile(dd.values, [33.33, 66.67])
            t = np.where(np.isfinite(x), np.searchsorted(cut, x), -1)
            parts = []
            for j in range(3):
                m = tv & (t == j)
                if m.sum() < 100:
                    continue
                yy = (prim[m] == 1).astype(float)
                ap = {nm: self._ap_sorted(yy[np.argsort(-sc[nm][m], kind="mergesort")], np.ones(len(yy))) for nm in sc}
                p1 = {nm: (prim[fl[nm][0.01] & m] == 1).mean() for nm in sc}
                ne = int((tsel & (t[ev["start"]] == j)).sum())
                parts.append(f"T{j + 1}: rows {int(m.sum())} base {100 * yy.mean():.2f}% ev {ne} RF AP {ap['fullA RF']:.4f} P@1 {100 * p1['fullA RF']:.1f}% VOL AP {ap['volume LR']:.4f} P@1 {100 * p1['volume LR']:.1f}%")
            self.lg(f"Q4 regime {name}: " + " | ".join(parts))
        # calendar control: per-day AP and date-cluster bootstrap of the pooled AP difference
        Dv = self.D[tv]; yv = (prim[tv] == 1).astype(float)
        dd = pd.DataFrame({"d": Dv, "y": yv, "a": sc["fullA RF"][tv], "b": sc["volume LR"][tv]})
        aps = []
        for d, g in dd.groupby("d"):
            if g["y"].sum() > 0:
                aps.append((self._ap_sorted(g["y"].values[np.argsort(-g["a"].values)], np.ones(len(g))), self._ap_sorted(g["y"].values[np.argsort(-g["b"].values)], np.ones(len(g)))))
        aps = np.array(aps)
        uq, di = np.unique(Dv, return_inverse=True)
        Wd = self._boot_W(1000, 31, len(uq))
        oa = np.argsort(-dd["a"].values, kind="mergesort"); ob = np.argsort(-dd["b"].values, kind="mergesort")
        d0 = self._ap_sorted(yv[oa], np.ones(len(yv))) - self._ap_sorted(yv[ob], np.ones(len(yv)))
        bd = np.array([self._ap_sorted(yv[oa], Wd[b][di][oa]) - self._ap_sorted(yv[ob], Wd[b][di][ob]) for b in range(1000)])
        S("Q5 calendar control", f"days with >=1 positive {len(aps)} | mean daily AP RF {aps[:, 0].mean():.4f} VOL {aps[:, 1].mean():.4f} RF>VOL on {100 * (aps[:, 0] > aps[:, 1]).mean():.1f}% of days | pooled dAP {d0:+.4f} date-bootstrap {self._ci(bd)} p {self._pval(bd):.4f}")
        self.lg("CHECK " + self.s4_check)

    def mode_s4xseg(self):
        """EXPLORATORY (not confirmatory): pre-onset (1-10) vs placebo (31-40) inside the pre-declared tradable
        segments S0 / S1 / S2, RF and volume LR re-ranked inside the segment; E1 and E3 test events with onset in the
        segment; also with C10 deduplication; paired event bootstrap by security (2,000)"""
        S = self.set_runtime_statistic
        self._s4_finish()
        sc = self._s4_score(["fullA RF", "volume LR"], True)
        scoredA = self.U["A"] & (self.D >= SCORE_START)
        nsec = int(self.SID.max()) + 1
        W = self._boot_W(2000, 505, nsec)
        evs = {r: self._s4_events(PRIMARY, r) for r in ("E1", "E3")}
        for seg, p, d in (("S0", 1, 1e5), ("S1", 1, 5e5), ("S2", 5, 1e6)):
            fm = (self.PX >= p) & (self.DV >= d)
            for nm in ("fullA RF", "volume LR"):
                fl, pr = self._s4_flags(sc[nm], scoredA & fm)
                for r in ("E1", "E3"):
                    ev = evs[r]
                    tsel = (ev["date"] >= T0) & (ev["date"] <= T1) & fm[ev["start"]]
                    aid, ain = self._s4_assoc(ev)
                    parts = []
                    for k in (0.01, 0.05):
                        for rule in ("N0", "C10"):
                            f = fl[k] if rule == "N0" else self._s4_dedup(fl[k], "C10", aid, scoredA & fm)
                            c = self._s4_capture(ev, tsel, f)
                            use = c["pok"]
                            pre = (c["pre"][use] > 0).astype(np.float32); plc = (c["plac"][use] > 0).astype(np.float32)
                            sd = c["sid"][use]
                            P1 = np.bincount(sd, weights=pre, minlength=nsec); P0 = np.bincount(sd, weights=plc, minlength=nsec); N = np.bincount(sd, minlength=nsec).astype(np.float32)
                            dd = 100 * (W @ (P1 - P0)) / np.maximum(W @ N, 1e-9)
                            rp, rq = (pre.mean(), plc.mean()) if len(pre) else (np.nan, np.nan)
                            parts.append(f"k{int(k * 100)}{rule}: {100 * rp:.1f}/{100 * rq:.1f}% d{100 * (rp - rq):+.1f}{self._ci(dd, 1)} r{rp / max(rq, 1e-9):.2f}")
                    line = f"n {int(tsel.sum())} | " + " | ".join(parts)
                    if nm == "fullA RF":
                        S(f"XS {seg} {r} {SHORT[nm]}", line[:198])
                    self.lg(f"XS {seg} {r} {SHORT[nm]} pre1-10/placebo31-40: {line}")
        self.lg("CHECK " + self.s4_check)
