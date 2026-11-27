# region imports
from AlgorithmImports import *
import hashlib, time as _time
from datetime import datetime as _dt, timedelta as _td, date as _date
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s4_core import *
from xup_s4_core import _o
from xup_s45_core import *
# endregion
#
# Stage 4.6 core (research/extreme_upside/stage46/protocol.md): raw daily OHLC per row (wrapper around the Stage 4.5
# wrapper), frozen signal groups (L2 / STATE / VOLU) and the matched control, minute-data access (regular session,
# RAW), the H-next trigger, entry-price proxies and the frozen +30 / -10 / t+5 bracket from the entry price.
# Security-level records never leave QC; modes print aggregates only.

KEEP46 = _o(2020, 6, 1)
COST46 = {"optimistic": 1.0 * S30 + 0.001, "neutral": 2.0 * S30 + 0.005, "conservative": 3.0 * S30 + 0.015}
# (name, $vol threshold, window minutes, breakout type); index 0 = PRIMARY
VAR46 = [("P", 1e6, 30, "high"), ("V0.5M", 5e5, 30, "high"), ("V2M", 2e6, 30, "high"), ("V5M", 5e6, 30, "high"),
         ("W5", 1e6, 5, "high"), ("W15", 1e6, 15, "high"), ("W60", 1e6, 60, "high"), ("BCLOSE", 1e6, 30, "close")]
OUTC = ["neither", "target", "ambiguous", "adverse", "incomplete"]


class S46Core:

    # ---------------- panel extension: raw O/H/L and adjustment factor per row ----------------
    def _security(self, sid, cls, adj, raw):
        r = self._security_s45(sid, cls, adj, raw)
        if r is None:
            return None
        if not hasattr(self, "X46"):
            self.X46 = []
        kd = r[0]
        n = len(kd)
        k0 = int(np.searchsorted(kd, KEEP46))
        if k0 >= n:
            self.X46.append((n, k0, None))
            return r
        try:
            d = kd[k0:]
            rds, ro, rh, rl, rc, rv = raw
            ads, ao, ah, al, ac, av = adj
            ir = np.searchsorted(rds, d); ia = np.searchsorted(ads, d)
            okr = (ir < len(rds)) & (rds[np.minimum(ir, len(rds) - 1)] == d)
            oka = (ia < len(ads)) & (ads[np.minimum(ia, len(ads) - 1)] == d)
            ir, ia = np.minimum(ir, len(rds) - 1), np.minimum(ia, len(ads) - 1)
            nan = np.float32(np.nan)
            O = np.where(okr, ro[ir], nan).astype(np.float32); H = np.where(okr, rh[ir], nan).astype(np.float32)
            L = np.where(okr, rl[ir], nan).astype(np.float32); C = np.where(okr, rc[ir], nan).astype(np.float32)
            with np.errstate(divide="ignore", invalid="ignore"):
                AF = np.where(okr & oka & (rc[ir] > 0), ac[ia] / rc[ir], nan).astype(np.float32)
            ex = (O, H, L, C, AF)
        except Exception as e:
            self.err.append("s46x " + type(e).__name__)
            ex = None
        self.X46.append((n, k0, ex))
        return r

    def _s46_finish(self):
        if getattr(self, "s46_ready", False):
            return
        self._s45_finish()
        X = self.X46
        assert len(X) == len(self.sid_list), "X46 / parts misaligned"
        N = len(self.D)
        assert sum(x[0] for x in X) == N, "X46 row count"
        self.RO, self.RH, self.RL, self.RCL, self.AF = (np.full(N, np.nan, dtype=np.float32) for _ in range(5))
        off = 0
        for i in range(len(X)):
            n, k0, ex = X[i]
            if ex is not None:
                a, b = off + k0, off + n
                self.RO[a:b], self.RH[a:b], self.RL[a:b], self.RCL[a:b], self.AF[a:b] = ex
            X[i] = None
            off += n
        self.X46 = None
        k = self.D >= KEEP46
        f = k & np.isfinite(self.RCL)
        mis = int((np.abs(self.RCL[f] / self.PX[f] - 1) > 1e-4).sum())
        nm = int((k & ~np.isfinite(self.RCL)).sum())
        self.s46_ok = self.s45_ok and mis == 0 and not any(e.startswith("s46x") for e in self.err)
        self.set_runtime_statistic("S46 CHECK", ("OK " if self.s46_ok else "FAILED ") + f"raw OHLC rows>=2020-06 {int(k.sum())} | raw close vs panel price mismatches {mis} | missing {nm} | S45 {'OK' if self.s45_ok else 'FAILED'}")
        self._s45_trim()
        self.s46_ready = True

    # ---------------- frozen groups ----------------
    def _s46_groups(self, uname="S1", folds=("a", "b"), lo=None, hi=None, volu=True):
        """frozen Stage 4.5 population and per-day top-10 % signal masks (L2, STATE, VOLU)"""
        exante, lab, st, mv, eh = self._s45_primary(uname, 0.05, "E1", 3, "trail")
        specs = [("STATE", "state", []), ("L2_FULL", "l2", FULL45)] + ([("LR_VOLU", "lr", G_STATE + G_VOLU)] if volu else [])
        sc = self._s45_models(exante, lab, st, eh, specs, folds=folds)
        lo = T0 if lo is None else lo
        hi = T1 if hi is None else hi
        per = (self.D >= lo) & (self.D <= hi)
        popev = exante & np.isfinite(sc["L2_FULL"]) & per
        sig = {nm: self._s45_signals(sc[nm], popev, 0.10) for nm, _, _ in specs}
        return dict(pop=popev, L2=sig["L2_FULL"], STATE=sig["STATE"], VOLU=sig.get("LR_VOLU"), lab=lab, st=st, sc=sc)

    def _s46_controls(self, g):
        """one same-date S1-P5 non-signal row per L2 row, nearest in standardised (log price, log trailing $vol, atr_p)"""
        pool = g["pop"] & ~g["L2"] & ~g["STATE"]
        atr = self.F[:, self.FC45["atr_p"]].astype(np.float64)
        Z = np.column_stack([np.log(np.maximum(self.RC, 1e-6)), np.log(np.maximum(self.DVMED.astype(np.float64), 1.0)), atr])
        m = g["pop"]
        mu, sd = np.nanmean(Z[m], axis=0), np.nanstd(Z[m], axis=0)
        Z = (Z - mu) / np.where(sd > 0, sd, 1)
        Z = np.where(np.isfinite(Z), Z, 0)
        ctl = np.zeros(len(self.D), dtype=bool)
        L = np.nonzero(g["L2"])[0]; P = np.nonzero(pool)[0]
        dl = pd.Series(L).groupby(self.D[L]); dp = {d: v.values for d, v in pd.Series(P).groupby(self.D[P])}
        nmiss = 0
        for d, rows in dl:
            cand = list(dp.get(d, []))
            for r in sorted(rows.values, key=lambda x: hashlib.md5(f"c|{self.sid_list[self.SID[x]]}|{d}".encode()).hexdigest()):
                if not cand:
                    nmiss += 1
                    continue
                dist = [(float(((Z[c] - Z[r]) ** 2).sum()), hashlib.md5(f"t|{self.sid_list[self.SID[c]]}|{d}".encode()).hexdigest(), c) for c in cand]
                best = min(dist)[2]
                ctl[best] = True
                cand.remove(best)
        return ctl, nmiss

    # ---------------- minute data ----------------
    def _s46_df(self, h, quote=False):
        if h is None or len(h) == 0:
            return None
        df = h.reset_index()
        tcol = "time" if "time" in df.columns else df.columns[1]
        tt = pd.to_datetime(df[tcol])
        if getattr(tt.dt, "tz", None) is not None:
            tt = tt.dt.tz_convert("America/New_York")
        mins = (tt.dt.hour * 60 + tt.dt.minute).values.astype(np.int32)
        o = np.argsort(mins, kind="mergesort")
        out = {"m": mins[o], "d": np.array([t.toordinal() for t in tt.dt.date.values])[o] if len(tt) else np.array([], dtype=np.int64)}
        cols = ("bidopen", "bidclose", "askopen", "askclose", "bidsize", "asksize") if quote else ("open", "high", "low", "close", "volume")
        for c in cols:
            out[c] = df[c].values.astype(np.float64)[o] if c in df.columns else np.full(len(df), np.nan)
        return out

    def _s46_shift(self, b):
        """bar-label convention: 0 = bar END times (09:31..16:00), 1 = bar START times (09:30..15:59); decided by majority"""
        if not hasattr(self, "s46_lab"):
            self.s46_lab = [0, 0]
        if b is not None and len(b["m"]):
            self.s46_lab[0] += int((b["m"] == 570).any()); self.s46_lab[1] += int((b["m"] == 960).any())
        return 1 if self.s46_lab[0] > self.s46_lab[1] else 0

    def _s46_minute(self, sym, d, quote=False):
        t0 = _dt.combine(_date.fromordinal(int(d)), _dt.min.time())
        self.s46_calls = getattr(self, "s46_calls", 0) + 1
        if quote:
            h = self.history(QuoteBar, sym, t0, t0 + _td(days=1), Resolution.MINUTE, fill_forward=False, extended_market_hours=False)
        else:
            h = self.history(sym, t0, t0 + _td(days=1), Resolution.MINUTE, fill_forward=False, extended_market_hours=False, data_normalization_mode=DataNormalizationMode.RAW)
        b = self._s46_df(h, quote)
        if b is None:
            return None
        keep = b["d"] == int(d)
        b = {k: v[keep] for k, v in b.items()}
        sh = self._s46_shift(b) if not quote else self._s46_shift(None)
        b["m"] = b["m"] + sh
        reg = (b["m"] > 570) & (b["m"] <= 960)
        b = {k: v[reg] for k, v in b.items()}
        if not quote:
            ok = b["volume"] > 0
            b = {k: v[ok] for k, v in b.items()}
        return b if len(b["m"]) else None

    # ---------------- trigger and entry ----------------
    def _s46_trigger(self, b, Href, var):
        """returns (m_star, same_bar, dv30) or (None, None, dv30); completed bars only"""
        _, thr, win, typ = var
        dvc = np.cumsum(b["close"] * b["volume"])
        dv30 = float(dvc[b["m"] <= 600][-1]) if (b["m"] <= 600).any() else 0.0
        brk = (b["high"] > Href) if typ == "high" else (b["close"] > Href)
        ib = np.nonzero(brk)[0]; iv = np.nonzero(dvc >= thr)[0]
        if len(ib) == 0 or len(iv) == 0:
            return None, None, dv30, (len(ib) > 0 and b["m"][ib[0]] <= 570 + win), (len(iv) > 0 and b["m"][iv[0]] <= 570 + win)
        mb, mvv = b["m"][ib[0]], b["m"][iv[0]]
        ms = max(mb, mvv)
        okb, okv = mb <= 570 + win, mvv <= 570 + win
        if ms > 570 + win:
            return None, None, dv30, okb, okv
        return int(ms), bool(ib[0] == iv[0]), dv30, okb, okv

    def _s46_entry(self, b, q, ms):
        """first executable-price proxy after the end of bar ms: (P_e, type 1 quote / 2 minute proxy, s_trig, j_e)"""
        je = np.nonzero(b["m"] > ms)[0]
        je = int(je[0]) if len(je) else -1
        if q is not None:
            for k in np.nonzero((q["m"] > ms) & (q["m"] <= ms + 2))[0]:
                a = q["askopen"][k] if np.isfinite(q["askopen"][k]) and q["askopen"][k] > 0 else q["askclose"][k]
                bd = q["bidopen"][k] if np.isfinite(q["bidopen"][k]) and q["bidopen"][k] > 0 else q["bidclose"][k]
                if np.isfinite(a) and np.isfinite(bd) and a > 0 and bd > 0 and a >= bd and (a - bd) / ((a + bd) / 2) <= 0.20:
                    return float(a), 1, float((a - bd) / ((a + bd) / 2)), je
        if je >= 0:
            return float((b["open"][je] + b["high"][je]) / 2), 2, np.nan, je
        return np.nan, 0, np.nan, je

    # ---------------- bracket from the entry price ----------------
    def _s46_complete(self, i):
        n = len(self.D)
        if i + 5 >= n or self.GS[i + 5] != self.GS[i]:
            return False, "window"
        w = slice(i, i + 6)
        if not (np.isfinite(self.RO[w]).all() and np.isfinite(self.RH[w]).all() and np.isfinite(self.RL[w]).all() and np.isfinite(self.RCL[w]).all()):
            return False, "daily"
        af = self.AF[w].astype(np.float64)
        if not np.isfinite(af).all() or np.max(np.abs(af / af[0] - 1)) > 0.005:
            return False, "corp"
        return True, ""

    def _s46_bracket(self, i, sym, b, je, Pe, cache):
        """outcome code (OUTC index), gross, gross_gap, hold, mae, mfe, minL5, maxH5, c1, c3, c5"""
        T, A = 1.3 * Pe, 0.9 * Pe
        lo_run, hi_run = np.inf, -np.inf
        code, gross, ggap, hold = 0, np.nan, np.nan, 5
        h1, l1 = b["high"][je:], b["low"][je:]
        ht, la = h1 >= T, l1 <= A
        ev = np.nonzero(ht | la)[0]
        minL5 = min(float(l1.min()), float(np.nanmin(self.RL[i + 2:i + 6])))
        maxH5 = max(float(h1.max()), float(np.nanmax(self.RH[i + 2:i + 6])))
        if len(ev):
            k = ev[0]
            code = 2 if (ht[k] and la[k]) else (1 if ht[k] else 3)
            lo_run, hi_run, hold = float(l1[:k + 1].min()), float(h1[:k + 1].max()), 1
        else:
            lo_run, hi_run = float(l1.min()), float(h1.max())
            for s in range(2, 6):
                o, hh, ll = float(self.RO[i + s]), float(self.RH[i + s]), float(self.RL[i + s])
                lo_run, hi_run = min(lo_run, ll), max(hi_run, hh)
                if o >= T:
                    code, hold = 1, s
                elif o <= A:
                    code, hold, ggap = 3, s, o / Pe - 1
                elif hh >= T and ll <= A:
                    key = (sym, int(self.D[i + s]))
                    if key not in cache:
                        try:
                            cache[key] = self._s46_minute(sym, self.D[i + s])
                        except Exception:
                            cache[key] = None
                    mb = cache[key]
                    code, hold = 2, s
                    if mb is not None:
                        t2, a2 = mb["high"] >= T, mb["low"] <= A
                        e2 = np.nonzero(t2 | a2)[0]
                        if len(e2) and not (t2[e2[0]] and a2[e2[0]]):
                            code = 1 if t2[e2[0]] else 3
                elif hh >= T:
                    code, hold = 1, s
                elif ll <= A:
                    code, hold = 3, s
                if code:
                    break
        gross = {0: float(self.RCL[i + 5]) / Pe - 1, 1: 0.30, 2: -0.10, 3: -0.10}[code]
        if not np.isfinite(ggap):
            ggap = gross
        c = [float(self.RCL[i + k]) / Pe - 1 for k in (1, 3, 5)]
        return code, gross, ggap, hold, lo_run / Pe - 1, hi_run / Pe - 1, minL5 / Pe - 1, maxH5 / Pe - 1, c[0], c[1], c[2]
