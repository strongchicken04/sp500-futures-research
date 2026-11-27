# Stage 4.5 protocol — conditional timing, capturable targets, liquid-universe validation

Pre-registered on 2026-11-26, before any Stage 4.5 run. Every change after this point goes into "Amendments" with
date and reason. Changes after results are visible are allowed only if they cannot affect any criterion.

## 0. Status of the data periods (disclosure)
- 2021–2025 were examined extensively in Stages 3–4. They are **not** an untouched test. All 2021–2025 results
  are "historical out-of-sample replication under prior research exposure".
- 2026-01-01 .. 2026-08-27 was also examined in Stages 3–4. It is a separate recent-period diagnostic, not
  independent confirmation.
- Genuine confirmation requires a prospective shadow evaluation on data after 2026-08-27.

## 1. Fixed inputs
- **Panel.** The Stage 4 canonical revised panel (Stage 4 Amendment 1): 6,028,644 rows / 24,426 primary events.
  - Every run must pass the S4 CHECK (exact counts, `mh10 == R`, date order) and an S45 CHECK. The S45 CHECK
    compares the new path outcomes with the Stage 4 outcomes on all rows: A10 = mh10, B5 = c5, B10 = c10,
    M10 = mc10, L10 = ml10.
- **State model.** The frozen Stage 3 full-A RF (SPECS "fullA RF"), never retrained or modified.
  - Rows ≥ 2021-01-01 use the TEST-split refit (trained 2006-02 .. 2020-12-31 minus 60 days). This is the frozen
    Stage 3 model.
  - Rows 2016-11-01 .. 2020-12-31 use the MODEL-split refit (trained 2006-02 .. 2016-12-31 minus 60 days).
  - Why the split: the second-stage model's training rows must have out-of-sample state scores. Any refit is
    in-sample on 2006–2016.
  - Deviation from the brief's suggested development window (2006–2016): explained in §5.
- **Conventions (unchanged):**
  - adjusted ratios for returns and labels; raw close / raw volume for price and liquidity;
  - fill-forward off; segments split at gaps > 10 market sessions; no label crosses a segment;
  - incomplete windows are flagged, never silently made negative.

## 2. Universes and state (fixed)
- **Membership at prediction time t uses only data through the close of t.** Primary rule (trailing median):
  - **S1:** raw close(t) ≥ $1 AND median raw dollar volume of sessions t−19..t ≥ $500k. **Primary.**
  - **S0:** close ≥ $1, median ≥ $100k.
  - **S2:** close ≥ $5, median ≥ $1M.
  - **S5M:** close ≥ $5, median ≥ $5M.
  - **A:** no filter.
- **Sensitivity rule** (Stage 4 style): dollar volume of session t only, instead of the trailing median.
- **State.** The RF score is ranked inside the universe each day (percentile among that day's universe rows).
  - P1 / P5 / P10 = top 1 / 5 / 10 % = the ceil(k · n_day) highest scores.
  - **Primary state: S1-P5.**
- **Recent-move exclusion (ex-ante).** A row is excluded from the timing population if any event move day of
  the same security lies in [t−10, t]. An extreme move has then already started; the exclusion uses past price
  data only. Excluded rows are counted and reported as "in-event / recent-event" rows.

## 3. Events and short-horizon onset labels
- **Move day = the first session of the actual price excursion.**
  - **E1 (primary):** Stage 3/4 E1 episodes of A10/+100 %. Move day τ = min over the episode's positive rows r
    of (r + t100(r)), the first session whose HIGH reaches 2 × the reference OPEN(r+1).
  - **E2:** the same on E2 events.
  - **E3:** the first excursion day: HIGH ≥ 2 × min OPEN of sessions τ−9..τ.
  - **B10 / B-max10:** E1 grouping of the B10/+100 and B-max10/+100 labels. Move day = min over positive rows
    of (r + tc100(r)), the first CLOSE ≥ 2 × reference.
  - Families are never merged.
- **ONSET_k(t), k ∈ {1, 2, 3, 5}:**
  - 1 if some event of the same segment has its move day in sessions t+1..t+k;
  - 0 if not and the window t+1..t+k is complete;
  - −1 (invalid) if t+k is beyond the segment end or the data end;
  - excluded if the recent-move exclusion applies.
  - **Primary target: ONSET_3 with E1.**
- **Event-level counting.**
  - Each event counts once.
  - An event is "eligible" in a population if at least one of its pre-window rows τ−3..τ−1 belongs to the
    conditional population.
  - "All events" = every move day in the period inside the universe; reported as a second denominator.
- **Timing categories (never mixed):**
  - pre-event = a signal in τ−k..τ−1;
  - onset-session = a signal at τ (not credited: the move happens during session τ, before the close
    prediction);
  - during / after = rows excluded by the recent-move rule.

## 4. Second-stage features (all computed from data through close t; QC module `xup_s45_core.py`)
| Group | Features |
|---|---|
| **STATE** (baseline input) | `rf` = RF percentile inside the universe (day t) |
| **VACC** (volatility acceleration) | `atr_p`, `d_atr1`, `d_atr3`, `d_atr5` (ATR/price ratio vs t−k), `rv3`, `rv5_20` (= rv5 / rv20), `range_rel20` (range_p / median range_p of t−20..t−1), `abs_r1` |
| **VOLU** (volume acceleration) | `dv_rel20` (dollar volume / median of t−20..t−1), `vol_rel20` (raw volume / median), `dlogdv1`, `dlogdv3`, `dlogdv5`, `vtrend` |
| **PATH** (compression / path) | `r1`, `r3`, `r5`, `gap`, `intraday`, `clv`, `wick_up`, `wick_lo`, `compress` (median range 5 / median range 20), `dsma20` (close / SMA20 − 1), `dhi20`, `dlo20`, `up_streak`, `dn_streak`, `nbig10` (sessions in t−9..t with range_p > 2 × the prior-60 median), `maxdd10` (min close / running max − 1 over t−9..t) |
| **TRANS** (state persistence / transition) | `rf`, `d_rf1`, `d_rf3`, `d_rf5` (percentile change), `run5` (consecutive sessions in P5 up to t), `enter5` (in P5 at t and not at t−1), `nent250` (entries into P5 over t−249..t), `since_ev` (sessions since the last move day ≤ t, capped at 500), `nev250` (move days in t−249..t) |
| **FULL** | union of all groups |

- **Leakage test (S45FEATURE).** For hash-sampled securities and dates, features at t are recomputed:
  (a) from the full series, (b) from the series truncated at t, (c) with all bars after t replaced by different
  values. All three must be identical (NaN equality included). A failing feature is removed (amendment).
- **State-transition features** use the RF percentile series up to t only. Event-history features use move days
  ≤ t only (price-observable at t).

## 5. Splits, models, hyperparameters (fixed)
- **Training window:** starts 2017-01-01, the first full year whose state scores are out-of-sample (MODEL-split
  RF). This deviates from the brief's 2006–2016 development window: 2006–2016 state scores would be in-sample
  for every available RF refit, a leakage risk for the state feature.
- **Hyperparameter validation:** train 2017-01-01 .. 2019-12-31 minus 60 days, validate on 2020. The choice is
  then frozen for all folds:
  - L2 LR: C ∈ {0.01, 0.1, 1}.
  - Timing RF: min_samples_leaf ∈ {20, 50, 100}, 300 trees, max_features √p, random_state 7, n_jobs 1.
  - Criterion: validation PR-AUC on S1-P5 ONSET_3.
- **Rolling-origin evaluation** (purge / embargo: training rows must end ≥ 60 calendar days before the test
  start, which also covers the 10-session outcome windows):
  - fold a: train 2017 .. 2020-12-31 minus 60 days → evaluate 2021–2022;
  - fold b: train 2017 .. 2022-12-31 minus 60 days → evaluate 2023–2025;
  - fold c: train 2017 .. 2025-12-31 minus 60 days → evaluate 2026 YTD (diagnostic).
  - The pooled 2021–2025 result (a + b) is the primary historical replication.
- **Preprocessing:** winsorise at training p1/p99, median imputation, missing indicators, standardisation, all
  fitted on training rows only (Stage 3 `_prep`).
- **Models (limited set):**
  1. Conditional base rate.
  2. **STATE baseline:** rank by the frozen RF percentile (no fit). This is the critical comparator.
  3. Unregularised LR (C = 1e4) on STATE + one group, for each of VACC, VOLU, PATH, TRANS.
  4. **L2 LR on FULL = the PRIMARY timing model.**
  5. RF on FULL (secondary family).
  6. Leave-one-group-out L2 LR (FULL minus VACC, minus VOLU, minus PATH, minus TRANS), for the C2 robustness
     check.
- **Training population:** S1-P5 rows, not excluded, with a valid ONSET_3 label. The same population definition
  is used per secondary population.

## 6. Signals and metrics
- **Row level** (conditional population, test rows, valid labels):
  - PR-AUC; precision at the pooled top 1 / 5 / 10 % (evaluation only);
  - per-day top 10 % / 25 % precision; lift over the conditional base rate;
  - Brier, log loss, 10-bin calibration.
- **Signal** (primary) = per-day top 10 % (ceil) of the conditional population by the model's score. The state
  baseline uses the RF percentile within the same population.
- **Event level (E1 primary):**
  - pre-event capture = share of eligible events with ≥ 1 signal in τ−3..τ−1;
  - unique events captured; event precision = share of signals followed by a move day within 3 sessions;
  - false signals per captured event; signals per security; first-signal lead (1 / 2 / 3).
- **Placebo:**
  - same security, pre window τ−3..τ−1 vs placebo τ−33..τ−31 (primary);
  - secondary: τ−5..τ−1 vs τ−45..τ−41, and τ−3..τ−1 vs τ−63..τ−61;
  - detection = ≥ 1 signal in the window;
  - each window needs ≥ 1 valid prediction row of the same segment and must lie in the scored period;
  - **membership-matched:** the security must satisfy the S1 membership rule (trailing-median rule, at t) on
    every row of both windows. Matched and unmatched results are both reported, with the number of events lost
    to matching.
- **Bootstrap:**
  - security-cluster Poisson, 2,000 resamples, seed 4501;
  - two-way security × date, 2,000 resamples, seeds 4502 / 4503, for the primary comparisons;
  - event-level metrics resample securities over events.

## 7. Capturable targets (from adjusted OPEN(t+1); daily bars)
- **Family A:** max HIGH, h ∈ {1, 3, 5, 10} × {+50, +100, +200 %}.
- **Family B:** CLOSE(t+h), h ∈ {1, 3, 5, 10} × {+20, +50, +100 %}.
- **Family B-max:** max CLOSE, same grid.
- **Family C:** upside {+20, +30, +50 %} (HIGH) reached BEFORE the adverse limit {−5, −10, −15 %} (LOW),
  h ∈ {1, 3, 5}.
  - Sessions are scanned in order. If both are touched in the same session, the outcome is AMBIGUOUS and never
    a success; on day 1 the open is the entry.
  - Outcomes: success / adverse-first / ambiguous / neither / incomplete.
- **Family D (VWAP):** true VWAP needs minute data for every row, which is infeasible on 1 CPU for millions of
  rows. Only samples are used: the entry-reference audit in S45EXEC. Close-confirmed targets are covered by
  Families B / B-max. No daily-bar approximation is called VWAP.
- **Primary capturable short list (for C4):**
  - CB3_20 (B-max h3 +20 %);
  - CB5_50 (B-max h5 +50 %);
  - FC3_20_10 (C, +20 % before −10 %, h3);
  - **FC5_30_10** (C, +30 % before −10 %, h5; the primary bracket);
  - FC5_50_15.
  - Every other target is secondary. BH at q = 0.05 within each family.

## 8. Downside, liquidity, costs
- **Downside**, per selected group (S1 conditional population; state-baseline signals; timing signals;
  unconditional S1):
  - close-to-entry at t+1 / 2 / 3 / 5 / 10;
  - min LOW at 1 / 2 / 3 / 5 / 10;
  - max favourable excursion; max drawdown within 5 / 10;
  - touch shares of −5 / −10 / −20 / −30 / −50 % within 10 sessions;
  - close shares below −10 / −20 / −30 / −50 % at t+5 / t+10;
  - quantiles; time to the max adverse and max favourable excursion;
  - success vs failure split on FC5_30_10.
- **Liquidity (S45ROBUST):**
  - S0 / S1 / S2 / S5M / A, each under the trailing-median and the same-day rule;
  - a grid of price {1, 2, 5} × median dollar volume {250k, 500k, 1M};
  - a minimum-history variant (≥ 120 sessions in the segment);
  - re-ranking inside each population. No selection.
- **Execution / costs (S45EXEC):**
  - minute quotes on hash samples: S1 timing signals (entry day t+1), S2 timing signals, S1 non-signal
    conditional-population controls, and S1 move days;
  - spread p25 / p50 / p75 / p90, full session and first 30 minutes; coverage;
  - minutes to the first two-sided quote;
  - first-5 / 15-minute VWAP vs open (regular session, from minute trade bars).
- **Round-trip cost scenarios** (formulas frozen now; s30 = median first-30-minute relative quoted spread of the
  S1 timing-signal sample measured in S45EXEC):

  | Scenario | Round-trip cost |
  |---|---|
  | optimistic | 1.0 × s30 + 0.10 % |
  | **neutral** | 2.0 × s30 + 0.50 % |
  | conservative | 3.0 × s30 + 1.50 % |

  The numbers are written into the code (`COST_*`) by an amendment after S45EXEC and before S45OUTCOME.
- **Payoff proxy (NOT a trading simulation):** primary bracket FC5_30_10.
  - +30 % if the target comes first;
  - −10 % if the adverse limit comes first;
  - AMBIGUOUS → −10 % (conservative);
  - neither → close(t+5) return;
  - incomplete → excluded and counted;
  - minus the round-trip cost.

## 9. Pre-registered criteria
- **C1 Integrity:** S4 CHECK and S45 CHECK pass in every primary run; leakage test with 0 mismatches; labels
  validated (onset counts match the event counts); all primary runs automatically VALID.
- **C2 Conditional timing improvement:** in S1-P5, ONSET_3, E1, pooled 2021–25. All four must hold:
  - (a) paired difference in pre-event capture (primary L2 LR minus STATE baseline, per-day top-10 % signals),
    with security-cluster bootstrap 95 % CI > 0;
  - (b) two-way bootstrap CI > 0;
  - (c) point estimate > 0 in both 2021–22 and 2023–25;
  - (d) each leave-one-group-out model still beats the baseline (point estimate > 0).
- **C3 Within-security placebo** (primary L2 LR signals, S1-P5, ONSET_3 windows). All three must hold:
  - pre / placebo ratio ≥ 1.5 AND difference CI lower bound > 0, in the unmatched AND the membership-matched
    analysis (E1);
  - the same holds (ratio ≥ 1.5, CI > 0, matched) for at least one of E2 / E3.
- **C4 Capturable target:** at least one short-list target, in S1-P5 2021–25 with timing signals, satisfies all
  of:
  - (i) precision ≥ 1.5 × the conditional base rate, with a paired CI of (precision − base) > 0;
  - (ii) lift ≥ 1.2 in both 2021–22 and 2023–25;
  - (iii) acceptable adverse:
    - for C targets, P(success first) > P(adverse first + ambiguous);
    - for B-max targets, P(target) > P(min LOW over h ≤ −threshold);
  - (iv) for C targets, ≥ 50 % of successes also reach the threshold on a CLOSE within h.
  - A Family-A-only result cannot pass C4.
- **C5 Downside**, for S1-P5 timing signals in 2021–25. All three must hold:
  - P(B-max h5 ≥ +20 %) > P(min LOW within 5 sessions ≤ −20 %);
  - median close(t+5) return ≥ 0;
  - P(close(t+5) ≤ −30 %) ≤ 5 %.
- **C6 Liquidity:** the C2 and C4 conclusions hold in S1 (primary), and their direction is reproduced in S2 (same
  sign of the C2 point estimate and the C4 lift > 1).
- **C7 Cost:** mean payoff proxy (FC5_30_10, timing signals, S1) under the NEUTRAL scenario has a
  security-bootstrap 95 % CI lower bound > 0. The conservative scenario is reported. Optimistic-only survival
  fails.
- **C8 Robustness:** the C2 direction (point estimate > 0) holds in each of:
  - E2 and E3;
  - 2021–22 and 2023–25;
  - the RF timing family;
  - A-strict;
  - the same-day dollar-volume rule;
  - S2;
  - price buckets $1–5 and ≥ $5.
  - "Not dependent" = at most one of these fails.
- **C9 Statistical integrity:** paired inference, dependence-respecting bootstrap, no test tuning, all
  deviations documented, no INVALID output used.

## 10. Decision mapping (fixed)
- **A:** C1–C9 all PASS.
- **B:** C1, C2, C3, C4, C7 and C9 PASS, but C5, C6 or C8 fails. A restricted simulation is then defensible.
- **C:** C1 and C9 PASS, and C2, C3 or C4 PASS, but the requirements for A / B are not met.
- **D:** C1 or C9 fails, or C2, C3 and C4 all fail. Then neither timing nor a capturable target exists beyond
  the persistent state.

## Amendments

### Amendment 1 (2026-11-26, before any Stage 4.5 QC result was seen) — run-up diagnostic
- **Problem.** With the move-day definition (first session reaching +100 %), a stock that rose, for example,
  +60 % on day t and crosses +100 % on t+1 counts as "pre-event". In substance that is detection of a move
  already under way.
- **Added to S45MODEL (diagnostic and sensitivity, not a new criterion):**
  - (a) the distribution of the run-up at the first signal row of each captured event, defined as
    xr = HIGH(t) / min OPEN(t−9..t) − 1 (Stage 4 path variable, past-only), with the shares ≥ 30 % and ≥ 50 %;
  - (b) a STRICT pre-move sensitivity: the population additionally requires xr(t) < 50 %, the frozen scores are
    re-ranked inside it, and the C2 capture difference is recomputed with its CI.
- **Use:** these results are reported next to C2 and inform the interpretation of "timing". They do not change
  the C2 rule.

### Amendment 2 (2026-11-26, technical; after S45AUDIT v1 died without output, before any Stage 4.5 result was seen)
- **What happened.** S45AUDIT v1 (backtest 1e42cf0b…) finished in QC with no runtime statistic and no log
  line. Even the panel line `P0` is missing, so the process died inside `on_end_of_algorithm`. Most likely cause:
  memory. The QC node (B-MICRO) has 7.8 GB, and the S45 arrays plus per-universe state caches in float64 add
  several GB. The run is kept as INVALID in `results/xup_s45_audit_raw.txt`.
- **Changes (none can affect a criterion):**
  1. S45 arrays (features, path outcomes, Family C codes) are filled only for rows from 2016-06-01. The earliest
     row any Stage 4.5 analysis uses is 2016-11-01. Features at t use only past bars, and outcomes are computed
     from the full series before rows are kept, so stored values are identical.
     - The S45 CHECK compares path outcomes with Stage 4 on those rows (count reported).
  2. Feature matrix stored as float16, values clipped at ±65,000. Model inputs are winsorised at p1/p99 anyway.
     - `dvmed20` (membership) is kept separately in float32.
     - The leakage test compares recomputations in float64 and is unaffected.
  3. Transition / event-history features and timing-model scores are stored as float32. The universe percentile
     `pr` and the frozen RF scores stay float64, so membership in P1/P5/P10 is unchanged.
  4. Caches of non-primary universes are dropped after use. The two frozen RF refits are released after scoring.
  5. Memory checkpoints are logged (`MEM`).
  6. The price × dollar-volume grid and the same-day-rule universes run as a separate mode, S45GRID, so that
     S45ROBUST stays within limits. Content is unchanged from §8.

### Amendment 3 (2026-11-27 ~00:30 UTC) — second QC historical-data revision; canonical Stage 4.5 panel
- **Observation.** S45FEATURE v1 (backtest d315e7fa…) used the same code base, the same fixed-hash sample and the
  same 2,947 securities with data. It built **6,027,629 rows and 24,428 primary events**, against the Stage 4
  canonical 6,028,644 / 24,426.
  - Segments (3,541), `mh10 == R` and date order are unchanged.
  - QC data points processed rose from 84,115,119 (Stage 4) to 84,271,765.
  - As in Stage 4 Amendment 1, this is a revision of QC's historical data, not a code change. Stage 4.5 code
    does not touch the Stage 3/4 row construction; the S45 CHECK compares against Stage 4 arrays of the same build.
- **Seen before this amendment:** the S45FEATURE v1 leakage results (F1 0 mismatches, F2 0 mismatches) and the
  exploratory univariate AUCs (F3).
  - These are exploratory or integrity outputs, not criteria tied to data values.
  - The run is kept as INVALID and repeated as v2.
- **Consequences:**
  1. All Stage 4.5 analyses use the revised panel. The integrity check requires exactly 6,027,629 rows and
     24,428 primary events (plus `mh10 == R`, date order and the S45 CHECK).
     - Set in `xup_s45_core.py` by overriding the Stage 4 constants. The check text still says "S4 canon".
     - A further revision will again invalidate runs instead of passing silently.
  2. An S4DIAG run on the revised data gives the per-year breakdown of the change (documented in results).
  3. Stage 4 results are not changed. Stage 4.5 compares STATE and timing models within the same build, so the
     revision cannot favour either side.
  4. No analysis definition, threshold or criterion changes.

### Amendment 4 (2026-11-27 ~02:00 UTC, after S45MODEL v1; before S45OUTCOME) — exploratory strict pre-move outcome line
- **Trigger.** S45MODEL v1 showed that 71 % of the events captured by the L2 timing model had a run-up of
  ≥ 50 % at the first signal (median 64.8 %). In the strict pre-move population (xr < 50 %), the capture gain
  shrinks from +42.6 pp to +21.0 pp.
- **Addition.** S45OUTCOME gets one exploratory line, X7. It shows the outcomes of L2 signals re-ranked inside the
  strict population: FC5_30_10 precision vs that population's base, CB5_50, median B5, P(L5 ≤ −20 %), and the
  neutral payoff proxy with its CI.
- **Status.** It enters no criterion. C4, C5 and C7 are evaluated exactly as pre-registered. Its purpose is to show
  whether outcomes depend on buying stocks that are already up strongly.

### Amendment 5 (2026-11-27 ~03:00 UTC, technical) — memory and run splitting
- **What happened.** The local polling of S45ROBUST v1 crashed on a network error (RemoteDisconnected). The
  collector then read a stale result file and recorded the run as INVALID, although the QC backtest was still
  running.
  - That line stays in the raw file.
  - The backtest is collected again from the QC API under the label "v1-collected".
- **Changes:**
  - `deploy_long.py` retries transient network errors.
- **Memory:**
  - After the frozen RF scores are computed, the Stage 3 feature matrix keeps only the columns the timing models
    use. The values are identical (synthetic check: MODEL output line-for-line equal).
  - Heap memory is returned to the OS after caches are dropped.
- **Run splitting:** robustness and grid can run as S45ROBUSTA / S45ROBUSTB and S45GRIDA / S45GRIDB (same
  variants, split in two runs). C8 is evaluated over all ten items across the parts.
- No definition, threshold or criterion changes.

### Amendment 6 (2026-11-27 ~04:15 UTC, after S45EXEC v1 and before S45OUTCOME) — cost constants
- **s30.** S45EXEC v1 (backtest 58371170…, VALID; 150 S1 timing-signal entry days, 140 with quotes) gives
  s30 = 0.9479 %.
- **Round-trip costs** from the pre-registered formulas:

  | Scenario | Formula | Cost |
  |---|---|---|
  | optimistic | 1.0 × s30 + 0.10 % | 1.048 % |
  | neutral | 2.0 × s30 + 0.50 % | 2.396 % |
  | conservative | 3.0 × s30 + 1.50 % | 4.344 % |

- **Code.** `S30 = 0.009479` in `xup_s45_core.py`. No formula changes.
