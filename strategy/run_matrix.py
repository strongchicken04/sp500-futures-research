"""
Run a matrix of ORB configurations and produce a summary table + equity chart.

Usage:
    python3 strategy/run_matrix.py --data-dir <NAS100_dir> --out-dir results
"""
import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from orb_backtest import Config, run_backtest, compute_metrics, buy_hold_metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    scenarios = [
        # name, start, end, cost_bps, allow_short
        ("paper_2016_2020_1.5bp", 2016, 2020, 1.5, True),
        ("paper_2016_2020_gross", 2016, 2020, 0.0, True),
        ("paper_2016_2020_3bp",  2016, 2020, 3.0, True),
        ("longonly_2016_2020",   2016, 2020, 1.5, False),
        ("full_2005_2020_1.5bp", 2005, 2020, 1.5, True),
        ("longonly_2005_2020",   2005, 2020, 1.5, False),
    ]

    summary = {}
    curves = {}
    for name, s, e, cost, shrt in scenarios:
        cfg = Config(data_dir=args.data_dir, start_year=s, end_year=e,
                     cost_bps_per_side=cost, allow_short=shrt)
        trades, eq, raw = run_backtest(cfg)
        m = compute_metrics(cfg, trades, eq, raw)
        summary[name] = {
            "window": f"{s}-{e}", "cost_bps": cost, "short": shrt,
            "n_trades": m["n_trades"],
            "win_rate_pct": round(m["win_rate_pct"], 1),
            "expectancy_R": round(m["expectancy_R"], 3),
            "profit_factor": round(m["profit_factor"], 2),
            "total_return_pct": round(m["total_return_pct"], 1),
            "cagr_pct": round(m["cagr_pct"], 1),
            "sharpe": round(m["sharpe"], 2),
            "max_drawdown_pct": round(m["max_drawdown_pct"], 1),
            "buy_hold_cagr_pct": round(m["buy_hold"]["cagr_pct"], 1),
            "buy_hold_sharpe": round(m["buy_hold"]["sharpe"], 2),
            "buy_hold_maxdd_pct": round(m["buy_hold"]["max_drawdown_pct"], 1),
        }
        curves[name] = eq.copy()
        print(f"{name:26s} exp {m['expectancy_R']:+.3f}R  "
              f"CAGR {m['cagr_pct']:+6.1f}%  Sharpe {m['sharpe']:+.2f}  "
              f"MaxDD {m['max_drawdown_pct']:6.1f}%  (B&H CAGR "
              f"{m['buy_hold']['cagr_pct']:+.1f}%)")

    with open(os.path.join(args.out_dir, "summary_matrix.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # ---- Equity chart: primary window strategy vs buy & hold ----
    cfg = Config(data_dir=args.data_dir, start_year=2016, end_year=2020,
                 cost_bps_per_side=1.5, allow_short=True)
    trades, eq, raw = run_backtest(cfg)
    bh_closes = raw.groupby("date")["close"].last()
    bh_closes.index = pd.to_datetime(bh_closes.index)
    bh_closes = bh_closes.sort_index()
    bh_norm = bh_closes / bh_closes.iloc[0] * cfg.start_equity

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(eq["date"], eq["equity"], label="5-min ORB (4x, 1% risk, 1.5bp)", lw=1.6)
    ax.plot(bh_norm.index, bh_norm.values, label="Buy & Hold NAS100", lw=1.4, alpha=0.8)
    ax.set_yscale("log")
    ax.set_title("5-min ORB on NAS100 (NQ proxy) vs Buy & Hold — 2016 to 2020-05")
    ax.set_ylabel("Equity ($, log scale)")
    ax.legend(); ax.grid(True, which="both", alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out_dir, "equity_curve_2016_2020.png"), dpi=130)
    print("\nWrote summary_matrix.json and equity_curve_2016_2020.png")

    # markdown table
    cols = ["window", "cost_bps", "short", "n_trades", "win_rate_pct",
            "expectancy_R", "profit_factor", "cagr_pct", "sharpe",
            "max_drawdown_pct", "buy_hold_cagr_pct"]
    lines = ["| scenario | " + " | ".join(cols) + " |",
             "|" + "---|" * (len(cols) + 1)]
    for name, r in summary.items():
        lines.append("| " + name + " | " + " | ".join(str(r[c]) for c in cols) + " |")
    with open(os.path.join(args.out_dir, "summary_matrix.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
