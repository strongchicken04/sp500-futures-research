# Extreme upside moves — Stage 3 protocol (pre-registered before any Stage 3 result)

Written and committed 2026-11-25, **before** the first Stage 3 panel / baseline / univariate output was seen.
Any later change is recorded in the "Amendments" section with its date and reason. Changes after test-period
results are seen are not allowed.

## 1. Targets (frozen, from the owner brief and Stage 2)
- Prediction time: close of session t. Earliest entry reference: adjusted OPEN(t+1).
- Window: the security's next h sessions (t+1 .. t+h) inside the same data segment. Segments split at gaps
  > 10 market sessions. Fill-forward is off.
- Family A: max adjusted HIGH(t+1..t+h) / adjusted OPEN(t+1) − 1 ≥ threshold.
- Family B: adjusted CLOSE(t+h) / adjusted OPEN(t+1) − 1 ≥ threshold.
- Family B-max: max adjusted CLOSE(t+1..t+h) / adjusted OPEN(t+1) − 1 ≥ threshold. Reported separately.
- Thresholds 50 / 100 / 200 %; horizons 5 / 10 / 20 sessions; 27 targets. Families are never combined.
- **Primary endpoint: Family A, h = 10, +100 %.**
- Incomplete window (segment end, delisting or data end 2026-08-27): label invalid. The row stays in the panel
  and in the denominators of the incomplete-window tables, but is excluded from label-based statistics.
  Stage 2 showed upside counts change < 2 % across delisting assumptions.
- Episodes (descriptive counts only): an episode starts at the first t of a security with a positive label. The
  next episode of that security can start only ≥ h sessions after the previous start. Consecutive positive days
  inside h sessions are merged into the episode.

## 2. Universes (Stage 2 section 11.8, unchanged)
A (main), A-strict, A-ex-ADR, A-fund (sensitivity), B (Morningstar common, snapshot ≤ 40 days),
C (B with float, 2011–), D (A with usable FINRA SI, 2018-01-11 .. 2026-08-27).
- The panel is a fixed-hash sample of securities: md5(QC security id) mod 5 = 0, about 20 % of the securities.
  The same sample is used in every run.
- Every eligible day of every sampled security is in the panel. No selection on outcomes.
- Eligible day: real bar, raw close > 0, ≥ 20 prior sessions in the segment, date 2006-02-01 .. 2026-08-27.

## 3. Periods
- Development: 2006–2016. Validation: 2017–2020. **Final untouched test: 2021–2025.** 2026 YTD reported
  separately.
- Purge / embargo: a training row is dropped if its label window ends after the start of the next period
  (window end date > boundary). An extra embargo of 20 sessions is applied before each boundary.
- Descriptive blocks: 2006–09, 2010–14, 2015–19, 2020–22, 2023–25, 2026 YTD.

## 4. Baseline (Stage 3B)
For each universe × target × block:
- eligible rows, valid labels, positives, rate;
- distinct securities with an event, episodes;
- median / p90 of Family-A returns among events;
- price-stratum shares, incomplete-window share, missing-session share.

## 5. Univariate tests (Stage 3C) — run on 2006–2020 only (test years untouched)
- Deciles: monthly cross-sectional deciles of the variable inside the universe. Ties and missing values are
  kept as a separate "missing" bin and reported.
- Per decile: rows, positives, rate.
- Effect: top vs bottom decile absolute difference, relative risk, odds ratio.
- 95 % CIs: cluster bootstrap over securities, 200 resamples, fixed seed.
- Monotonicity: logistic slope of rate on decile index. Bootstrap CI; Spearman ρ across the 10 deciles.
- Distribution test: Mann-Whitney AUC of the variable for events vs non-events, with the same bootstrap CI.
  Naive U p-values are not used for inference, because rows are dependent.
- p-value: two-sided bootstrap p for the top-vs-bottom log RR. Benjamini–Hochberg q = 0.05 within the
  primary-endpoint family below.
- Variables (pre-specified):

| H | Primary variable | Secondary | Universe | Expected sign |
|---|---|---|---|---|
| H1 | lmcap | lds | B | − |
| H2 | rvol20 | rvol5 | A | + |
| H3 | si_ds | dtc | D | + |
| H4 | lfloat | float_ds | C | − |
| H5 | atr_p | rv20 | A | + |
| H6 | gap | intraday | A | ± (two-sided) |
| H7 | r20 | r5 | A | + |
| H8 | lpx | lpx_prev | A | − |
| H9 | ldv | rdv20 | A | ± (two-sided) |

- Primary BH family: the 18 variables above on the primary endpoint. Secondary endpoints (26 targets) get a
  separate BH family, labelled descriptive.
- H10 (combinations): two-way decile tables lpx × rvol20, r20 × rvol20, atr_p × lpx and, on B,
  lmcap × rvol20. The formal test is in the model stage: additive logistic model vs gradient boosting
  (interactions) on the validation period.
- A coefficient or p-value alone is never called support. A hypothesis has evidence only if all of these hold:
  BH-significant, sign as expected or the two-sided effect meaningful, consistent in ≥ 4 of 5 descriptive
  blocks, and the effect replicates in the untouched test period (Stage 3G).

## 6. Models (Stage 3D–F) — draft, frozen after the univariate review (amendment logged)
- Models: logistic regression (unregularised, small feature sets); L2 logistic (C on a 4-point grid
  chosen on validation); random forest (300 trees, min_samples_leaf 200, max_features √p, balanced
  subsample); histogram gradient boosting (learning rate 0.05, max_leaf_nodes 31, early stopping on an internal
  time-ordered 10 % holdout of the training years, l2 0.1).
- Training subsample: all positives plus a fixed-seed 10 % of negatives, weighted back to the population
  (memory / 1 CPU). Evaluation always uses the full, unsampled validation or test rows.
- Missing values: median imputation from the training period plus a missing indicator for each group (B, C, D).
- Baselines: unconditional rate; price-only (lpx, pstrat); momentum-only (r1..r20, dhi*, dlo*, streaks);
  volume-only (lvol, rvol*, ldv, rdv20, vtrend).
- Feature groups: price + momentum; price + volume; price + volatility; mcap + price + volume (B); full
  price / volume (A); full + fundamentals (B); full + short interest (D, 2018–); full + float (C, partial).
- Metrics, each with the event count:
  - PR-AUC (primary);
  - precision and recall at top 1 / 5 / 10 % (ranked within each day, pooled);
  - lift vs the unconditional rate;
  - Brier score; calibration (deciles of predicted probability, observed vs predicted);
  - ROC-AUC (secondary).
- CIs: cluster bootstrap by security, 200 resamples.
- Selection on validation only. The final specification is frozen in an amendment before the TEST run. TEST
  is run once: refit on 2006–2020 with purge / embargo, evaluate on 2021–2025, report 2026 YTD separately.

## 7. Tradability (reported, not optimised)
For the top-ranked 1 % of test predictions:
- raw price, dollar volume, price strata;
- missing-session / zero-volume flags; halt proxy (missing sessions);
- share of family-A events not confirmed by family B / B-max;
- share driven by an intraday high more than 2× above the close.
No trading-profit claim from family A.

## Amendments
(none yet)

### Amendment 1 (2026-11-25, before any Stage 3 result was seen)
- Block consistency for the univariate stage uses the four descriptive blocks inside 2006–2020: 2006–09,
  2010–14, 2015–19 and 2020 alone. The untouched 2021–2025 replication is the fifth check, run in Stage 3G.
- The Mann-Whitney AUC bootstrap uses 60 cluster resamples, for compute reasons on 1 CPU. The relative-risk,
  odds-ratio and slope CIs keep 200.
- The panel's market-cap snapshots are weekly. The universe pass is weekly, so a security that lived less
  than one week can be missed.

### Amendment 2 (2026-11-25, after the univariate results on 2006–2020, before any model result was seen)
Model implementation, fixed here before the first MODEL run (smoke runs included):
- **Random forest:** 200 trees, min_samples_leaf 200, max_features √p, max_samples 0.5, no class balancing.
  The draft said 300 trees and a balanced subsample; changed for compute on 1 CPU. The training subsample is
  already weighted back to the population.
- **Gradient boosting:** HistGradientBoosting with learning rate 0.05, max_leaf_nodes 31, l2 0.1. The number of
  trees (25 to 500, in steps of 25) is chosen on the last 10 % of the training rows by date, by weighted log loss,
  stopping after 3 steps without improvement. The model is then refit on all training rows. Missing values are
  handled natively.
- **L2 logistic:** C ∈ {0.001, 0.01, 0.1, 1}, chosen on validation PR-AUC. TEST uses that C, fixed (L2_C_FROZEN).
- **Unregularised LR:** C = 1e4. Inputs are winsorised at the training p1/p99, median-imputed, given missing
  indicators and standardised.
- **Purge / embargo:** training ends 60 calendar days (≈ 41 sessions) before the next period. That is ≥ the
  maximum horizon (20) plus the 20-session embargo.
- **Splits:**
  - A and B: development 2006-02..2016 / validation 2017–2020.
  - C (float from 2011): development 2011–2016 / validation 2017–2020.
  - D (SI from 2018-01-11): development 2018-01-11..2019 / validation 2020 only. D therefore has a much
    shorter history; this is a known limitation.
- **CIs:** model-metric CIs use 60 Poisson cluster-bootstrap resamples by security (2026 YTD: 30) instead of 200,
  for compute reasons.
- **Secondary endpoints:** the full-A GBM is refit for A5/+50, A20/+200, B10/+100, B-max10/+100 and A10/+50,
  and reported descriptively.
- **H10 formal test:** validation PR-AUC of full-A GBM minus full-A LR, with a cluster-bootstrap CI.

**Pre-committed rule for the TEST run (decided now, before MODEL results):**
- **FROZEN = all specifications that run without error in MODEL.** Every one is refit on the full development +
  validation window and evaluated once on 2021–2025, so no model is selected on test results.
- **"Best model":** the specification with the highest validation PR-AUC within universe A. It is named in
  Amendment 3 before TEST.
- **Model evidence:** a model is described as having predictive value beyond simple baselines only if its test
  PR-AUC CI lies above the CI of the best single-group baseline (price-only, momentum-only or volume-only LR).
- **Univariate replication:** the 18 univariate variables are replicated on 2021–2025 with identical code
  (`_univ_rep`), with no selection.
- No retuning after TEST. 2026 YTD is reported separately and never used for selection.
