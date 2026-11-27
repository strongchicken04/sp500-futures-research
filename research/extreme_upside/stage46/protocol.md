# Stage 4.6 protocol: intraday continuation confirmation (H-next)

Pre-registered on 2026-11-27, before any Stage 4.6 run and before any intraday outcome of the entry rule was computed.

- Changes after this commit go to "Amendments" with date and reason.
- A change made after results are visible may not touch a primary endpoint, the primary rule, the costs or a
  decision criterion.

## 0. Exposure and status (disclosure)
- 2021–2025 was examined in Stages 3–4.5. The daily-bar outcomes of the same L2 signals are known:
  - next-open bracket payoff −2.96 % after neutral costs;
  - median close t+5 −3.4 %.
- The intraday H-next condition itself has never been computed. Stage 4.5 only sampled spreads and VWAP on 150
  signal days.
- The 2021–2025 result is a new, narrowly defined **historical replication**, not untouched out-of-sample
  confirmation.
- 2026-01-01 .. 2026-08-27 was also examined before. It is a diagnostic only.
- Genuine confirmation requires the prospective shadow log (§11) on data after 2026-08-27.

## 1. Hypothesis
**H-next:** take S1-P5 rows with a frozen L2 timing signal at the close of t. Enter on t+1 only after (a) a
completed regular-session minute bar trades above the session-t high AND (b) cumulative regular-session dollar
volume reaches $1,000,000, both within the first 30 minutes. This gives a positive mean payoff after the neutral
cost, and it beats the identical rule applied to frozen STATE signals.

## 2. Frozen inputs
- **Panel.** The canonical Stage 4.5 panel: 6,027,629 rows / 24,428 primary events.
  - S4 CHECK and S45 CHECK (3,094,930 rows ≥ 2016-06, 0 mismatches) must pass in every run.
  - Data end 2026-08-27; fixed-hash 20 % sample; 2,947 securities with data.
  - A further QC data revision invalidates runs. It would be handled by an amendment that fixes one canonical panel
    and reproduces the baselines.
- **Models.** Stage 4.5 code, unchanged and deterministic:
  - STATE = the frozen Stage 3 full-A RF score ranked daily inside S1 (TEST split from 2021; MODEL split before).
  - L2_FULL and LR_VOLU = Stage 4.5 specs fitted on the Stage 4.5 rolling-origin folds:
    - a: train ≤ 2020-12-31 − 60 d → 2021–22;
    - b: ≤ 2022-12-31 − 60 d → 2023–25;
    - c: ≤ 2025-12-31 − 60 d → 2026.
  - Hyperparameters are re-derived by the same code (train 2017–19, validate 2020). They must equal Stage 4.5:
    L2 C = 0.01, RF leaf = 100.
  - Nothing is refitted on test data. Nothing is tuned.
- **Population.** Stage 4.5 S1-P5 (`_s45_pop("S1", 0.05, "E1", 3, "trail")`):
  - raw close ≥ $1;
  - trailing 20-session median dollar volume ≥ $500k;
  - top 5 % of the state rank inside S1;
  - not within 10 sessions after a move day;
  - scored rows of 2021-01-01 .. 2025-12-31 (2026 for the diagnostic).
- **Reproduction check (S46AUDIT):**
  - L2 and STATE signal counts 2021–25 = 5,492 each;
  - population rows = 49,697 (Stage 4.5 OUTCOME G1);
  - hyperparameters as above.

## 3. Groups (signals at the close of t; per-day top 10 % = ceil(0.10 · n_day) of the S1-P5 population)
| Group | Definition | Role |
|---|---|---|
| **L2** | per-day top 10 % by frozen L2_FULL score | primary |
| **STATE** | per-day top 10 % by frozen state percentile (same daily count as L2) | critical comparator |
| **VOLU** | per-day top 10 % by Stage 4.5 LR_VOLU (STATE + volume-acceleration LR, same folds) | volume-only baseline |
| **CONTROL** | for each L2 row, one S1-P5 population row of the **same date** that is neither an L2 nor a STATE signal. Nearest in standardised (log raw close, log trailing median $vol, `atr_p`); matched without replacement within the date; ties broken by md5(security, date). No outcome or event information is used | matched control |

Market cap is not used: it exists only for part of the universe.

## 4. Data for the trigger and outcomes (inside QC only)
- **Daily raw OHLC per row** (QC daily RAW bars, the same series that built the panel), kept for rows
  ≥ 2020-06-01.
  - Reference level H_t = raw HIGH of session t (regular session daily bar).
  - Later-day OHLC for t+2..t+5 and the raw close of t+5 come from the same arrays.
- **Corporate actions.** The ratio adjusted close / raw close is stored per row. If it changes by more than 0.5 %
  between t and t+5, a split or dividend falls inside the window → **incomplete (corporate action)**: excluded from
  the complete-case analysis, counted, and included in the conservative sensitivity.
- **Minute data:**
  - QC minute TradeBars (RAW, regular hours only, fill-forward off) for session t+1, for every observation;
  - QC minute QuoteBars for session t+1, only for observations that trigger under any pre-registered variant;
  - minute TradeBars of a later session only to resolve a same-session double touch.
  - **Time convention:** bars are labelled by their end time, New York local (verified in Stage 4). The regular
    session is bar ends 09:31–16:00.
- **No minute coverage on t+1** (no regular-session trade bar) → "no minute data": counted, never a trade.

## 5. Primary trigger and entry (no look-ahead)
- **Bars and confirmation times.** For completed regular-session minute bars of t+1, in time order:
  - Breakout bar m_b = first bar with HIGH > H_t. The breakout is observable at the end of m_b.
  - Volume bar m_v = first bar at whose end the cumulative Σ close × volume (regular session, completed bars) is
    ≥ $1,000,000.
  - Confirmation m* = later of m_b and m_v.
  - **Trigger:** m* ends no later than 10:00 (first 30 minutes). Otherwise no trade.
- **Same-bar confirmation (m_b = m_v).** It is flagged "same-bar" and counted.
  - The entry is always after the end of m*, so it does not depend on the order of events inside that bar. Same-bar
    triggers therefore stay in the primary analysis. This follows the brief's requirement not to assume a favourable
    intra-bar order: no price inside m* is ever used.
  - Sensitivity: same-bar triggers excluded.
- **Entry price** = the first executable-price proxy after the end of m*:
  - **Quote-based (preferred):** the ask at the open of the first minute QuoteBar ending after m*, i.e. ask-open
    of bar m*+1, else its ask-close. Valid if bid > 0, ask ≥ bid and (ask − bid) / mid ≤ 20 %, within 2 minutes after
    m*.
  - **Minute-bar proxy (used only when no valid quote):** (OPEN + HIGH) / 2 of the first trade bar ending after m*.
    It never uses the bar low or the breakout level.
  - The primary entry is quote-based where valid, otherwise the minute proxy (flagged). These are price proxies, not
    fills.
- **Entry-time spread** s_trig = (ask − bid) / mid of the entry quote.

## 6. Primary endpoint: the frozen bracket from the entry price P_e
- **Levels:** target 1.30 · P_e (HIGH), adverse limit 0.90 · P_e (LOW), horizon through the close of session t+5.
- **Ordering:**
  - Session t+1: minute bars after the entry (the entry bar included, since the entry is at its open), in time
    order. A bar touching both levels = **ambiguous**.
  - Sessions t+2..t+5: daily raw bars.
    - OPEN ≥ target → target first (gap).
    - OPEN ≤ adverse limit → adverse first (gap).
    - HIGH ≥ target and LOW ≤ adverse limit in the same session → that session's minute bars resolve it; a bar
      touching both, or missing minute data, = **ambiguous**.
    - Otherwise the touched level, else continue.
- **Outcomes:**
  - target first;
  - adverse first;
  - ambiguous;
  - neither (exit at raw close t+5);
  - incomplete (t+5 beyond the segment or data end, corporate action, or missing daily bars).
- **Payoff, gross (frozen Stage 4.5 convention):**
  - target first +30 %;
  - adverse first −10 %;
  - **ambiguous −10 %** (conservative, as in Stage 4.5);
  - neither: close t+5 / P_e − 1.
- **Net payoff** = gross − round-trip cost (§7).
- **Primary metric:** mean neutral net payoff per triggered L2 signal, complete cases (2021–25).
- **Also reported per group:**
  - median net payoff;
  - win rate (net > 0);
  - outcome shares;
  - mean and median holding sessions;
  - MAE / MFE over the holding period, and touch shares of ±20 / 30 / 50 % over t+1..t+5 from P_e;
  - close returns at t+1, t+3 and t+5 from P_e;
  - net payoff percentiles p5 / p10 / p25 / p50 / p75 / p90 / p95.
- **Gap-realistic sensitivity:** a gap through the adverse limit exits at that session's open; a gap through the
  target is capped at +30 %.

## 7. Costs (frozen Stage 4.5, Amendment 6; s30 = 0.9479 %)
| Scenario | Round-trip cost | Role |
|---|---|---|
| optimistic | 1.0 · s30 + 0.10 % = 1.048 % | |
| **neutral** | 2.0 · s30 + 0.50 % = 2.396 % | **PRIMARY** |
| conservative | 3.0 · s30 + 1.50 % = 4.344 % | |

- The quote-based entry already pays the ask, so the frozen cost on top is conservative.
- **Quote-informed sensitivity:** cost_QI = 2 · s_trig + 0.50 % per observation (the neutral formula with the
  observed entry-time spread), on quote-valid observations.
- **Reported:** the s_trig distribution (p10 / 25 / 50 / 75 / 90) and gross and net results separately. Market impact
  is not measured.

## 8. Denominators and selection analysis (per group)
1. Eligible signals.
2. Minute coverage on t+1.
3. Breakout within 30 minutes.
4. $1M within 30 minutes.
5. Both (= triggered).
6. Valid quote-based entry.
7. Any entry price.
8. Complete bracket outcome.

**Triggered vs non-triggered:** price, trailing $vol, `atr_p`, run-up xr, first-30-min $vol.

**Triggered only:** move from the prior close to the entry, distance from H_t to the entry, s_trig, entry time.

**Decomposition:** the triggered subset entered at the next open (daily Stage 4.5 bracket) vs entered at the trigger;
all L2 signals at the next open (Stage 4.5 baseline).

## 9. Statistics
- **Security-cluster Poisson bootstrap**, 2,000 replicates, seed 4601.
- **Two-way security × date bootstrap**, 2,000 replicates, seeds 4602 / 4603.
- **Paired comparisons** (L2 − STATE, L2 − CONTROL, L2 − VOLU): both group means are recomputed on the same
  replicate weights (joint resampling of securities, and of dates for two-way). The difference CI is the 2.5–97.5
  percentile. The p-value is two-sided: 2 · min(share ≤ 0, share ≥ 0).
- **CIs** for mean net payoff, target-first and adverse-first rates, trigger rate (security bootstrap).
- **Dedup (pre-specified):** within a group, a triggered signal is dropped if the same security had a triggered
  entry in the previous 5 sessions.
- **Power:** if the triggered complete L2 sample is below 300, results are reported as underpowered.

## 10. Secondary analyses (computed only after the primary result is recorded in the same run; exploratory)
- **Sensitivities** (L2; same bracket and costs), each changing one element only:
  - volume threshold $0.5M / $2M / $5M (window 30 min);
  - window 5 / 15 / 60 min ($1M);
  - breakout = first completed bar CLOSING above H_t (30 min, $1M).

  Seven variants plus the primary. BH at q = 0.05 over the seven p-values (H0: mean neutral net = 0, security
  bootstrap). No variant can change the decision.
- **Robustness** (primary rule):
  - 2021–22, 2023–25; leave-one-year-out (2021..2025);
  - A-strict (subset without unresolved instrument classes);
  - 10 hash security groups, leave-one-out;
  - top-10-security contribution removed;
  - quote-valid-only; minute-proxy-only; same-bar excluded;
  - conservative ambiguous / incomplete;
  - gap-realistic; quote-informed cost;
  - E1 diagnostic: share of triggered signals with an E1 move day in t+1..t+3, and payoff by that split. Diagnostic
    only, never used to select.
- **S46ROBUST** (separate run): the primary rule on S2-P5 L2 and STATE signals (2021–25), and on S1-P5 L2 and STATE
  signals 2026 YTD (fold c; diagnostic).

## 11. Prospective shadow log
- **Mode S46SHADOW.** It builds the panel through the current QC data end and uses the frozen models (fold c L2,
  TEST-split RF). For every session after 2026-08-27 it applies the primary rule to that day's S1-P5 L2 and STATE
  signals and records, per observation, inside QC only (ObjectStore key `xup_s46_shadow/<date>`, written once, never
  overwritten):
  - signal date;
  - H_t;
  - trigger time;
  - entry proxy and its type;
  - s_trig;
  - bracket outcome;
  - frozen neutral net payoff;
  - a model fingerprint (hash of the L2 coefficients and of the RF score on a fixed probe set).
- **Output:** aggregates only. No orders, no broker connection.
- **Status:** with the current data end there are no prospective sessions. The framework is built and tested, and it
  must be re-run as QC data extend.
- **Minimum prospective sample** (to be reported from the historical trigger rate):
  n = ((1.645 + 0.842) · σ / δ)², with σ = historical SD of the L2 triggered neutral payoff and δ = 2.0 pp (smallest
  effect of interest), one-sided α 0.05, power 0.80. Duration = n / (historical triggered L2 signals per session).

## 12. Decision gate (primary rule, L2, 2021–25, complete cases, neutral cost)
- **G1** mean net payoff > 0.
- **G2** 95 % CI lower bound > 0, under both the security-cluster and the two-way bootstrap.
- **G3** L2 − STATE mean net payoff difference ≥ +1.0 pp, with the paired security-bootstrap CI lower bound > 0.
- **G4** not driven by few securities or one period. All of:
  - point estimate > 0 in 2021–22 and in 2023–25;
  - > 0 in every leave-one-year-out;
  - > 0 after removing the top-10 contributing securities;
  - > 0 in every leave-one-security-group-out.
- **G5** point estimate > 0 under the conservative treatment (incomplete and corporate-action cases = −10 % − cost;
  ambiguous already −10 %).
- **G6** valid quote-based entry for ≥ 80 % of triggered L2 signals, and the quote-valid-only mean net payoff > 0.
- **G7** the decision uses only the primary rule. No secondary variant can satisfy G1–G6.

**Mapping:**
- **C (inconclusive)** if the data are inadequate: triggered complete L2 observations < 300, or valid entry prices
  (quote or minute) for < 50 % of triggered L2 signals.
- **Else B (not supported)** if any of:
  - G1 fails (mean ≤ 0);
  - G3 fails;
  - adverse first > target first + neither;
  - G4 or G5 fails.
- **Else C** if G2 fails (positive but uncertain) or G6 fails (execution quality).
- **Else A** (all of G1–G7): justifies only a controlled execution study, never a strategy claim.

## 13. Runs
| Run | Content |
|---|---|
| S46AUDIT | reproduction of the frozen counts, group construction, matched-control balance, minute and quote coverage audit on a hash sample (no outcome computed) |
| S46MAIN | all of §5–§10 for L2 / STATE / VOLU / CONTROL 2021–25 |
| S46ROBUST | S2 and 2026 |
| S46SHADOW | framework |

All runs go to `results/xup_s46_<mode>_raw.txt` with an automatic VALID / INVALID verdict. Invalid runs are kept.

## Amendments

### Amendment 1 (2026-11-27 ~21:50 UTC, after S46AUDIT v1, before any outcome) — third QC data revision; canonical Stage 4.6 panel
- **Observation.** S46AUDIT v1 (backtest b3a06dff…) ran with unchanged code. It built a different panel:

  | Quantity | Stage 4.5 canonical | S46AUDIT v1 |
  |---|---|---|
  | Hash-sample securities | 2,986 | 2,989 |
  | Securities with data | 2,947 | 2,949 |
  | Rows | 6,027,629 | 6,030,760 |
  | Primary events | 24,428 | 24,429 |
  | Segments | 3,541 | 3,543 |
  | QC data points | — | 84,631,056 |

  - QC added securities to its universe and revised history.
  - The run is INVALID (count checks) and kept.
- **Why not restrict to the old security set.** The old panel cannot be rebuilt: it would need the list of security
  identifiers, which must not leave QC. Following the brief ("do not mix versions"), one new canonical panel is fixed
  for all of Stage 4.6:
  - **6,030,760 rows / 24,429 primary events**;
  - S45 CHECK on 3,098,061 rows ≥ 2016-06.

  All Stage 4.6 runs require exactly these counts.
- **Effect on the frozen pipeline** (seen in v1):
  - S1-P5 population 49,802 rows (S4.5 49,697);
  - L2 / STATE / VOLU signals 5,497 each (S4.5 5,492);
  - L2 C = 0.01 unchanged;
  - the RF timing model's leaf choice moved from 100 to 20, which is irrelevant: the RF timing model is not used in
    Stage 4.6.
- **Baseline reproduction on the new panel**, added to S46MAIN (line M0b) before the intraday outcomes:
  - the Stage 4.5 C2 capture (L2 vs STATE);
  - the next-open neutral payoff of all L2 signals;
  - L2 event precision.

  These are reported next to the Stage 4.5 values (69.3 / 26.7 %, −2.96 %, 7.19 %).
- **Seen before this amendment:** only counts, group balance and the minute / quote coverage audit (no trigger, no
  outcome).
- S46AUDIT is repeated as v2 on the new canonical panel.
- No hypothesis, endpoint, threshold, cost or criterion changes.
