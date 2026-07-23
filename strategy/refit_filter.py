"""
Re-fit the regime filter on the real-NQ panel (results/nq_panel_real.csv).

The original filter (fit on OANDA 2005-2015) leaned on HIGH realised vol, which
inverted after 2020 and hurt risk-adjusted returns out-of-sample. This script
finds the durable signal (gap size, plus a low-vol leg) and a directional tilt
(short-only on gap-down days), fitting thresholds on 2009-2019 real NQ and
validating on 2020-2025.

Run: python3 strategy/refit_filter.py --panel results/nq_panel_real.csv
"""
import argparse, json
import numpy as np
import pandas as pd

BASE = "brk5_10R"


def load(panel_csv):
    p = pd.read_csv(panel_csv, index_col=0, parse_dates=True)
    p = p.dropna(subset=["rvol20", "gap_pct", "trend50"]).copy()
    p["absgap"] = p["gap_pct"].abs()
    return p


def ev(R, df):
    R = R.dropna()
    if len(R) < 20:
        return None
    tpy = len(R) / ((df.index[-1] - df.index[0]).days / 365.25)
    return dict(share=len(R) / len(df) * 100, expR=R.mean(), win=(R > 0).mean() * 100,
                rsharpe=R.mean() / R.std() * np.sqrt(tpy) if R.std() else 0)


def combined_R(df, gmed, vlo, directional=True):
    fav = (df.absgap > gmed) | (df.rvol20 < vlo)
    R = df[BASE].copy()
    if directional:                       # gap-down days -> short-only breakout
        R = R.mask(df.gap_pct < -gmed, df["brk5_short"])
    return R.where(fav)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="results/nq_panel_real.csv")
    ap.add_argument("--out", default="results/refit_filter.json")
    args = ap.parse_args()
    p = load(args.panel)
    tr = p[p.index.year <= 2019]
    gmed = float(tr["absgap"].median())
    vlo = float(tr["rvol20"].quantile(1 / 3))

    signals = {
        "no filter (base)": lambda d: d[BASE],
        "OLD filter": lambda d: d[BASE].where(
            ((d.rvol20 > 0.156) | (d.absgap > 0.003)) & (d.trend50 <= 0.0406)),
        "RE-FIT gap|lowvol": lambda d: combined_R(d, gmed, vlo, directional=False),
        "RE-FIT +directional": lambda d: combined_R(d, gmed, vlo, directional=True),
    }
    report = {}
    for name, seg in [("2009-2019", p[p.index.year <= 2019]),
                      ("2020-2025_OOS", p[p.index.year >= 2020]),
                      ("2016-2025", p[p.index.year >= 2016])]:
        print(f"\n===== {name} (n={len(seg)}) =====")
        print(f"  {'signal':22s} {'share%':>6s} {'expR':>7s} {'win%':>5s} {'Rsharpe':>8s}")
        report[name] = {}
        for sn, fn in signals.items():
            m = ev(fn(seg), seg)
            if m:
                report[name][sn] = {k: round(v, 3) for k, v in m.items()}
                print(f"  {sn:22s} {m['share']:6.0f} {m['expR']:+7.3f} {m['win']:5.1f} {m['rsharpe']:8.2f}")

    refit = {"filter": f"(|gap| > {gmed:.4f}) OR (rvol20 < {vlo:.3f})",
             "directional": f"on gap-down (< -{gmed:.4f}) days use short-only breakout",
             "thresholds_fit_on": "real NQ 2009-2019",
             "gap_med": gmed, "vlo": vlo, "by_period": report}
    with open(args.out, "w") as f:
        json.dump(refit, f, indent=2)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
