"""
Regime-filtered ORB meta-strategy.

Uses the regime features from `regime_research.build_panel` to trade the 5-min
ORB (breakout, long+short, 10R target) ONLY on days whose regime is favourable,
then runs the real cost-and-size-aware engine (`orb_backtest.run_backtest`) so we
see NET, compounded performance vs the unfiltered baseline and buy & hold.

Filter (thresholds fit on TRAIN 2005-2015 only, then frozen):
    favourable = ( rvol20 > train_median(rvol20)          # high realised vol
                   OR |gap| > train_median(|gap|) )        # or a meaningful gap
                 AND trend50 <= train_q75(trend50)          # not a strong uptrend
"""
from __future__ import annotations
import argparse, json, os
import numpy as np
import pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

from orb_backtest import Config, run_backtest, compute_metrics
from regime_research import build_panel


def favourable_dates(panel: pd.DataFrame, thr: dict) -> set:
    f = panel.dropna(subset=["rvol20", "gap_pct", "trend50"]).copy()
    fav = ((f["rvol20"] > thr["vol"]) | (f["gap_pct"].abs() > thr["gap"])) \
          & (f["trend50"] <= thr["up"])
    return set(f.index[fav].strftime("%Y-%m-%d"))


def summarize(m: dict) -> dict:
    return {k: (round(m[k], 3) if isinstance(m.get(k), (int, float)) else m.get(k))
            for k in ["n_trades", "win_rate_pct", "expectancy_R", "profit_factor",
                      "cagr_pct", "sharpe", "max_drawdown_pct"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", default="results")
    ap.add_argument("--cost-bps", type=float, default=1.5)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    panel = build_panel(args.data_dir, 2005, 2020)
    train = panel[panel.year <= 2015]
    thr = {"vol": float(train["rvol20"].median()),
           "gap": float(train["gap_pct"].abs().median()),
           "up": float(train["trend50"].quantile(0.75))}
    allowed = favourable_dates(panel, thr)
    print("thresholds (train-fit):", {k: round(v, 4) for k, v in thr.items()})
    print(f"favourable days: {len(allowed)} / {len(panel)} "
          f"({len(allowed)/len(panel)*100:.0f}%)")

    windows = {"train_2005_2015": (2005, 2015),
               "test_2016_2020": (2016, 2020),
               "full_2005_2020": (2005, 2020)}
    results = {"thresholds": thr, "favourable_day_share_pct": round(len(allowed)/len(panel)*100, 1)}
    curves = {}
    for wname, (s, e) in windows.items():
        cfg = Config(data_dir=args.data_dir, start_year=s, end_year=e,
                     cost_bps_per_side=args.cost_bps)
        # baseline (all days)
        t0, eq0, raw = run_backtest(cfg)
        m0 = compute_metrics(cfg, t0, eq0, raw)
        # filtered
        t1, eq1, _ = run_backtest(cfg, allowed_dates=allowed)
        m1 = compute_metrics(cfg, t1, eq1, raw)
        results[wname] = {"baseline": summarize(m0), "filtered": summarize(m1),
                          "buy_hold": {k: round(m0["buy_hold"][k], 2)
                                       for k in ["cagr_pct", "sharpe", "max_drawdown_pct"]}}
        curves[wname] = (eq0, eq1, raw)
        print(f"\n===== {wname} (cost {args.cost_bps}bp/side) =====")
        print(f"  {'':10s} {'trades':>6s} {'win%':>6s} {'expR':>6s} {'PF':>5s} "
              f"{'CAGR%':>7s} {'Sharpe':>7s} {'MaxDD%':>7s}")
        for lbl, m in [("baseline", m0), ("filtered", m1)]:
            print(f"  {lbl:10s} {m['n_trades']:6d} {m['win_rate_pct']:6.1f} "
                  f"{m['expectancy_R']:+6.3f} {m['profit_factor']:5.2f} "
                  f"{m['cagr_pct']:+7.1f} {m['sharpe']:7.2f} {m['max_drawdown_pct']:7.1f}")
        bh = m0["buy_hold"]
        print(f"  {'buy&hold':10s} {'':6s} {'':6s} {'':6s} {'':5s} "
              f"{bh['cagr_pct']:+7.1f} {bh['sharpe']:7.2f} {bh['max_drawdown_pct']:7.1f}")

    with open(os.path.join(args.out_dir, "regime_strategy_results.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    # ---- equity chart on TEST (out-of-sample) ----
    eq0, eq1, raw = curves["test_2016_2020"]
    bh = raw.groupby("date")["close"].last(); bh.index = pd.to_datetime(bh.index)
    bh = (bh.sort_index() / bh.iloc[0]) * 100000
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(eq1["date"], eq1["equity"], label="Regime-filtered ORB", lw=1.8, color="#2ca02c")
    ax.plot(eq0["date"], eq0["equity"], label="Unfiltered ORB (all days)", lw=1.3, color="#1f77b4", alpha=0.8)
    ax.plot(bh.index, bh.values, label="Buy & Hold NAS100", lw=1.2, color="#ff7f0e", alpha=0.7)
    ax.set_yscale("log"); ax.set_title("Regime-filtered vs unfiltered ORB — OUT-OF-SAMPLE test 2016-2020 (NAS100)")
    ax.set_ylabel("Equity ($, log)"); ax.legend(); ax.grid(True, which="both", alpha=0.25)
    fig.tight_layout(); fig.savefig(os.path.join(args.out_dir, "regime_equity_test.png"), dpi=130)
    print(f"\nWrote regime_strategy_results.json and regime_equity_test.png")


if __name__ == "__main__":
    main()
