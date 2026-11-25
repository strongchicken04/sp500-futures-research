# Stage 3C/3D — univariate review (development + validation years 2006–2020 only)

Source: `results/xup_s3_univ_raw.txt` (UNIV v1). Primary endpoint: Family A, h = 10, +100 %.

**Method:**
- Monthly cross-sectional deciles inside the universe.
- RR / OR CIs: 200 Poisson cluster-bootstrap resamples by security. AUC CI: 60 resamples.
- BH over the 18 primary tests.
- Blocks: 2006–09 / 2010–14 / 2015–19 / 2020.

**Status rule (protocol §5):**
1. BH-significant.
2. Expected sign, or a meaningful two-sided effect.
3. Consistent in ≥ 4 of 5 blocks.
4. Replicates in 2021–2025.

Criterion 4 is still OPEN: TEST has not run yet. Statuses below are therefore "in-sample only". None of them is a
claimed discovery.

| H | Variable [universe] | Top vs bottom decile RR [95 % CI] | q | AUC | Blocks (RR) | Sign vs expected | In-sample status |
|---|---|---|---|---|---|---|---|
| H1 | lmcap [B] | 0.01 [0.00, 0.01] | 0.006 | 0.135 | 0.02/0.00/0.00/0.00 | as expected (−) | passes 1–3 |
| H1s | lds [B] | 0.08 [0.05, 0.15] | 0.006 | 0.335 | 0.25/0.00/0.00/0.17 | as expected | passes 1–3 |
| H2 | rvol20 [A] | 0.94 [0.84, 1.01] | 0.169 | 0.483 | 1.16/1.00/0.76/0.81 | not + | **fails** (n.s.; U-shape: d1 0.64 %, d5 0.20 %, d10 0.60 %) |
| H2s | rvol5 [A] | 0.97 [0.91, 1.02] | 0.286 | 0.485 | 1.08/0.95/0.87/0.91 | not + | **fails** (U-shape) |
| H3 | si_ds [D] | 0.76 [0.41, 1.37] | 0.320 | 0.462 | –/–/1.04/0.66 | not + | **fails** (n.s.; only 2018–2020 available) |
| H3s | dtc [D] | 0.21 [0.12, 0.31] | 0.006 | 0.319 | –/–/0.21/0.21 | **opposite** | contradicts H3: LOW days-to-cover → more events |
| H4 | lfloat [C] | 0.04 [0.02, 0.09] | 0.006 | 0.294 | –/0.00/0.02/0.11 | as expected (−) | passes 1–3 (3 of 3 available blocks) |
| H4s | float_ds [C] | 0.45 [0.19, 0.84] | 0.036 | 0.410 | –/0.18/0.51/0.49 | as expected | passes 1–3, weak |
| H5 | atr_p [A] | 48.9 [34.3, 77.0] | 0.006 | 0.871 | 29.8/70.7/100.0/55.0 | as expected (+) | passes 1–3; the strongest variable |
| H5s | rv20 [A] | 61.7 [39.9, 105.1] | 0.006 | 0.850 | 34.6/164.5/111.1/71.8 | as expected | passes 1–3 |
| H6 | gap [A] | 1.39 [1.30, 1.48] | 0.006 | 0.540 | 1.35/1.38/1.44/1.37 | two-sided | significant but small; U-shape (d1 0.67 %, d10 0.93 %, middle ~0.12 %) |
| H6s | intraday [A] | 0.69 [0.65, 0.72] | 0.006 | 0.452 | 0.65/0.74/0.68/0.74 | two-sided | significant, small; both tails elevated |
| H7 | r20 [A] | 0.49 [0.44, 0.56] | 0.006 | 0.392 | 0.40/0.53/0.49/0.68 | **opposite** (+ expected) | contradicts H7 as stated: the 20-day losers (d1 1.18 %) beat the winners (d10 0.58 %); middle ~0.14 % |
| H7s | r5 [A] | 0.67 [0.61, 0.72] | 0.006 | 0.441 | 0.56/0.75/0.64/0.94 | **opposite** | as H7 |
| H8 | lpx [A] | 0.01 [0.00, 0.02] | 0.006 | 0.119 | 0.02/0.01/0.00/0.00 | as expected (−) | passes 1–3; d1 2.12 % vs d10 0.023 % |
| H8s | lpx_prev [A] | 0.01 [0.00, 0.02] | 0.006 | 0.119 | same | as expected | passes 1–3 (near-duplicate of H8) |
| H9 | ldv [A] | 0.03 [0.02, 0.05] | 0.006 | 0.242 | 0.03/0.01/0.02/0.10 | two-sided: strongly − | passes 1–3 |
| H9s | rdv20 [A] | 0.77 [0.69, 0.83] | 0.006 | 0.452 | 0.88/0.89/0.64/0.68 | two-sided | small; U-shape |

**Secondary endpoints:** 383 of 468 tests (18 variables × 26 targets) pass BH q < 0.05. They are descriptive only.
Signs agree across the A / B / B-max families for H1, H4, H5, H7, H8 and H9.

**H10 (combinations), descriptive quintile tables:**
- Low price × extreme relative volume: q1 price × q5 rvol20 = 1.73 %; q1 × q3 = 1.08 %.
- Losers × extreme relative volume: r20 q1 × rvol20 q1 = 1.00 %, q1 × q5 = 0.97 %.
- High ATR × low price: 1.97 % (n 500k, 9,853 positives).
- These are below the additive-logit expectation (5.24 %), i.e. sub-additive: high ATR and low price largely
  measure the same thing.
- The formal H10 test (GBM vs additive LR) is in MODEL.

**Interpretation limits (must be read with the table):**
1. **Collinearity and mechanics.** lpx, ldv, lmcap, lfloat, atr_p and rv20 are strongly correlated. Most of
   them proxy "sub-$1 / micro-cap / illiquid".
   - 41 % of primary events in A are below $1; the sub-$1 event rate is 2–6 % against 0.03–0.16 % above $5.
   - A +100 % move in a sub-$1 stock is a few ticks. These univariate effects are therefore NOT independent,
     and they are partly mechanical (tick size, discreteness, bad-tick highs).
   - The model stage measures incremental value.
2. **U-shapes.** rvol, gap, intraday, r5/r20, rdv20 and si_ds are U-shaped. The pre-registered top-vs-bottom
   contrast misses this, and it is kept as registered. The U-shape is a descriptive observation, not a tested
   hypothesis; testing it would be a new hypothesis for a later stage.
3. **H7 (momentum).** As pre-specified, H7 is contradicted in-sample: extreme LOSERS have the higher rate. This
   is consistent with distressed / reverse-split micro-caps and with bounce volatility, but that explanation is
   untested.
4. **H3 (short interest).** SI only exists from 2018. H3 has a single development block plus 2020, and its CI
   is wide. Low days-to-cover is more likely a liquidity proxy (high volume) than a squeeze signal.
5. **Time variation.** The event rate is strongly time-varying: A primary is 0.155 % in 2010–14 and 0.732 % in
   2023–25. RR blocks are computed within a block, so this does not drive the RRs, but it does matter for
   calibration in the test period.
6. **Data quality.** In 2006–2014, 22–29 % of A rows have a missing session in the last 20 days (miss20). This
   is mostly no-trade days of illiquid stocks in the older data, not real halts. The B-universe 2006–09 p90
   event return is 3,011 %, which signals possible bad prints in the old penny-stock data. Neither is a stop
   condition: labels use the same bars as features and Stage 2 checks passed. Both are documented as
   limitations.
