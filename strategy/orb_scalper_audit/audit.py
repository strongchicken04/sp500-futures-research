"""
Forensic audit of the '15m automated ORB scalper' family (per the video):
OR auto-calculated (first 15/30 min RTH), signal = 15m bar CLOSE beyond the range
('yellow bar'), entry next 1-min bar open, stop {opposite OR extreme | OR midpoint},
TP {0.25R,0.5R,1R,2R,3R}, EOD flat, 1 trade/day, both directions.

Run through the Parameter Optimization Machine (plateau, walk-forward, CSCV PBO,
noise floor) on IS 2005-2017, exactly the process the video advertises (param
optimization + SPP + MC + OOS) - implemented strictly. Costs 0.5 bp/side
(generous: micro futures are cheap; 1bp sensitivity in the table).
Open verdict: if a variation passes, it passes.
"""
import sys, os, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from lab.lab import build_cache, OPEN_MIN, EOD_MIN                      # noqa
from optimizer.machine import (sharpe_daily, perf_stats, pick_plateau,  # noqa
                               pick_argmax, walk_forward, cscv_pbo, verdict)
from optimizer.adapter_vwap_gates import synth_days                     # noqa

OR_LENS = [15, 30]
STOPS = ["opp", "mid"]
TPS = [0.25, 0.5, 1.0, 2.0, 3.0]


def day_trade(a, or_len, stop_mode, tp_R, cost_bps=0.5):
    """One day, one config -> net return (0.0 if no trade). 15m signal, 1m walk."""
    m, o, h, l, c = a["m"], a["o"], a["h"], a["l"], a["c"]
    n = len(m)
    end_or = OPEN_MIN + or_len
    ior = np.searchsorted(m, end_or)
    if ior < 3 or ior >= n - 16:
        return 0.0
    or_h = h[:ior].max(); or_l = l[:ior].min()
    if or_h <= or_l:
        return 0.0
    # scan 15m bars after the OR for a close beyond the range
    k15 = end_or
    entry_i = 0; d = 0
    while k15 + 15 <= 960:
        j0 = np.searchsorted(m, k15); j1 = np.searchsorted(m, k15 + 15)
        if j1 <= j0:
            k15 += 15; continue
        c15 = c[j1 - 1]
        if c15 > or_h: d = 1
        elif c15 < or_l: d = -1
        if d != 0:
            entry_i = j1          # next 1-min bar
            break
        k15 += 15
    if d == 0 or entry_i >= n - 1:
        return 0.0
    e = o[entry_i]
    stop = (or_l if d == 1 else or_h) if stop_mode == "opp" else (or_h + or_l) / 2.0
    R = (e - stop) if d == 1 else (stop - e)
    if R <= 0:
        return 0.0
    tp = e + d * tp_R * R
    cost = 2 * cost_bps / 1e4
    for k in range(entry_i, n):
        if m[k] >= EOD_MIN:
            return d * (c[k] - e) / e - cost
        if d == 1:
            if l[k] <= stop: return (stop - e) / e - cost
            if h[k] >= tp:   return (tp - e) / e - cost
        else:
            if h[k] >= stop: return -(stop - e) / e - cost
            if l[k] <= tp:   return -(tp - e) / e - cost
    return d * (c[-1] - e) / e - cost


def build_DR(days, dates, cost_bps=0.5):
    cfgs = [(ol, sm, tp) for ol in OR_LENS for sm in STOPS for tp in TPS]
    DR = np.zeros((len(cfgs), len(dates)))
    for j, dte in enumerate(dates):
        a = days[dte]
        for i, (ol, sm, tp) in enumerate(cfgs):
            DR[i, j] = day_trade(a, ol, sm, tp, cost_bps)
    grid = [("or_len", OR_LENS), ("stop", STOPS), ("tp_R", TPS)]
    return DR, grid


def main():
    out = "/home/user/sp500-futures-research/results/orb_scalper_audit"
    os.makedirs(out, exist_ok=True)
    days, dates, _ = build_cache()
    is_dates = [d for d in dates if 2005 <= int(d[:4]) <= 2017]
    years = np.array([int(d[:4]) for d in is_dates])
    DR, grid = build_DR(days, is_dates)
    shape = tuple(len(v) for _, v in grid)
    cfg_names = [f"OR{ol} stop={sm} TP={tp}R" for ol in OR_LENS for sm in STOPS for tp in TPS]
    sh = sharpe_daily(DR)

    print("=== config table (net 0.5bp/side, IS 2005-2017) ===")
    print(f"{'config':26} {'trades':>6} {'win%':>6} {'avgBps':>7} {'Sharpe':>7}")
    tbl = []
    for i, nm in enumerate(cfg_names):
        r = DR[i][DR[i] != 0]
        tbl.append(dict(cfg=nm, n=len(r), win=round(float((r > 0).mean() * 100), 1),
                        avg=round(float(r.mean() * 1e4), 2), sharpe=round(float(sh[i]), 2)))
        print(f"{nm:26} {len(r):>6} {(r>0).mean()*100:>6.1f} {r.mean()*1e4:>7.2f} {sh[i]:>7.2f}")

    j_plat = pick_plateau(sh, shape)
    wf, wf_mask, picks = walk_forward(DR, years, shape, pick_plateau)
    st_wf = perf_stats(wf)
    pbo, _ = cscv_pbo(DR, S=12, picker=pick_plateau, shape=shape)
    noise_wf = []
    for s in range(3):
        sd_, sdt_ = synth_days(len(is_dates), seed=300 + s)
        DRn, _ = build_DR(sd_, sdt_)
        yn = np.array([int(d[:4]) for d in sdt_])
        noise_wf.append(float(sharpe_daily(walk_forward(DRn, yn, shape, pick_plateau)[0])))
    ver = verdict(st_wf["sharpe"], pbo, noise_wf)
    print(f"\n[machine] plateau pick: {cfg_names[j_plat]} (IS Sharpe {sh[j_plat]:.2f})")
    print(f"[machine] WF: {st_wf}")
    print(f"[machine] PBO: {pbo*100:.0f}%  noise WF: {[round(x,2) for x in noise_wf]}")
    print(f"[machine] VERDICT: {'PASS' if ver['pass_all'] else 'FAIL'}  {ver}")

    # scalper corner = his 80% profile: OR15, stop=opp, TP=0.25R
    i_corner = cfg_names.index("OR15 stop=opp TP=0.25R")
    rc = DR[i_corner][DR[i_corner] != 0]
    stc = perf_stats(DR[i_corner])
    print(f"\n[scalper corner] OR15/opp/0.25R: win {(rc>0).mean()*100:.1f}%  "
          f"avg {rc.mean()*1e4:+.2f}bps  Sharpe {stc['sharpe']:.2f}  tot {stc['tot']:.1f}%")

    # 1bp sensitivity for the best config
    DR1, _ = build_DR(days, is_dates, cost_bps=1.0)
    sh1 = sharpe_daily(DR1)
    json.dump(dict(table=tbl, plateau_pick=cfg_names[j_plat],
                   plateau_is_sharpe=round(float(sh[j_plat]), 3),
                   wf=st_wf, pbo=round(pbo, 3), noise_wf=[round(x, 3) for x in noise_wf],
                   verdict=ver,
                   corner_profile=dict(win=round(float((rc > 0).mean() * 100), 1),
                                       avg_bps=round(float(rc.mean() * 1e4), 2),
                                       sharpe=stc["sharpe"], tot=stc["tot"]),
                   best_sharpe_at_1bp=round(float(sh1.max()), 3),
                   wf_picks=[(int(y), cfg_names[j]) for y, j in picks]),
              open(f"{out}/audit.json", "w"), indent=2)

    # charts
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 6))
    cols = ["#2ca02c" if s > 0 else "#d62728" for s in sh]
    ax.barh(range(len(cfg_names)), sh, color=cols)
    ax.set_yticks(range(len(cfg_names)), cfg_names, fontsize=8)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("net Sharpe (0,5 bp/side, IS 2005-2017)")
    ax.set_title("ORB scalper rodina — všech 20 konfigurací\n(zelená = kladný Sharpe)")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{out}/audit_sharpes.png", dpi=120); plt.close(fig)

    eq = np.cumprod(1 + DR[i_corner]) * 100
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(pd.to_datetime(is_dates), eq, lw=1.3, color="#d62728")
    ax.axhline(100, color="k", ls=":", lw=0.8)
    ax.set_title(f"'80% win rate' roh rodiny (OR15, stop protější, TP 0,25R)\n"
                 f"win rate {(rc>0).mean()*100:.1f} % — a přesto: {stc['tot']:.0f} % celkem, Sharpe {stc['sharpe']:.2f}")
    ax.set_ylabel("účet (start 100)")
    ax.grid(True, alpha=0.25)
    fig.tight_layout(); fig.savefig(f"{out}/audit_corner_equity.png", dpi=120); plt.close(fig)
    print("\nsaved audit.json + 2 charts")


if __name__ == "__main__":
    main()
