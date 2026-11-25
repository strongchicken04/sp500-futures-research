# region imports
from AlgorithmImports import *
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s4_core import *
# endregion
#
# Stage 4B event-level evaluation + deduplication (S4EVAL) and Stage 4C lead time (S4LEAD).


class S4ModesB:

    def _s4_prep_eval(self, names):
        self._s4_finish()
        sc = self._s4_score(names, True)
        scored = self.U["A"] & (self.D >= SCORE_START)
        testrows = scored & (self.D >= T0) & (self.D <= T1)
        fl, pr = {}, {}
        for nm in names:
            fl[nm], pr[nm] = self._s4_flags(sc[nm], scored)
        return sc, scored, testrows, fl, pr

    def _s4_clean(self, ev, h=10, back=40):
        """event has no earlier event of the same security whose [start, last + h] reaches into [onset - back, onset - 1]"""
        s, l, sid = ev["start"], ev["last"], ev["sid"]
        prev_l = np.append([-10 ** 12], l[:-1])
        same = np.append([False], sid[1:] == sid[:-1])
        return ~(same & (prev_l + h >= s - back))

    def _s4_prescore(self, ev, sel, pr, h=10, pw=(31, 40)):
        qv = 1 - np.nan_to_num(pr, nan=1.0)
        s = ev["start"][sel]
        s0 = self.SEG0[s]
        pre, plc = np.full(len(s), np.nan), np.full(len(s), np.nan)
        for j in range(len(s)):
            a = max(s[j] - h, s0[j])
            if a < s[j]:
                pre[j] = qv[a:s[j]].max()
            pa, pb = s[j] - pw[1], s[j] - pw[0]
            if pa >= s0[j] and self.D[pa] >= SCORE_START:
                plc[j] = qv[pa:pb + 1].max()
        return pre, plc

    def _auc2(self, a, b):
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        if len(a) == 0 or len(b) == 0:
            return np.nan
        x = np.concatenate([a, b]); r = pd.Series(x).rank().values
        return (r[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))

    def mode_s4eval(self):
        S = self.set_runtime_statistic
        sc, scored, testrows, fl, pr = self._s4_prep_eval(MN)
        nsec = int(self.SID.max()) + 1
        evd = {r: self._s4_events(PRIMARY, r) for r in ("E1", "E2", "E3")}
        asc = {r: self._s4_assoc(evd[r]) for r in evd}
        for r in ("E1", "E2", "E3"):
            ev = evd[r]; aid, ain = asc[r]
            tsel = (ev["date"] >= T0) & (ev["date"] <= T1)
            ne = int(tsel.sum())
            for nm in (MN if r == "E1" else ["fullA RF", "volume LR"]):
                for k in (0.01, 0.05, 0.10):
                    f = fl[nm][k]
                    cap = self._s4_capture(ev, tsel, f)
                    anyc = (cap["pre"] + cap["dur"]) > 0
                    prec = cap["pre"] > 0
                    ino = (cap["pre"] == 0) & (cap["dur"] > 0)
                    sig = f & testrows
                    nsig = int(sig.sum())
                    a = aid[sig]; asd = a >= 0
                    uniq = len(np.unique(a[asd]))
                    cnt = np.bincount(a[asd]) if asd.any() else np.zeros(1)
                    rep = int((cnt[cnt > 0] - 1).sum())
                    sids = self.SID[sig]
                    nall = np.bincount(sids, minlength=nsec); nas = np.bincount(sids[asd], minlength=nsec)
                    noev = int(((nall >= 2) & (nas == 0)).sum())
                    capn = int(anyc.sum())
                    S(f"V {r} {SHORT[nm]} k{int(k * 100)}", (f"ev {ne} cap {pct(capn, ne)} pre {pct(prec.sum(), ne)} in-only {pct(ino.sum(), ne)} none {pct(ne - capn, ne)}"
                                                           f" | sig {nsig} assoc {pct(asd.sum(), nsig)} uniq-ev/sig {uniq / max(nsig, 1):.3f} false/cap {(nsig - asd.sum()) / max(capn, 1):.1f}"
                                                           f" rep/cap {rep / max(capn, 1):.1f} repeat-share {pct(rep, nsig)} secs>=2sig-noev {noev}")[:198])
                    if k == 0.05:
                        ps, pl = self._s4_prescore(ev, tsel, pr[nm])
                        both = np.isfinite(ps) & np.isfinite(pl)
                        gt = (ps[both] > pl[both]).mean() + 0.5 * (ps[both] == pl[both]).mean() if both.any() else np.nan
                        self.lg(f"RANK {r} {SHORT[nm]} k{int(k * 100)}: pre-score med {np.nanmedian(ps):.3f} placebo med {np.nanmedian(pl):.3f} | pre>placebo {100 * gt:.1f}% (n {int(both.sum())}) | event-vs-placebo AUC {self._auc2(ps, pl):.3f}")
        # deduplication (E1)
        ev = evd["E1"]; aid, ain = asc["E1"]
        tsel = (ev["date"] >= T0) & (ev["date"] <= T1)
        ne = int(tsel.sum())
        for nm in ("fullA RF", "volume LR"):
            for k in (0.01, 0.05, 0.10):
                base_sig = None
                for rule in ("N0", "C10", "C20", "CW", "CE"):
                    kept = self._s4_dedup(fl[nm][k], rule, aid, scored)
                    sig = kept & testrows
                    nsig = int(sig.sum())
                    cap = self._s4_capture(ev, tsel, kept)
                    anyc = (cap["pre"] + cap["dur"]) > 0
                    capn = int(anyc.sum())
                    asd = aid[sig] >= 0
                    if rule == "N0":
                        base_sig, base_cap = nsig, max(capn, 1)
                    ld = cap["lead"][cap["lead"] > 0]
                    yrs = "/".join(str(int((sig & (self.Y == y)).sum())) for y in range(2021, 2026))
                    self.lg(f"DEDUP {SHORT[nm]} k{int(k * 100)} {rule}: sig {nsig} cap {pct(capn, ne)} pre {pct((cap['pre'] > 0).sum(), ne)} prec {pct(asd.sum(), nsig)} false {int(nsig - asd.sum())}"
                            f" removed/cap {(base_sig - nsig) / base_cap:.1f} lead1-40 p25/50/75 {q(ld, (25, 50, 75))} | 21-25 {yrs}")
        self.lg("CHECK " + self.s4_check)

    def mode_s4lead(self):
        S = self.set_runtime_statistic
        sc, scored, testrows, fl, pr = self._s4_prep_eval(["fullA RF", "volume LR"])
        wins = ((1, 2), (3, 5), (6, 10), (11, 20), (21, 40))
        defs = (("A", "E1"), ("B", "E1"), ("M", "E1"), ("A", "E3"), ("A", "E2"))
        evs = {}
        for fam, rule in defs:
            ev = self._s4_events(TI[(fam, 10, 1.0)], rule)
            evs[(fam, rule)] = ev
            tsel = (ev["date"] >= T0) & (ev["date"] <= T1)
            s, l = ev["start"][tsel], ev["last"][tsel]
            s0 = self.SEG0[s]
            for nm in ("fullA RF", "volume LR"):
                for k in ((0.01, 0.05, 0.10) if nm == "fullA RF" else (0.05,)):
                    if rule == "E2" and k != 0.05:
                        continue
                    f = fl[nm][k]
                    cf = np.concatenate([[0], np.cumsum(f)])
                    parts = []
                    for a, b in wins:
                        ok = (s - b >= s0) & (self.D[np.maximum(s - b, 0)] >= SCORE_START)
                        c = self._wcount(cf, s - b, s - a)
                        parts.append(f"{a}-{b} {100 * (c[ok] > 0).mean() if ok.any() else np.nan:.1f}%")
                    lo40 = np.maximum(s - 40, s0)
                    pre40 = self._wcount(cf, lo40, s - 1) > 0
                    dur = self._wcount(cf, s, l) > 0
                    cap = self._s4_capture(ev, tsel, f)
                    ld = cap["lead"][cap["lead"] > 0]
                    S(f"L {fam}{rule} {SHORT[nm]} k{int(k * 100)}", (f"n {len(s)} | " + " ".join(parts) + f" | pre1-40 {100 * pre40.mean():.1f}% in-only {100 * (~pre40 & dur).mean():.1f}%"
                                                                    f" none {100 * (~pre40 & ~dur).mean():.1f}% | lead p10/25/50/75/90 {q(ld)} mean {ld.mean() if len(ld) else np.nan:.1f}")[:198])
        # C4 / C5: pre-onset (1-10) vs placebo (31-40), RF, paired event-level bootstrap by security
        nsec = int(self.SID.max()) + 1
        W = self._boot_W(2000, 404, nsec)
        for fam, rule in (("A", "E1"), ("A", "E2"), ("A", "E3")):
            ev = evs[(fam, rule)]
            tsel = (ev["date"] >= T0) & (ev["date"] <= T1)
            clean = self._s4_clean(ev)
            for k in (0.01, 0.05, 0.10):
                cap = self._s4_capture(ev, tsel, fl["fullA RF"][k])
                for tag, m in (("all", np.ones(int(tsel.sum()), dtype=bool)), ("clean", clean[tsel])):
                    use = cap["pok"] & m
                    pre = (cap["pre"][use] > 0).astype(np.float32); plc = (cap["plac"][use] > 0).astype(np.float32)
                    sidu = cap["sid"][use]
                    P1 = np.bincount(sidu, weights=pre, minlength=nsec); P0 = np.bincount(sidu, weights=plc, minlength=nsec); N = np.bincount(sidu, minlength=nsec).astype(np.float32)
                    bn = W @ N
                    d = (W @ P1 - W @ P0) / np.maximum(bn, 1e-9)
                    rp, rq = pre.mean() if len(pre) else np.nan, plc.mean() if len(plc) else np.nan
                    line = f"pre1-10 {100 * rp:.1f}% placebo31-40 {100 * rq:.1f}% diff {100 * (rp - rq):+.1f}pp {self._ci(100 * d, 1)} ratio {rp / max(rq, 1e-9):.2f} n {len(pre)}"
                    if k == 0.05 and tag == "all":
                        S(f"C4 {fam}{rule} RF k5", line)
                    else:
                        self.lg(f"C4 {fam}{rule} RF k{int(k * 100)} {tag}: {line}")
        # lead vs magnitude (A E1, RF, k 1 / 5)
        ev = evs[("A", "E1")]
        tsel = (ev["date"] >= T0) & (ev["date"] <= T1)
        mx, cB, cM, adv, px, dv = ev["mx"][tsel], ev["confB"][tsel], ev["confM"][tsel], ev["adv"][tsel], ev["px"][tsel], ev["dv"][tsel]

        def grp(m):
            if not m.any():
                return "n 0"
            return (f"n {int(m.sum())} maxret med {100 * np.median(mx[m]):.0f}% p75 {100 * np.percentile(mx[m], 75):.0f}% | conf B {100 * cB[m].mean():.0f}% Bmax {100 * cM[m].mean():.0f}%"
                    f" | adv med {100 * np.nanmedian(adv[m]) if np.isfinite(adv[m]).any() else np.nan:.0f}% | px med {np.median(px[m]):.2f} <$1 {100 * (px[m] < 1).mean():.0f}% $vol med {np.median(dv[m]) / 1e3:.0f}k")
        for k in (0.01, 0.05):
            cap = self._s4_capture(ev, tsel, fl["fullA RF"][k])
            gpre = cap["pre"] > 0; gin = (cap["pre"] == 0) & (cap["dur"] > 0); gno = (cap["pre"] + cap["dur"]) == 0
            for tag, m in (("pre1-10", gpre), ("in-only", gin), ("none", gno)):
                self.lg(f"MAG k{int(k * 100)} {tag}: " + grp(m))
            ld = cap["lead"]
            for a, b in ((1, 2), (3, 5), (6, 10), (11, 40)):
                self.lg(f"MAG k{int(k * 100)} lead {a}-{b}: " + grp((ld >= a) & (ld <= b)))
            has = ld > 0
            if has.sum() > 10:
                rho = pd.Series(ld[has]).corr(pd.Series(mx[has]), method="spearman")
                rho2 = pd.Series(ld[has]).corr(pd.Series(cM[has].astype(float)), method="spearman")
                self.lg(f"MAG k{int(k * 100)} Spearman(lead, max ret) {rho:+.3f}  Spearman(lead, Bmax confirmation) {rho2:+.3f}  n {int(has.sum())}")
        self.lg("CHECK " + self.s4_check)
