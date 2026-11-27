# Stage 4.5 — feature audit (S45FEATURE v2, VALID)

Source: `results/xup_s45_feature_raw.txt`, run "S45FEATURE v2" (backtest f1cb45e5…).
- S4 CHECK OK: 6,027,629 rows, 24,428 primary events.
- S45 CHECK OK: 3,094,930 rows ≥ 2016-06, 0 mismatches.
- v1 (INVALID, previous count constants only) gave identical F1–F4 lines.

## 1. Leakage tests (C1 component)
| Test | Design | Result |
|---|---|---|
| F1 per-security recomputation | 25 hash-sampled securities (≥ 500 rows) × 3 hash-sampled dates = 75 (security, t) cases. All 19 new features at t are recomputed from (a) the full series, (b) the series truncated at t, (c) the series with every bar after t multiplied by random factors 0.3–3. Comparison with NaN equality and relative tolerance 1e-9 | **0 mismatches** (0 fetch failures) |
| F2 state / event history | For 2 cut dates (2022-06-30, 2024-03-29): every universe percentile after the cut is replaced by a random number and every later move day removed. The 7 transition features and 2 event-history features are recomputed on rows ≤ cut | **0 mismatches** on 1,092,896 row checks |

- The Stage 3/4 features reused in the FULL set were audited in Stages 3–4 and are unchanged.
- No feature had to be removed.

## 2. Coverage (F4; % finite, S1-P5 training / test rows)
- All features 100 / 100, except:
  - `vtrend` 98 / 99;
  - `nbig10` 97 / 96;
  - `d_rf1` 98 / 98, `d_rf3` 96 / 95, `d_rf5` 94 / 93 (need a scored row k sessions earlier).
- Missing values are median-imputed with missing indicators (`_prep`).

## 3. Exploratory univariate association (F3; training window only, not used for selection)
- **Setup:** S1-P5 ONSET_3 training rows 2017-01-01 .. 2020-12-31 − 60 d: 36,262 rows, 335 positives (0.92 %).
- **Statistic:** AUC of each feature, with a security-bootstrap CI (300 resamples) and BH across 39 features.
- **Result:** **32 of 39 features have q < 0.05.**

Strongest (AUC; > 0.5 means higher values before onset):

| Feature | AUC [95 % CI] | Reading |
|---|---|---|
| `dlo20` (close vs 20-day low) | 0.814 [0.775, 0.851] | already far above the recent low |
| `rv3` | 0.729 [0.689, 0.767] | short-term volatility up |
| `abs_r1` | 0.729 [0.696, 0.758] | large last-day move |
| `r1` / `r3` | 0.710 / 0.710 | positive recent returns |
| `atr_p` | 0.707 [0.670, 0.747] | high ATR / price |
| `intraday`, `up_streak` | 0.701 / 0.701 | up-days, closes near highs |
| `rf` (state percentile) | 0.639 [0.600, 0.681] | the state rank still matters inside P5 |
| `dn_streak` | 0.381 | no down streak |
| `nent250` | 0.387 | fewer past entries into P5 |
| `d_atr1` | 0.390 | ATR ratio vs t−1 lower |

Not significant: `wick_up`, `dhi20`, `d_atr5`, `d_rf1`, `d_rf3`, `run5`, `enter5`.

**Interpretation (pre-results warning).**
- The strongest univariate signals are run-up variables: distance from the 20-day low, recent returns, up
  streaks.
- A timing model will lean on "the move has started"; for that reason Amendment 1 added the run-up diagnostic and
  the strict pre-move sensitivity.
- The state-transition features (d_rf, run5, enter5) carry almost no univariate information.
