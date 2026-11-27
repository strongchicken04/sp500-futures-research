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
| S45GRIDA | v1 | 7370770f… | VALID | |
| S45EXEC | v1 | 58371170… | VALID | s30 → Amendment 6 |
| S45OUTCOME | v1 | 31a02072… | VALID | after Amendment 6 |
| S45GRIDB | v1 | e94412fb… | VALID | |
| S4DIAG | s45rev2 | b8bb81be… | INVALID by design (Stage 4 count constants) | diagnostic: per-year breakdown of the data revision |

**Data revision breakdown** (S4DIAG s45rev2 vs Stage 4 S4DIAG):
- Rows 2006–2020: identical, year by year.
- Rows 2021–2026 changed:

  | Year | Rows | Change |
  |---|---|---|
  | 2021 | 317,550 → 317,370 | −180 |
  | 2022 | 343,547 → 343,296 | −251 |
  | 2023 | 330,272 → 330,074 | −198 |
  | 2024 | 314,330 → 314,281 | −49 |
  | 2025 | 306,074 → 305,824 | −250 |
  | 2026 | 202,221 → 202,134 | −87 |
  | **Total** | | **−1,015** |

- Primary positives +2 (2022). Securities with rows: −1 each in 2022, 2023 and 2025.
- Same 2,947 securities, same 3,541 segments.
- The revision touches only the test years. All Stage 4.5 comparisons are within one build.

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

## 6. Price × liquidity grid (S45GRIDA v1; capture STATE → L2, Δ [CI], L2 event precision)
| Price | median $vol ≥ 250k | ≥ 500k | ≥ 1M |
|---|---|---|---|
| ≥ $1 | 381 ev: 23.4 → 69.3 %, +45.9 [39.0, 53.1], 8.0 % | 303 ev: 26.7 → 69.3 %, +42.6 [34.0, 49.8], 7.2 % | 243 ev: 32.1 → 73.7 %, +41.6 [32.3, 48.6], 6.7 % |
| ≥ $2 | 334 ev: 32.3 → 71.3 %, +38.9 [31.3, 46.0], 7.6 % | 263 ev: 38.4 → 73.0 %, +34.6 [26.7, 41.5], 6.8 % | 216 ev: 48.6 → 75.9 %, +27.3 [18.0, 37.1], 6.1 % |
| ≥ $5 (S45GRIDB v1) | 197 ev: 62.9 → 78.7 %, +15.7 [8.4, 22.9], 5.6 % | 165 ev: 67.3 → 77.0 %, +9.7 [2.6, 17.6], 5.0 % | 139 ev: 69.8 → 79.9 %, +10.1 [2.4, 19.3], 4.6 % |

Same-day dollar-volume rule (S45GRIDB v1):

| Universe | Eligible / all events | Capture STATE → L2 | Δ [95 % CI] | L2 event precision |
|---|---|---|---|---|
| S0 | 619 / 882 | 21.0 → 65.3 % | +44.3 [38.6, 49.6] | 10.24 % |
| S2 | 217 / 264 | 66.8 → 80.2 % | +13.4 [6.8, 20.4] | 6.48 % |
| S5M | 159 / 184 | 70.4 → 78.6 % | +8.2 [2.0, 15.3] | 5.63 % |

The gain shrinks monotonically with price and liquidity. The STATE capture rises over the same direction.

## 7. Execution (S45EXEC v1; minute data, hash samples, 2021–25)
| Sample | Done / with quotes | Spread p25 / 50 / 75 / 90, full session | First 30 min | First 5 min (p25 / 50 / 75) | VWAP15 / open − 1 (p25 / 50 / 75) | Regular-session $vol median |
|---|---|---|---|---|---|---|
| S1 L2 signals, entry t+1 | 150 / 140 | 0.39 / 0.70 / 1.29 / 2.61 % | 0.58 / **0.95** / 1.99 / 3.65 % | 0.67 / 1.25 / 2.46 % | −1.83 / −0.04 / +1.52 % | $4.9M |
| S2 L2 signals, entry t+1 | 80 / 74 | 0.13 / 0.41 / 1.08 / 2.19 % | 0.27 / 0.72 / 1.85 / 3.60 % | 0.36 / 0.91 / 2.61 % | −0.90 / +0.28 / +1.33 % | $16.1M |
| S1 controls, t+1 | 60 / 54 | 0.49 / 0.66 / 0.92 / 1.13 % | 0.56 / 0.89 / 1.37 / 2.27 % | 0.85 / 1.12 / 2.69 % | −0.81 / +0.21 / +1.15 % | $1.7M |
| S1 E1 move days | 80 / 71 | 0.28 / 0.41 / 0.73 / 1.33 % | 0.34 / 0.57 / 1.13 / 1.98 % | 0.37 / 0.65 / 1.30 % | −0.74 / +1.80 / +5.29 % | $77.5M |

- The first two-sided quote and the first trade arrive in the first minute (median and p90 = 1 minute) in all
  samples.
- First-30-minute dollar volume on S1 signal entry days: median $0.7M, p25 $0.24M. Capacity is limited.
- **s30 = 0.948 %.** Round-trip costs (Amendment 6): optimistic 1.05 %, neutral 2.40 %, conservative 4.34 %.
- **Price buckets** (S1 signals): spread first 30 min, median $1–5 0.79 %, ≥ $5 1.29 %.
- **Coverage:** about 93 % of sampled items have minute quotes (140 / 150, 74 / 80, 54 / 60, 71 / 80).

## 8. Capturable targets, downside, costs — C4, C5, C7 (S45OUTCOME v1)
**Groups** (2021–25):

| Group | Rows | Securities |
|---|---|---|
| G0 unconditional S1 | 1,097,183 | 1,641 |
| G1 S1-P5 population | 49,697 | 743 |
| G2 STATE signals | 5,492 | 361 |
| G3 L2 timing signals | 5,492 | 565 |

All returns are from the adjusted OPEN(t+1); incomplete windows are excluded (G3: 33 of 5,492 for h = 5).

### 8.1 Families (P in G3 / G1 / G2, lift G3 / G1; BH within family)
- **Family A** (max HIGH), 8 / 12 significant:
  - A3_50 4.26 / 1.64 / 4.09 % (×2.60);
  - A5_50 6.87 / 3.22 / 7.29 % (×2.14);
  - A5_100 1.67 / 0.80 / 1.89 %;
  - A10_100 4.08 / 1.94 / 4.06 % (×2.10).
- **Family B** (close at t+h), 11 / 12:
  - B3_20 8.24 / 4.80 / 7.53 %;
  - B5_20 11.08 / 7.78 / 10.33 %;
  - B5_50 2.64 / 1.26 / 2.49 %;
  - B10_100 1.63 / 0.67 / 1.30 %.
- **Family B-max** (max close), 11 / 12:
  - CB3_20 11.20 / 6.01 / 9.83 %;
  - CB5_20 17.11 / 11.10 / 15.65 %;
  - CB5_50 3.74 / 1.73 / 3.57 %;
  - CB10_100 2.72 / 1.12 / 2.53 %.
- **Family C** (upside before adverse), 27 / 27:
  - FC3_20_10 17.35 / 10.60 / 16.65 %;
  - FC5_30_10 12.77 / 7.97 / 12.65 %;
  - FC5_50_15 6.28 / 2.91 / 6.30 %.
- All 1-day targets have P < 7.1 %.
- In every family, the timing signals are ≈ the STATE signals (G3 ≈ G2). The lift over the population is
  1.2–3.8×.

### 8.2 C4 short list (G3 vs G1; security bootstrap 2,000)
| Target | P (G3) | Base (G1) | Lift | CI of P − base (pp) | vs STATE (pp) | Lift 21–22 / 23–25 | Adverse condition | Close confirmation | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| CB3_20 | 11.20 % | 6.01 % | 1.86 | [4.14, 6.16] | +1.37 [0.06, 2.57] | 1.65 / 2.01 | P(L3 ≤ −20 %) 14.22 % > P → fail | — | fail |
| **CB5_50** | **3.74 %** | **1.73 %** | **2.16** | **[1.32, 2.71]** | +0.17 [−0.82, 1.13] | 1.55 / 2.47 | P(L5 ≤ −50 %) 1.52 % < P → ok | — | **PASS** |
| FC3_20_10 | 17.35 % | 10.60 % | 1.64 | [5.57, 7.86] | +0.70 [−1.01, 2.18] | 1.60 / 1.66 | success 17.35 % vs adverse 46.01 % + ambiguous 0.91 % → fail | 58 % | fail |
| FC5_30_10 (primary bracket) | 12.77 % | 7.97 % | 1.60 | [3.61, 5.87]; two-way [3.28, 6.35] | +0.12 [−1.33, 1.53] | 1.44 / 1.72 | 12.77 % vs 57.30 % + 0.38 % → fail | 60 % | fail |
| FC5_50_15 | 6.28 % | 2.91 % | 2.16 | [2.49, 4.26] | −0.01 [−1.16, 1.14] | 1.67 / 2.49 | 6.28 % vs 39.53 % + 0.07 % → fail | 57 % | fail |

- **→ C4 PASS**, on CB5_50 only: a max close ≥ +50 % within 5 sessions, in 3.74 % of 5,492 signals.
- It fails on every adverse-constrained bracket.
- The timing model is not better than the STATE signals on any capturable target (all CIs vs STATE include 0
  except CB3_20).

### 8.3 FC5_30_10 outcome composition (G3)
| Outcome | Rows (of 5,492) | Median price | Median $vol | Median run-up xr | Median close t+10 |
|---|---|---|---|---|---|
| success | 697 | $4.77 | $2.17M | 44 % | +21 % |
| adverse first | 3,128 | $4.47 | $2.33M | 44 % | −14 % |
| ambiguous | 21 | | | 59 % | −3 % |
| neither | 1,613 | | | 42 % | +2 % |
| incomplete | 33 | | | | |

Successes and failures look alike ex ante (same price, liquidity and run-up).

### 8.4 Downside (C5) — distributions per group
| Group | Close t+1 / 3 / 5 / 10 (median) | Close t+5 p10 / p90 | min LOW within 5 / 10 (median) | Touch ≤ −20 / −30 / −50 % within 10 | Close t+10 ≤ −30 / −50 % | Max drawdown within 10 (median) | max HIGH within 10 (median) |
|---|---|---|---|---|---|---|---|
| G0 unconditional S1 | −0.0 / −0.0 / 0.0 / 0.0 % | −7.7 / +7.4 % | −3.5 / −5.0 % | 6 / 2 / 0 % | 0.9 / 0.1 % | −8.7 % | +5.0 % |
| G1 S1-P5 population | −0.7 / −1.5 / −2.2 / −3.7 % | −17.4 / +16.9 % | −9.2 / −13.3 % | 29 / 11 / 2 % | 6.0 / 1.2 % | −21.3 % | +11.6 % |
| G2 STATE signals | −1.2 / −2.6 / −3.8 / −6.1 % | −22.1 / +20.4 % | −11.7 / −16.6 % | 41 / 20 / 4 % | 11.5 / 2.5 % | −27.1 % | +14.8 % |
| **G3 L2 timing signals** | **−0.9 / −2.0 / −3.4 / −5.4 %** | −22.6 / +21.8 % | −12.1 / −17.0 % | **42 / 20 / 4 %** | 10.9 / 2.3 % | −26.8 % | +14.4 % |
| S2 L2 signals | −0.4 / −0.8 / −1.5 / −2.9 % | −19.9 / +18.4 % | −9.7 / −13.8 % | 33 / 14 / 3 % | 7.9 / 1.8 % | −22.1 % | +11.7 % |

**C5** (G3):
- P(max close ≥ +20 % within 5) 17.11 % < P(min LOW ≤ −20 % within 5) 24.97 %;
- median close t+5 −3.38 % (< 0);
- P(close t+5 ≤ −30 %) 4.69 % (≤ 5 %, ok).

**→ C5 FAIL** (two of three conditions fail).

### 8.5 Payoff proxy and costs — C7 (FC5_30_10 bracket per signal row; not a simulation)
| Scenario | Round-trip cost | G3 mean [security CI] | G3 dedup-5 | STATE | Population | 2021–22 / 2023–25 |
|---|---|---|---|---|---|---|
| gross (implied) | 0 | −0.56 % | | −0.85 % | −0.53 % | |
| optimistic | 1.05 % | −1.61 % [−2.17, −1.08] | −1.66 % | −1.90 % | −1.58 % | −2.03 / −1.29 |
| **neutral** | **2.40 %** | **−2.96 % [−3.52, −2.43]**; two-way [−3.69, −2.21] | −3.01 % | −3.25 % | −2.93 % | −3.37 / −2.63 |
| conservative | 4.34 % | −4.91 % [−5.47, −4.38] | −4.96 % | −5.19 % | −4.88 % | −5.32 / −4.58 |

**→ C7 FAIL.** Negative in every scenario and both periods. The timing signals earn the same as the whole
conditional population; even at zero cost the mean is negative.

### 8.6 Family A vs B-max / C (G3)
- A5 ≥ +50 % occurs in 6.87 % of signals.
- Of those hits:
  - 54 % also reach a close ≥ +50 % within 5 sessions (CB5_50 3.74 % overall);
  - 91 % reach +50 % before −15 % (FC5_50_15 6.28 % overall).
- Half of the extreme intraday highs are not held to a close.

### 8.7 Exploratory strict pre-move outcome (Amendment 4, X7; no criterion)
L2 signals re-ranked inside the xr < 50 % population: 5,095 signals, population 45,379.
- FC5_30_10 11.68 % vs 7.71 % (CI of the difference [2.81, 5.20]); CB5_50 3.11 %.
- Median close t+5 −3.54 %; P(L5 ≤ −20 %) 22.5 %.
- Neutral payoff −3.18 % [−3.74, −2.63].

Removing chased run-ups does not change the economics.

### 8.8 S2 (C6 part)
- S2-P5 L2 signals: 4,982 (population 43,136).
- Lifts: CB3_20 ×1.76, CB5_50 ×2.17, FC3_20_10 ×1.70, FC5_30_10 ×1.65, FC5_50_15 ×2.23 (all > 1).
- S2 downside is milder (median close t+5 −1.5 %), but still negative.

## 9. Decision summary
| Criterion | Status |
|---|---|
| C1 | PASS |
| C2 | PASS |
| C3 | PASS |
| C4 | PASS (CB5_50 only) |
| C5 | FAIL |
| C6 | PASS |
| C7 | FAIL |
| C8 | PASS |
| C9 | PASS |

**→ Decision C** (`stage5_decision.md`).
