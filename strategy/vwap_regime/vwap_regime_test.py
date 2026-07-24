"""
Empirical test of the model from:
  Lee, C.Y. (2026) "VWAP-Based Regime Classification Model for Intraday Price
  Dynamics", SSRN 6438039.

The paper defines ONLY a classifier (no trading rules, no backtest, no data):
    p_t  = (P_t - VWAP_t) / sigma_t            (volatility-standardised deviation)
    R_t  = +1 if p_t >  k ;  -1 if p_t < -k ;  0 otherwise   (k > 0)
The author lists "empirically testing the model" as future work. This script
supplies that missing test on NAS100 (NQ proxy) 1-min data with tick volume.

VWAP  = intraday session VWAP (reset at the 09:30 ET cash open) on typical price.
sigma = rolling 20-bar stdev of close (one reasonable choice; paper leaves it open).
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # strategy/
from orb_backtest import load_rth_1min, Config


def build(data_dir, s, e):
    df = load_rth_1min(Config(data_dir=data_dir, start_year=s, end_year=e)).copy().reset_index(drop=True)
    df["tp"] = (df["high"] + df["low"] + df["close"]) / 3.0
    out = []
    for _, g in df.groupby("date", sort=True):
        g = g.sort_values("etmin").copy()
        g["vwap"] = (g["tp"] * g["volume"]).cumsum() / g["volume"].cumsum().replace(0, np.nan)
        g["sig"] = g["close"].rolling(20, min_periods=10).std()
        g["p"] = (g["close"] - g["vwap"]) / g["sig"]
        g["ret1"] = g["close"].shift(-1) / g["close"] - 1.0
        for H in (5, 15, 30, 60):
            g[f"fwd{H}"] = g["close"].shift(-H) / g["close"] - 1.0
        out.append(g)
    return pd.concat(out, ignore_index=True).dropna(subset=["p", "ret1"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--start-year", type=int, default=2012)
    ap.add_argument("--end-year", type=int, default=2020)
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()
    df = build(args.data_dir, args.start_year, args.end_year)
    ndays = df["date"].nunique()
    res = {"rows": int(len(df)), "days": int(ndays), "conditional_fwd_bps": {}, "strategy": {}}

    # 1) conditional forward returns by regime
    for k in (1.0, 1.5, 2.0):
        R = pd.Series(np.where(df["p"] > k, 1, np.where(df["p"] < -k, -1, 0)), index=df.index)
        rec = {}
        for H in (5, 15, 30, 60):
            c = f"fwd{H}"
            tr = R != 0
            rec[H] = {"pos": float(df.loc[R == 1, c].mean() * 1e4),
                      "neu": float(df.loc[R == 0, c].mean() * 1e4),
                      "neg": float(df.loc[R == -1, c].mean() * 1e4),
                      "cont_hit_pct": float((np.sign(df.loc[tr, c]) == np.sign(R[tr])).mean() * 100)}
        res["conditional_fwd_bps"][k] = rec

    # 2) regime-following strategy net of cost
    for k in (1.0, 1.5, 2.0):
        df["pos"] = np.where(df["p"] > k, 1, np.where(df["p"] < -k, -1, 0))
        df["pnl"] = df["pos"] * df["ret1"]
        turn = df.groupby("date")["pos"].apply(lambda s: s.diff().abs().fillna(s.abs()).sum()).sum()
        gross = df["pnl"].sum()
        daily = df.groupby("date")["pnl"].sum()
        res["strategy"][k] = {
            "trades_per_day": float(turn / ndays),
            "gross_bps_per_trade": float(gross / turn * 1e4),
            "gross_sharpe": float(daily.mean() / daily.std() * np.sqrt(252)),
            "net_total_pct_1bp": float((gross - turn * 1e-4) * 100),
            "net_total_pct_2bp": float((gross - turn * 2e-4) * 100)}

    with open(f"{args.out_dir}/vwap_regime_results.json", "w") as f:
        json.dump(res, f, indent=2)

    # chart: conditional fwd returns (k=1) + net-of-cost equity bleed
    k = 1.0
    df["pos"] = np.where(df["p"] > k, 1, np.where(df["p"] < -k, -1, 0))
    df["pnl"] = df["pos"] * df["ret1"]
    df["chg"] = df.groupby("date")["pos"].transform(lambda s: s.diff().abs().fillna(s.abs()))
    df["net1"] = df["pnl"] - df["chg"] * 1e-4
    eq = (1 + df["net1"]).cumprod()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.6))
    Hs = [5, 15, 30, 60]
    rc = res["conditional_fwd_bps"][1.0]
    x = np.arange(len(Hs)); w = 0.27
    a1.bar(x - w, [rc[H]["pos"] for H in Hs], w, label="R=+1 (above VWAP)", color="#2ca02c")
    a1.bar(x, [rc[H]["neu"] for H in Hs], w, label="R=0 (near VWAP)", color="#999999")
    a1.bar(x + w, [rc[H]["neg"] for H in Hs], w, label="R=-1 (below VWAP)", color="#d62728")
    a1.set_xticks(x); a1.set_xticklabels([f"{H}m" for H in Hs]); a1.axhline(0, color="k", lw=0.6)
    a1.set_ylabel("Mean forward return (bps)"); a1.set_title("Forward return by VWAP regime (k=1)\n-- drift is real but < 1 bp; hit rate < 50%")
    a1.legend(fontsize=8); a1.grid(True, axis="y", alpha=0.25)
    a2.plot(eq.values, color="#d62728", lw=1.2)
    a2.set_yscale("log"); a2.set_title("Regime-following strategy, net of 1 bp/side\n-- ~28 flips/day, edge swamped by cost")
    a2.set_ylabel("equity (x, log)"); a2.set_xlabel("bar #"); a2.grid(True, which="both", alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{args.out_dir}/vwap_regime_test.png", dpi=130)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
