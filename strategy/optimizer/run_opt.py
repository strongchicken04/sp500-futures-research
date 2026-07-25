"""
Run the Parameter Optimization Machine on the VWAP band + gates strategy.
IS = 2005-2017 ONLY (true OOS 2018-2020/05 stays locked, untouched).

Outputs to results/optimizer/: metrics JSON + 5 diagnostic charts.
"""
import sys, os, json, time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from machine import (sharpe_daily, perf_stats, neighborhood_score, pick_plateau,
                     pick_argmax, walk_forward, cscv_pbo, verdict)          # noqa
from adapter_vwap_gates import build_DR, synth_days                          # noqa
from lab.lab import build_cache                                              # noqa

OUT = "/home/user/sp500-futures-research/results/optimizer"
IS_Y0, IS_Y1 = 2005, 2017
N_NOISE = 3


def cfg_name(grid, shape, j):
    idx = np.unravel_index(j, shape)
    return {name: vals[i] for (name, vals), i in zip(grid, idx)}


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()

    # ---------- real data (IS only) ----------
    days, dates, _ = build_cache()
    is_dates = [d for d in dates if IS_Y0 <= int(d[:4]) <= IS_Y1]
    print(f"[data] IS days: {len(is_dates)}  ({is_dates[0]}..{is_dates[-1]})", flush=True)

    DR, grid, ddates = build_DR(days, is_dates)
    shape = tuple(len(v) for _, v in grid)
    years = np.array([int(d[:4]) for d in ddates])
    print(f"[grid] {DR.shape[0]} configs x {DR.shape[1]} days  ({time.time()-t0:.0f}s)", flush=True)

    # ---------- full-IS selection: plateau vs argmax ----------
    sh = sharpe_daily(DR)
    j_plat = pick_plateau(sh, shape)
    j_peak = pick_argmax(sh, shape)
    rec = cfg_name(grid, shape, j_plat)
    peak = cfg_name(grid, shape, j_peak)
    print(f"[pick] plateau center: {rec}  (IS Sharpe {sh[j_plat]:.2f})", flush=True)
    print(f"[pick] raw peak      : {peak}  (IS Sharpe {sh[j_peak]:.2f})", flush=True)

    # journal's hand-picked config for reference
    try:
        j_journal = next(i for i in range(DR.shape[0])
                         if cfg_name(grid, shape, i) ==
                         {"band_bps": 20.0, "gap_pct": 25.0, "trend_pct": 60.0})
    except StopIteration:
        j_journal = None

    # ---------- walk-forward (honest estimate) ----------
    wf_plat, wf_mask, picks_plat = walk_forward(DR, years, shape, pick_plateau)
    wf_peak, _, picks_peak = walk_forward(DR, years, shape, pick_argmax)
    st_wf_plat = perf_stats(wf_plat)
    st_wf_peak = perf_stats(wf_peak)
    st_is_rec = perf_stats(DR[j_plat, wf_mask])     # fixed rec config, same window
    print(f"[wf] plateau rule: {st_wf_plat}", flush=True)
    print(f"[wf] argmax rule : {st_wf_peak}", flush=True)

    # ---------- PBO ----------
    pbo_arg, om_arg = cscv_pbo(DR, S=12)
    pbo_pla, om_pla = cscv_pbo(DR, S=12, picker=pick_plateau, shape=shape)
    print(f"[pbo] argmax {pbo_arg*100:.0f}%   plateau {pbo_pla*100:.0f}%", flush=True)

    # ---------- noise floor ----------
    noise_wf, noise_is_best = [], []
    for s in range(N_NOISE):
        sd_, sdt_ = synth_days(len(is_dates), seed=100 + s)
        DRn, _, _ = build_DR(sd_, sdt_)
        yn = np.array([int(d[:4]) for d in sdt_])
        shn = sharpe_daily(DRn)
        noise_is_best.append(float(shn.max()))
        wfn, _, _ = walk_forward(DRn, yn, shape, pick_plateau)
        noise_wf.append(float(sharpe_daily(wfn)))
        print(f"[noise {s}] best IS Sharpe {shn.max():.2f} -> WF Sharpe {noise_wf[-1]:.2f}", flush=True)

    ver = verdict(st_wf_plat["sharpe"], pbo_pla, noise_wf)

    # ---------- save metrics ----------
    res = dict(
        window=f"{IS_Y0}-{IS_Y1}", n_days=len(ddates), n_configs=int(DR.shape[0]),
        grid={n: v for n, v in grid},
        recommended=rec, recommended_is_sharpe=round(float(sh[j_plat]), 3),
        raw_peak=peak, raw_peak_is_sharpe=round(float(sh[j_peak]), 3),
        journal_config_is_sharpe=(round(float(sh[j_journal]), 3) if j_journal is not None else None),
        journal_config_plateau_rank=(int((neighborhood_score(sh, shape) >
                                          neighborhood_score(sh, shape)[j_journal]).sum() + 1)
                                     if j_journal is not None else None),
        wf_plateau=st_wf_plat, wf_argmax=st_wf_peak, is_fixed_rec_same_window=st_is_rec,
        wf_picks_plateau=[(y, cfg_name(grid, shape, j)) for y, j in picks_plat],
        pbo_argmax=round(pbo_arg, 3), pbo_plateau=round(pbo_pla, 3),
        noise_wf_sharpes=[round(x, 3) for x in noise_wf],
        noise_best_is_sharpes=[round(x, 3) for x in noise_is_best],
        verdict=ver, cost_bps_per_side=1.0,
        note="True OOS 2018-2020/05 untouched. WF numbers are the honest expectation.")
    with open(f"{OUT}/vwap_gates_optimization.json", "w") as f:
        json.dump(res, f, indent=2, default=str)

    # ================= charts =================
    bands = grid[0][1]; gaps = grid[1][1]; trends = grid[2][1]
    S3 = sh.reshape(shape)
    it_rec = trends.index(rec["trend_pct"])

    # 1) heatmap band x gap at recommended trend slice
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(S3[:, :, it_rec], cmap="RdYlGn", aspect="auto",
                   vmin=-max(abs(S3.min()), S3.max()), vmax=max(abs(S3.min()), S3.max()))
    ax.set_xticks(range(len(gaps)), [f"{g:.0f}" for g in gaps])
    ax.set_yticks(range(len(bands)), [f"{b:.0f}" for b in bands])
    ax.set_xlabel("gap gate percentil"); ax.set_ylabel("šířka pásma (bps)")
    ib, ig, _ = np.unravel_index(j_plat, shape)
    pb, pg, pt = np.unravel_index(j_peak, shape)
    ax.scatter([ig], [ib], s=380, facecolors="none", edgecolors="blue", linewidths=3,
               label="střed plošiny (výběr mašiny)")
    if pt == it_rec:
        ax.scatter([pg], [pb], marker="x", s=200, c="black", linewidths=3, label="surový vrchol (argmax)")
    for i in range(len(bands)):
        for j in range(len(gaps)):
            ax.text(j, i, f"{S3[i, j, it_rec]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title(f"Obrázek: Mapa Sharpe (řez trend gate={rec['trend_pct']:.0f}) — IS 2005–2017\n"
                 f"mašina vybírá střed plošiny, ne vrchol")
    ax.legend(loc="lower right", fontsize=8)
    fig.colorbar(im, label="Sharpe")
    fig.tight_layout(); fig.savefig(f"{OUT}/opt_heatmap.png", dpi=120); plt.close(fig)

    # 2) WF equity: honest vs in-sample-fixed
    wf_dates = pd.to_datetime(np.array(ddates)[wf_mask])
    eq_wf = np.cumprod(1 + wf_plat); eq_is = np.cumprod(1 + DR[j_plat, wf_mask])
    eq_pk = np.cumprod(1 + wf_peak)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(wf_dates, eq_is * 100, lw=1.3, color="#999999", ls="--",
            label=f"IS-fixní konfigurace (optimistické): Sharpe {st_is_rec['sharpe']:.2f}")
    ax.plot(wf_dates, eq_wf * 100, lw=1.8, color="#1f77b4",
            label=f"WALK-FORWARD, plateau pravidlo (poctivé): Sharpe {st_wf_plat['sharpe']:.2f}")
    ax.plot(wf_dates, eq_pk * 100, lw=1.2, color="#d62728", alpha=0.8,
            label=f"walk-forward, argmax pravidlo: Sharpe {st_wf_peak['sharpe']:.2f}")
    ax.axhline(100, color="gray", lw=0.7, ls=":")
    ax.set_ylabel("hodnota účtu (start = 100)")
    ax.set_title("Obrázek: Walk-forward test — poctivé očekávání vs in-sample iluze (2009–2017)")
    ax.legend(); ax.grid(True, alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{OUT}/opt_walkforward.png", dpi=120); plt.close(fig)

    # 3) parameter stability across folds
    fig, axs = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    fold_years = [y for y, _ in picks_plat]
    for ax_, pname, pi in zip(axs, ["band_bps", "gap_pct", "trend_pct"], range(3)):
        vals = [cfg_name(grid, shape, j)[pname] for _, j in picks_plat]
        ax_.step(fold_years, vals, where="mid", lw=2, color="#1f77b4", marker="o")
        ax_.axhline(rec[pname], color="green", ls="--", lw=1,
                    label=f"finální doporučení {rec[pname]:.0f}")
        ax_.set_ylabel(pname); ax_.grid(True, alpha=0.25); ax_.legend(fontsize=8)
    axs[-1].set_xlabel("testovací rok (fold)")
    axs[0].set_title("Obrázek: Stabilita vybraných parametrů napříč walk-forward foldy")
    fig.tight_layout(); fig.savefig(f"{OUT}/opt_param_stability.png", dpi=120); plt.close(fig)

    # 4) PBO histogram
    fig, ax = plt.subplots(figsize=(10, 5.5))
    bins = np.linspace(0, 1, 21)
    ax.hist(om_arg, bins=bins, alpha=0.55, color="#d62728",
            label=f"argmax výběr: PBO {pbo_arg*100:.0f} %")
    ax.hist(om_pla, bins=bins, alpha=0.55, color="#2ca02c",
            label=f"plateau výběr: PBO {pbo_pla*100:.0f} %")
    ax.axvline(0.5, color="k", ls="--", lw=1.5, label="medián (0,5) — pod ním = selhání")
    ax.set_xlabel("relativní OOS pořadí IS vítěze (1 = nejlepší)")
    ax.set_ylabel("počet CSCV splitů (z 924)")
    ax.set_title("Obrázek: PBO — jak často in-sample vítěz selže na druhé půlce dat")
    ax.legend(); ax.grid(True, alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{OUT}/opt_pbo.png", dpi=120); plt.close(fig)

    # 5) noise floor
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    labels = ["REÁLNÁ data\n(WF Sharpe)"] + [f"šum #{i+1}\n(WF Sharpe)" for i in range(N_NOISE)] \
             + [f"šum #{i+1}\n(nejlepší IS)" for i in range(N_NOISE)]
    vals = [st_wf_plat["sharpe"]] + noise_wf + noise_is_best
    cols = ["#2ca02c"] + ["#d62728"] * N_NOISE + ["#f4a582"] * N_NOISE
    ax.bar(range(len(vals)), vals, color=cols)
    for i, v in enumerate(vals):
        ax.text(i, v + (0.02 if v >= 0 else -0.06), f"{v:.2f}", ha="center", fontsize=9)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(range(len(vals)), labels, fontsize=8)
    ax.set_ylabel("Sharpe")
    ax.set_title("Obrázek: Noise floor — mašina puštěná na náhodná data bez edge\n"
                 "reálný WF výsledek musí být nad vším, co si výběr vyrobí ze šumu")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{OUT}/opt_noise_floor.png", dpi=120); plt.close(fig)

    print(f"\nDONE {time.time()-t0:.0f}s -> {OUT}", flush=True)
    print(json.dumps(res["verdict"], indent=1), flush=True)


if __name__ == "__main__":
    main()
