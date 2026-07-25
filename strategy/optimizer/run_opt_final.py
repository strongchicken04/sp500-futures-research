"""
Machine run on the journal's FINAL strategy version:
    VWAP band 20 bps + gap gate 25 + trend gate 60 + VT15 vol-targeting.

Grid = 4 axes: band_bps x gap_pct x trend_pct x vt_target (0 = sizing off).
Vol targeting: daily leverage L_t = clip(target / sigma_t, 0, 3), where sigma_t is
the 20-day realized vol of the STRATEGY'S OWN past daily returns (shifted 1 day,
past-only; L=1 until 20 days of history). This is a standard account-level VT;
the journal's exact VT15 internals may differ slightly - assumption documented.

IS 2005-2017 only; true OOS 2018-2020/05 stays locked. For the journal config
(fitted on 2018-2025) this window is OUT-OF-ERA - an honest external check.
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
VTS = [0.0, 10.0, 15.0, 20.0]          # vol target in % p.a.; 0 = off
VT_WIN, VT_CAP = 20, 3.0
USER_CFG = {"band_bps": 20.0, "gap_pct": 25.0, "trend_pct": 60.0, "vt_target": 15.0}
N_NOISE = 3


def add_vt_axis(DR3: np.ndarray, vts=VTS, window=VT_WIN, cap=VT_CAP):
    """Expand (ncfg, ndays) -> (ncfg*len(vts), ndays), vt as the LAST grid axis.
    Leverage from past-only rolling vol of each config's own daily returns."""
    df = pd.DataFrame(DR3.T)                                    # days x cfg
    sd = df.rolling(window, min_periods=window).std().shift(1).to_numpy().T
    ann = sd * np.sqrt(252)
    outs = []
    for vt in vts:
        if vt <= 0:
            outs.append(DR3.copy())
        else:
            L = np.where(np.isnan(ann) | (ann <= 1e-6), 1.0,
                         np.clip((vt / 100.0) / np.where(ann <= 1e-6, 1.0, ann), 0.0, cap))
            outs.append(DR3 * L)
    DR4 = np.stack(outs, axis=-1)                               # (ncfg, nd, V)
    ncfg, nd = DR3.shape
    return np.transpose(DR4, (0, 2, 1)).reshape(ncfg * len(vts), nd)


def cfg_name(grid, shape, j):
    idx = np.unravel_index(j, shape)
    return {name: vals[i] for (name, vals), i in zip(grid, idx)}


def cfg_index(grid, shape, cfg):
    idx = tuple(vals.index(cfg[name]) for name, vals in grid)
    return int(np.ravel_multi_index(idx, shape))


def full_pipeline(days, dates):
    DR3, grid3, dd = build_DR(days, dates)
    DR = add_vt_axis(DR3)
    grid = grid3 + [("vt_target", VTS)]
    shape = tuple(len(v) for _, v in grid)
    years = np.array([int(d[:4]) for d in dd])
    return DR, grid, shape, years, dd


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    days, dates, _ = build_cache()
    is_dates = [d for d in dates if IS_Y0 <= int(d[:4]) <= IS_Y1]
    DR, grid, shape, years, dd = full_pipeline(days, is_dates)
    print(f"[grid] {DR.shape[0]} configs x {DR.shape[1]} days ({time.time()-t0:.0f}s)", flush=True)

    sh = sharpe_daily(DR)
    ns = neighborhood_score(sh, shape)
    j_plat = pick_plateau(sh, shape)
    j_peak = pick_argmax(sh, shape)
    j_user = cfg_index(grid, shape, USER_CFG)
    rec, peak = cfg_name(grid, shape, j_plat), cfg_name(grid, shape, j_peak)
    user_rank_sh = int((sh > sh[j_user]).sum() + 1)
    user_rank_ns = int((ns > ns[j_user]).sum() + 1)
    print(f"[pick] plateau: {rec} (IS Sharpe {sh[j_plat]:.2f})", flush=True)
    print(f"[user] {USER_CFG}: IS Sharpe {sh[j_user]:.2f}, rank {user_rank_sh}/{DR.shape[0]}, "
          f"plateau-rank {user_rank_ns}", flush=True)

    wf_plat, wf_mask, picks = walk_forward(DR, years, shape, pick_plateau)
    wf_peak, _, _ = walk_forward(DR, years, shape, pick_argmax)
    st_wf = perf_stats(wf_plat)
    st_wf_peak = perf_stats(wf_peak)
    st_user_wfwin = perf_stats(DR[j_user, wf_mask])       # user config fixed, same window
    st_user_full = perf_stats(DR[j_user])                 # user config, full IS
    st_rec_wfwin = perf_stats(DR[j_plat, wf_mask])
    print(f"[wf] plateau {st_wf} | user-fixed {st_user_wfwin}", flush=True)

    pbo_arg, om_arg = cscv_pbo(DR, S=12)
    pbo_pla, om_pla = cscv_pbo(DR, S=12, picker=pick_plateau, shape=shape)
    print(f"[pbo] argmax {pbo_arg*100:.0f}% plateau {pbo_pla*100:.0f}%", flush=True)

    noise_wf, noise_is = [], []
    for s in range(N_NOISE):
        sdys, sdts = synth_days(len(is_dates), seed=200 + s)
        DRn, gn, shn_, yn, _ = full_pipeline(sdys, sdts)
        shn = sharpe_daily(DRn)
        noise_is.append(float(shn.max()))
        wfn, _, _ = walk_forward(DRn, yn, shn_, pick_plateau)
        noise_wf.append(float(sharpe_daily(wfn)))
        print(f"[noise {s}] best IS {shn.max():.2f} -> WF {noise_wf[-1]:.2f}", flush=True)

    ver = verdict(st_wf["sharpe"], pbo_pla, noise_wf)
    res = dict(
        window=f"{IS_Y0}-{IS_Y1}", n_configs=int(DR.shape[0]),
        grid={n: v for n, v in grid},
        vt_model=f"L_t=clip(target/sigma20(own past rets,shift1),0,{VT_CAP}); L=1 first {VT_WIN}d",
        recommended=rec, recommended_is_sharpe=round(float(sh[j_plat]), 3),
        raw_peak=peak, raw_peak_is_sharpe=round(float(sh[j_peak]), 3),
        user_config=USER_CFG,
        user_is_sharpe=round(float(sh[j_user]), 3),
        user_rank_sharpe=user_rank_sh, user_rank_plateau=user_rank_ns,
        user_full_is=st_user_full, user_fixed_wf_window=st_user_wfwin,
        rec_fixed_wf_window=st_rec_wfwin,
        wf_plateau=st_wf, wf_argmax=st_wf_peak,
        wf_picks=[(y, cfg_name(grid, shape, j)) for y, j in picks],
        pbo_argmax=round(pbo_arg, 3), pbo_plateau=round(pbo_pla, 3),
        noise_wf_sharpes=[round(x, 3) for x in noise_wf],
        noise_best_is_sharpes=[round(x, 3) for x in noise_is],
        verdict=ver,
        note="Journal cfg was fitted on 2018-2025; this 2005-2017 window is out-of-era "
             "for it. True OOS 2018-2020/05 remains locked.")
    with open(f"{OUT}/final_version_optimization.json", "w") as f:
        json.dump(res, f, indent=2, default=str)

    # ---- charts ----
    bands, gaps, trends, vts = (grid[0][1], grid[1][1], grid[2][1], grid[3][1])
    S4 = sh.reshape(shape)
    it, iv = trends.index(rec["trend_pct"]), vts.index(rec["vt_target"])
    fig, ax = plt.subplots(figsize=(10, 6))
    M = S4[:, :, it, iv]
    im = ax.imshow(M, cmap="RdYlGn", aspect="auto",
                   vmin=-max(abs(S4.min()), S4.max()), vmax=max(abs(S4.min()), S4.max()))
    ax.set_xticks(range(len(gaps)), [f"{g:.0f}" for g in gaps])
    ax.set_yticks(range(len(bands)), [f"{b:.0f}" for b in bands])
    ax.set_xlabel("gap gate percentil"); ax.set_ylabel("šířka pásma (bps)")
    ib_, ig_, _, _ = np.unravel_index(j_plat, shape)
    ax.scatter([ig_], [ib_], s=380, facecolors="none", edgecolors="blue", linewidths=3,
               label="výběr mašiny (střed plošiny)")
    ub, ug, ut, uv = np.unravel_index(j_user, shape)
    if ut == it and uv == iv:
        ax.scatter([ug], [ub], marker="s", s=300, facecolors="none", edgecolors="purple",
                   linewidths=3, label="tvoje finální konfigurace")
    for i in range(len(bands)):
        for j in range(len(gaps)):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title(f"Obrázek: Mapa Sharpe (řez trend={rec['trend_pct']:.0f}, VT={rec['vt_target']:.0f}) — IS 2005–2017")
    ax.legend(loc="lower left", fontsize=8)
    fig.colorbar(im, label="Sharpe")
    fig.tight_layout(); fig.savefig(f"{OUT}/final_heatmap.png", dpi=120); plt.close(fig)

    wf_dates = pd.to_datetime(np.array(dd)[wf_mask])
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(wf_dates, np.cumprod(1 + DR[j_user, wf_mask]) * 100, lw=1.5, color="#9467bd",
            label=f"tvoje konfigurace (fixní, out-of-era): Sharpe {st_user_wfwin['sharpe']:.2f}")
    ax.plot(wf_dates, np.cumprod(1 + wf_plat) * 100, lw=1.8, color="#1f77b4",
            label=f"mašina walk-forward (poctivé): Sharpe {st_wf['sharpe']:.2f}")
    ax.plot(wf_dates, np.cumprod(1 + DR[j_plat, wf_mask]) * 100, lw=1.2, ls="--", color="#999999",
            label=f"doporučená konfigurace fixně (optimistické): Sharpe {st_rec_wfwin['sharpe']:.2f}")
    ax.axhline(100, color="gray", lw=0.7, ls=":")
    ax.set_ylabel("hodnota účtu (start = 100)")
    ax.set_title("Obrázek: Finální verze z deníku vs Parameter Optimization Machine (2009–2017)")
    ax.legend(); ax.grid(True, alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{OUT}/final_walkforward.png", dpi=120); plt.close(fig)

    fig, axs = plt.subplots(4, 1, figsize=(10, 8.5), sharex=True)
    fy = [y for y, _ in picks]
    for ax_, pname in zip(axs, ["band_bps", "gap_pct", "trend_pct", "vt_target"]):
        vals = [cfg_name(grid, shape, j)[pname] for _, j in picks]
        ax_.step(fy, vals, where="mid", lw=2, marker="o", color="#1f77b4")
        ax_.axhline(USER_CFG[pname], color="purple", ls="--", lw=1.2,
                    label=f"tvoje hodnota {USER_CFG[pname]:.0f}")
        ax_.set_ylabel(pname); ax_.grid(True, alpha=0.25); ax_.legend(fontsize=8)
    axs[-1].set_xlabel("testovací rok (fold)")
    axs[0].set_title("Obrázek: Stabilita parametrů napříč foldy vs tvoje finální hodnoty")
    fig.tight_layout(); fig.savefig(f"{OUT}/final_param_stability.png", dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bins = np.linspace(0, 1, 21)
    ax.hist(om_arg, bins=bins, alpha=0.55, color="#d62728", label=f"argmax: PBO {pbo_arg*100:.0f} %")
    ax.hist(om_pla, bins=bins, alpha=0.55, color="#2ca02c", label=f"plateau: PBO {pbo_pla*100:.0f} %")
    ax.axvline(0.5, color="k", ls="--", lw=1.5)
    ax.set_xlabel("relativní OOS pořadí IS vítěze"); ax.set_ylabel("počet splitů")
    ax.set_title("Obrázek: PBO — 4D mřížka (1152 konfigurací)")
    ax.legend(); ax.grid(True, alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{OUT}/final_pbo.png", dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    labels = ["REÁLNÁ data\n(WF)"] + [f"šum #{i+1}\n(WF)" for i in range(N_NOISE)]
    vals = [st_wf["sharpe"]] + noise_wf
    ax.bar(range(len(vals)), vals, color=["#2ca02c"] + ["#d62728"] * N_NOISE)
    for i, v in enumerate(vals):
        ax.text(i, v + (0.02 if v >= 0 else -0.06), f"{v:.2f}", ha="center")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(range(len(vals)), labels, fontsize=9)
    ax.set_ylabel("Sharpe"); ax.set_title("Obrázek: Noise floor — 4D pipeline na datech bez edge")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{OUT}/final_noise_floor.png", dpi=120); plt.close(fig)

    print(f"\nDONE {time.time()-t0:.0f}s", flush=True)
    print(json.dumps(ver, indent=1), flush=True)


if __name__ == "__main__":
    main()
