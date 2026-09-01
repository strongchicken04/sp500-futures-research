#!/usr/bin/env python3
"""VIX band fade strategy backtest (NQ 2018-2025).

Hypothesis (median excursion 0.85 study):
  Median daily MFE from open on NQ is 0.85 x (VIX-implied 1sigma band).
  Therefore, when price DOES reach the 1sigma band (100% excursion),
  the day is already above-median for excursion, and mean reversion is
  the base-rate outcome.

Strategy:
  band       = open * (vix_prev / sqrt(252)) / 100
  upper      = open + band
  lower      = open - band
  SHORT fade at upper if high > upper (band touched from below)
    entry = upper
    TP    = open                        (+1.0 x band gain)
    SL    = upper + SL_mult x band      (grid over 0.3, 0.5, 0.75, 1.0)
  LONG fade at lower if low < lower  (mirror)

Fill logic (daily H/L/C only, conservative):
  tp_hit = (favorable extreme reaches TP level)
  sl_hit = (adverse extreme reaches SL level)
  if both -> SL (order unknown, conservative)
  elif tp_hit -> +band (in points)
  elif sl_hit -> -SL_mult * band
  else -> EOD at close (entry - close for short, close - entry for long)

Costs: 0.75 pts per trade (~= 1 tick slip + commission).

Prints net pnl per trade in bps and points, win rate, RR, and z-stat
against zero, for each SL multiplier and combined long+short.
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

COST = 0.75          # pts per trade net (comm + 1 tick)
SL_MULTS = (0.3, 0.5, 0.75, 1.0)
SQRT252 = math.sqrt(252.0)


def load(path):
    rows = json.loads(Path(path).read_text())
    out = []
    for r in rows:
        try:
            o = float(r["nq_open"]); h = float(r["nq_high"])
            lo = float(r["nq_low"]); c = float(r["nq_close"])
            v = float(r["vix_prev"])
            if o > 0 and v > 0 and h >= lo:
                out.append((r["date"], o, h, lo, c, v))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def run_side(rows, side, sl_mult):
    """Return per-trade pnl in points (side=+1 long fade bottom, -1 short fade top)."""
    trades = []
    for date, o, h, lo, c, v in rows:
        band = o * (v / SQRT252) / 100.0
        upper = o + band
        lower = o - band

        if side == -1:                              # SHORT fade at upper
            if h <= upper:
                continue
            entry = upper
            tp_lvl = o                              # TP = open (reversion)
            sl_lvl = upper + sl_mult * band
            fav = entry - lo                        # favorable move for short
            adv = h - entry                         # adverse move for short
            fav_target = entry - tp_lvl             # = band
            adv_target = sl_lvl - entry             # = sl_mult * band
            tp_hit = fav >= fav_target
            sl_hit = adv >= adv_target
            if sl_hit and tp_hit:
                pnl = -adv_target                   # conservative SL
                how = "S"
            elif tp_hit:
                pnl = fav_target
                how = "T"
            elif sl_hit:
                pnl = -adv_target
                how = "S"
            else:
                pnl = entry - c
                how = "E"

        else:                                       # LONG fade at lower
            if lo >= lower:
                continue
            entry = lower
            tp_lvl = o
            sl_lvl = lower - sl_mult * band
            fav = h - entry
            adv = entry - lo
            fav_target = tp_lvl - entry
            adv_target = entry - sl_lvl
            tp_hit = fav >= fav_target
            sl_hit = adv >= adv_target
            if sl_hit and tp_hit:
                pnl = -adv_target
                how = "S"
            elif tp_hit:
                pnl = fav_target
                how = "T"
            elif sl_hit:
                pnl = -adv_target
                how = "S"
            else:
                pnl = c - entry
                how = "E"

        # cost & bps normalization (use open as denominator, era-aware)
        pnl_net = pnl - COST
        bps = 10000.0 * pnl_net / o
        trades.append((date, entry, pnl, pnl_net, bps, how, o, band))
    return trades


def stats(trades):
    if not trades:
        return dict(n=0)
    pnls_bps = [t[4] for t in trades]
    pnls_pts = [t[3] for t in trades]
    n = len(trades)
    mu_bps = sum(pnls_bps) / n
    mu_pts = sum(pnls_pts) / n
    var = sum((x - mu_bps) ** 2 for x in pnls_bps) / max(n - 1, 1)
    sd = math.sqrt(var)
    z = mu_bps / (sd / math.sqrt(n)) if sd > 0 else 0.0
    wins = sum(1 for x in pnls_pts if x > 0)
    losses = sum(1 for x in pnls_pts if x < 0)
    tp = sum(1 for t in trades if t[5] == "T")
    sl = sum(1 for t in trades if t[5] == "S")
    eod = sum(1 for t in trades if t[5] == "E")
    return dict(n=n, mu_bps=mu_bps, mu_pts=mu_pts, sd_bps=sd, z=z,
                win_pct=100.0 * wins / n, loss_pct=100.0 * losses / n,
                tp_pct=100.0 * tp / n, sl_pct=100.0 * sl / n,
                eod_pct=100.0 * eod / n, total_pts=sum(pnls_pts))


def per_year(trades):
    d = defaultdict(list)
    for t in trades:
        d[t[0][:4]].append(t[4])           # bps
    return [(y, len(d[y]), sum(d[y]) / len(d[y])) for y in sorted(d)]


def run_side_eod(rows, side):
    """Honest close-based test: signal = band touched, exit = daily close.

    NO TP/SL ordering assumption. If touched, we assume the touch happened
    (fill at band edge), then hold to EOD close. Tests pure reversion.
    """
    trades = []
    for date, o, h, lo, c, v in rows:
        band = o * (v / SQRT252) / 100.0
        upper = o + band
        lower = o - band
        if side == -1:
            if h <= upper:
                continue
            entry = upper
            pnl = entry - c
        else:
            if lo >= lower:
                continue
            entry = lower
            pnl = c - entry
        pnl_net = pnl - COST
        bps = 10000.0 * pnl_net / o
        trades.append((date, entry, pnl, pnl_net, bps, "E", o, band))
    return trades


def main():
    rows = load("/home/user/sp500-futures-research/results/vix_band/vix_band_days.json")
    print(f"n dni: {len(rows)}\n")

    # -- CLEAN CONTROL: EOD-only (no TP/SL, no touch-fill mirage) --
    print("=== CONTROL: EOD close only (no TP/SL, honest) ===")
    s_short = run_side_eod(rows, -1)
    s_long = run_side_eod(rows, 1)
    for name, s in (("short EOD (touched upper -> hold to close)", stats(s_short)),
                    ("long  EOD (touched lower -> hold to close)", stats(s_long)),
                    ("COMBINED EOD                             ", stats(s_short + s_long))):
        if s.get("n", 0) == 0:
            print(f"  {name}: 0 trades"); continue
        print(f"  {name}: n={s['n']:4d}  "
              f"avg={s['mu_pts']:+7.2f} pts / {s['mu_bps']:+6.2f} bps  "
              f"z={s['z']:+5.2f}  win={s['win_pct']:4.1f}%  "
              f"total={s['total_pts']:+7.0f} pts")
    print()

    all_results = []
    for sl_mult in SL_MULTS:
        short = run_side(rows, -1, sl_mult)
        long_ = run_side(rows, 1, sl_mult)
        both = short + long_
        s_s = stats(short); s_l = stats(long_); s_b = stats(both)
        all_results.append((sl_mult, s_s, s_l, s_b))
        print(f"=== SL = {sl_mult} x band (RR = {1/sl_mult:.2f}:1) ===")
        for name, s in (("short (fade top)", s_s),
                        ("long  (fade bot)", s_l),
                        ("COMBINED       ", s_b)):
            if s.get("n", 0) == 0:
                print(f"  {name}: (0 trades)")
                continue
            print(f"  {name}: n={s['n']:4d}  "
                  f"avg={s['mu_pts']:+6.2f} pts / {s['mu_bps']:+6.2f} bps  "
                  f"z={s['z']:+5.2f}  "
                  f"TP={s['tp_pct']:4.1f}% SL={s['sl_pct']:4.1f}% EOD={s['eod_pct']:4.1f}%  "
                  f"win={s['win_pct']:4.1f}%  total={s['total_pts']:+7.0f} pts")
        print()

    # Yearly breakdown for the best (highest z) combined config
    best = max(all_results, key=lambda x: x[3]["z"] if x[3].get("n") else -99)
    sl_mult, _, _, s_b = best
    print(f"=== Best config: SL = {sl_mult} x band (COMBINED z = {s_b['z']:+.2f}) ===")
    short = run_side(rows, -1, sl_mult)
    long_ = run_side(rows, 1, sl_mult)
    both = short + long_
    print("Roky (COMBINED, bps net):")
    for y, n, mu in per_year(both):
        print(f"  {y}  n={n:4d}  avg={mu:+6.2f} bps")


if __name__ == "__main__":
    main()
