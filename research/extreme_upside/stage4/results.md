# Stage 4 — results (all numbers from QC aggregate outputs; raw files in `results/xup_s4_*_raw.txt`)

**Data and periods.**
- Panel: the revised canonical panel, 6,028,644 rows / 24,426 primary events (Amendment 1), unless stated
  otherwise.
- Test: 2021–2025, 1,605,424 valid rows, 9,367 primary positives, base rate 0.583 %.
- 2026 YTD (to 2026-08-27) is descriptive only.
- Primary model: frozen full-A RF. Primary endpoint: A10/+100 %.

## 1. Reproduction and the Stage 3 discrepancy (S4AUDIT v1 / v2)

**S4AUDIT v1** (pre-revision data) reproduces TEST v1 exactly:

| Metric | TEST v1 (Stage 3) | S4AUDIT v1 |
|---|---|---|
| RF PR-AUC | 0.0596 | 0.0596 |
| RF P@1 % | 7.74 % (1,296 / 16,749) | 7.74 % (1,296 / 16,749) |
| RF P@5 % | 5.31 % | 5.31 % (4,293 / 80,800) |
| RF P@10 % | 3.96 % | 3.96 % (6,370 / 161,006) |
| RF R@10 % | 68 % | 68.5 % |
| Volume LR PR-AUC / P@1 % | 0.0460 / 7.02 % | 0.0460 / 7.02 % (1,176 / 16,749) |
| Base / positives / rows | 0.580 % / 9,300 / 1.604 M | 0.580 % / 9,300 / 1,604,540 |

All six models match TEST v1, including the GBM, LR, price and momentum models.

**Discrepancy table (1,296 vs 1,263):**

| Metric | Source | Definition | Numerator / denominator | Explanation | Canonical value |
|---|---|---|---|---|---|
| RF top-1 % positives | Stage 3 report §D; `T fullA RF` (TEST v1) | P@1 %, S3-rank, full-A **RF** | 1,296 / 16,749 | RF model | **1,296 / 16,749 (7.74 %) for RF** |
| "top-1 %" positives | Stage 3 report §H; `T tradability top1% fullA GBM` (TEST v1) | `_tradability()` uses **full-A GBM** (code: `res["fullA GBM"]`) | 1,263 / 16,749 | a different model, not a different row set: GBM P@1 % = 7.54 % = 1,263 / 16,749 | **1,263 / 16,749 is GBM** |

The Stage 3 §H tradability profile ($0.66 median, 62 % < $1, 27 % < $100k, 29 % / 53 % close confirmation) is
therefore **GBM's**.

The **RF** top-1 % profile, recomputed in S4AUDIT with the same formula:
- median price $0.46, 78 % < $1, 19 % at $1–5;
- median dollar volume $470k, 21 % < $100k;
- close confirmation B 29 %, B-max 50 %; 35 % of events above +200 %.

**Data revision (S4AUDIT v2, revised panel):**
- RF PR-AUC 0.0601, P@1 % 7.73 % (1,295 / 16,752).
- Volume LR 0.0461 / 7.13 %.
- Base 0.583 %, 9,367 positives.
- The revision moves the metrics by ≤ 0.0005 PR-AUC.

**Stage 4 ranking (S4-rank, invalid-label rows included in the daily ranking; 0.39 % of rows):**
- RF P@1 % 7.77 % (1,264 / 16,261 valid among 16,789 selected).
- The difference from S3-rank is negligible.

## 2. Event populations (S4EVENTS v2)
| Definition | Events (all years) | Securities | Positive days | Days / event (mean, median) | Duration (median, p90) | Incomplete | Test 2021–25 events |
|---|---|---|---|---|---|---|---|
| E1 A10/+100 (Stage 3 rule) | 4,215 | 1,159 | 24,426 | 5.80 / 6 | 7 / 10 | 112 | **1,539** (511 securities) |
| E2 A10/+100 (merged windows) | 3,744 | 1,159 | 24,426 | 6.52 / 7 | 8 / 11 | 105 | 1,342 |
| E3 path excursions | 3,883 | 1,172 | 15,753 excursion days | 4.06 / 2 | 3 / 10 | 184 | 1,387 |
| E1 B10/+100 | 1,851 | 827 | 7,758 | 4.19 / 3 | 4 / 9 | 37 | 713 |
| E2 B10/+100 | 1,779 | 827 | 7,758 | 4.36 / 3 | 4 / 9 | 36 | 677 |
| E1 B-max10/+100 | 2,324 | 922 | 12,551 | 5.40 / 5 | 6 / 10 | 55 | 865 |
| E2 B-max10/+100 | 2,171 | 922 | 12,551 | 5.78 / 6 | 7 / 10 | 53 | 794 |

- **E1 vs E2:** 882 of 4,215 E1 episodes (20.9 %) are merged by E2 with a neighbour. 471 E1 episodes start
  ≤ 10 rows after the previous one ends.
- **E3 vs E1:** 98.2 % of E3 move days lie inside an E1 span; every E1 episode contains an excursion day.
- **Close confirmation of E1 A-events:** B 45 %, B-max 57 % (all years).
- **Test E1 events:** median maximum return +154 %; 32 incomplete. 2026 YTD: 280 events, 32 incomplete.
- **Test E1 events by onset price:**

  | < $0.10 | 0.10–0.49 | 0.50–0.99 | 1–2.99 | 3–4.99 | 5–9.99 | ≥ 10 |
  |---|---|---|---|---|---|---|
  | 31 | 305 | 240 | 513 | 172 | 165 | 113 |

- **Test E1 events by onset dollar volume:**

  | < 100k | 100–500k | 500k–1M | 1–5M | 5–10M | > 10M |
  |---|---|---|---|---|---|
  | 523 | 405 | 136 | 235 | 61 | 179 |

## 3. Event-level evaluation (S4EVAL v2; 1,539 test E1 events; signals in test rows)
| Model, k | Capture | Pre-onset | In-event only | None | Signals | Associated | Unique events / signal | False / captured | Repeats / captured |
|---|---|---|---|---|---|---|---|---|---|
| RF 1 % | 28.8 % | 22.2 % | 6.7 % | 71.2 % | 16,789 | 17.2 % | 0.026 | 31.3 | 5.5 |
| RF 5 % | 62.8 % | 55.4 % | 7.4 % | 37.2 % | 81,210 | 12.5 % | 0.012 | 73.5 | 9.5 |
| RF 10 % | 79.5 % | 73.6 % | 6.0 % | 20.5 % | 161,756 | 9.4 % | 0.008 | 119.7 | 11.4 |
| Volume LR 1 % | 22.0 % | 18.9 % | 3.1 % | 78.0 % | 16,789 | 16.5 % | 0.019 | 41.3 | 7.2 |
| Volume LR 5 % | 50.8 % | 45.8 % | 5.0 % | 49.2 % | 81,210 | 10.3 % | 0.009 | 93.2 | 9.7 |
| Price LR 1 % / 5 % | 15.5 / 41.8 % | 13.6 / 39.4 % | | | | 14.1 / 10.3 % | | | |
| Momentum LR 1 % / 5 % | 30.0 / 58.4 % | 22.7 / 51.1 % | | | | 14.3 / 10.6 % | | | |
| Full-A LR 1 % / 5 % | 30.8 / 61.7 % | 25.0 / 55.0 % | | | | 16.5 / 12.4 % | | | |
| Full-A GBM 1 % / 5 % | **40.2 / 67.6 %** | 31.2 / 59.1 % | | | | 17.1 / 12.2 % | | | |

- **Repeat share of RF signals** (signals repeating an already flagged event): 14.6 % at 1 %, 11.3 % at 5 %.
  Securities with ≥ 2 signals and no event: 168 at 1 %, 268 at 5 %.
- **Other definitions, RF top 5 %:**
  - E2: capture 60.9 %, pre-onset 51.5 %;
  - E3 (relative to the move day): capture 76.4 %, pre-move 60.2 %, in-event only 16.2 %.
- **Event ranking** (pre-score = max daily percentile in onset − 10..−1, vs the same security 31–40 sessions
  earlier):

  | Model | Median pre-score | Median placebo | Pre > placebo | AUC |
  |---|---|---|---|---|
  | RF | 0.961 | 0.949 | 56.3 % | 0.546 |
  | Volume LR | 0.940 | 0.937 | | 0.512 |
  | GBM | | | | 0.547 |
  | E3, RF | | | | 0.586 |

  Event-level scores barely rise before onset relative to the same stock a month earlier.

## 4. Deduplication (S4EVAL v2, E1)
| RF, k | Rule | Signals | Capture | Pre-onset | Event precision | Removed / captured | Lead (first, 1–40) p25 / 50 / 75 |
|---|---|---|---|---|---|---|---|
| 1 % | N0 | 16,789 | 28.8 % | 22.2 % | 17.2 % | 0 | 14 / 27 / 39 |
| 1 % | C10 | 2,641 | 26.6 % | 17.8 % | 16.6 % | 31.9 | 13 / 25 / 34 |
| 1 % | C20 | 1,786 | 21.5 % | 12.3 % | 17.0 % | 33.8 | 13 / 23 / 30 |
| 1 % | CW | 1,316 | 15.9 % | 8.6 % | 16.7 % | 34.8 | 10 / 20 / 29 |
| 1 % | CE (oracle) | 2,763 | 28.4 % | 20.5 % | 15.5 % | 31.6 | 13 / 25 / 34 |
| 5 % | N0 | 81,210 | 62.8 % | 55.4 % | 12.5 % | 0 | 29 / 40 / 40 |
| 5 % | C10 | 9,998 | 60.3 % | 47.4 % | 11.7 % | 73.6 | 26 / 32 / 36 |
| 5 % | CW | 2,874 | 17.1 % | 8.5 % | 8.5 % | 81.0 | 11 / 20 / 31 |

- **Effect of deduplication:** it removes 84–88 % of the signals (C10) at a capture cost of 2–3 pp. Paired
  bootstrap, RF 5 %: Δcapture −2.5 pp [−3.3, −1.8]. It does **not** improve event precision (Δ −0.8 pp
  [−1.2, −0.5] at 5 %).
- **Conclusion unchanged:** most raw signals are repeats of the same chronically flagged securities.
  Deduplication makes the signal list ~6–8× shorter, but it does not change the quality conclusions.
- **Signals per year** (RF 1 %, C10, 2021–25): 513 / 543 / 562 / 510 / 513, in the 20 % sample.

## 5. Lead time and the confirmatory C4 / C5 test (S4LEAD v1)
**Share of test events with ≥ 1 RF signal in each window before onset:**

| Definition, k | 1–2 | 3–5 | 6–10 | 11–20 | 21–40 | Before onset (1–40) | In-event only | None |
|---|---|---|---|---|---|---|---|---|
| A E1, RF 1 % | 16.1 % | 15.5 % | 16.2 % | 20.7 % | 22.6 % | 34.0 % | 4.4 % | 61.6 % |
| A E1, RF 5 % | 47.0 % | 47.3 % | 50.7 % | 52.9 % | 56.0 % | 65.8 % | 4.7 % | 29.4 % |
| A E1, RF 10 % | 67.9 % | 67.6 % | 69.1 % | 72.4 % | 77.0 % | 82.6 % | 3.3 % | 14.1 % |
| A E1, volume LR 5 % | 38.7 % | 40.3 % | 42.2 % | 47.1 % | 50.6 % | 57.3 % | 3.1 % | 39.6 % |
| A E3 (move day), RF 5 % | 51.3 % | 49.3 % | 50.1 % | 52.7 % | 56.5 % | 68.4 % | 11.8 % | 19.8 % |
| B E1, RF 5 % | 41.5 % | 42.1 % | 44.2 % | 48.1 % | 50.7 % | 61.0 % | 3.8 % | 35.2 % |
| B-max E1, RF 5 % | 44.0 % | 44.0 % | 46.2 % | 49.7 % | 52.0 % | 62.8 % | 4.9 % | 32.4 % |

- **The window profile is flat:** an event is about as likely to have a signal 21–40 sessions before onset as
  1–2 sessions before. The signal reflects a persistent stock state, not a timing alarm. The median
  first-signal lead is 27 sessions at 1 % and the 40-session cap at 5 %.

**C4 / C5 (RF top 5 %, pre 1–10 vs same-security placebo 31–40, paired bootstrap 2,000):**

| Definition | Pre-onset | Placebo | Δ [95 % CI] | Ratio | ≥ 20 % | CI > 0 | Ratio ≥ 1.5 | Verdict |
|---|---|---|---|---|---|---|---|---|
| E1 (C4) | 57.0 % | 49.8 % | +7.2 pp [4.8, 9.6] | 1.14 | yes | yes | **no** | **FAIL** |
| E2 (C5) | 53.1 % | 47.9 % | +5.2 pp [2.6, 7.8] | 1.11 | yes | yes | no | FAIL |
| E3 (C5) | 61.2 % | 48.5 % | +12.7 pp [9.9, 15.4] | 1.26 | yes | yes | no | FAIL |

- **Exploratory variants:**
  - top 1 %: E1 22.8 vs 15.7 % (ratio 1.45); E3 clean 20.8 vs 12.0 % (1.73);
  - "clean" events (no earlier event within 40 sessions): E1 5 % 46.6 vs 41.2 % (1.13).

**Lead vs magnitude (RF 5 %, E1):**

| Group | n | Median max return | B / B-max confirmation | Median adverse before target | Median onset price |
|---|---|---|---|---|---|
| Pre-signal (1–10) | 853 | 160 % | 41 / 54 % | −10 % | $0.77 |
| In-event only | 114 | 193 % | 65 / 78 % | −14 % | $1.79 |
| No signal | 572 | 140 % | 52 / 60 % | −6 % | $3.16 |

- Spearman(lead, max return) = +0.055 and Spearman(lead, B-max confirmation) = −0.028. **Earlier signals are not
  associated with larger or better-confirmed moves.** Pre-signalled events are cheaper and less often
  close-confirmed.

## 6. Tradability strata (S4TRAD v1; global daily RF selection, test)
| Stratum | Rows | Base | P@1 / 5 / 10 % | Top-1 % rows | Capture 1 / 5 / 10 % | Event precision 1 / 5 % |
|---|---|---|---|---|---|---|
| px < 0.10 | 1,121 | 16.06 % | 17.5 / 15.6 / 16.1 % | 680 | 94 / 100 / 100 % | 38 / 36 % |
| px 0.10–0.49 | 34,633 | 5.27 % | 8.4 / 6.3 / 5.5 % | 8,207 | 65 / 95 / 100 % | 19 / 15 % |
| px 0.50–0.99 | 53,080 | 3.06 % | 6.4 / 4.7 / 3.8 % | 3,815 | 34 / 82 / 95 % | 13 / 11 % |
| px 1–2.99 | 185,418 | 1.69 % | 5.9 / 4.7 / 3.3 % | 2,604 | 17 / 57 / 82 % | 14 / 11 % |
| px 3–4.99 | 112,784 | 0.91 % | 7.0 / 4.9 / 3.4 % | 344 | 13 / 40 / 59 % | 15 / 12 % |
| px 5–9.99 | 224,080 | 0.42 % | 4.8 / 5.9 / 4.1 % | 334 | 12 / 39 / 54 % | 11 / 11 % |
| px ≥ 10 | 994,308 | 0.06 % | 6.1 / 3.2 / 2.5 % | 277 | 6 / 19 / 44 % | 12 / 7 % |
| px ≥ 5 & $vol ≥ 1M | 917,510 | 0.10 % | 4.9 / 4.2 / 3.4 % | 546 | 13 / 40 / 59 % | 11 / 9 % |

- **Concentration of the global selection:** 78 % of the RF top 1 % is below $1. In sub-$1 strata the base
  rate is already 3–16 %, so lift there is small (1.1–2.1×).
- **Above $5:** precision is 5–6 % against 0.06–0.42 % base rates, but the global ranking puts almost no
  selections there.
- **Volume LR above $5:** it makes 0 top-1 % selections in the px ≥ $5 & $vol ≥ $100k cell (RF: 611).
- **Volatility:** ATR / rv20 deciles 1–7 (2006–20 cut-offs) contain almost no events and no selections. The
  signal lives in the top 2 volatility deciles.

## 7. Liquidity filters, re-ranked inside the filter (S4FILT v1)
| Filter | Rows kept | Events kept | Base | P@1 % | Lift, validation / test | Capture 1 / 5 % | Event precision 1 % | Median price / $vol of top 1 % |
|---|---|---|---|---|---|---|---|---|
| none | 100 % | 1,539 | 0.58 % | 7.8 % | 21.2 / 13.3 | 29 / 63 % | 17 % | $0.43 / $501k |
| S0: px ≥ 1, $vol ≥ 100k | 81.2 % | 700 | 0.31 % | 5.3 % | 22.0 / 17.2 | 38 / 72 % | 13 % | $1.86 / $1.1M |
| **S1: px ≥ 1, $vol ≥ 500k** | 69.2 % | 457 | 0.23 % | 4.9 % | 22.7 / 21.5 | 43 / 76 % | 12 % | $2.04 / $2.7M |
| S2: px ≥ 5, $vol ≥ 1M | 57.1 % | 177 | 0.10 % | 4.1 % | 22.6 / 41.2 | 60 / 81 % | 9 % | $9.30 / $8.5M |
| px ≥ 5, $vol ≥ 5M | 43.6 % | 120 | 0.08 % | 3.5 % | 26.2 / 45.4 | 66 / 84 % | 7 % | $10.8 / $28M |

- **C6 PASSES for S0, S1 and S2:** lift ≥ 3× in validation and test, ≥ 100 events, top-5 % capture ≥ 30 %.
- **No filter destroys the ranking.** Removing sub-$1 and illiquid names removes 30–60 % of the events. Inside
  the remaining universe the frozen RF still ranks strongly (lift 17–45×), but absolute top-1 % precision is
  only 3.5–5.3 %.

## 8. Statistical uncertainty and paired comparisons (S4BOOT v1)
**Individual metrics** (security-cluster bootstrap, 2,000):

| Model | PR-AUC | Two-way | P@1 % |
|---|---|---|---|
| RF | 0.0601 [0.0536, 0.0670] | [0.0531, 0.0687] | 7.73 % [6.73, 8.77] |
| Volume LR | 0.0461 [0.0394, 0.0539] | | 7.13 % [5.91, 8.43] |
| GBM | 0.0570 | | |
| Full-A LR | 0.0545 | | |

**Paired differences** (same rows; security-cluster 2,000 / security × date 1,000):

| Pair | ΔPR-AUC [CI] p | Two-way CI | ΔP@1 % [CI] | ΔP@5 % [CI] | ΔP@10 % |
|---|---|---|---|---|---|
| RF − volume LR | **+0.0139 [0.0080, 0.0195] p 0.0005** | [0.0069, 0.0201] p 0.001 | +0.60 pp [−0.56, 1.72] p 0.32 | +1.13 pp [0.72, 1.51] | +0.83 pp |
| Full-A LR − volume LR | +0.0084 [0.0024, 0.0135] p 0.009 | [0.0011, 0.0146] | +0.08 pp [−1.06, 1.15] | +1.03 pp | +0.75 pp |
| GBM − volume LR | +0.0109 [0.0045, 0.0165] p 0.001 | [0.0033, 0.0172] | +0.51 pp [−0.68, 1.61] | +1.03 pp | +0.76 pp |
| RF − price LR | +0.0223 [0.0166, 0.0281] | | +1.63 pp [0.33, 2.84] | +1.13 pp | +0.88 pp |
| RF − momentum LR | +0.0171 [0.0123, 0.0223] | | +1.43 pp [0.42, 2.39] | +0.83 pp | +0.54 pp |

- **RF vs volume LR, events** (E1, security bootstrap): Δcapture at 5 % +12.0 pp [9.3, 14.7]; Δpre-onset at 5 %
  +9.6 pp [6.8, 12.3]; Δevent precision at 5 % +2.3 pp [1.5, 3.0]. At 1 %: Δcapture +6.8 pp [4.2, 9.4].
- **GBM − volume LR at 1 %:** Δcapture +18.2 pp [15.3, 21.1].
- **Reading.** Under paired comparisons, RF outperforms the volume baseline on overall ranking (PR-AUC), at
  top 5–10 % and on event capture, robustly to date clustering. At the top 1 % row precision the two are
  statistically indistinguishable. This replaces the Stage 3 "inconclusive", which came from overlapping
  individual CIs; Stage 3 itself is unchanged.

**Period stability:**

| Period | Base | RF PR-AUC | Volume LR PR-AUC | ΔPR-AUC (300 resamples) | RF P@1 % | RF capture 5 % | RF event precision 5 % |
|---|---|---|---|---|---|---|---|
| 2021–22 | 0.364 % | 0.0472 | 0.0332 | +0.0140 [0.0036, 0.0271] | 5.61 % | 69.1 % | 9.2 % |
| 2023–25 | 0.736 % | 0.0649 | 0.0516 | +0.0133 [0.0064, 0.0199] | 9.18 % | 60.5 % | 14.9 % |
| 2026 YTD | 0.908 % | 0.0809 | 0.0616 | +0.0193 [0.0040, 0.0320] | 10.29 % | 63.6 % | 17.4 % |

- PR-AUC and precision scale with the base rate. The RF advantage and event capture are stable.
- Share of RF top-1 % below $1: 67 / 86 / 85 % by period.

## 9. Outcomes and downside (S4OUTC v1; relative to adjusted OPEN(t+1); daily bars)
| Set (test) | n | Median close t+5 / t+10 / t+20 | c10 < 0 | c20 ≤ −50 % | Low within 20 sessions ≤ −50 % | Hit +100 % (high) / +100 % (close) | Median max high 10d / max close 10d |
|---|---|---|---|---|---|---|---|
| Unconditional | 1,611,773 | −0.03 / −0.05 / −0.13 % | 50 % | 0.7 % | 1.2 % | 0.6 / 0.3 % | 5.2 / 3.1 % |
| **RF top 1 %** | 16,789 | **−4.1 / −7.1 / −12.4 %** | 63 % | **8.0 %** | **13.9 %** | 7.8 / 3.9 % | 16.6 / 7.3 % |
| RF top 5 % | 81,210 | −3.1 / −5.4 / −9.4 % | 62 % | 5.1 % | 8.9 % | 5.4 / 2.8 % | 13.9 / 6.5 % |
| Volume LR top 1 % | 16,789 | −2.6 / −4.6 / −8.3 % | 62 % | 5.3 % | 9.3 % | 7.1 / 3.0 % | 14.2 / 6.5 % |
| Price LR top 1 % | 16,789 | −2.4 / −4.3 / −8.1 % | 61 % | 4.7 % | 8.3 % | 6.1 / 2.8 % | 13.2 / 6.2 % |
| RF top 1 % in S1 | 11,788 | −5.2 / −8.5 / −14.2 % | 65 % | 8.9 % | 14.2 % | 4.9 / 3.1 % | 14.8 / 6.3 % |

- **RF top 1 %, failures vs successes:**
  - failures (no event, n 14,997): median c10 −8.7 %; c20 p5 / p25 / p50 −57.5 / −30.6 / −14.1 %;
    c20 ≤ −50 % in 8.4 %;
  - successes (n 1,264): median c10 +56.9 %, c20 median +27.1 %, but c20 p5 −46.1 %; only 29.1 % hold a
    +100 % close at t+10.
- **Gap between high and close:** the median gap between the 10-day maximum high and the maximum close is 9 pp
  for RF top 1 %, vs 2 pp unconditionally.
- **Incomplete 20-session windows** (segment end: delisting or data gap): 888 of 16,789 RF top-1 % rows (5.3 %),
  vs 0.8 % unconditionally. Their realised value is unknown.
- **C7: FLAG.** In S1, 3.82 % of RF top-1 % selections close ≤ −50 % at t+10, vs 3.06 % reaching a +100 %
  close in the window.

## 10. Universe and label robustness (S4ROBUST v1; RF re-ranked inside each universe; test)
| Universe | A events | Capture / pre at 1 % | Capture / pre / placebo at 5 % | B events: capture / pre / placebo at 5 % | B-max events: capture / pre / placebo at 5 % | S1 lift / capture 5 % |
|---|---|---|---|---|---|---|
| A | 1,539 | 28.8 / 22.2 % | 62.8 / 55.4 / 49.8 % | 713: 55.4 / 49.9 / 45.2 % | 865: 59.5 / 51.7 / 46.6 % | 21.5 / 76.1 % |
| A-strict | 1,300 | 29.3 / 22.6 % | 62.7 / 55.3 / 50.8 % | 600: 55.0 / 48.8 / 45.5 % | 731: 59.1 / 50.8 / 47.1 % | 22.6 / 76.8 % |
| A-ex-ADR | 1,469 | 28.5 / 21.9 % | 63.1 / 55.9 / 49.3 % | 677: 55.4 / 50.2 / 44.8 % | 822: 59.2 / 51.9 / 46.1 % | 21.4 / 76.6 % |
| A-fund | 1,537 | 28.8 / 22.2 % | 62.7 / 55.2 / 49.5 % | 712: 55.3 / 50.0 / 44.8 % | 864: 59.4 / 51.7 / 46.3 % | 21.4 / 76.1 % |
| B | 1,080 | 31.3 / 24.4 % | 62.9 / 56.1 / 50.2 % | 490: 53.7 / 48.4 / 43.9 % | 606: 58.4 / 50.8 / 45.6 % | 23.0 / 78.2 % |

- **E2 / E3 in the sensitivity universes, RF 5 %:** E2 pre / placebo ≈ 51–52 / 47–49 %; E3 pre / placebo
  ≈ 59–60 / 48–49 %.
- **Incomplete labels:** RF P@1 % is 7.77 % excluding invalid-label rows vs 7.53 % counting them as negatives;
  capture of complete vs incomplete events is 62.7 vs 68.8 % (32 events).
- **Conclusion:** none of the Stage 4 conclusions depend on unresolved securities, ADRs, the fund-like flag,
  incomplete labels or the event family.

## 11. Execution-data audit (S4EXEC v1; hash samples)
- **Coverage:** minute trade bars, pre-market bars and minute quote bars exist for 105 / 120 signal entry days,
  107 / 120 move days and 54 / 60 controls.
- **Median quoted relative spread** (median of per-day medians, regular session as masked):

  | Sample | p25 / p50 / p75 | First 30 minutes |
  |---|---|---|
  | Signal entry day (t+1) | 0.60 / 1.06 / 1.93 % | 0.90 / 1.66 / 3.15 % |
  | Move day | 0.38 / 0.78 / 1.52 % | |
  | Controls (mostly ≥ $5) | 0.09 / 0.17 / 0.44 % | |

- **Spreads by price on signal entry days:** < $1 1.10 % (n 101), $1–5 0.87 % (14), ≥ $5 0.82 % (5).
- **Flagged as unverified:** v1 minute dollar-volume figures (inconsistent with daily bars) and the "high
  outside regular hours" share (89 % even on controls, which suggests a session-mask / time-zone problem).
  S4EXEC v2 re-checks them with diagnostics.

## 12. Calibration and ranking stability (S4CALIB v2; v1 ended in QC without any output and is kept as INVALID)
**Calibration on test rows** (pred / obs = Σ predicted / Σ observed):

| Model | Brier | Log loss | ECE10 | Pred / obs | Top-1 % bin: predicted vs observed |
|---|---|---|---|---|---|
| RF | 5.613e-3 | 0.0274 | 0.103 pp | 0.84 | 8.86 vs 8.81 % |
| Full-A LR | 5.647e-3 | 0.0282 | 0.168 pp | 0.74 | 10.24 vs 8.22 % |
| GBM | 5.973e-3 | 0.0286 | 0.101 pp | 0.94 | **18.34 vs 8.55 %** (over-confident at the top) |
| Volume LR | 5.689e-3 | 0.0306 | 0.185 pp | 0.68 | 9.64 vs 7.52 % |

- RF decile reliability: top two deciles 0.84 / 1.15 % and 3.48 / 4.09 % (predicted / observed).

**Drift (RF, predicted / observed):**

| Breakdown | Values |
|---|---|
| Year | 2021 0.60 (base 0.35 %); 2022 1.33 (0.38 %); 2023 1.04 (0.54 %); 2024 0.70 (0.83 %); 2025 0.70 (0.84 %); 2026 YTD 0.66 (0.91 %) |
| Price | < 0.10 0.54; 0.10–0.49 0.96; 0.50–0.99 0.97; 1–2.99 0.83; 3–4.99 0.65; 5–9.99 0.56; ≥ 10 1.03 |
| Dollar volume | 0.78–0.91 |
| SPY-vol tercile | 0.64 / 0.80 / 1.10 |

- Monthly correlation of base rate with observed / predicted: +0.727 over 60 months. Probability levels lag the
  base rate: they under-predict in high-event years and over-predict in quiet ones, while the ranking stays
  stable.

**Frozen calibration experiment** (MODEL-split RF trained to 2016; Platt / isotonic fitted on validation
2017–2020 only):

| Period | Model | Pred / obs | ECE10 | Log loss | PR-AUC |
|---|---|---|---|---|---|
| Test | MODEL-split RF raw | 0.72 | 0.172 pp | 0.0278 | 0.0574 |
| Test | + Platt | 1.09 | 0.103 pp | 0.0276 | 0.0574 |
| Test | + isotonic | 1.10 | 0.066 pp | 0.0274 | 0.0566 |
| Test | TEST-refit RF | 0.84 | 0.103 pp | 0.0274 | 0.0601 |
| 2026 YTD | MODEL-split RF raw | 0.57 | | | |
| 2026 YTD | + Platt | 0.87 | | | |
| 2026 YTD | + isotonic | 0.86 | | | |

- Validation-fitted calibration fixes most of the level error. It cannot follow later base-rate shifts, and it
  does not change the ranking.

**Ranking stability:**
- Spearman rank correlations: RF–GBM 0.925, RF–LR 0.879, RF–volume LR 0.780, RF–price 0.771, volume–price 0.984.
  Within-day RF–volume LR 0.778.
- Share of RF selections also chosen by volume LR: 37 % (top 1 %), 58 % (top 5 %), 66 % (top 10 %). By full-A
  LR: 64 / 80 / 84 %.
- **Persistence:** 82.7 % of RF top-1 % selections (90.8 % of top 5 %) were also selected the previous session;
  volume LR 81.9 / 89.8 %.
- Security-level mean RF percentile, 2021–22 vs 2023–25: Spearman 0.911 over 1,387 securities.
- The ranking is very stable, and largely a stock state.

**Where the RF advantage over volume LR comes from** (PR-AUC):

| Subset | RF | Volume LR | Difference |
|---|---|---|---|
| All | 0.0601 | 0.0461 | +0.0139 |
| Excluding top 1 % securities | | | +0.0144 |
| Excluding top 5 % securities | | | +0.0132 |
| Excluding px < 0.10 | | | +0.0156 |
| Price < $1 | 0.0833 | 0.0788 | **+0.0045** |
| Price ≥ $1 | 0.0433 | 0.0189 | **+0.0244** |

- The advantage is not driven by a few securities. It comes mainly from stocks ≥ $1, where volume alone ranks
  poorly.

## 13. Concentration and regimes (S4CONC v1; test 2021–25)
**Selections and dates:**
- 1,255 test days; eligible rows per day p10 / p50 / p90 = 1,220 / 1,270 / 1,370.
- RF top-1 % selections: 13 per day (max 14) in the 20 % sample, i.e. about 65 per day in the full universe.
- Date concentration of positives: 3.4 % of positive rows fall on the top 1 % of days, 14.2 % on the top 5 %.
- Daily E1 onsets: mean 1.23, variance / mean 1.53; 11 days above mean + 3 sd.
- Daily event rate: variance is 4.2× the binomial variance; intraclass correlation 0.0025.
- Common-date shocks exist but are small relative to cross-sectional variation.

**Security concentration** (of 1,832 securities with test rows, 511 had ≥ 1 event):

| Share from | Top 1 % of securities | Top 5 % | Top 10 % |
|---|---|---|---|
| Events | 12.9 % | 43.5 % | 65.8 % |
| RF top-1 % selections | 22.9 % | 64.3 % | **86.9 %** |

The selection is much more concentrated than the events: a small set of permanently flagged securities.

**Regimes** (past-only variables, tercile cut-offs from 2006–2020):

| Regime variable | Tercile | Rows | Base | RF AP | RF P@1 % | Volume LR AP | Volume LR P@1 % |
|---|---|---|---|---|---|---|---|
| SPY 20-day vol | T1 (low) | 341k | 0.69 % | 0.0762 | 9.2 % | 0.0498 | 7.9 % |
| | T2 | 744k | 0.60 % | 0.0576 | 7.5 % | 0.0499 | 7.3 % |
| | T3 (high) | 520k | 0.49 % | 0.0568 | 7.2 % | 0.0408 | 6.3 % |
| IWM 20-day return | T1 | 634k | 0.48 % | 0.0647 | 7.9 % | 0.0447 | 6.3 % |
| | T2 | 438k | 0.59 % | 0.0594 | 7.7 % | 0.0492 | 7.0 % |
| | T3 | 534k | 0.70 % | 0.0604 | 7.6 % | 0.0481 | 8.2 % |
| Panel median r20 | T1 | 671k | 0.50 % | 0.0625 | 7.8 % | 0.0451 | 6.6 % |
| | T2 | 513k | 0.59 % | 0.0612 | 7.9 % | 0.0507 | 7.2 % |
| | T3 | 421k | 0.71 % | 0.0600 | 7.4 % | 0.0462 | 7.9 % |

- Regimes change the base rate moderately (0.48–0.71 %). They do not remove the RF ranking advantage: RF AP is
  above volume LR in all nine cells.

**Calendar control:**
- Mean per-day AP (1,207 days with ≥ 1 positive): RF 0.1059 vs volume LR 0.0896; RF better on 65.5 % of days.
- Pooled ΔPR-AUC +0.0139, date-cluster bootstrap [0.0117, 0.0163], p 0.001.
- **The RF advantage is not a calendar-concentration artefact.**

## 14. Exploratory: pre-event vs placebo inside S0 / S1 / S2 (S4XSEG v1; Amendment 2; not confirmatory)
| Segment, definition | n | RF top 1 %: pre / placebo, ratio | RF top 5 %: pre / placebo, Δ [CI], ratio | Volume LR top 5 %: pre / placebo, ratio |
|---|---|---|---|---|
| S0, E1 | 700 | 28.7 / 13.7 %, 2.10 | 62.3 / 41.6 %, +20.7 [15.7, 25.3], 1.50 | 42.3 / 29.9 %, 1.42 |
| S1, E1 | 457 | 32.6 / 15.0 %, 2.17 | 63.7 / 42.9 %, +20.8 [15.2, 26.5], 1.49 | 41.0 / 30.9 %, 1.33 |
| S2, E1 | 177 | 44.2 / 23.3 %, 1.89 | 68.7 / 44.2 %, +24.5 [16.1, 33.9], 1.56 | 35.6 / 25.2 %, 1.41 |
| S1, E3 | 1,042 | 24.1 / 12.6 %, 1.92 | 56.6 / 31.8 %, +24.8 [21.0, 28.9], 1.78 | 39.9 / 25.1 %, 1.59 |
| S2, E3 | 431 | 37.3 / 14.5 %, 2.57 | 51.0 / 24.8 %, +26.2 [20.5, 32.0], 2.06 | 35.7 / 19.0 %, 1.88 |

- **Deduplication:** with C10 the ratios are similar or higher; for example S1 E1 top 5 %: 54.6 / 34.4 %, ratio
  1.59.
- **The contrast is much stronger than in the full universe** (E1 top 5 % ratio 1.14). But there is a
  confounder: segment membership depends on dollar volume at t, which rises before events. In the placebo window
  the stock is more often outside the segment and cannot be flagged.
- **E3 inflation:** E3 counts events whose move day, with its volume spike, is in the segment.
- **What a confirmatory test needs:** a membership-matched placebo.
- **Status:** a promising lead, not an established result.
