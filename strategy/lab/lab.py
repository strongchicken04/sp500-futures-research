"""
20-strategy intraday backtest lab — NAS100 (NQ proxy) 1-min.

IS window : 2005-01 .. 2017-12  (13 years)
OOS window: 2018-01 .. 2020-05  (HELD OUT, untouched)

Costs: `COST_BPS` per side (default 1.0 bps) applied to entry and exit.
Sizing: 1 unit of notional per trade (unlevered); daily return = sum of that
day's trade returns; equity compounds daily. This makes strategies with very
different trade counts directly comparable on a risk-adjusted basis.
"""
from __future__ import annotations
import os, sys, pickle
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orb_backtest import load_rth_1min, Config

DATA = "/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/fsdata/pyfinancialdata/data/currencies/oanda/NAS100_USD"
CACHE = "/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/lab_cache.pkl"
COST_BPS = 1.0
IS = (2005, 2017)
OOS = (2018, 2020)
OPEN_MIN, EOD_MIN = 570, 959     # 09:30 .. 15:59 ET


# --------------------------------------------------------------------------- #
def build_cache():
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as f:
            return pickle.load(f)
    df = load_rth_1min(Config(data_dir=DATA, start_year=2005, end_year=2020))
    df = df.sort_values(["date", "etmin"]).reset_index(drop=True)
    days = {}
    for date, g in df.groupby("date", sort=True):
        days[date] = dict(
            m=g["etmin"].to_numpy(np.int32), o=g["open"].to_numpy(float),
            h=g["high"].to_numpy(float), l=g["low"].to_numpy(float),
            c=g["close"].to_numpy(float), v=g["volume"].to_numpy(float))
    dates = sorted(days)
    # daily context
    rows = []
    for d in dates:
        a = days[d]
        rows.append((d, a["o"][0], a["h"].max(), a["l"].min(), a["c"][-1]))
    ctx = pd.DataFrame(rows, columns=["date", "O", "H", "L", "C"]).set_index("date")
    ctx["prevC"] = ctx["C"].shift(1)
    ctx["prevH"] = ctx["H"].shift(1)
    ctx["prevL"] = ctx["L"].shift(1)
    tr = pd.concat([ctx["H"] - ctx["L"], (ctx["H"] - ctx["prevC"]).abs(),
                    (ctx["L"] - ctx["prevC"]).abs()], axis=1).max(axis=1)
    ctx["atr14"] = tr.rolling(14).mean().shift(1)
    ctx["gap"] = ctx["O"] / ctx["prevC"] - 1.0
    ctx["absgap"] = ctx["gap"].abs()
    ctx["oc"] = (ctx["C"] - ctx["O"]).abs()
    ctx["noise14"] = (ctx["oc"] / ctx["O"]).rolling(14).mean().shift(1)   # Zarattini noise band
    ctx["trendiness"] = (ctx["C"] - ctx["O"]).abs() / (ctx["H"] - ctx["L"]).replace(0, np.nan)
    ctx["prevTrend"] = ctx["trendiness"].shift(1)
    ctx["rvol20"] = ctx["C"].pct_change().rolling(20).std().shift(1) * np.sqrt(252)
    ctx["sma50"] = ctx["C"].rolling(50).mean().shift(1)
    ctx["trend50"] = ctx["prevC"] / ctx["sma50"] - 1.0
    ctx["year"] = pd.to_datetime(ctx.index).year
    obj = (days, dates, ctx)
    with open(CACHE, "wb") as f:
        pickle.dump(obj, f)
    return obj


def resample_day(a, tf):
    """Aggregate a day's 1-min arrays into tf-minute bars."""
    b = (a["m"] - OPEN_MIN) // tf
    idx = np.flatnonzero(np.r_[True, b[1:] != b[:-1]])
    ends = np.r_[idx[1:], len(b)]
    o = a["o"][idx]
    c = a["c"][ends - 1]
    h = np.maximum.reduceat(a["h"], idx)
    l = np.minimum.reduceat(a["l"], idx)
    v = np.add.reduceat(a["v"], idx)
    m = a["m"][idx]
    return dict(m=m, o=o, h=h, l=l, c=c, v=v)


def ema(x, span):
    al = 2.0 / (span + 1.0)
    out = np.empty_like(x); out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = al * x[i] + (1 - al) * out[i - 1]
    return out


def rsi(x, n=2):
    d = np.diff(x, prepend=x[0])
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    au = pd.Series(up).ewm(alpha=1/n, adjust=False).mean().to_numpy()
    ad = pd.Series(dn).ewm(alpha=1/n, adjust=False).mean().to_numpy()
    rs = au / np.where(ad == 0, np.nan, ad)
    return 100 - 100 / (1 + rs)


def vwap_arr(a):
    tp = (a["h"] + a["l"] + a["c"]) / 3.0
    cpv = np.cumsum(tp * a["v"]); cv = np.cumsum(a["v"])
    return np.divide(cpv, np.where(cv == 0, np.nan, cv))


def _walk_exit(h, l, c, k0, d, stop, tgt, kend):
    """Walk bars from k0..kend; return (exit_px, kexit). Stop checked before target."""
    for k in range(k0, kend + 1):
        if d == 1:
            if l[k] <= stop: return stop, k
            if tgt is not None and h[k] >= tgt: return tgt, k
        else:
            if h[k] >= stop: return stop, k
            if tgt is not None and l[k] <= tgt: return tgt, k
    return c[kend], kend


# =========================================================================== #
#  STRATEGIES: f(a1, x) -> list[(dir, entry_px, exit_px)]
#  a1 = day's 1-min arrays; x = daily context row (prev-day info only = ex-ante)
# =========================================================================== #

# ---------- 1-3: Opening Range Breakout family --------------------------------
def _orb(a1, x, or_len, target_R):
    m, o, h, l, c = a1["m"], a1["o"], a1["h"], a1["l"], a1["c"]
    i0 = np.searchsorted(m, OPEN_MIN)
    ie = np.searchsorted(m, OPEN_MIN + or_len)
    if ie >= len(m) or ie <= i0: return []
    or_o, or_c = o[i0], c[ie - 1]
    or_h, or_l = h[i0:ie].max(), l[i0:ie].min()
    d = 1 if or_c > or_o else (-1 if or_c < or_o else 0)
    if d == 0: return []
    e = o[ie]; stop = or_l if d == 1 else or_h
    R = (e - stop) if d == 1 else (stop - e)
    if R <= 0: return []
    tgt = e + d * target_R * R if target_R else None
    px, _ = _walk_exit(h, l, c, ie, d, stop, tgt, len(m) - 1)
    return [(d, e, px)]

def s01_orb5_10r(a1, x):  return _orb(a1, x, 5, 10.0)
def s02_orb15_3r(a1, x):  return _orb(a1, x, 15, 3.0)
def s03_orb30_eod(a1, x): return _orb(a1, x, 30, None)

# ---------- 4-5: VWAP hysteresis band (user's family) -------------------------
def _vwap_band(a1, x, band_bps=20.0, gates=False):
    if gates:
        if not (x.get("gapOK", True) and x.get("trendOK", True)): return []
    m, o, h, l, c = a1["m"], a1["o"], a1["h"], a1["l"], a1["c"]
    vw = vwap_arr(a1)
    b = band_bps / 1e4
    pos, e = 0, 0.0
    for k in range(len(m)):
        if np.isnan(vw[k]) or m[k] < OPEN_MIN + 1: continue
        up, dn = vw[k] * (1 + b), vw[k] * (1 - b)
        if m[k] >= EOD_MIN:
            if pos: return [(pos, e, c[k])]
            return []
        if pos == 0:
            if c[k] > up: pos, e = 1, c[k]
            elif c[k] < dn: pos, e = -1, c[k]
        elif pos == 1 and c[k] < dn: return [(1, e, c[k])]
        elif pos == -1 and c[k] > up: return [(-1, e, c[k])]
    return [(pos, e, c[-1])] if pos else []

def s04_vwap_band(a1, x):       return _vwap_band(a1, x, 20.0, gates=False)
def s05_vwap_band_gates(a1, x): return _vwap_band(a1, x, 20.0, gates=True)

# ---------- 6: previous-day high/low breakout ---------------------------------
def s06_pdh_pdl_break(a1, x):
    """Breakout of prev-day high/low. NOTE: fills must respect gaps — on ~22% of
    days the session opens already beyond PDH, so filling *at* PDH would be a
    look-ahead (price never traded there). Entry = max(level, bar open)."""
    if np.isnan(x["prevH"]) or np.isnan(x["atr14"]): return []
    m, o, h, l, c = a1["m"], a1["o"], a1["h"], a1["l"], a1["c"]
    st = 0.5 * x["atr14"]
    for k in range(len(m)):
        if m[k] >= EOD_MIN: break
        if h[k] > x["prevH"]:
            e = max(x["prevH"], o[k])                      # gap-safe fill
            px, _ = _walk_exit(h, l, c, k, 1, e - st, None, len(m) - 1)
            return [(1, e, px)]
        if l[k] < x["prevL"]:
            e = min(x["prevL"], o[k])                      # gap-safe fill
            px, _ = _walk_exit(h, l, c, k, -1, e + st, None, len(m) - 1)
            return [(-1, e, px)]
    return []

# ---------- 7: intraday Donchian (5-min, 20 bars) -----------------------------
def s07_donchian20(a1, x):
    a = resample_day(a1, 5); m, h, l, c = a["m"], a["h"], a["l"], a["c"]
    n = len(m)
    if n < 25: return []
    out = []; pos, e = 0, 0.0
    for k in range(20, n):
        hh = h[k - 20:k].max(); ll = l[k - 20:k].min()
        if m[k] >= EOD_MIN:
            if pos: out.append((pos, e, c[k])); pos = 0
            break
        if pos == 0:
            if c[k] > hh: pos, e = 1, c[k]
            elif c[k] < ll: pos, e = -1, c[k]
        elif pos == 1 and c[k] < l[k - 10:k].min(): out.append((1, e, c[k])); pos = 0
        elif pos == -1 and c[k] > h[k - 10:k].max(): out.append((-1, e, c[k])); pos = 0
    if pos: out.append((pos, e, c[-1]))
    return out

# ---------- 8: intraday momentum (Zarattini 'Beat the Market' style) ----------
def s08_intraday_momentum(a1, x):
    if np.isnan(x["noise14"]): return []
    m, o, h, l, c = a1["m"], a1["o"], a1["h"], a1["l"], a1["c"]
    band = x["noise14"] * x["O"]
    up, dn = x["O"] + band, x["O"] - band
    pos, e = 0, 0.0
    for k in range(len(m)):
        if m[k] >= EOD_MIN: break
        if pos == 0:
            if c[k] > up: pos, e = 1, c[k]
            elif c[k] < dn: pos, e = -1, c[k]
        elif (pos == 1 and c[k] < dn) or (pos == -1 and c[k] > up):
            return [(pos, e, c[k])]
    return [(pos, e, c[-1])] if pos else []

# ---------- 9: first-hour range breakout --------------------------------------
def s09_first_hour_break(a1, x):
    m, o, h, l, c = a1["m"], a1["o"], a1["h"], a1["l"], a1["c"]
    ie = np.searchsorted(m, OPEN_MIN + 60)
    if ie >= len(m) - 5: return []
    hh, ll = h[:ie].max(), l[:ie].min()
    for k in range(ie, len(m)):
        if m[k] >= EOD_MIN: break
        if c[k] > hh:
            px, _ = _walk_exit(h, l, c, k, 1, ll, None, len(m) - 1); return [(1, c[k], px)]
        if c[k] < ll:
            px, _ = _walk_exit(h, l, c, k, -1, hh, None, len(m) - 1); return [(-1, c[k], px)]
    return []

# ---------- 10: EMA 9/21 cross (5-min) ----------------------------------------
def s10_ema_cross(a1, x):
    a = resample_day(a1, 5); m, c = a["m"], a["c"]
    if len(m) < 25: return []
    e9, e21 = ema(c, 9), ema(c, 21)
    out = []; pos, e = 0, 0.0
    for k in range(21, len(m)):
        if m[k] >= EOD_MIN:
            if pos: out.append((pos, e, c[k])); pos = 0
            break
        up = e9[k] > e21[k]; upp = e9[k-1] > e21[k-1]
        if pos == 0:
            if up and not upp: pos, e = 1, c[k]
            elif (not up) and upp: pos, e = -1, c[k]
        elif (pos == 1 and not up) or (pos == -1 and up):
            out.append((pos, e, c[k])); pos = 0
    if pos: out.append((pos, e, c[-1]))
    return out

# ---------- 11: VWAP reversion (fade stretched price) -------------------------
def s11_vwap_reversion(a1, x):
    m, h, l, c = a1["m"], a1["h"], a1["l"], a1["c"]
    vw = vwap_arr(a1)
    sd = pd.Series(c).rolling(30, min_periods=20).std().to_numpy()
    out = []; pos, e, tgt, stop = 0, 0., 0., 0.
    for k in range(len(m)):
        if np.isnan(vw[k]) or np.isnan(sd[k]) or sd[k] <= 0: continue
        if m[k] >= EOD_MIN:
            if pos: out.append((pos, e, c[k])); pos = 0
            break
        z = (c[k] - vw[k]) / sd[k]
        if pos == 0:
            if z > 2.0: pos, e, tgt, stop = -1, c[k], vw[k], c[k] + 1.5 * sd[k]
            elif z < -2.0: pos, e, tgt, stop = 1, c[k], vw[k], c[k] - 1.5 * sd[k]
        else:
            if pos == 1 and (l[k] <= stop or h[k] >= tgt):
                out.append((1, e, stop if l[k] <= stop else tgt)); pos = 0
            elif pos == -1 and (h[k] >= stop or l[k] <= tgt):
                out.append((-1, e, stop if h[k] >= stop else tgt)); pos = 0
    if pos: out.append((pos, e, c[-1]))
    return out

# ---------- 12: Bollinger fade (5-min, 20/2) ----------------------------------
def s12_bollinger_fade(a1, x):
    a = resample_day(a1, 5); m, h, l, c = a["m"], a["h"], a["l"], a["c"]
    if len(m) < 25: return []
    s = pd.Series(c); mid = s.rolling(20).mean().to_numpy(); sd = s.rolling(20).std().to_numpy()
    out = []; pos, e = 0, 0.
    for k in range(20, len(m)):
        if np.isnan(mid[k]) or np.isnan(sd[k]) or sd[k] <= 0: continue
        if m[k] >= EOD_MIN:
            if pos: out.append((pos, e, c[k])); pos = 0
            break
        up, dn = mid[k] + 2*sd[k], mid[k] - 2*sd[k]
        if pos == 0:
            if c[k] > up: pos, e = -1, c[k]
            elif c[k] < dn: pos, e = 1, c[k]
        else:
            if (pos == 1 and c[k] >= mid[k]) or (pos == -1 and c[k] <= mid[k]):
                out.append((pos, e, c[k])); pos = 0
    if pos: out.append((pos, e, c[-1]))
    return out

# ---------- 13: RSI(2) intraday mean reversion (5-min) ------------------------
def s13_rsi2(a1, x):
    a = resample_day(a1, 5); m, c = a["m"], a["c"]
    if len(m) < 15: return []
    r = rsi(c, 2)
    out = []; pos, e = 0, 0.
    for k in range(5, len(m)):
        if m[k] >= EOD_MIN:
            if pos: out.append((pos, e, c[k])); pos = 0
            break
        if pos == 0:
            if r[k] < 5: pos, e = 1, c[k]
            elif r[k] > 95: pos, e = -1, c[k]
        elif (pos == 1 and r[k] > 55) or (pos == -1 and r[k] < 45):
            out.append((pos, e, c[k])); pos = 0
    if pos: out.append((pos, e, c[-1]))
    return out

# ---------- 14: opening gap fade ----------------------------------------------
def s14_gap_fade(a1, x):
    if np.isnan(x["gap"]) or abs(x["gap"]) < 0.002: return []
    m, o, h, l, c = a1["m"], a1["o"], a1["h"], a1["l"], a1["c"]
    d = -1 if x["gap"] > 0 else 1                    # fade the gap
    e = o[0]; tgt = x["prevC"]                        # target = gap fill
    stop = e * (1 + d * -0.004)                       # 40 bps adverse stop
    px, _ = _walk_exit(h, l, c, 0, d, stop, tgt, len(m) - 1)
    return [(d, e, px)]

# ---------- 15: late-day reversal (fade the day at 14:30) ---------------------
def s15_late_reversal(a1, x):
    m, o, c = a1["m"], a1["o"], a1["c"]
    k = np.searchsorted(m, 870)                        # 14:30
    if k >= len(m) - 5: return []
    move = c[k] / o[0] - 1.0
    if abs(move) < 0.004: return []
    d = -1 if move > 0 else 1
    return [(d, c[k], c[-1])]

# ---------- 16: overnight hold (close -> next open) ---------------------------
def s16_overnight(a1, x):
    if np.isnan(x["prevC"]): return []
    return [(1, x["prevC"], a1["o"][0])]               # bought at prev close, sold at open

# ---------- 17: power-hour momentum (15:00 -> close, side = vs VWAP) ----------
def s17_power_hour(a1, x):
    m, c = a1["m"], a1["c"]
    vw = vwap_arr(a1)
    k = np.searchsorted(m, 900)                        # 15:00
    if k >= len(m) - 2 or np.isnan(vw[k]): return []
    d = 1 if c[k] > vw[k] else -1
    return [(d, c[k], c[-1])]

# ---------- 18: lunch fade (12:00 fade morning move, exit 14:00) --------------
def s18_lunch_fade(a1, x):
    m, o, c = a1["m"], a1["o"], a1["c"]
    k0 = np.searchsorted(m, 720); k1 = np.searchsorted(m, 840)
    if k0 >= len(m) or k1 >= len(m): return []
    move = c[k0] / o[0] - 1.0
    if abs(move) < 0.003: return []
    d = -1 if move > 0 else 1
    return [(d, c[k0], c[k1])]

# ---------- 19: Instagram EMA9 + VWAP wick (3-min) ----------------------------
def s19_ema_vwap_wick(a1, x):
    a = resample_day(a1, 3); m, o, h, l, c = a["m"], a["o"], a["h"], a["l"], a["c"]
    if len(m) < 12: return []
    vw = vwap_arr(a); em = ema(c, 9)
    out = []; pos, e = 0, 0.
    for k in range(1, len(m) - 1):
        if np.isnan(vw[k]): continue
        if m[k] >= EOD_MIN:
            if pos: out.append((pos, e, c[k])); pos = 0
            break
        if pos == 0:
            if l[k] < vw[k] and c[k] > vw[k]: pos, e = 1, o[k+1]
            elif h[k] > vw[k] and c[k] < vw[k]: pos, e = -1, o[k+1]
        elif (pos == 1 and c[k] < em[k]) or (pos == -1 and c[k] > em[k]):
            out.append((pos, e, o[k+1])); pos = 0
    if pos: out.append((pos, e, c[-1]))
    return out

# ---------- 20: Instagram 'No Wick' (1-min, 1:1 RR, EMA50 trend) --------------
def s20_no_wick(a1, x):
    m, o, h, l, c = a1["m"], a1["o"], a1["h"], a1["l"], a1["c"]
    if len(m) < 60: return []
    em = ema(c, 50)
    bh = np.maximum(o, c); bl = np.minimum(o, c); rg = np.maximum(h - l, 1e-9)
    tw = (h - bh) / rg; bw = (bl - l) / rg
    out = []; pend = []; pos, e, stop, tgt = 0, 0., 0., 0.
    for k in range(50, len(m)):
        if m[k] >= EOD_MIN:
            if pos: out.append((pos, e, c[k])); pos = 0
            break
        if pos:
            if pos == 1:
                if l[k] <= stop: out.append((1, e, stop)); pos = 0
                elif h[k] >= tgt: out.append((1, e, tgt)); pos = 0
            else:
                if h[k] >= stop: out.append((-1, e, stop)); pos = 0
                elif l[k] <= tgt: out.append((-1, e, tgt)); pos = 0
        if pos == 0 and pend:
            pend = [p for p in pend if p[2] >= k]
            for lvl, d, _ in pend:
                if (d == -1 and h[k] >= lvl) or (d == 1 and l[k] <= lvl):
                    e = lvl
                    if d == -1:
                        sh = h[max(0, k-15):k+1].max()
                        if sh <= e: continue
                        stop, tgt = sh, e - (sh - e)
                    else:
                        sl = l[max(0, k-15):k+1].min()
                        if sl >= e: continue
                        stop, tgt = sl, e + (e - sl)
                    pos = d; pend = []; break
        if pos == 0:
            if c[k] < o[k] and tw[k] <= 0.15 and c[k] < em[k]: pend.append((h[k], -1, k + 8))
            if c[k] > o[k] and bw[k] <= 0.15 and c[k] > em[k]: pend.append((l[k], 1, k + 8))
    if pos: out.append((pos, e, c[-1]))
    return out


STRATEGIES = {
    "01_orb5_10r": (s01_orb5_10r, "trend"), "02_orb15_3r": (s02_orb15_3r, "trend"),
    "03_orb30_eod": (s03_orb30_eod, "trend"), "04_vwap_band": (s04_vwap_band, "trend"),
    "05_vwap_band_gates": (s05_vwap_band_gates, "trend"), "06_pdh_pdl_break": (s06_pdh_pdl_break, "trend"),
    "07_donchian20": (s07_donchian20, "trend"), "08_intraday_momentum": (s08_intraday_momentum, "trend"),
    "09_first_hour_break": (s09_first_hour_break, "trend"), "10_ema_cross": (s10_ema_cross, "trend"),
    "11_vwap_reversion": (s11_vwap_reversion, "revert"), "12_bollinger_fade": (s12_bollinger_fade, "revert"),
    "13_rsi2": (s13_rsi2, "revert"), "14_gap_fade": (s14_gap_fade, "revert"),
    "15_late_reversal": (s15_late_reversal, "revert"), "16_overnight": (s16_overnight, "time"),
    "17_power_hour": (s17_power_hour, "time"), "18_lunch_fade": (s18_lunch_fade, "time"),
    "19_ema_vwap_wick": (s19_ema_vwap_wick, "instagram"), "20_no_wick": (s20_no_wick, "instagram"),
}


# =========================================================================== #
#  ENGINE
# =========================================================================== #
def add_gates(ctx, gap_pct=25.0, trend_pct=60.0, win=250):
    """Rolling-percentile gates (past-only) used by strategy 05."""
    ag = ctx["absgap"].to_numpy(); pt = ctx["prevTrend"].to_numpy()
    gok = np.ones(len(ctx), bool); tok = np.ones(len(ctx), bool)
    hg, ht = [], []
    for i in range(len(ctx)):
        if len(hg) >= 60 and not np.isnan(ag[i]):
            gok[i] = (np.mean(np.array(hg) <= ag[i]) * 100) >= gap_pct
        if len(ht) >= 60 and not np.isnan(pt[i]):
            tok[i] = (np.mean(np.array(ht) <= pt[i]) * 100) <= trend_pct
        if not np.isnan(ag[i]): hg.append(ag[i]); hg[:] = hg[-win:]
        if not np.isnan(pt[i]): ht.append(pt[i]); ht[:] = ht[-win:]
    ctx["gapOK"] = gok; ctx["trendOK"] = tok
    return ctx


def run_strategy(name, days, dates, ctx, y0, y1, cost_bps=COST_BPS):
    fn = STRATEGIES[name][0]
    cost = cost_bps / 1e4
    recs = []
    for d in dates:
        yr = int(d[:4])
        if yr < y0 or yr > y1: continue
        x = ctx.loc[d]
        try:
            trs = fn(days[d], x)
        except Exception:
            trs = []
        for (dr, e, xp) in trs:
            if e is None or e <= 0 or dr == 0: continue
            r = dr * (xp - e) / e - 2 * cost
            recs.append((d, dr, r))
    t = pd.DataFrame(recs, columns=["date", "dir", "ret"])
    return t


def metrics(t, dates_in_window):
    idx = pd.to_datetime(dates_in_window)
    if len(t) == 0:
        return dict(n=0, cagr=0, sharpe=0, mdd=0, win=0, pf=0, avgbps=0, tot=0,
                    yearly={}, daily=pd.Series(0.0, index=idx))
    dr = t.groupby("date")["ret"].sum().reindex(dates_in_window).fillna(0.0)
    dr.index = pd.to_datetime(dr.index)
    eq = (1 + dr).cumprod()
    yrs = (dr.index[-1] - dr.index[0]).days / 365.25
    cagr = (eq.iloc[-1] ** (1 / yrs) - 1) * 100 if eq.iloc[-1] > 0 else -100.0
    sharpe = dr.mean() / dr.std() * np.sqrt(252) if dr.std() else 0.0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    r = t["ret"].to_numpy()
    gw = r[r > 0].sum(); gl = -r[r <= 0].sum()
    yearly = {int(y): round(((1 + g).prod() - 1) * 100, 2)
              for y, g in dr.groupby(dr.index.year)}
    return dict(n=len(r), cagr=cagr, sharpe=sharpe, mdd=mdd,
                win=(r > 0).mean() * 100, pf=(gw / gl if gl > 0 else np.inf),
                avgbps=r.mean() * 1e4, tot=(eq.iloc[-1] - 1) * 100,
                yearly=yearly, daily=dr, equity=eq,
                trades_per_year=len(r) / yrs, calmar=(cagr / abs(mdd) if mdd else 0))


# =========================================================================== #
#  CHARTS  (4 per strategy, Czech titles, matching the requested style)
# =========================================================================== #
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm

def charts(name, m, outdir, seed=42):
    os.makedirs(outdir, exist_ok=True)
    rng = np.random.default_rng(seed)
    dr = m["daily"]; eq = m.get("equity", (1 + dr).cumprod())
    r = dr.to_numpy()

    # --- 1) equity curve + drawdown ---
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1]})
    a1.plot(eq.index, eq.values * 100, lw=1.5, color="#1f77b4")
    a1.axhline(100, color="gray", ls="--", lw=0.8, alpha=0.6)
    a1.set_ylabel("hodnota účtu (%, start = 100)")
    a1.set_title(f"Obrázek: Equity curve – {name}\nCAGR {m['cagr']:.1f} % · Sharpe {m['sharpe']:.2f} · MDD {m['mdd']:.1f} % · {m['n']} obchodů")
    a1.grid(True, alpha=0.25)
    dd = (eq - eq.cummax()) / eq.cummax() * 100
    a2.fill_between(eq.index, dd.values, 0, color="#d62728", alpha=0.4)
    a2.set_ylabel("drawdown (%)"); a2.set_xlabel("čas"); a2.grid(True, alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{outdir}/{name}_equity.png", dpi=120); plt.close(fig)

    # --- 2) Monte Carlo fan chart (250 trading days forward) ---
    N, H = 500, 250
    paths = np.empty((N, H + 1))
    for i in range(N):
        s = rng.choice(r, H, replace=True)
        paths[i] = np.r_[0.0, (np.cumprod(1 + s) - 1) * 100]
    fig, ax = plt.subplots(figsize=(12.5, 6))
    colors = cm.Spectral(np.linspace(0, 1, N))
    order = np.argsort(paths[:, -1])
    for j, i in enumerate(order):
        ax.plot(paths[i], color=colors[j], lw=0.5, alpha=0.55)
    ax.plot(np.median(paths, axis=0), "k--", lw=2.2, label="medián")
    ax.axhline(0, color="#1f77b4", lw=1)
    ax.set_xlabel("čas (obchodní dny)"); ax.set_ylabel("kumulativní výnos (%)")
    ax.set_title(f"Obrázek: Monte Carlo simulace – svazek možných průběhů zhodnocení (fan chart)\n{name}")
    ax.legend(loc="upper left"); ax.grid(True, alpha=0.3)
    fig.tight_layout(); fig.savefig(f"{outdir}/{name}_mc_fan.png", dpi=120); plt.close(fig)

    # --- 3) Monte Carlo cloud: return vs max drawdown ---
    M = 400; rets = np.empty(M); mdds = np.empty(M)
    for i in range(M):
        s = rng.choice(r, H, replace=True)
        e = np.cumprod(1 + s)
        rets[i] = (e[-1] - 1) * 100
        mdds[i] = ((e - np.maximum.accumulate(e)) / np.maximum.accumulate(e)).min() * 100
    fig, ax = plt.subplots(figsize=(9.5, 6.5))
    pos = rets > 0
    ax.scatter(mdds[pos], rets[pos], s=22, color="#2ca02c", alpha=0.65, label="scénář s kladným výnosem")
    ax.scatter(mdds[~pos], rets[~pos], s=22, color="#d62728", alpha=0.65, label="scénář se záporným výnosem")
    ax.axhline(0, color="k", lw=1)
    ax.set_xlabel("maximální drawdown (%)"); ax.set_ylabel("výnos (%)")
    ax.set_title(f"Obrázek: Monte Carlo simulace – oblak možných výsledků\n{name} · {pos.mean()*100:.0f} % scénářů kladných")
    ax.legend(loc="lower right"); ax.grid(True, alpha=0.3)
    fig.tight_layout(); fig.savefig(f"{outdir}/{name}_mc_cloud.png", dpi=120); plt.close(fig)

    # --- 4) yearly returns ---
    ys = list(m["yearly"].keys()); vs = [m["yearly"][y] for y in ys]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar([str(y) for y in ys], vs, color=["#2ca02c" if v >= 0 else "#d62728" for v in vs])
    for i, v in enumerate(vs):
        ax.text(i, v + (0.6 if v >= 0 else -1.6), f"{v:+.1f}%", ha="center", fontsize=8.5)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylabel("roční výnos (%)"); ax.set_xlabel("rok")
    ax.set_title(f"Obrázek: Roční výnosy strategie (rozklad výsledků v čase)\n{name}")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{outdir}/{name}_yearly.png", dpi=120); plt.close(fig)
    return {"mc_positive_pct": float(pos.mean()*100),
            "mc_median_ret": float(np.median(rets)),
            "mc_p5_ret": float(np.percentile(rets,5)),
            "mc_median_mdd": float(np.median(mdds)),
            "mc_p5_mdd": float(np.percentile(mdds,5))}
