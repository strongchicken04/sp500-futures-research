# Stage 4.6: results (H-next intraday continuation confirmation)

All numbers are aggregates from VALID QC runs. Raw outputs are in `results/xup_s46_*_raw.txt`.
- **Protocol:** `protocol.md`, commit 2e229f8, pre-registered before any intraday outcome. Amendments 1–2 are
  technical: the canonical panel after a QC data revision, and a quote-normalization defect fix.
- **Status of 2021–25:** historical replication, not untouched out-of-sample data.

## 1. Executive summary
**Decision: B — H-NEXT NOT SUPPORTED. Do not proceed to Stage 5 or to an execution study.**

| Claim | Verdict | Evidence (L2, S1-P5, 2021–25) |
|---|---|---|
| Detecting a continuation | yes, partly | The trigger fires on 859 of 5,497 L2 signals (15.6 %) vs 320 of 5,497 STATE signals (5.8 %). Triggered L2 signals reach an E1 move day within 3 sessions in 162 / 857 cases (18.9 %), vs 7.2 % for all L2 signals at the next open (Stage 4.5) |
| Obtaining a better entry | no | The triggered subset entered at the next open earns −1.02 % (neutral). Entered at the trigger it earns −3.13 %. The confirmation costs about 2.1 pp; the entry is a median 4.6 % above the prior close |
| Positive gross payoff | no | gross −0.73 % per trade (n 857) |
| Positive net payoff | no | neutral −3.13 % [−4.21, −2.12], two-way [−4.91, −1.35]; optimistic −1.78 %; conservative −5.07 % |
| Robust trading strategy | no | negative in every period, leave-one-year-out, security group and sensitivity variant |

The −10 % limit is hit before +30 % in 60.0 % of triggered trades; +30 % comes first in 12.1 %.

## 2. Decision
**B — H-next not supported.**
- Gate:

  | G1 | G2 | G3 | G4 | G5 | G6 | G7 |
  |---|---|---|---|---|---|---|
  | FAIL | FAIL | PASS | FAIL | FAIL | FAIL | PASS |

- Also fails: adverse first (60.0 %) > target first + neither (40.0 %). Reasons in §18.

## 3. Data and model integrity
- **Canonical panel** (Amendment 1, after the third QC data revision): 6,030,760 rows / 24,429 primary events / 3,543
  segments. 2,989 sample securities, 2,949 with data.
  - Identical in S46AUDIT v1 and v2, S46DIAG v1 and S46MAIN v2.
  - S4, S45 and S46 CHECK OK in every VALID run: S45 CHECK 3,098,061 rows; raw close vs panel price 0 mismatches.
- **Frozen models:** L2 C = 0.01 (unchanged). L2 / STATE / VOLU signals 5,497 each (S4.5 5,492). S1-P5 population
  49,802 rows (S4.5 49,697).
- **Stage 4.5 baseline reproduced on the new panel (M0b):**

  | Metric | Stage 4.6 panel | Stage 4.5 |
  |---|---|---|
  | C2 capture, L2 vs STATE | 69.9 % vs 25.5 % of 302 eligible events | 69.3 / 26.7 % of 303 |
  | Next-open neutral payoff, L2 | −2.91 % | −2.96 % |
  | L2 event precision | 7.19 % | 7.19 % |

- **Signal timing:** scores use data through the close of t; the trigger uses t+1 minute bars only after completion.
  Leakage tests of Stage 4.5 apply unchanged.
- **Implementation defect found and fixed** (Amendment 2):
  - QuoteBars had been requested in QC's default ADJUSTED normalization. 22 % of sampled sessions had quote mids
    more than 10 % away from the RAW trades (up to 20×).
  - S46MAIN v1 and S46ROBUST v1 are INVALID, kept and not used.
  - After the fix, the quote-mid vs trade discrepancy is at most about 1 %.

## 4. Minute-data coverage (S46MAIN v2, all signals; S46AUDIT v2 samples)
| Group | Eligible | Regular-session minute bars on t+1 | Coverage |
|---|---|---|---|
| L2 | 5,497 | 4,953 | 90.1 % |
| STATE | 5,497 | 4,838 | 88.0 % |
| VOLU | 5,497 | 4,947 | 90.0 % |
| CONTROL | 5,497 | 5,024 | 91.4 % |

- Quotes:
  - present on every audited session with trades;
  - valid bid / ask on 100 % of audited quote bars;
  - sizes on 92–93 %.
- Bar labels are end times (09:31..16:00; shift 0).
- The day-t minute high equals the daily high (|diff| < 4·10⁻⁶ %).
- Sessions without minute bars are counted as "no trade".

## 5. Trigger logic and entry reconstruction (as pre-registered)
- **Reference:** H_t = raw daily high of t.
- **Breakout:** the first completed regular-session minute bar with HIGH > H_t.
- **Volume:** the first bar end at which cumulative Σ close × volume ≥ $1M.
- **Confirmation:** m* = the later of the two; trigger if m* ≤ 10:00.
- **Entry:**
  - the ask at the open of the first quote bar after m* (valid spread ≤ 20 %, ask within ±20 % of the last trade);
  - otherwise (open + high) / 2 of the next trade bar.
- **Same-bar confirmations** (209 of 859 L2 triggers) never use a price inside the confirming bar. Excluding them:
  −2.67 %.

## 6. Trigger rates and denominators (2021–25)
| Step | L2 | STATE | VOLU | CONTROL |
|---|---|---|---|---|
| 1 eligible signals | 5,497 | 5,497 | 5,497 | 5,497 |
| 2 minute coverage t+1 | 4,953 | 4,838 | 4,947 | 5,024 |
| 3 breakout within 30 min | 1,638 | 942 | 1,276 | 1,225 |
| 4 $1M within 30 min | 2,067 | 1,026 | 1,986 | 1,164 |
| 5 both = triggered | **859** | 320 | 725 | 394 |
| trigger rate of eligible [95 % CI] | **15.6 %** [13.9, 17.4] | 5.8 % [4.9, 6.8] | 13.2 % [11.9, 14.5] | 7.2 % [6.0, 8.3] |
| 6 valid quote-based entry | 852 (99.2 %) | 316 | 716 | 393 |
| 7 any entry price | 859 | 320 | 725 | 394 |
| 8 complete bracket outcome | 857 | 318 | 724 | 393 |

Incomplete triggered cases (window or corporate action): L2 2, STATE 2, VOLU 1, CONTROL 1.

## 7–9. Results by group (primary rule, complete cases)
| Metric | L2 + trigger | STATE + trigger | VOLU + trigger | Controls + trigger |
|---|---|---|---|---|
| Eligible signals | 5,497 | 5,497 | 5,497 | 5,497 |
| Triggered signals | 859 | 320 | 725 | 394 |
| Trigger rate | 15.6 % | 5.8 % | 13.2 % | 7.2 % |
| Valid entry prices | 859 (852 quote) | 320 (316) | 725 (716) | 394 (393) |
| Mean gross payoff | −0.73 % | −2.49 % | −1.06 % | −1.19 % |
| Mean net payoff, neutral | **−3.13 %** | −4.88 % | −3.45 % | −3.58 % |
| 95 % CI, neutral (security bootstrap) | [−4.21, −2.12]; two-way [−4.91, −1.35] | [−6.40, −3.30] | [−4.47, −2.39] | [−4.95, −2.14] |
| Median net payoff | −12.40 % | −12.40 % | −12.40 % | −12.40 % |
| Win rate (net > 0) | 29 % | 21 % | 28 % | 30 % |
| Target first | 12.1 % | 12.9 % | 11.2 % | 8.9 % |
| Adverse first | 60.0 % | 69.8 % | 57.9 % | 56.0 % |
| Ambiguous | 0.0 % | 0.0 % | 0.0 % | 0.0 % |
| Neither | 27.9 % | 17.3 % | 30.9 % | 35.1 % |
| Incomplete (of triggered) | 2 | 2 | 1 | 1 |
| Median MAE | −10.3 % | −10.6 % | −10.2 % | −10.2 % |
| P(touch −20 % within 5 sessions) | 31 % | 38 % | 28 % | 22 % |
| Median close t+5 vs entry | −4.5 % | −8.7 % | −3.7 % | −4.1 % |

**L2 versus STATE** (paired by joint security resampling, 2,000 replicates):

| Difference L2 − STATE | Point | 95 % CI | p |
|---|---|---|---|
| Trigger rate | +9.8 pp | [8.3, 11.3] | |
| Target-first rate | −0.8 pp | [−4.7, 3.0] | |
| Adverse-first rate | −9.8 pp | [−15.8, −4.0] | |
| Mean gross payoff | +1.76 pp | [0.03, 3.35] | |
| Mean neutral net payoff | **+1.76 pp** | [0.03, 3.35] (two-way [−1.27, 4.50]) | 0.044 |

**L2 versus the others:**

| Comparison | Net payoff difference | 95 % CI | p | Trigger rate difference | Target-first difference | Adverse-first difference |
|---|---|---|---|---|---|---|
| L2 − CONTROL | +0.46 pp | [−1.39, 2.15] | 0.63 | +8.5 pp | +3.2 pp | +4.0 pp |
| L2 − VOLU | +0.32 pp | [−0.61, 1.25] | 0.52 | +2.4 pp | | |

L2 is "less bad" than STATE (fewer adverse-first outcomes), but it is indistinguishable from matched controls and the
volume baseline, and all four are negative.

## 10. Gross vs net payoff, and the entry-price decomposition
| L2 version | Neutral net | n |
|---|---|---|
| All L2 signals at the next open (Stage 4.5 bracket) | −2.91 % | 5,466 |
| Triggered subset entered at the next open | −1.02 % | |
| Triggered subset entered at the trigger | −3.13 % | 857 |

- The trigger selects a somewhat better subset, but waiting for the confirmation moves the entry up:
  - entry vs prior close p25 / 50 / 75: +2.0 / +4.6 / +9.3 %;
  - entry vs prior high: −0.06 / +1.25 / +4.3 %;
  - entry time after 09:30: 2 / 7 / 16 minutes.

  The later, higher entry turns −1.02 % into −3.13 %.
- **Selection** (triggered vs not, among L2 with coverage):

  | | Price | Trailing $vol | ATR | Run-up xr | First-30-min $vol |
  |---|---|---|---|---|---|
  | Triggered | $5.62 | $6.08M | 9.8 % | 52 % | $4.65M |
  | Not triggered | $4.67 | $1.89M | 13.6 % | 42 % | $0.42M |

  The rule picks more liquid names with a larger run-up already in place, not lower-volatility "clean" breakouts.

## 11. Cost sensitivity (L2 triggered)
| Scenario | Mean net [95 % CI] |
|---|---|
| gross | −0.73 % |
| optimistic (1.05 %) | −1.78 % [−2.86, −0.77] |
| **neutral (2.40 %)** | **−3.13 % [−4.21, −2.12]** |
| conservative (4.34 %) | −5.07 % [−6.16, −4.07] |
| quote-informed (2 × s_trig + 0.5 %) | −2.82 % [−3.96, −1.77] |

- Entry-time spread s_trig, p10 / 25 / 50 / 75 / 90: 0.21 / 0.33 / 0.57 / 0.97 / 1.63 %. The median is below the
  Stage 4.5 s30 (0.95 %), which helps a little.
- Even at zero cost the mean is negative.

## 12. Adverse excursion and downside tails (L2 triggered, n 857)
| Measure | Value |
|---|---|
| MAE / MFE (holding period), median | −10.3 % / +7.6 % |
| Touch within 5 sessions from entry, −20 / −30 / −50 % | 31 / 11 / 2 % |
| Touch within 5 sessions from entry, +20 / +30 / +50 % | 26 / 15 / 6 % |
| Close vs entry, t+1 / t+3 / t+5 (median) | −1.8 / −3.4 / −4.5 % |
| Net payoff p5 / 10 / 25 / 50 / 75 / 90 / 95 | −12.4 / −12.4 / −12.4 / −12.4 / +3.8 / +27.6 / +27.6 % |
| Holding period, mean / median | 2.89 / 2 sessions |

## 13. Statistical inference
- **Bootstrap:** security-cluster Poisson, 2,000 replicates (seed 4601); two-way security × date (seeds 4602 / 4603).
- **Paired differences:** joint resampling with identical weights. p-values are two-sided percentile-based.
- **Power:** 857 complete triggered L2 trades. The CI half-width is about 1 pp, so the negative mean is precisely
  estimated. The test is not underpowered.

## 14. Period and universe robustness (L2, primary rule, neutral)
| Cut | Mean net |
|---|---|
| 2021–22 (n 394) | −3.78 % |
| 2023–25 (n 463) | −2.57 % |
| Leave-one-year-out (2021 / 2022 / 2023 / 2024 / 2025 left out) | −2.96 / −2.91 / −3.43 / −3.08 / −3.24 % |
| 10 hash security groups, leave-one-out | −3.47 … −2.78 % |
| Top-10 contributing securities removed | −4.24 % |
| A-strict | −3.21 % |
| Dedup 5 sessions (n 626) | −2.93 % |
| Conservative ambiguous / incomplete | −3.15 % [−4.23, −2.14] |
| Gap-realistic | −3.29 % |
| Quote-entry only (n 850) | −3.06 % |
| Minute-proxy only (n 7) | −11.19 % |
| Same-bar triggers excluded | −2.67 % |

**E1 diagnostic** (never used to select): with a move day in t+1..t+3, +5.65 % (n 162); without, −5.17 % (n 695).
Detecting the actual move would pay; the trigger does not separate the two groups well enough.

**S2 and 2026 YTD** (S46ROBUST v2, backtest d2c2494b…, VALID; primary rule, neutral):

| Population | Group | Eligible | Triggered (rate) | Complete | Mean net [95 % CI] | Gross | T / A / N |
|---|---|---|---|---|---|---|---|
| S2-P5 2021–25 | L2 | 4,983 | 1,070 (21.5 %) | 1,062 | −2.95 % [−3.78, −2.18]; two-way [−4.33, −1.63] | −0.56 % | 7.8 / 49.7 / 42.5 % |
| S2-P5 2021–25 | STATE | 4,983 | 570 (11.4 %) | 570 | −3.95 % [−5.06, −2.83] | −1.56 % | 9.8 / 59.3 / 30.9 % |
| S1-P5 2026 YTD (diagnostic) | L2 | 701 | 145 (20.7 %) | 143 | −3.12 % [−5.55, −0.92] | −0.72 % | 13.3 / 60.8 / 25.9 % |
| S1-P5 2026 YTD (diagnostic) | STATE | 701 | 48 (6.8 %) | 48 | −4.73 % [−9.53, −0.70] | −2.34 % | 8.3 / 68.8 / 22.9 % |

L2 − STATE: S2 +1.00 pp [−0.04, 2.02] (p 0.06); 2026 +1.61 pp [−2.50, 6.37] (p 0.44).

## 15. Secondary sensitivities (exploratory; BH over 7 variants; each changes one element)
| Variant | Triggered | n | Mean net [95 % CI] |
|---|---|---|---|
| $0.5M / 30 min | 1,085 | 1,083 | −3.20 % [−4.13, −2.30] |
| $2M | 655 | 653 | −3.19 % [−4.32, −2.13] |
| $5M | 416 | 415 | −3.96 % [−5.33, −2.60] |
| 5 min | 377 | 375 | −3.65 % [−5.02, −2.26] |
| 15 min | 630 | 628 | −3.36 % [−4.47, −2.26] |
| 60 min | 1,144 | 1,141 | −2.92 % [−3.84, −2.09] |
| close-above breakout | 777 | 775 | −2.99 % [−4.15, −1.89] |

All are significantly negative (BH q < 0.01). No variant comes near zero.

## 16. Prospective shadow log
<!--SHADOW-->

## 17. Limitations
See `limitations.md`. The main ones:
- historical exposure;
- minute-quote granularity (first ask of the next minute bar, not tick-level);
- no size or impact;
- the exit at exactly ±levels (gap-realistic sensitivity reported);
- a 20 % sample;
- the QC data revision (new canonical panel).

## 18. Decision gate: exact reasons
| Gate | Requirement | Result | Status |
|---|---|---|---|
| G1 | mean neutral net > 0 | −3.13 % | **FAIL** |
| G2 | security and two-way CI lower bound > 0 | −4.21 % / −4.91 % | **FAIL** |
| G3 | L2 − STATE ≥ +1.0 pp, security CI > 0 | +1.76 pp [0.03, 3.35] (two-way CI includes 0) | PASS, but between two negative means |
| G4 | positive in both periods, every leave-one-year-out, without the top-10 securities, every security group | all negative | **FAIL** |
| G5 | conservative treatment > 0 | −3.15 % | **FAIL** |
| G6 | ≥ 80 % quote entries AND quote-only mean > 0 | 99.2 % quote entries, but quote-only −3.06 % | **FAIL** (payoff part) |
| G7 | decision from the primary rule only | | PASS |

- Additional B condition: adverse first 60.0 % > target first 12.1 % + neither 27.9 %.
- C (inconclusive) does not apply: 857 complete trades (≥ 300) and valid entry prices for 100 % of them.
