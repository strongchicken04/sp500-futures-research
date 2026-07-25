"""
Parameter Optimization Machine — anti-overfit by construction.

Charter (hard rules, encoded below — do not soften them per-strategy):
  1. NEVER pick the argmax. Pick the CENTER OF THE PLATEAU: each config is scored
     by the mean Sharpe of its full grid neighborhood (itself + adjacent cells in
     every parameter dimension). A lone spike gets dragged down by bad neighbors.
  2. The honest performance estimate is WALK-FORWARD: re-run the selection rule on
     each rolling train window, trade the NEXT year with what was selected, stitch
     the out-of-fold segments. Report THAT number, not the in-sample one.
  3. PBO (probability of backtest overfitting, CSCV of Bailey & Lopez de Prado):
     split days into S blocks, for every balanced block-split rank configs on one
     half and check where the winner lands on the other half. PBO = share of
     splits where the IS winner is below the OOS median. PBO >= 50% => selection
     is noise => REJECT.
  4. NOISE FLOOR: run the entire pipeline on synthetic random-walk data with no
     edge by construction. The real walk-forward Sharpe must exceed the noise
     distribution, otherwise the "edge" is manufactured by the search itself.
  5. The grid is pre-defined and coarse. One pass. No refinement loops, no second
     visit to the data after seeing results.

Generic over strategies: a strategy plugs in via an ADAPTER that produces a
daily-return matrix DR[config, day] for the full parameter grid (see
adapter_vwap_gates.py for the contract).
"""
from __future__ import annotations
import itertools
from itertools import combinations
import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
#  metrics
# --------------------------------------------------------------------------- #
def sharpe_daily(dr: np.ndarray) -> np.ndarray:
    """Annualised Sharpe along the last axis (daily returns)."""
    mu = dr.mean(axis=-1)
    sd = dr.std(axis=-1)
    return np.where(sd > 0, mu / np.where(sd == 0, 1, sd) * np.sqrt(252), 0.0)


def perf_stats(dr: np.ndarray) -> dict:
    eq = np.cumprod(1.0 + dr)
    n = len(dr)
    cagr = (eq[-1] ** (252.0 / n) - 1.0) * 100 if eq[-1] > 0 else -100.0
    peak = np.maximum.accumulate(eq)
    mdd = ((eq - peak) / peak).min() * 100
    sh = float(sharpe_daily(dr))
    return dict(sharpe=round(sh, 3), cagr=round(float(cagr), 2),
                mdd=round(float(mdd), 2), tot=round(float((eq[-1] - 1) * 100), 1),
                calmar=round(float(cagr / abs(mdd)) if mdd else 0.0, 2))


# --------------------------------------------------------------------------- #
#  1) plateau selection
# --------------------------------------------------------------------------- #
def neighborhood_score(metric_flat: np.ndarray, shape: tuple) -> np.ndarray:
    """Mean of each cell's full neighborhood (itself + all adjacent cells,
    edges use the neighbors that exist). Returns flat array."""
    M = metric_flat.reshape(shape)
    acc = np.zeros_like(M, dtype=float)
    cnt = np.zeros_like(M, dtype=float)
    for off in itertools.product([-1, 0, 1], repeat=M.ndim):
        src, dst = [], []
        ok = True
        for o, dim in zip(off, M.shape):
            if dim == 1 and o != 0:
                ok = False
                break
            if o == 0:
                src.append(slice(None)); dst.append(slice(None))
            elif o == 1:
                src.append(slice(1, None)); dst.append(slice(None, -1))
            else:
                src.append(slice(None, -1)); dst.append(slice(1, None))
        if not ok:
            continue
        acc[tuple(dst)] += M[tuple(src)]
        cnt[tuple(dst)] += 1.0
    return (acc / cnt).ravel()


def pick_plateau(sharpes: np.ndarray, shape: tuple) -> int:
    """Index of the plateau center = argmax of neighborhood-mean Sharpe."""
    return int(np.argmax(neighborhood_score(sharpes, shape)))


def pick_argmax(sharpes: np.ndarray, shape: tuple) -> int:
    """Naive rule, kept ONLY as the control arm for PBO / WF comparison."""
    return int(np.argmax(sharpes))


# --------------------------------------------------------------------------- #
#  2) walk-forward
# --------------------------------------------------------------------------- #
def walk_forward(DR: np.ndarray, years: np.ndarray, shape: tuple,
                 picker=pick_plateau, train_len: int = 4):
    """Rolling windows: train `train_len` years -> pick config -> trade next year.
    Returns stitched OOS daily returns, their day-mask, and per-fold picks."""
    yrs = sorted(set(int(y) for y in years))
    oos_parts, mask_parts, picks = [], [], []
    for i in range(train_len, len(yrs)):
        tr = yrs[i - train_len:i]
        te = yrs[i]
        m_tr = np.isin(years, tr)
        m_te = years == te
        j = picker(sharpe_daily(DR[:, m_tr]), shape)
        oos_parts.append(DR[j, m_te])
        mask_parts.append(m_te)
        picks.append((te, j))
    oos = np.concatenate(oos_parts)
    mask = np.logical_or.reduce(mask_parts)
    return oos, mask, picks


# --------------------------------------------------------------------------- #
#  3) PBO via CSCV (block aggregates -> exact & fast)
# --------------------------------------------------------------------------- #
def cscv_pbo(DR: np.ndarray, S: int = 12, picker=None, shape: tuple = None):
    """Probability of Backtest Overfitting. Default selection = argmax (the
    standard CSCV); pass picker+shape to test a different selection rule."""
    ncfg, n = DR.shape
    edges = np.linspace(0, n, S + 1).astype(int)
    sums = np.stack([DR[:, edges[k]:edges[k + 1]].sum(1) for k in range(S)])       # S x cfg
    sqs = np.stack([(DR[:, edges[k]:edges[k + 1]] ** 2).sum(1) for k in range(S)])
    lens = np.array([edges[k + 1] - edges[k] for k in range(S)], dtype=float)

    def half_sharpe(block_ids):
        s = sums[block_ids].sum(0); q = sqs[block_ids].sum(0); m = lens[block_ids].sum()
        mu = s / m
        var = np.maximum(q / m - mu ** 2, 0.0)
        sd = np.sqrt(var)
        return np.where(sd > 0, mu / np.where(sd == 0, 1, sd) * np.sqrt(252), 0.0)

    omegas = []
    for comb in combinations(range(S), S // 2):
        ins = list(comb)
        outs = [k for k in range(S) if k not in comb]
        sh_in = half_sharpe(ins)
        sh_out = half_sharpe(outs)
        j = picker(sh_in, shape) if picker is not None else int(np.argmax(sh_in))
        omega = np.sum(sh_out <= sh_out[j]) / (ncfg + 1.0)     # relative OOS rank
        omegas.append(omega)
    omegas = np.array(omegas)
    return float((omegas < 0.5).mean()), omegas


# --------------------------------------------------------------------------- #
#  4) verdict
# --------------------------------------------------------------------------- #
def verdict(wf_sharpe: float, pbo: float, noise_wf_sharpes: list) -> dict:
    noise = np.array(noise_wf_sharpes) if len(noise_wf_sharpes) else np.array([0.0])
    noise_hi = float(noise.max())
    ok_wf = wf_sharpe > 0.3
    ok_pbo = pbo < 0.5
    ok_noise = wf_sharpe > noise_hi
    return dict(
        pass_all=bool(ok_wf and ok_pbo and ok_noise),
        wf_sharpe_ok=bool(ok_wf), pbo_ok=bool(ok_pbo), above_noise=bool(ok_noise),
        noise_max_wf_sharpe=round(noise_hi, 3),
        rule="PASS iff WF Sharpe > 0.3 AND PBO < 50% AND WF Sharpe > max(noise WF Sharpe)")
