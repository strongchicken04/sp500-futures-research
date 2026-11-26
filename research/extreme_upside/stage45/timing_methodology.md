# Stage 4.5 — conditional timing methodology

## 1. Two-stage design
1. **State (frozen, not re-estimated).** The Stage 3 full-A RF score. Rows ≥ 2021 use the TEST-split refit;
   rows 2016-11..2020 use the MODEL-split refit, so every training row of stage 2 has an out-of-sample score.
   - The score is ranked each day inside the universe (S1 primary): P1 / P5 / P10.
2. **Timing.** Within the conditional population (S1-P5, not excluded, valid ONSET_3), a second-stage model
   predicts whether the move day falls in the next 3 sessions.

## 2. Features (from data through the close of t)
- **STATE:** `rf`.
- **VACC** (8): volatility acceleration.
- **VOLU** (6): volume acceleration.
- **PATH** (16): compression / path.
- **TRANS** (9): state persistence, entries into P5, event history.

Definitions: protocol §4. Leakage tests in S45FEATURE:
- **F1:** per-security recomputation on truncated and future-replaced series; requires 0 mismatches.
- **F2:** transition and event-history features with all later percentiles randomised and later move days
  removed; requires 0 mismatches.

## 3. Models (limited, pre-registered)
| Model | Role |
|---|---|
| Conditional base rate | reference |
| STATE: rank by `rf` inside the population | **critical comparator** |
| LR (C = 1e4) on STATE + one group (VACC / VOLU / PATH / TRANS) | group contributions |
| **L2 LR on FULL** | **primary timing model** |
| RF on FULL (300 trees) | secondary family |
| L2 LR leave-one-group-out | C2(d) robustness |

- **Hyperparameters:** chosen once (train 2017-01..2019-12 minus 60 days, validate 2020, PR-AUC), then frozen.
  - L2 C ∈ {0.01, 0.1, 1}; RF leaf ∈ {20, 50, 100}.
- **Preprocessing:** Stage 3 `_prep` (winsorise p1/p99, impute medians, missing indicators, standardise; fitted
  on training only).

## 4. Rolling-origin folds (purge ≥ 60 calendar days)
| Fold | Training | Evaluation |
|---|---|---|
| a | 2017-01-01 .. 2020-12-31 − 60 d | 2021–2022 |
| b | 2017-01-01 .. 2022-12-31 − 60 d | 2023–2025 |
| c | 2017-01-01 .. 2025-12-31 − 60 d | 2026 YTD (diagnostic) |

- The pooled a + b result is the primary historical replication.
- It is not an untouched test (protocol §0).

## 5. Signals and comparison (C2)
- **Signal:** the per-day top 10 % (ceil) of the conditional population by score. The same rule applies to STATE
  and to the timing model, so both produce the same number of signals.
- **C2:** paired difference in pre-event capture over the same eligible E1 events, L2_FULL minus STATE.
  - Security-cluster bootstrap (2,000, seed 4501) and two-way security × date (2,000, seeds 4502 / 4503).
  - The point estimate must be > 0 in both periods and for all four LOGO models.
- **Row-level metrics (secondary):** PR-AUC, pooled P@1/5/10 %, per-day top 10 / 25 % precision, lift, Brier,
  log loss, 10-bin calibration.

## 6. Placebo (C3)
- L2_FULL signals; pre-event vs same-security placebo windows (event_definitions §3).
- Detection is ≥ 1 signal in the window, analysed unmatched and membership-matched.
- Pass rule: ratio ≥ 1.5 AND difference CI > 0 (security bootstrap).

## 7. Robustness (C8, S45ROBUST / S45GRID)
- The C2 comparison is repeated, with re-ranking in each population, for:
  - E2 and E3 labels;
  - RF family;
  - A-strict;
  - the same-day dollar-volume rule;
  - S2;
  - price $1–5 and ≥ $5;
  - also reported: P1, P10, S0, S5M, A, history ≥ 120 sessions, and the price × median dollar-volume grid.
- At most one C8 item may have a non-positive point estimate.
