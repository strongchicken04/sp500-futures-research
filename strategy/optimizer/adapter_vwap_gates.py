"""
Adapter: VWAP hysteresis band + gap/trend gates  ->  DR[config, day] matrix.

ADAPTER CONTRACT (for any future strategy):
    build_DR(...) must return
        DR    : np.ndarray (n_configs, n_days) of NET daily returns (0.0 = no trade),
        grid  : list of (param_name, values) in the SAME axis order as DR reshape,
        dates : list of day strings aligned with DR columns.
    Day t's return may use ONLY information available up to day t (gates use
    strictly past-only rolling percentiles).

Decomposition trick for this strategy: the intraday result depends ONLY on the
band width; the two gates merely decide WHETHER the day is traded. So we simulate
n_bands x n_days once, compute past-only percentile ranks of |gap| and yesterday's
trendiness once, and every (band, gap_thr, trend_thr) config is a cheap mask.
"""
from __future__ import annotations
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab.lab import vwap_arr, OPEN_MIN, EOD_MIN     # noqa: E402


# --------------------------------------------------------------------------- #
#  intraday simulation (identical logic to lab._vwap_band, per-day net return)
# --------------------------------------------------------------------------- #
def day_return_band(a: dict, band_bps: float, cost_bps: float = 1.0) -> float:
    """Exact per-day replica of lab._vwap_band (incl. exit at the close of the
    FIRST bar >= 15:59, matching the lab implementation bar-for-bar)."""
    m, c = a["m"], a["c"]
    vw = vwap_arr(a)
    b = band_bps / 1e4
    cost = 2 * cost_bps / 1e4
    pos, e = 0, 0.0
    for k in range(len(m)):
        if np.isnan(vw[k]) or m[k] < OPEN_MIN + 1:
            continue
        if m[k] >= EOD_MIN:
            return pos * (c[k] - e) / e - cost if pos else 0.0
        up, dn = vw[k] * (1 + b), vw[k] * (1 - b)
        if pos == 0:
            if c[k] > up: pos, e = 1, c[k]
            elif c[k] < dn: pos, e = -1, c[k]
        elif pos == 1 and c[k] < dn:
            return (c[k] - e) / e - cost
        elif pos == -1 and c[k] > up:
            return -(c[k] - e) / e - cost
    if pos:
        return pos * (c[-1] - e) / e - cost
    return 0.0


# --------------------------------------------------------------------------- #
#  daily context + past-only percentile ranks
# --------------------------------------------------------------------------- #
def daily_ctx(days: dict, dates: list) -> pd.DataFrame:
    rows = []
    for d in dates:
        a = days[d]
        rows.append((d, a["o"][0], a["h"].max(), a["l"].min(), a["c"][-1]))
    ctx = pd.DataFrame(rows, columns=["date", "O", "H", "L", "C"]).set_index("date")
    ctx["prevC"] = ctx["C"].shift(1)
    ctx["absgap"] = (ctx["O"] / ctx["prevC"] - 1.0).abs()
    tr = (ctx["C"] - ctx["O"]).abs() / (ctx["H"] - ctx["L"]).replace(0, np.nan)
    ctx["prevTrend"] = tr.shift(1)
    return ctx


def rolling_rank(values: np.ndarray, win: int = 250, minh: int = 60) -> np.ndarray:
    """Percentile rank (0-100) of each value vs the PAST `win` values only.
    NaN until `minh` history exists. History is appended AFTER ranking."""
    out = np.full(len(values), np.nan)
    hist: list = []
    for i, v in enumerate(values):
        if len(hist) >= minh and not np.isnan(v):
            h = np.asarray(hist)
            out[i] = np.mean(h <= v) * 100.0
        if not np.isnan(v):
            hist.append(v)
            if len(hist) > win:
                hist.pop(0)
    return out


# --------------------------------------------------------------------------- #
#  DR builder
# --------------------------------------------------------------------------- #
BANDS = [10.0, 15.0, 20.0, 25.0, 30.0, 35.0]
GAPS = [0.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
TRENDS = [40.0, 50.0, 60.0, 70.0, 80.0, 100.0]


def build_DR(days: dict, dates: list, bands=None, gaps=None, trends=None,
             cost_bps: float = 1.0):
    bands = bands or BANDS
    gaps = gaps or GAPS
    trends = trends or TRENDS
    nd = len(dates)

    # 1) intraday returns per band
    R = np.zeros((len(bands), nd))
    for ib, bb in enumerate(bands):
        for j, d in enumerate(dates):
            R[ib, j] = day_return_band(days[d], bb, cost_bps)

    # 2) past-only gate ranks
    ctx = daily_ctx(days, dates)
    rg = rolling_rank(ctx["absgap"].to_numpy())
    rt = rolling_rank(ctx["prevTrend"].to_numpy())
    gap_ok = {g: (np.isnan(rg) | (rg >= g)) for g in gaps}       # skip low-gap days
    tr_ok = {t: (np.isnan(rt) | (rt <= t)) for t in trends}      # skip post-trend days

    # 3) assemble grid (axis order: band, gap, trend)
    DR = np.zeros((len(bands) * len(gaps) * len(trends), nd))
    i = 0
    for ib in range(len(bands)):
        for g in gaps:
            for t in trends:
                DR[i] = R[ib] * (gap_ok[g] & tr_ok[t])
                i += 1
    grid = [("band_bps", bands), ("gap_pct", gaps), ("trend_pct", trends)]
    return DR, grid, list(dates)


# --------------------------------------------------------------------------- #
#  synthetic no-edge data for the noise floor
# --------------------------------------------------------------------------- #
def synth_days(n_days: int, seed: int, sigma_daily: float = 0.012,
               gap_sigma: float = 0.006):
    """GBM 1-min days: zero drift, no intraday structure => no edge by construction."""
    rng = np.random.default_rng(seed)
    px = 2000.0
    days, dates = {}, []
    bdates = pd.bdate_range("2005-01-03", periods=n_days)
    m = np.arange(OPEN_MIN, OPEN_MIN + 390, dtype=np.int32)
    sig = sigma_daily / np.sqrt(390)
    for i in range(n_days):
        px *= float(np.exp(rng.normal(0, gap_sigma)))
        closes = px * np.exp(np.cumsum(rng.normal(0, sig, 390)))
        opens = np.r_[px, closes[:-1]]
        wick = np.abs(rng.normal(0, sig * 0.5, 390))
        highs = np.maximum(opens, closes) * (1 + wick)
        lows = np.minimum(opens, closes) * (1 - wick)
        vols = rng.integers(100, 1000, 390).astype(float)
        d = bdates[i].strftime("%Y-%m-%d")
        days[d] = dict(m=m, o=opens, h=highs, l=lows, c=closes, v=vols)
        dates.append(d)
        px = float(closes[-1])
    return days, dates
