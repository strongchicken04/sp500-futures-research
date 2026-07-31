"""
Machine run: Holmberg vol-scaled ORB (alpha books z realneho NQ) + regime gaty.

Grid (4 osy, 160 konfiguraci):
    alpha      : [10, 5, 1, 0.5, 0.1] %   (5 QC knih, rolling 250d prahy)
    vol_gate   : [0=off, 40, 50, 60]      (past-only rank rvol20 > prah)
    gap_gate   : [0=off, 40, 50, 60]      (past-only rank |gap| > prah)
    trend_cap  : [100=off, 75]            (past-only rank trend50 <= prah)
  Gaty kombinovane jako v regime vyzkumu: (vol OR gap) AND trend.

DR[cfg, day] = bps obchodu / 1e4 (net 2 bps costs), 0 kdyz kniha neobchodovala
nebo filtr den zablokoval. Data: obchody 2018-2025 z QC (hb_trades_full.json),
featury z realneho NQ panelu (nq_panel_real.csv), ranky past-only 250d.

POZOR (poctivost): obchody existuji jen 2018-2025, takze grid IS = stejna era.
Poctive cislo je walk-forward (train 4y -> test 1y, foldy 2022-2025). Noise
floor = kompletni pipeline (GBM minutove dny s vol-clusteringem, nulovy drift,
prahy, first-touch, featury, gaty, WF) na 3 syntetickych svetech.
"""
import sys, os, json, time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from machine import (sharpe_daily, perf_stats, neighborhood_score, pick_plateau,
                     pick_argmax, walk_forward, cscv_pbo, verdict)          # noqa

ROOT = "/home/user/sp500-futures-research"
OUT = f"{ROOT}/results/optimizer"
TRADES = "/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/hb_trades_full.json"
PANEL = f"{ROOT}/results/nq_panel_real.csv"

ALPHAS = [10.0, 5.0, 1.0, 0.5, 0.1]
ZS = [1.2816, 1.6449, 2.3263, 2.5758, 3.0902]
VOLS = [0.0, 40.0, 50.0, 60.0]
GAPS = [0.0, 40.0, 50.0, 60.0]
TRENDS = [100.0, 75.0]
COST_BPS = 2.0
RANK_WIN = 250
REF_CFG = {"alpha": 5.0, "vol_gate": 50.0, "gap_gate": 50.0, "trend_cap": 75.0}
N_NOISE = 3


def past_rank(x: np.ndarray, win: int = RANK_WIN, minp: int = 60) -> np.ndarray:
    """Percentil (0-100) x[t] vuci predchozim `win` hodnotam (bez x[t]). NaN dokud < minp."""
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(n):
        lo = max(0, t - win)
        h = x[lo:t]
        h = h[~np.isnan(h)]
        if len(h) >= minp and not np.isnan(x[t]):
            out[t] = 100.0 * (h <= x[t]).sum() / len(h)
    return out


def build_DR_real():
    panel = pd.read_csv(PANEL, parse_dates=["date"]).set_index("date").sort_index()
    rv = past_rank(panel["rvol20"].to_numpy())
    rg = past_rank(panel["gap_pct"].abs().to_numpy())
    rt = past_rank(panel["trend50"].to_numpy())
    panel["rank_vol"], panel["rank_gap"], panel["rank_trend"] = rv, rg, rt

    trades = json.load(open(TRADES))
    tmap = {}                                   # (date, ai) -> bps
    for t in trades:
        tmap[(t["date"], t["ai"])] = t["bps"]

    days = panel[(panel.index.year >= 2010)
                 & panel["rank_vol"].notna() & panel["rank_gap"].notna()
                 & panel["rank_trend"].notna()]
    dd = [d.strftime("%Y-%m-%d") for d in days.index]
    return _assemble(days, dd, tmap)


def _assemble(days: pd.DataFrame, dd: list, tmap: dict):
    nd = len(dd)
    rv = days["rank_vol"].to_numpy()
    rg = days["rank_gap"].to_numpy()
    rt = days["rank_trend"].to_numpy()
    raw = np.zeros((len(ALPHAS), nd))
    for ai in range(len(ALPHAS)):
        for k, d in enumerate(dd):
            b = tmap.get((d, ai))
            if b is not None:
                raw[ai, k] = (b - COST_BPS) / 1e4
    DR = np.zeros((len(ALPHAS), len(VOLS), len(GAPS), len(TRENDS), nd))
    for iv, V in enumerate(VOLS):
        for ig, G in enumerate(GAPS):
            conds = []
            if V > 0:
                conds.append(rv > V)
            if G > 0:
                conds.append(rg > G)
            ok = np.logical_or.reduce(conds) if conds else np.ones(nd, bool)
            for it, U in enumerate(TRENDS):
                m = ok & (rt <= U)
                DR[:, iv, ig, it, :] = raw * m[None, :]
    grid = [("alpha", ALPHAS), ("vol_gate", VOLS), ("gap_gate", GAPS), ("trend_cap", TRENDS)]
    shape = tuple(len(v) for _, v in grid)
    years = np.array([int(d[:4]) for d in dd])
    return DR.reshape(-1, nd), grid, shape, years, dd


def synth_world(ndays_out: int, seed: int):
    """Zero-edge svet: GBM minutove dny s AR(1) vol-clusteringem, cela Holmberg
    pipeline (rolling prahy, first-touch, gap-safe fill) + featury + ranky."""
    rng = np.random.default_rng(seed)
    warm = 320
    nd = ndays_out + warm
    NM = 390
    mu_lv = np.log(0.012)
    lv = np.empty(nd)
    lv[0] = mu_lv
    for t in range(1, nd):
        lv[t] = mu_lv + 0.97 * (lv[t - 1] - mu_lv) + rng.normal(0, 0.15)
    sig = np.exp(lv)                                    # denni vol (close-to-close scale)

    closes = np.empty(nd)
    opens = np.empty(nd)
    oc = np.empty(nd)                                   # log(C/O)
    tr_bps = np.full((len(ALPHAS), nd), np.nan)         # bps prvniho obchodu / NaN
    prev_c = 100.0
    hist = []
    for t in range(nd):
        o = prev_c * np.exp(rng.normal(0, 0.6 * sig[t]))
        steps = rng.normal(0, sig[t] / np.sqrt(NM), NM)
        cs = np.cumsum(steps)
        c = o * np.exp(cs[-1])
        opens[t], closes[t] = o, c
        oc[t] = np.log(c / o)
        if len(hist) >= 60:
            h = np.array(hist[-RANK_WIN:])
            m, s = h.mean(), h.std(ddof=1)
            for ai, z in enumerate(ZS):
                ru, rl = m + s * z, m - s * z
                iu = np.argmax(cs >= ru) if (cs >= ru).any() else NM
                idn = np.argmax(cs <= rl) if (cs <= rl).any() else NM
                if iu == NM and idn == NM:
                    continue
                if iu <= idn:
                    e = o * np.exp(ru)
                    tr_bps[ai, t] = 1e4 * (c / e - 1.0)
                else:
                    e = o * np.exp(rl)
                    tr_bps[ai, t] = 1e4 * (e / c - 1.0) * (c / e)  # ~ short bps
        hist.append(oc[t])
        prev_c = c

    dcl = np.diff(np.log(closes), prepend=np.log(closes[0]))
    rvol20 = pd.Series(dcl).rolling(20).std().to_numpy() * np.sqrt(252)
    gap = np.empty(nd)
    gap[0] = np.nan
    gap[1:] = np.log(opens[1:] / closes[:-1])
    t50 = np.full(nd, np.nan)
    t50[50:] = closes[50:] / closes[:-50] - 1.0

    df = pd.DataFrame({"rank_vol": past_rank(rvol20), "rank_gap": past_rank(np.abs(gap)),
                       "rank_trend": past_rank(t50)})
    keep = np.arange(nd) >= warm
    df = df[keep].reset_index(drop=True)
    ok = df.notna().all(axis=1).to_numpy()
    df = df[ok].reset_index(drop=True)
    kept_idx = np.where(keep)[0][ok]
    y0 = 2018
    dd = [f"{y0 + k // 250:04d}-{(k % 250) // 21 + 1:02d}-{k % 21 + 1:02d}" for k in range(len(df))]
    tmap = {}
    for ai in range(len(ALPHAS)):
        for k, t in enumerate(kept_idx):
            if not np.isnan(tr_bps[ai, t]):
                tmap[(dd[k], ai)] = float(tr_bps[ai, t])
    return _assemble(df, dd, tmap)


def cfg_name(grid, shape, j):
    idx = np.unravel_index(j, shape)
    return {name: vals[i] for (name, vals), i in zip(grid, idx)}


def cfg_index(grid, shape, cfg):
    idx = tuple(vals.index(cfg[name]) for name, vals in grid)
    return int(np.ravel_multi_index(idx, shape))


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    DR, grid, shape, years, dd = build_DR_real()
    print(f"[grid] {DR.shape[0]} cfg x {DR.shape[1]} days ({time.time()-t0:.0f}s)", flush=True)

    sh = sharpe_daily(DR)
    ns = neighborhood_score(sh, shape)
    j_plat = pick_plateau(sh, shape)
    j_peak = pick_argmax(sh, shape)
    j_ref = cfg_index(grid, shape, REF_CFG)
    rec, peak = cfg_name(grid, shape, j_plat), cfg_name(grid, shape, j_peak)
    print(f"[pick] plateau {rec} IS Sharpe {sh[j_plat]:.2f} | argmax {peak} {sh[j_peak]:.2f} "
          f"| ref {REF_CFG} {sh[j_ref]:.2f}", flush=True)

    wf_plat, wf_mask, picks = walk_forward(DR, years, shape, pick_plateau)
    wf_peak, _, _ = walk_forward(DR, years, shape, pick_argmax)
    st_wf = perf_stats(wf_plat)
    st_wf_peak = perf_stats(wf_peak)
    st_ref_wfwin = perf_stats(DR[j_ref, wf_mask])
    print(f"[wf] plateau {st_wf} | argmax {st_wf_peak['sharpe']} | ref fixed {st_ref_wfwin['sharpe']}", flush=True)

    pbo_arg, om_arg = cscv_pbo(DR, S=12)
    pbo_pla, om_pla = cscv_pbo(DR, S=12, picker=pick_plateau, shape=shape)
    print(f"[pbo] argmax {pbo_arg*100:.0f}% plateau {pbo_pla*100:.0f}%", flush=True)

    noise_wf, noise_is = [], []
    for s in range(N_NOISE):
        DRn, gn, shn_, yn, _ = synth_world(DR.shape[1], seed=300 + s)
        shn = sharpe_daily(DRn)
        noise_is.append(float(shn.max()))
        wfn, _, _ = walk_forward(DRn, yn, shn_, pick_plateau)
        noise_wf.append(float(sharpe_daily(wfn)))
        print(f"[noise {s}] best IS {shn.max():.2f} -> WF {noise_wf[-1]:.2f}", flush=True)

    ver = verdict(st_wf["sharpe"], pbo_pla, noise_wf)
    res = dict(
        window="2010-2025 (full era; WF folds 2014-2025)",
        n_configs=int(DR.shape[0]), grid={n: v for n, v in grid},
        cost_bps_per_trade=COST_BPS,
        recommended=rec, recommended_is_sharpe=round(float(sh[j_plat]), 3),
        raw_peak=peak, raw_peak_is_sharpe=round(float(sh[j_peak]), 3),
        ref_config=REF_CFG, ref_is_sharpe=round(float(sh[j_ref]), 3),
        ref_fixed_wf_window=st_ref_wfwin,
        wf_plateau=st_wf, wf_argmax=st_wf_peak,
        wf_picks=[(int(y), cfg_name(grid, shape, j)) for y, j in picks],
        pbo_argmax=round(pbo_arg, 3), pbo_plateau=round(pbo_pla, 3),
        noise_wf_sharpes=[round(x, 3) for x in noise_wf],
        noise_best_is_sharpes=[round(x, 3) for x in noise_is],
        verdict=ver,
        note="Trades exist only 2018-2025 (QC real NQ, rolling thresholds, gap-safe "
             "fills, 2bps cost). Grid IS = same era; honest number is the WF stitch. "
             "Noise = full pipeline on GBM worlds with vol clustering, zero drift.")
    with open(f"{OUT}/holmberg_optimization.json", "w") as f:
        json.dump(res, f, indent=2, default=str)

    # charts
    S4 = sh.reshape(shape)
    it = TRENDS.index(rec["trend_cap"])
    ia = ALPHAS.index(rec["alpha"])
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    M = S4[ia, :, :, it]
    vm = max(abs(S4.min()), S4.max())
    im = ax.imshow(M, cmap="RdYlGn", aspect="auto", vmin=-vm, vmax=vm)
    ax.set_xticks(range(len(GAPS)), [f"{g:.0f}" for g in GAPS])
    ax.set_yticks(range(len(VOLS)), [f"{v:.0f}" for v in VOLS])
    ax.set_xlabel("gap gate percentil (0=off)"); ax.set_ylabel("vol gate percentil (0=off)")
    _, iv_, ig_, _ = np.unravel_index(j_plat, shape)
    ax.scatter([ig_], [iv_], s=380, facecolors="none", edgecolors="blue", linewidths=3)
    for i in range(len(VOLS)):
        for j in range(len(GAPS)):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=9)
    ax.set_title(f"Holmberg ORB: Sharpe mapa (alpha={rec['alpha']}%, trend_cap={rec['trend_cap']:.0f}) IS 2018-2025")
    fig.colorbar(im, label="Sharpe")
    fig.tight_layout(); fig.savefig(f"{OUT}/holmberg_heatmap.png", dpi=120); plt.close(fig)

    wf_dates = pd.to_datetime(np.array(dd)[wf_mask])
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(wf_dates, np.cumprod(1 + wf_plat) * 100, lw=1.8, color="#1f77b4",
            label=f"walk-forward plateau (poctive): Sharpe {st_wf['sharpe']:.2f}")
    ax.plot(wf_dates, np.cumprod(1 + DR[j_ref, wf_mask]) * 100, lw=1.3, color="#9467bd",
            label=f"ref cfg fixne (alpha5+50/50/75): Sharpe {st_ref_wfwin['sharpe']:.2f}")
    ax.axhline(100, color="gray", lw=0.7, ls=":")
    ax.set_ylabel("ucet (start=100)")
    ax.set_title("Holmberg ORB + gaty: walk-forward 2022-2025 (foldy, train 4 roky)")
    ax.legend(); ax.grid(True, alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{OUT}/holmberg_walkforward.png", dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.5, 5))
    bins = np.linspace(0, 1, 21)
    ax.hist(om_arg, bins=bins, alpha=0.55, color="#d62728", label=f"argmax: PBO {pbo_arg*100:.0f} %")
    ax.hist(om_pla, bins=bins, alpha=0.55, color="#2ca02c", label=f"plateau: PBO {pbo_pla*100:.0f} %")
    ax.axvline(0.5, color="k", ls="--", lw=1.5)
    ax.set_xlabel("relativni OOS poradi IS viteze"); ax.set_ylabel("pocet splitu")
    ax.set_title("Holmberg ORB: PBO (160 konfiguraci, S=12)")
    ax.legend(); ax.grid(True, alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{OUT}/holmberg_pbo.png", dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    labels = ["REAL (WF)"] + [f"noise #{i+1} (WF)" for i in range(N_NOISE)]
    vals = [st_wf["sharpe"]] + noise_wf
    ax.bar(range(len(vals)), vals, color=["#2ca02c"] + ["#d62728"] * N_NOISE)
    for i, v in enumerate(vals):
        ax.text(i, v + (0.02 if v >= 0 else -0.06), f"{v:.2f}", ha="center")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(range(len(vals)), labels, fontsize=9)
    ax.set_ylabel("Sharpe"); ax.set_title("Holmberg ORB: noise floor (plna pipeline, zero-edge svety)")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{OUT}/holmberg_noise_floor.png", dpi=120); plt.close(fig)

    print(f"\nDONE {time.time()-t0:.0f}s", flush=True)
    print(json.dumps(ver, indent=1), flush=True)


if __name__ == "__main__":
    main()
