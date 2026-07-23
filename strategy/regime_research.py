"""
Regime research for ORB variants on NAS100 (NQ proxy).

Step 1: build a daily panel with, for every trading day:
  * ex-ante regime features (known at/near the 09:30 open), and
  * the realized R-multiple of each ORB variant that day.

The R-multiple is instrument- and sizing-independent, so it is the clean signal
for "which variant works in which regime". Sizing/costs are layered on later.

Variants (all long+short unless noted):
  brk5_10R      5-min opening range, breakout, 10R target / EOD
  brk5_eod      5-min OR, breakout, no target -> hold to close (pure momentum)
  brk15_10R     15-min OR, breakout, 10R
  brk30_10R     30-min OR, breakout, 10R
  brk5_long     5-min OR, breakout, 10R, LONG only
  brk5_short    5-min OR, breakout, 10R, SHORT only
  fade5_3R      5-min OR, FADE (mean-revert the open), 3R target
  fade5_eod     5-min OR, FADE, hold to close
"""
from __future__ import annotations
import argparse, json, os
import numpy as np
import pandas as pd

from orb_backtest import load_rth_1min, Config

OR_START = 9 * 60 + 30
RTH_LAST = 15 * 60 + 59

VARIANTS = {
    "brk5_10R":  dict(or_len=5,  signal="brk",  target_R=10.0, side="both"),
    "brk5_eod":  dict(or_len=5,  signal="brk",  target_R=None, side="both"),
    "brk15_10R": dict(or_len=15, signal="brk",  target_R=10.0, side="both"),
    "brk30_10R": dict(or_len=30, signal="brk",  target_R=10.0, side="both"),
    "brk5_long": dict(or_len=5,  signal="brk",  target_R=10.0, side="long"),
    "brk5_short":dict(or_len=5,  signal="brk",  target_R=10.0, side="short"),
    "fade5_3R":  dict(or_len=5,  signal="fade", target_R=3.0,  side="both"),
    "fade5_eod": dict(or_len=5,  signal="fade", target_R=None, side="both"),
}


def sim_variant(bars: dict, or_len, signal, target_R, side):
    """Return realized R-multiple (gross) for one variant on one day, or None."""
    or_start = OR_START
    or_last = OR_START + or_len - 1
    entry_min = OR_START + or_len
    if or_start not in bars or entry_min not in bars or or_last not in bars:
        return None
    o = bars[or_start][0]
    c = bars[or_last][3]
    hs = [bars[m][1] for m in range(or_start, or_last + 1) if m in bars]
    ls = [bars[m][2] for m in range(or_start, or_last + 1) if m in bars]
    or_high, or_low = max(hs), min(ls)
    d = 1 if c > o else (-1 if c < o else 0)
    if d == 0:
        return None
    if signal == "fade":
        d = -d
    if side == "long" and d != 1:
        return None
    if side == "short" and d != -1:
        return None
    entry = bars[entry_min][0]
    stop = or_low if d == 1 else or_high
    R = (entry - stop) if d == 1 else (stop - entry)
    if R <= 0:
        return None
    target = entry + d * target_R * R if target_R else None
    for m in range(entry_min, RTH_LAST + 1):
        b = bars.get(m)
        if b is None:
            continue
        _, h2, l2, _ = b
        if d == 1:
            if l2 <= stop:
                return -1.0
            if target is not None and h2 >= target:
                return float(target_R)
        else:
            if h2 >= stop:
                return -1.0
            if target is not None and l2 <= target:
                return float(target_R)
    last = max((m for m in bars if entry_min <= m <= RTH_LAST), default=None)
    if last is None:
        return None
    exitp = bars[last][3]
    return float(d * (exitp - entry) / R)


def build_panel(data_dir, start_year, end_year) -> pd.DataFrame:
    cfg = Config(data_dir=data_dir, start_year=start_year, end_year=end_year)
    df = load_rth_1min(cfg)

    # daily OHLC (RTH) for feature engineering
    g = df.groupby("date")
    daily = pd.DataFrame({
        "open": g.apply(lambda x: x.loc[x["etmin"].idxmin(), "open"], include_groups=False),
        "high": g["high"].max(),
        "low": g["low"].min(),
        "close": g.apply(lambda x: x.loc[x["etmin"].idxmax(), "close"], include_groups=False),
    })
    daily.index = pd.to_datetime(daily.index)
    daily = daily.sort_index()

    # ex-ante features (shifted so they use info available at today's open)
    prev_close = daily["close"].shift(1)
    tr = pd.concat([
        daily["high"] - daily["low"],
        (daily["high"] - prev_close).abs(),
        (daily["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean().shift(1)            # known at open
    ret = daily["close"].pct_change()
    rvol20 = ret.rolling(20).std().shift(1) * np.sqrt(252)   # ann. realized vol
    sma50 = daily["close"].rolling(50).mean().shift(1)
    trend20 = (prev_close / daily["close"].shift(21) - 1.0)  # 20d momentum, ex-ante
    trend50 = (prev_close / sma50 - 1.0)
    gap = (daily["open"] / prev_close - 1.0)

    daily["atr14"] = atr14
    daily["atr14_pct"] = atr14 / prev_close
    daily["rvol20"] = rvol20
    daily["trend20"] = trend20
    daily["trend50"] = trend50
    daily["gap_pct"] = gap
    daily["dow"] = daily.index.dayofweek

    # per-day variant R
    var_rows = {k: {} for k in VARIANTS}
    for date, day in df.groupby("date"):
        bars = {int(r.etmin): (r.open, r.high, r.low, r.close)
                for r in day.itertuples(index=False)}
        for name, spec in VARIANTS.items():
            var_rows[name][date] = sim_variant(bars, **spec)

    for name in VARIANTS:
        s = pd.Series(var_rows[name]); s.index = pd.to_datetime(s.index)
        daily[f"R_{name}"] = s

    daily["year"] = daily.index.year
    return daily


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--start-year", type=int, default=2005)
    ap.add_argument("--end-year", type=int, default=2020)
    ap.add_argument("--out", default="results/daily_panel.csv")
    args = ap.parse_args()
    panel = build_panel(args.data_dir, args.start_year, args.end_year)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    panel.to_csv(args.out)
    print(f"panel: {len(panel)} days, {panel['year'].min()}-{panel['year'].max()}")
    print("\nVariant expectancy (mean R) and trade count, full sample:")
    for name in VARIANTS:
        col = f"R_{name}"; s = panel[col].dropna()
        print(f"  {name:11s}  n={len(s):5d}  meanR={s.mean():+.3f}  "
              f"win%={(s>0).mean()*100:4.1f}  sumR={s.sum():+.0f}")
    print(f"\nWrote {args.out}")
