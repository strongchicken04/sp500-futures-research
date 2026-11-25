# Stage 4 — statistical methodology

Code: `xup_s4_modes_d.py` (S4BOOT, S4CALIB), `xup_s4_modes_b.py` (C4/C5), `xup_s4_modes_e.py` (S4CONC).

## Evaluation rows
- **Row-level metrics** (PR-AUC, P@k): Stage 3 definition, i.e. universe A, valid primary labels, S3-rank
  within day. This makes the numbers directly comparable with TEST v1.
- **Periods:** test 2021–2025; sub-periods 2021–22 and 2023–25; 2026 YTD reported separately.

## Bootstrap schemes
- **Security cluster:** Poisson(1) weight per security (fixed seeds) applied to all of its rows or events.
  - 2,000 resamples for the model metrics and paired differences (seed 11).
  - 2,000 for the event-level comparisons and C4/C5 (seeds 11 / 404).
  - 1,000 / 300 for the period-stability metrics (seed 21; 300 for the per-period PR-AUC because of run time).
- **Two-way security × date:** product of independent Poisson weights per security and per trading day,
  1,000 resamples (seeds 12 / 13), for PR-AUC and P@1 % of all models and the main paired differences.
  - It addresses dependence from common market dates (cross-sectional shocks) in addition to within-security
    dependence.
  - Product weights are a standard multiway approximation and are mildly conservative.
- **Date cluster only:** 1,000 resamples (seed 31), used for the calendar-control check (S4CONC).
- **Weighted metrics in each resample:**
  - PR-AUC: weighted average precision on the fixed score order;
  - P@k: weighted share of positives among the fixed selections;
  - capture: weighted share of captured events.
- **CIs:** percentile 2.5 / 97.5 %.
- **p-value:** two-sided, 2 · min(P(Δ ≤ 0), P(Δ ≥ 0)), floor 1/B.

## Paired comparisons
- **Pairs** (same rows / events, same resample weights for both models):
  - RF − volume LR, full-A LR − volume LR, GBM − volume LR;
  - RF / full-A LR / GBM − price LR;
  - RF / full-A LR / GBM − momentum LR.
- **Metrics:** ΔPR-AUC, ΔP@1/5/10 %, Δcapture and Δpre-onset capture at 1 / 5 %, Δevent precision.
- **Overlapping individual CIs are never used for inference.** That rule caused the Stage 3 inconclusive
  verdict; Stage 4 replaces it with paired differences, as the brief asks. The Stage 3 verdict itself is not
  changed retroactively.

## Calibration
- **Metrics:** Brier; log loss; ECE (10 and 20 equal-mass bins); calibration-in-the-large (Σ predicted / Σ
  observed); decile reliability table; top-1 % bin.
- **Drift:** calibration-in-the-large by year, price stratum, dollar-volume stratum, ATR tercile and SPY 20-day
  realised-vol tercile. Tercile cut-offs come from 2006–2020; regime variables use past data only.
- **Monthly link:** correlation of the monthly base rate with the monthly observed / predicted ratio.
- **Frozen calibration experiment** (sensitivity only; the Stage 3 benchmark is unchanged):
  - the MODEL-split RF (trained on 2006–2016 minus 60 days) is scored on validation 2017–2020;
  - Platt scaling (logistic regression on logit p) and isotonic regression are fitted on validation rows only;
  - both are frozen and applied to that model's test and 2026 scores;
  - comparison with the uncalibrated MODEL-split RF and the TEST-refit RF.

## Ranking stability
- **Rank correlations:** Spearman between model scores (pooled; deterministic 300k-row subsample) and the
  correlation of within-day percentile ranks.
- **Top-k overlap:** share of RF selections also selected by each other model.
- **Persistence:** share of selections whose previous session was also selected.
- **Period stability:** security-level mean RF percentile, 2021–22 vs 2023–25 (Spearman).
- **Concentration of the RF advantage:** RF − volume LR PR-AUC after removing the top 1 % / 5 % of securities by
  positive rows, after removing rows below $0.10, and within price < 1 / ≥ 1.

## Concentration and regimes
- **Date concentration:**
  - selections per day;
  - share of positive rows on the top 1 % / 5 % of days;
  - dispersion of daily E1 onsets (variance / mean);
  - observed vs binomial variance of the daily event rate, with an intraclass correlation (ICC) estimate.
- **Security concentration:** share of events and of RF selections from the top 1 / 5 / 10 % of securities.
- **Regimes:** SPY 20-day realised vol, IWM 20-day return and the cross-sectional median r20 of the panel; all
  past-only, with tercile cut-offs from 2006–2020. Per tercile: base rate, events, RF / volume-LR PR-AUC and
  P@1 %.
- **Calendar control:** mean per-day AP (days with ≥ 1 positive), the share of days with RF AP > volume-LR AP,
  and the date-cluster bootstrap CI of the pooled ΔPR-AUC.

## Exploratory vs confirmatory
- **Confirmatory:** only the protocol §9 criteria (C1–C9).
- **Exploratory:** everything else, including all 2026 YTD numbers.
