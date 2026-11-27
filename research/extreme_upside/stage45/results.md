# Stage 4.5 — results

All numbers come from the VALID QC runs listed in §0 (aggregates only; raw outputs in `results/xup_s45_*_raw.txt`).
- Test period 2021-01-01 .. 2025-12-31 (folds a + b): historical replication under prior research exposure, not an
  untouched test.
- 2026-01-01 .. 2026-08-27: recent-period diagnostic (fold c).

## 0. Runs
| Mode | Label | Backtest | Verdict | Notes |
|---|---|---|---|---|
| S45AUDIT | v1 | 1e42cf0b… | INVALID | died without output (memory) → Amendment 2 |
| S45FEATURE | v1 | d315e7fa… | INVALID | second QC data revision (6,027,629 rows / 24,428 events) → Amendment 3 |
| S45AUDIT | v2 | 8e5b9923… | VALID | |
| S45FEATURE | v2 | f1cb45e5… | VALID | |
| S45MODEL | v1 | 391a593b… | VALID | |
| S45PLACEBO | v1 | bcf56d59… | VALID | |
| S45ROBUST | v1 | 1d936103… | INVALID → v1-collected VALID | local polling crashed (network); collected from the QC API (Amendment 5) |
<!--RUNS-->

Every VALID run:
- S4 CHECK OK: 6,027,629 rows, 24,428 primary events, `mh10 == R`, date order;
- S45 CHECK OK: 3,094,930 rows ≥ 2016-06, path outcomes identical to Stage 4.

## 1. Events, labels, populations (S45AUDIT v2)
**Move days.** "Rows ≥ 2016-11" are the ONSET_3 rows.

| Definition | Events 2017–20 | 2021–25 | 2026 YTD | ONSET_3 positives / 0 / invalid / excluded (rows ≥ 2016-11) |
|---|---|---|---|---|
| E1 | 808 | 1,539 | 299 | 7,187 / 2,933,324 / 7,057 / 27,792 |
| E2 | 719 | 1,337 | 248 | 6,961 / 2,935,964 / 7,074 / 25,361 |
| E3 | 740 | 1,389 | 257 | 7,155 / 2,935,147 / 6,985 / 26,073 |
| B10 | 338 | 711 | 147 | 3,472 / 2,951,787 / 7,117 / 12,984 |
| B-max10 | 422 | 862 | 181 | — |

- **Label validation:** move days = E1 episodes (4,216 = 4,216), with no same-day duplicates.
- **Lead from first label row to move day** (p10 / 50 / 90): 2 / 10 / 10 sessions. Stage 4 label episodes
  started up to 10 sessions before the actual excursion.

**Primary population S1-P5** (trailing-median rule; valid ONSET_3 rows, not excluded):

| Period | Rows | Securities | Positives | Base | Eligible E1 events / all S1 move days | Rows/day | Excluded (recent move) |
|---|---|---|---|---|---|---|---|
| train 2017–20 (−60 d) | 36,262 | 633 | 335 | 0.92 % | 135 / 219 | 37.6 | 2,396 |
| validation 2020 | 8,729 | 342 | 237 | 2.72 % | 97 / 168 | 34.5 | 1,557 |
| 2021–22 | 21,744 | 497 | 250 | 1.15 % | 109 / 170 | 43.2 | 2,091 |
| 2023–25 | 27,907 | 543 | 490 | 1.76 % | 194 / 243 | 37.1 | 3,669 |
| 2026 YTD | 6,179 | 302 | 147 | 2.38 % | 57 / 73 | 37.7 | 969 |

**Pooled test 2021–25:** 49,651 rows, 740 positives, base 1.49 %; 303 eligible of 413 S1 move days; 738 securities.

**Universe sizes** (median rows per day, test):

| Universe | trailing | same-day |
|---|---|---|
| S0 | 1,015 | 1,023 |
| S1 | 849 | 869 |
| S2 | 696 | 710 |
| S5M | 549 | 556 |
| A | 1,273 | 1,273 |

**Other populations** (test 2021–22 | 2023–25, base rate and eligible / all events):

| Population | 2021–22 | 2023–25 |
|---|---|---|
| S1-P1 | 1.82 %, 40 / 170 | 2.74 %, 75 / 243 |
| S1-P10 | 0.73 %, 128 / 170 | 0.98 %, 210 / 243 |
| S2-P5 | 0.59 %, 47 / 68 | 1.00 %, 92 / 111 |
| S0-P5 | 1.46 %, 162 / 248 | 2.35 %, 317 / 460 |
| S5M-P5 | 0.39 %, 24 / 33 | 0.66 %, 50 / 62 |
| A-P5 | 2.00 %, 240 / 400 | 3.16 %, 502 / 1,139 |
| S1-P5 same-day | 1.56 %, 163 / 223 | 2.89 %, 373 / 455 |

## 2. Features (S45FEATURE v2)
- **Leakage tests:**
  - F1: 0 mismatches in 75 (security, t) cases × 2 perturbations;
  - F2: 0 mismatches in 1,092,896 row checks.
- **Coverage:** ≥ 93 % for all features.
- **Exploratory univariate:** 32 / 39 features significant (BH). The strongest are run-up variables: `dlo20` AUC
  0.81, `rv3` 0.73, `abs_r1` 0.73, `r1` / `r3` 0.71. Details in `feature_audit.md`.

## 3. Conditional timing — C2 (S45MODEL v1)
**Hyperparameters** (train 2017–19, validate 2020): L2 C = 0.01 (validation PR-AUC 0.198 vs 0.166 / 0.152);
RF leaf = 100 (0.174; 20 → 0.173, 50 → 0.172).

**Row level, S1-P5 2021–25** (49,651 rows, base 1.49 %; per-day top 10 % = 5,492 signals for every model):

| Model | PR-AUC | Pooled P@1 / 5 / 10 % | Per-day top-10 % precision | Lift | Pre-event capture (of 303) |
|---|---|---|---|---|---|
| STATE (frozen RF rank) | 0.024 | 3.4 / 3.4 / 2.5 % | 2.68 % | 1.80 | 26.7 % (81) |
| LR STATE+VACC | 0.059 | 14.3 / 7.4 / 5.5 % | 4.72 % | 3.16 | 63.4 % (192) |
| LR STATE+VOLU | 0.080 | 17.3 / 9.7 / 6.9 % | 5.54 % | 3.71 | 62.7 % (190) |
| LR STATE+PATH | 0.131 | 24.1 / 13.5 / 8.5 % | 6.92 % | 4.64 | 66.3 % (201) |
| LR TRANS | 0.028 | 4.4 / 3.6 / 3.3 % | 2.75 % | 1.84 | 26.7 % (81) |
| **L2 FULL (primary)** | **0.141** | **24.3 / 13.5 / 8.9 %** | **7.19 %** | **4.83** | **69.3 % (210)** |
| RF FULL | 0.165 | 29.4 / 14.1 / 9.1 % | 7.43 % | 4.98 | 71.0 % (215) |
| L2 −VACC / −VOLU / −PATH / −TRANS | 0.146 / 0.138 / 0.082 / 0.136 | — | 7.14 / 6.94 / 5.92 / 7.14 % | — | 69.0 / 68.0 / 69.0 / 68.6 % |

**C2.** L2 FULL − STATE pre-event capture (303 eligible E1 events):
- **+42.6 pp** (69.3 % vs 26.7 %);
- security bootstrap [34.5, 49.8], two-way [28.6, 54.9], p = 0.0005;
- 2021–22 +31.2 pp, 2023–25 +49.0 pp;
- LOGO vs STATE: VACC +42.2, VOLU +41.3, PATH +42.2, TRANS +41.9.

**→ C2 PASS.**

Other comparisons:
- **PR-AUC difference L2 − STATE:** +0.118 [0.094, 0.146].
- **L2 vs other models (capture):**
  - RF −1.7 [−5.6, 2.4];
  - LR VACC +5.9 [−0.7, 12.4];
  - LR VOLU +6.6 [0.3, 12.9];
  - LR PATH +3.0 [−1.0, 6.9].

  The PATH group carries most of the gain; dropping PATH halves PR-AUC.
- **Event level:**

  | Model | Captured | Of all 413 S1 move days | Event precision | False signals per captured event | First-signal lead 1 / 2 / 3 |
  |---|---|---|---|---|---|
  | L2 | 210 | 50.8 % | 7.19 % | 24.3 | 66 / 49 / 95 |
  | STATE | 81 | 19.6 % | 2.68 % | 66.0 | — |

- **Calibration** (L2 deciles, predicted / observed %): 0.09 / 0.06 … 2.00 / 1.91, 8.48 / 8.94. Well
  calibrated.
- **Other horizons** (capture L2 vs STATE):

  | Horizon | L2 | STATE | Difference | Events |
  |---|---|---|---|---|
  | ONSET_1 | 66.3 % | 19.4 % | +46.9 pp [38.7, 54.2] | 273 |
  | ONSET_2 | 70.9 % | 23.0 % | +47.9 pp | 282 |
  | ONSET_5 | 69.4 % | 29.6 % | +39.8 pp | 324 |

- **2026 YTD (fold c)** (6,179 rows, 147 positives):

  | Model | PR-AUC | Capture | P10 |
  |---|---|---|---|
  | L2 | 0.242 | 46 / 57 | 12.2 % |
  | STATE | 0.043 | 16 / 57 | 5.3 % |

**Run-up diagnostic (Amendment 1)** — the decisive qualification:
- At the first L2 signal before a captured event, the stock is already far above its 10-session low open:
  - xr p25 / 50 / 75 = 46 / 65 / 82 %;
  - **92 % have xr ≥ 30 % and 71 % have xr ≥ 50 %.**
- For STATE signals: median xr 39 %, 42 % ≥ 50 %.
- **Strict pre-move** population (xr < 50 % at t, re-ranked; 176 eligible events):
  - capture L2 48.3 % vs STATE 27.3 %, **+21.0 pp [11.0, 31.1]**;
  - event precision L2 2.26 % vs STATE 1.71 %.
- **Interpretation.** Most of the timing gain is detection of a move that is already under way (E1 counts the move
  day as the first +100 % high). A smaller but significant gain remains before a large run-up, at very low
  precision.

## 4. Within-security placebo — C3 (S45PLACEBO v1)
L2 FULL signals; detection in τ−3..τ−1 vs τ−33..τ−31. "Matched" = S1 member on every row of both windows.

| Events | Unmatched (n, pre / placebo, Δ [CI], ratio) | Matched |
|---|---|---|
| **E1** | 225: 54.2 / 12.4 %, +41.8 [34.1, 49.5], 4.36 | **212: 55.2 / 12.7 %, +42.5 [34.4, 50.9], 4.33** |
| E2 | 194: 56.7 / 10.3 %, +46.4, 5.50 | 186: 56.5 / 10.8 %, +45.7 [37.9, 54.2], 5.25 |
| E3 | 198: 56.1 / 11.1 %, +44.9, 5.05 | 187: 56.7 / 11.2 %, +45.5 [37.6, 53.9], 5.05 |
| B10 | 133: 44.4 / 10.5 %, 4.21 | 128: 44.5 / 10.9 %, 4.07 |
| B-max10 | 160: 46.2 / 11.9 %, 3.89 | 153: 47.1 / 11.8 %, 4.00 |

- **E1 secondary windows (matched):**
  - 1–5 vs 41–45: 56.2 / 17.3 %, ratio 3.25;
  - 1–3 vs 61–63: 55.5 / 9.8 %, ratio 5.65.
- **RF FULL:** the same picture (matched ratio 4.37).
- **STATE (comparison):** matched E1 12.7 / 7.1 %, ratio 1.80, Δ +5.7 [0.5, 10.7].
- Matching removed 13 of 225 E1 events.

**→ C3 PASS.** The membership-matched contrast is as strong as the unmatched one. The Stage 4 liquid-segment lead
was not a membership artefact for the timing model. But the same run-up qualification applies: the pre-window
contains the start of the price excursion; the placebo window does not.

## 5. Robustness and liquidity — C8, C6 part (S45ROBUST v1)
Each population is re-ranked; models are retrained on its own training rows. Signals are the per-day top 10 % of
the population; capture is over its eligible test events (2021–25). Security bootstrap 1,000.

| Population | Rows / pos / base | Eligible / all events | Capture STATE → L2 | Δ [95 % CI] | Event precision STATE → L2 | Median price STATE / L2 |
|---|---|---|---|---|---|---|
| **S1-P5 (reference)** | 49,651 / 740 / 1.49 % | 303 / 413 | 26.7 → 69.3 % | **+42.6 [34.2, 49.8]** | 2.68 → 7.19 % | $1.91 / $4.58 |
| S1-P1 | 9,207 / 215 / 2.34 % | 115 / 413 | 28.7 → 62.6 % | +33.9 [22.2, 46.3] | 4.12 → 8.23 % | $1.74 / $2.12 |
| S1-P10 | 103,975 / 904 / 0.87 % | 338 / 413 | 41.7 → 73.7 % | +32.0 [24.8, 38.2] | 2.44 → 4.71 % | $1.98 / $5.30 |
| E2 labels | 50,578 / 681 / 1.35 % | 275 / 339 | 24.7 → 66.2 % | +41.5 [32.8, 49.2] | 2.29 → 5.76 % | |
| E3 labels | 50,386 / 692 / 1.37 % | 281 / 346 | 24.9 → 65.5 % | +40.6 [32.1, 48.4] | 2.29 → 5.97 % | |
| RF timing family | 49,651 / 740 / 1.49 % | 303 / 413 | 26.7 → 71.0 % | +44.2 [36.4, 51.7] | 2.68 → 7.43 % | $1.91 / $5.04 |
| S1 A-strict | 44,936 / 672 / 1.50 % | 274 / 367 | 27.0 → 69.7 % | +42.7 [33.8, 50.2] | 2.81 → 6.96 % | |
| S1 history ≥ 120 | 48,390 / 678 / 1.40 % | 277 / 369 | 31.0 → 70.8 % | +39.7 [30.8, 47.3] | 2.75 → 6.92 % | |
| S1 price $1–5 | 5,356 / 122 / 2.28 % | 66 / 196 | 40.9 → 68.2 % | +27.3 [11.8, 41.6] | 3.67 → 5.35 % | $1.67 / $1.79 |
| S1 price ≥ $5 | 45,981 / 405 / 0.88 % | 165 / 217 | 67.3 → 77.0 % | +9.7 [2.5, 17.4] | 3.81 → 4.97 % | $8.71 / $10.81 |
| S1 same-day $vol rule | 47,464 / 1,086 / 2.29 % | 537 / 678 | 27.2 → 69.6 % | +42.5 [36.4, 47.9] | 4.10 → 11.17 % | |
| **S2-P5** | 43,101 / 354 / 0.82 % | 139 / 179 | 69.8 → 79.9 % | **+10.1 [2.1, 19.3]** | 3.73 → 4.60 % | $9.06 / $11.46 |
| S0-P5 | 57,227 / 1,119 / 1.96 % | 479 / 708 | 21.3 → 67.2 % | +45.9 [39.4, 52.0] | 3.16 → 8.70 % | $1.77 / $3.22 |
| S5M-P5 | 33,713 / 185 / 0.55 % | 74 / 95 | 70.3 → 77.0 % | +6.8 [−3.3, 16.9] | 2.70 → 3.39 % | $10.97 / $14.99 |
| A-P5 | 70,938 / 1,891 / 2.67 % | 744 / 1,539 | 23.3 → 51.5 % | +28.2 [23.4, 32.9] | 4.70 → 8.51 % | $0.37 / $0.75 |

**C8 items** (C2 point estimate > 0), all 10 positive:

| Item | Δ (pp) |
|---|---|
| E2 | +41.5 |
| E3 | +40.6 |
| 2021–22 | +31.2 |
| 2023–25 | +49.0 |
| RF | +44.2 |
| A-strict | +42.7 |
| same-day rule | +42.5 |
| S2 | +10.1 |
| price $1–5 | +27.3 |
| price ≥ $5 | +9.7 |

**→ C8 PASS.** C6 part: the S2 direction of C2 is reproduced (+10.1 pp).

**Reading.**
- In liquid / higher-priced names (S2, S5M, price ≥ $5), the frozen state alone already captures about 70 % of
  the eligible events. The timing gain shrinks to about +7–10 pp, at event precision 3.4–5.0 %.
- The large S1 gain comes from sub-$5 names, where the state ranking points elsewhere and the move-in-progress
  features dominate.
- Turnover of L2 signals is about 50 % per day (STATE about 26 %). There are 4.4 signals per day in S1-P5.
<!--MORE-->
