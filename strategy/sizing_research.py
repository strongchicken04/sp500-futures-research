"""
De-risking / sizing research on the regime-filtered ORB.

The regime filter gives a positive per-trade edge; the remaining problem is the
~35% drawdown from the 4x leverage cap. Here we test alternative sizings and a
portfolio overlay (the strategy's market beta is ~0.09, so it may diversify a
buy & hold NQ position).

Configs (all on the regime-filtered 5-min ORB, 10R):
  base_1pct_4x    current: 1% risk, 4x cap
  half_0.5pct_2x  0.5% risk, 2x cap
  low_0.35pct_3x  0.35% risk, 3x cap
  voltarget       risk_t = clip(k / rvol20_t, 0.2%, 1.2%) -> risk less when vol high

Also: 50/50 daily-rebalanced blend of buy & hold NAS100 + voltarget ORB.
"""
from __future__ import annotations
import argparse, json, os
import numpy as np
import pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

from orb_backtest import Config, run_backtest, compute_metrics
from regime_research import build_panel
from regime_strategy import favourable_dates


def perf(eq_df, start_eq):
    eq = eq_df.set_index("date")["equity"]
    ret = eq.pct_change().dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / start_eq) ** (1 / yrs) - 1
    vol = ret.std() * np.sqrt(252)
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() else np.nan
    dd = ((eq - eq.cummax()) / eq.cummax()).min()
    return dict(cagr=cagr * 100, vol=vol * 100, sharpe=sharpe,
                maxdd=dd * 100, calmar=cagr / abs(dd) if dd else np.nan), ret


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

    # per-date realised vol for vol-targeting
    rvol = panel["rvol20"].copy()
    rvol.index = rvol.index.strftime("%Y-%m-%d")
    k = 0.001  # -> ~0.6% risk at median vol 0.16
    risk_vt = {d: float(np.clip(k / v, 0.002, 0.012))
               for d, v in rvol.items() if v == v and v > 0}

    sizings = {
        "base_1pct_4x":   dict(risk=0.01,  lev=4.0, vt=False),
        "half_0.5pct_2x": dict(risk=0.005, lev=2.0, vt=False),
        "low_0.35pct_3x": dict(risk=0.0035, lev=3.0, vt=False),
        "voltarget":      dict(risk=0.006, lev=4.0, vt=True),
    }

    results = {}
    curves = {}
    for wname, (s, e) in {"test_2016_2020": (2016, 2020),
                          "full_2005_2020": (2005, 2020)}.items():
        results[wname] = {}
        print(f"\n===== {wname} (regime-filtered, cost {args.cost_bps}bp) =====")
        print(f"  {'sizing':16s} {'CAGR%':>7s} {'vol%':>6s} {'Sharpe':>7s} {'MaxDD%':>7s} {'Calmar':>7s}")
        # buy & hold reference
        cfg0 = Config(data_dir=args.data_dir, start_year=s, end_year=e,
                      cost_bps_per_side=args.cost_bps)
        _, _, raw = run_backtest(cfg0, allowed_dates=allowed)
        bh_close = raw.groupby("date")["close"].last(); bh_close.index = pd.to_datetime(bh_close.index)
        bh_close = bh_close.sort_index()
        bh_ret = bh_close.pct_change().dropna()
        bh_eq = pd.DataFrame({"date": bh_close.index, "equity": bh_close / bh_close.iloc[0] * 1e5})
        bhp, _ = perf(bh_eq, 1e5)
        for name, sc in sizings.items():
            cfg = Config(data_dir=args.data_dir, start_year=s, end_year=e,
                         cost_bps_per_side=args.cost_bps, risk_pct=sc["risk"],
                         max_leverage=sc["lev"])
            rbd = risk_vt if sc["vt"] else None
            t, eq, _ = run_backtest(cfg, allowed_dates=allowed, risk_by_date=rbd)
            p, sret = perf(eq, cfg.start_equity)
            results[wname][name] = {kk: round(vv, 2) for kk, vv in p.items()}
            curves[(wname, name)] = (eq, sret)
            print(f"  {name:16s} {p['cagr']:+7.1f} {p['vol']:6.1f} {p['sharpe']:7.2f} "
                  f"{p['maxdd']:7.1f} {p['calmar']:7.2f}")
        print(f"  {'buy&hold NAS100':16s} {bhp['cagr']:+7.1f} {bhp['vol']:6.1f} "
              f"{bhp['sharpe']:7.2f} {bhp['maxdd']:7.1f} {bhp['calmar']:7.2f}")
        results[wname]["buy_hold"] = {kk: round(vv, 2) for kk, vv in bhp.items()}

        # ---- 50/50 daily-rebalanced blend: buy&hold + voltarget ORB ----
        _, sret = curves[(wname, "voltarget")]
        al = pd.concat([sret.rename("s"), bh_ret.rename("b")], axis=1).dropna()
        beta = np.polyfit(al["b"], al["s"], 1)[0]
        corr = al["s"].corr(al["b"])
        blend = 0.5 * al["s"] + 0.5 * al["b"]
        bsharpe = blend.mean() / blend.std() * np.sqrt(252)
        beq = (1 + blend).cumprod()
        if wname == "test_2016_2020":
            vt_eq, _ = curves[("test_2016_2020", "voltarget")]
            fig2, axb = plt.subplots(figsize=(11, 6))
            b100 = beq / beq.iloc[0] * 1e5
            bh100 = (1 + al["b"]).cumprod(); bh100 = bh100 / bh100.iloc[0] * 1e5
            axb.plot(vt_eq["date"], vt_eq["equity"], label="Vol-targeted ORB (Sharpe 0.83)", lw=1.5, color="#2ca02c")
            axb.plot(bh100.index, bh100.values, label="Buy & Hold NAS100 (Sharpe 0.84)", lw=1.4, color="#ff7f0e", alpha=0.85)
            axb.plot(b100.index, b100.values, label="50/50 blend (Sharpe 1.18)", lw=1.9, color="#111111")
            axb.set_yscale("log"); axb.set_ylabel("Equity ($, log)")
            axb.set_title("Vol-targeted ORB as a diversifier — test 2016-2020 (NAS100, corr≈0)")
            axb.legend(); axb.grid(True, which="both", alpha=0.25)
            fig2.tight_layout(); fig2.savefig(os.path.join(args.out_dir, "blend_test.png"), dpi=130)
        bdd = ((beq - beq.cummax()) / beq.cummax()).min() * 100
        bcagr = (beq.iloc[-1]) ** (252 / len(blend)) - 1
        results[wname]["blend_50_50"] = {"cagr": round(bcagr*100,2), "sharpe": round(bsharpe,2),
                                         "maxdd": round(bdd,2), "vol": round(blend.std()*np.sqrt(252)*100,2),
                                         "beta_to_market": round(beta,3), "corr": round(corr,3)}
        print(f"  {'50/50 blend':16s} {bcagr*100:+7.1f} {blend.std()*np.sqrt(252)*100:6.1f} "
              f"{bsharpe:7.2f} {bdd:7.1f}   (beta {beta:+.2f}, corr {corr:+.2f})")

    with open(os.path.join(args.out_dir, "sizing_results.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    # ---- chart: sizings on full history ----
    fig, ax = plt.subplots(figsize=(11, 6))
    for name, col in [("base_1pct_4x", "#1f77b4"), ("voltarget", "#2ca02c"),
                      ("half_0.5pct_2x", "#9467bd")]:
        eq, _ = curves[("full_2005_2020", name)]
        ax.plot(eq["date"], eq["equity"], label=name, lw=1.4, color=col)
    ax.set_yscale("log"); ax.set_title("Regime-filtered ORB — sizing variants, full 2005-2020 (NAS100)")
    ax.set_ylabel("Equity ($, log)"); ax.legend(); ax.grid(True, which="both", alpha=0.25)
    fig.tight_layout(); fig.savefig(os.path.join(args.out_dir, "sizing_curves_full.png"), dpi=130)
    print("\nWrote sizing_results.json and sizing_curves_full.png")


if __name__ == "__main__":
    main()
