# region imports
from AlgorithmImports import *
import time as _time
from datetime import datetime as _dt, timedelta as _td, date as _date
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s4_core import *
from xup_s4_core import _o
from xup_s45_core import *
# endregion
#
# Stage 4.5: S45ROBUST (population / universe / label / family sensitivities of the C2 capture comparison, C8, S2
# direction for C6), S45GRID (price x trailing-median dollar-volume grid, same-day rule universes) and S45EXEC
# (minute-quote samples: spreads, time to first two-sided quote, early VWAP vs open; s30 for the cost scenarios).

for _p in (1.0, 2.0, 5.0):
    for _d in (2.5e5, 5e5, 1e6):
        UNIV[f"G{int(_p)}_{int(_d / 1e3)}k"] = (_p, _d)
P21 = (T0, _o(2022, 12, 31)); P23 = (_o(2023, 1, 1), T1)


class S45ModesC:

    def _s45_c2var(self, uname, kst=0.05, defn="E1", k=3, rule="trail", alt="L2_FULL", B=1000):
        """C2-type comparison (alt timing model vs STATE, per-day top-10 % signals, pre-event capture) in one population"""
        self._s45_primary()
        exante, lab, st = self._s45_pop(uname, kst, defn, k, rule)
        mv = self._s45_mv(defn)
        eh = self._s45_evhist(self._s45_mv("E1"))
        kind = "rf" if alt.startswith("RF") else "l2"
        sc = self._s45_models(exante, lab, st, eh, [("STATE", "state", []), (alt, kind, FULL45)], folds=("a", "b"))
        test = (self.D >= T0) & (self.D <= T1)
        popev = exante & np.isfinite(sc[alt]) & test
        ev = popev & (lab >= 0)
        y = (lab[ev] == 1)
        sel = (mv["date"] >= T0) & (mv["date"] <= T1)
        allev = int((sel & st["umask"][np.maximum(mv["t1"] - 1, 0)]).sum())
        r = {"rows": int(ev.sum()), "pos": int(y.sum()), "base": y.mean() if len(y) else np.nan, "allev": allev}
        same1 = np.concatenate([[False], self.GS[1:] == self.GS[:-1]])
        nd = max(len(np.unique(self.D[popev])), 1)
        for nm in ("STATE", alt):
            sig = self._s45_signals(sc[nm], popev, 0.10)
            e = self._s45_evstats(mv, sel, sig, popev, lab, k)
            prev = np.zeros(len(sig), dtype=bool); prev[1:] = sig[:-1]
            prev &= same1
            r[nm] = e
            r[nm + "_turn"] = 1 - prev[sig].mean() if sig.any() else np.nan
            r[nm + "_spd"] = sig.sum() / nd
            r[nm + "_px"] = np.median(self.RC[sig]) if sig.any() else np.nan
            r[nm + "_dv"] = np.median(self.DVMED[sig]) if sig.any() else np.nan
        el = r["STATE"]["elig"]
        a, b = r[alt]["cap"][el].astype(float), r["STATE"]["cap"][el].astype(float)
        dts = mv["date"][sel][el]
        r["el"] = int(el.sum())
        if el.sum() == 0:
            r.update(d=np.nan, cs="[n/a]", lo=np.nan, per={"21-22": np.nan, "23-25": np.nan}, capS=np.nan, capL=np.nan)
            return r
        pb = self._s45_pairboot(a, b, r["STATE"]["sid"][el], None, B=B)
        r.update(d=pb["d"], cs=pb["cs"], lo=pb["lo_s"], capS=b.mean(), capL=a.mean())
        r["per"] = {}
        for tag, (lo, hi) in (("21-22", P21), ("23-25", P23)):
            m = (dts >= lo) & (dts <= hi)
            r["per"][tag] = (a[m].mean() - b[m].mean()) if m.any() else np.nan
        return r

    def _s45_c2txt(self, r, alt="L2_FULL"):
        return (f"rows {r['rows']} pos {r['pos']} base {100 * r['base']:.2f}% | ev {r['el']}/{r['allev']} cap S {100 * r['capS']:.1f}% {alt[:2]} {100 * r['capL']:.1f}% d {100 * r['d']:+.1f}pp {r['cs']}"
                f" | P10 S {100 * r['STATE']['prec']:.2f}% {alt[:2]} {100 * r[alt]['prec']:.2f}% | sig/d {r[alt + '_spd']:.1f} turn {100 * r[alt + '_turn']:.0f}%")

    def _s45_c2log(self, tag, r, alt="L2_FULL"):
        self.lg(f"RV {tag}: {self._s45_c2txt(r, alt)} | per 21-22 {100 * r['per']['21-22']:+.1f} 23-25 {100 * r['per']['23-25']:+.1f}pp"
                f" | turn S {100 * r['STATE_turn']:.0f}% | med px S ${r['STATE_px']:.2f} {alt[:2]} ${r[alt + '_px']:.2f} | med dvmed20 S {r['STATE_dv'] / 1e3:.0f}k {alt[:2]} {r[alt + '_dv'] / 1e3:.0f}k"
                f" | event precision S {100 * r['STATE']['prec']:.2f}% {alt[:2]} {100 * r[alt]['prec']:.2f}% false/captured {r[alt]['fpc']:.1f} signals/security {r[alt]['sps']:.1f}")

    def mode_s45robusta(self):
        self._s45_robust([("S1-P5 reference", dict(uname="S1")), ("S1-P1", dict(uname="S1", kst=0.01)), ("S1-P10", dict(uname="S1", kst=0.10)),
                          ("E2 labels", dict(uname="S1", defn="E2")), ("E3 labels", dict(uname="S1", defn="E3")),
                          ("RF family", dict(uname="S1", alt="RF_FULL")), ("S1 A-strict", dict(uname="S1/strict"))], part="A")

    def mode_s45robustb(self):
        self._s45_robust([("S1 history>=120", dict(uname="S1/h120")),
                          ("S1 price $1-5", dict(uname="S1/px1_5")), ("S1 price >=$5", dict(uname="S1/px5")),
                          ("S1 same-day $vol", dict(uname="S1", rule="day")),
                          ("S2-P5", dict(uname="S2")), ("S0-P5", dict(uname="S0")), ("S5M-P5", dict(uname="S5M")), ("A-P5", dict(uname="A"))], part="B")

    def _s45_robust(self, variants, part):
        S = self.set_runtime_statistic
        self._s45_finish()
        t0 = _time.time()
        c8 = {}
        for tag, kw in variants:
            alt = kw.pop("alt", "L2_FULL")
            try:
                r = self._s45_c2var(alt=alt, **kw)
            except Exception as e:
                S(f"R {tag}", f"ERROR {type(e).__name__}: {str(e)[:120]}")
                continue
            S(f"R {tag}", self._s45_c2txt(r, alt)[:198])
            self._s45_c2log(tag, r, alt)
            if tag == "S1-P5 reference":
                c8["2021-22"] = r["per"]["21-22"]; c8["2023-25"] = r["per"]["23-25"]
            for nm, key in (("E2 labels", "E2"), ("E3 labels", "E3"), ("RF family", "RF"), ("S1 A-strict", "A-strict"), ("S1 same-day $vol", "day rule"),
                            ("S2-P5", "S2"), ("S1 price $1-5", "px $1-5"), ("S1 price >=$5", "px >=$5")):
                if tag == nm:
                    c8[key] = r["d"]
            if tag == "S2-P5":
                self.s2dir = r["d"]
            self._s45_free()
            self.lg(f"T {tag} done at {(_time.time() - t0) / 60:.1f} min")
        keys = ["E2", "E3", "2021-22", "2023-25", "RF", "A-strict"] if part == "A" else ["day rule", "S2", "px $1-5", "px >=$5"]
        fails = [k for k in keys if not (k in c8 and np.isfinite(c8[k]) and c8[k] > 0)]
        S(f"C8 items part {part} (C2 direction)", (" ".join(f"{k} {100 * c8[k]:+.1f}" if k in c8 else f"{k} n/a" for k in keys) + f" | non-positive {len(fails)}: {fails} (C8 = all 10 items, at most 1 fail)")[:198])
        if part == "B":
            S("C6 part: S2 direction of C2", f"S2 capture difference {100 * getattr(self, 's2dir', np.nan):+.1f}pp -> {'same sign (>0)' if getattr(self, 's2dir', -1) > 0 else 'NOT reproduced'} (C4 lift in S2: S45OUTCOME)")
        self.lg(f"runtime {(_time.time() - t0) / 60:.1f} min")
        self._s45_end()

    def mode_s45grida(self):
        self._s45_grid((1, 2), ())

    def mode_s45gridb(self):
        self._s45_grid((5,), ("S0", "S2", "S5M"))

    def _s45_grid(self, prices, dayun):
        S = self.set_runtime_statistic
        self._s45_finish()
        t0 = _time.time()
        for p in prices:
            parts = []
            for d in (250, 500, 1000):
                nm = f"G{p}_{d}k"
                try:
                    r = self._s45_c2var(uname=nm, B=500)
                    parts.append(f"{d}k: ev {r['el']} S {100 * r['capS']:.1f} L2 {100 * r['capL']:.1f} d {100 * r['d']:+.1f}{r['cs']} P10 {100 * r['L2_FULL']['prec']:.1f}%")
                    self._s45_c2log(f"grid px>={p} dvmed>={d}k", r)
                except Exception as e:
                    parts.append(f"{d}k: ERROR {type(e).__name__}")
                self._s45_free()
            S(f"G price>=${p}", " | ".join(parts)[:198])
        for un in dayun:
            try:
                r = self._s45_c2var(uname=un, rule="day", B=500)
                S(f"G {un} same-day rule", self._s45_c2txt(r)[:198])
                self._s45_c2log(f"{un} same-day", r)
            except Exception as e:
                S(f"G {un} same-day rule", f"ERROR {type(e).__name__}: {str(e)[:120]}")
            self._s45_free()
        self.lg(f"runtime {(_time.time() - t0) / 60:.1f} min")
        self._s45_end()

    # ---------------- execution audit ----------------
    def _s45_mstats(self, tb, qb):
        out = {}
        if tb is not None and len(tb) > 0:
            df = tb.reset_index()
            tcol = "time" if "time" in df.columns else df.columns[1]
            tt = pd.to_datetime(df[tcol])
            if getattr(tt.dt, "tz", None) is not None:
                tt = tt.dt.tz_convert("America/New_York")
            mins = (tt.dt.hour * 60 + tt.dt.minute).values
            reg = (mins > 570) & (mins <= 960) & (df["volume"].values > 0)
            if reg.any():
                o, h, l, c, v = (df[x].values for x in ("open", "high", "low", "close", "volume"))
                i0 = np.nonzero(reg)[0][0]
                op = o[i0]
                out["n_reg"] = int(reg.sum())
                out["dv_reg"] = float((c[reg] * v[reg]).sum())
                out["dv_30"] = float((c[reg & (mins <= 600)] * v[reg & (mins <= 600)]).sum())
                out["t_trade"] = float(mins[i0] - 570)
                tp = (h + l + c) / 3
                for w in (5, 15, 30):
                    m = reg & (mins <= 570 + w)
                    if m.any() and op > 0:
                        out[f"vw{w}"] = float((tp[m] * v[m]).sum() / max(v[m].sum(), 1e-9) / op - 1)
        if qb is not None and len(qb) > 0:
            dq = qb.reset_index()
            qt = pd.to_datetime(dq["time"]) if "time" in dq.columns else pd.to_datetime(dq.iloc[:, 1])
            if getattr(qt.dt, "tz", None) is not None:
                qt = qt.dt.tz_convert("America/New_York")
            qm = (qt.dt.hour * 60 + qt.dt.minute).values
            if "bidclose" in dq.columns and "askclose" in dq.columns:
                b, a = dq["bidclose"].values, dq["askclose"].values
                ok = (qm > 570) & (qm <= 960) & (b > 0) & (a > 0) & (a >= b)
                out["n_q"] = int(ok.sum())
                if ok.any():
                    sp = (a - b) / ((a + b) / 2)
                    out["t_quote"] = float(qm[ok][0] - 570)
                    out["spr"] = float(np.median(sp[ok]))
                    for w in (5, 15, 30):
                        m = ok & (qm <= 570 + w)
                        out[f"spr{w}"] = float(np.median(sp[m])) if m.any() else np.nan
        return out

    def mode_s45exec(self):
        S = self.set_runtime_statistic
        self._s45_finish()
        t_start = _time.time()
        exante, lab, st, mv, eh = self._s45_primary()
        test = (self.D >= T0) & (self.D <= T1)
        nxt_ok = np.zeros(len(self.D), dtype=bool)
        nxt_ok[:-1] = self.GS[1:] == self.GS[:-1]
        sig, pops = {}, {}
        for un in ("S1", "S2"):
            ex, lb, s_ = self._s45_pop(un, 0.05, "E1", 3, "trail")
            sc = self._s45_models(ex, lb, s_, eh, [("L2_FULL", "l2", FULL45)], folds=("a", "b"))["L2_FULL"]
            pe = ex & np.isfinite(sc) & test
            sig[un] = self._s45_signals(sc, pe, 0.10)
            pops[un] = pe
        s1i = np.nonzero(sig["S1"] & nxt_ok)[0]
        s2i = np.nonzero(sig["S2"] & nxt_ok)[0]
        ci = np.nonzero(pops["S1"] & ~sig["S1"] & nxt_ok)[0]
        sel = (mv["date"] >= T0) & (mv["date"] <= T1) & st["umask"][np.maximum(mv["t1"] - 1, 0)]
        mi = mv["t1"][sel]
        samples = [("S1 L2 signal, entry t+1", self._hsel(s1i, 150, "x1"), 1), ("S2 L2 signal, entry t+1", self._hsel(s2i, 80, "x2"), 1),
                   ("S1 control (pop, no signal), t+1", self._hsel(ci, 60, "x3"), 1), ("S1 E1 move day", self._hsel(mi, 80, "x4"), 0)]
        S("X0 samples", f"S1 signals {len(s1i)}, S2 signals {len(s2i)}, S1 controls {len(ci)}, S1 E1 move days {len(mi)} (test 2021-25); hash samples 150/80/60/80; minute RAW, regular session from bar end times")
        errs = {}
        s30 = np.nan
        for name, idx, off in samples:
            rec = []
            for i in idx:
                if _time.time() - t_start > 50 * 60:
                    errs["time limit"] = errs.get("time limit", 0) + 1
                    break
                j = i + off
                sym = self.syms.get(self.sid_list[self.SID[j]])
                if sym is None:
                    errs["nosym"] = errs.get("nosym", 0) + 1
                    continue
                try:
                    tb, qb = self._minute(sym, self.D[j])
                    r = self._s45_mstats(tb, qb)
                    r["px"] = self.RC[j]
                    rec.append(r)
                except Exception as e:
                    errs[type(e).__name__] = errs.get(type(e).__name__, 0) + 1
            g = lambda k: np.array([x.get(k, np.nan) for x in rec], dtype=float)
            hq = np.isfinite(g("spr")); ht = np.isfinite(g("t_trade"))
            P = (25, 50, 75, 90)
            S(f"X1 {name}", (f"done {len(rec)}/{len(idx)} trades {int(ht.sum())} quotes {int(hq.sum())} | spread p25/50/75/90 full {q(100 * g('spr'), P)}% first30 {q(100 * g('spr30'), P)}%")[:198])
            S(f"X2 {name}", (f"first5 {q(100 * g('spr5'), (25, 50, 75))}% first15 {q(100 * g('spr15'), (25, 50, 75))}% | min to 1st 2-sided quote {q(g('t_quote'), (50, 90))} 1st trade {q(g('t_trade'), (50, 90))}"
                             f" | VWAP/open-1 5m {q(100 * g('vw5'), (25, 50, 75))}% 15m {q(100 * g('vw15'), (25, 50, 75))}%")[:198])
            self.lg(f"X3 {name}: $vol regular {q(g('dv_reg') / 1e3, (25, 50, 75))}k first30 {q(g('dv_30') / 1e3, (25, 50, 75))}k | VWAP30/open-1 {q(100 * g('vw30'), (25, 50, 75))}% | price {q(g('px'), (25, 50, 75))}")
            pxs = g("px")
            for lo_, hi_, lb_ in ((1, 5, "$1-5"), (5, 1e9, ">=$5")):
                m = (pxs >= lo_) & (pxs < hi_)
                if m.any():
                    self.lg(f"X4 {name} {lb_}: n {int(m.sum())} quotes {int(hq[m].sum())} spread med full {np.nanmedian(100 * g('spr')[m]):.2f}% first30 {np.nanmedian(100 * g('spr30')[m]):.2f}%")
            if name.startswith("S1 L2"):
                s30 = np.nanmedian(g("spr30")) if np.isfinite(g("spr30")).any() else np.nan
        S("X5 s30 (S1 timing-signal sample)", f"median first-30-min relative quoted spread s30 = {100 * s30:.4f}% -> round trip optimistic {100 * s30 + 0.10:.3f}% neutral {200 * s30 + 0.50:.3f}% conservative {300 * s30 + 1.50:.3f}%")
        S("X6 errors", ("none" if not errs else " ".join(f"{k} {v}" for k, v in errs.items())) + f" | runtime {(_time.time() - t_start) / 60:.1f} min")
        self._s45_end()
