# Extreme upside moves — Stage 4 protocol (pre-registered before any Stage 4 result)

Written 2026-11-26, before the first Stage 4 QC run. Later changes go into "Amendments" with date and reason.
The Stage 3 specification stays frozen: frozen commit `1249e43`, test output `ff1081f`, final Stage 3 commit
`991c7f0`. Stage 4 adds evaluation definitions only. It never changes Stage 3 labels, features, models,
universes or results.

## 0. Scope and confirmatory status
- **Confirmatory:** the Stage 5 decision criteria in §9, evaluated on 2021–2025 with the frozen Stage 3 models.
- **Exploratory and descriptive:** everything else, including 2026 YTD (2026-01-01 .. 2026-08-27).
- **No tuning.** Nothing is tuned on 2021–2025 or 2026. Any choice that needs data (none is planned) uses
  development / validation only.

## 1. Inputs reused unchanged
- Panel: `xup_s3_panel_inqc.py` with the same fixed-hash 20 % sample, universes, labels and features.
- **Stage 4 extension.** A wrapper around `_security` recomputes extra quantities from the same bars, after the
  Stage 3 row is built. It never changes an existing array. The extra quantities are:
  - segment id and market-session index;
  - forward-path outcomes;
  - path-excursion flags.
- Every Stage 4 run checks that the panel still has 6,022,604 rows and 24,371 primary events, and that the
  outcome `mh10` equals the Stage 3 return array `R`. A failed check invalidates the run.
- Models: the frozen SPECS of `xup_s3_modes_m.py`, refit with the TEST split exactly as in TEST v1 / ROBUST v1:
  same code, same seeds, training rows on A up to 2020-12-31 minus 60 days. This is deterministic: ROBUST v1
  reproduced TEST v1. The validation-period scores come from the MODEL split (training 2006-02 .. 2016-12 minus
  60 days).
  - Primary model: full-A RF.
  - Comparators: volume LR, price LR, momentum LR, full-A LR, full-A GBM.

## 2. Scores and daily selection
- **Scored rows:** universe A, dates 2020-11-02 .. 2026-08-27. These rows are after the purged training end.
- **Stage 4 daily ranking (S4-rank):**
  - each day, all eligible rows of the evaluated universe are ranked, whether or not their future label is
    valid. Label validity is future information.
  - top k % = the ceil(k · n_day) highest scores, ties broken by row order. k ∈ {1, 5, 10} %.
- **Stage 3 ranking (S3-rank):** only valid-label rows are ranked, exactly as in Stage 3. It is used only to
  reproduce the Stage 3 metrics in the audit.
- **Universe sensitivity:** rows are re-ranked inside each universe or filter, as in Stage 3 ROBUST.

## 3. Event definitions (retrospective labels, never features)
- **Sessions** are the security's consecutive eligible bars inside one segment. This is the clock the labels
  use; segments split at gaps > 10 market sessions.
- **h = 10.** The primary family is A10/+100 %. B10/+100 % and B-max10/+100 % are separate populations and are
  never combined.
- **E1 — Stage 3 episode rule, reproduced exactly as `_episodes`:**
  - positive rows are ordered by security and date;
  - a new episode starts when the security changes, or when the row distance to the episode's start is ≥ 10.
  - E1 counts row distance and does not check segment boundaries. It therefore reproduces Stage 3 exactly,
    including that quirk.
- **E2 — merged forward windows:**
  - a positive day t opens the window [t+1, t+10];
  - the next positive day of the same segment joins the event if it falls inside the current window, and the
    window end becomes max(end, t'+10). So long runs chain into one event;
  - a new event starts only after the window has expired.
- **E3 — price-path excursions, independent of the label rows:**
  - day τ is an excursion day if adjusted HIGH(τ) ≥ 2 × min adjusted OPEN over the sessions [τ−9, τ] of the
    same segment;
  - excursion days of a segment that are ≤ 10 sessions apart form one event;
  - the event's **move day** is its first excursion day, and its reference price is that minimum open;
  - E3 timing is measured relative to the move day.
- **E4 — close-confirmed populations:** E1 and E2 applied to the B10/+100 % and B-max10/+100 % labels.
- **Event attributes:**
  - E1 / E2 onset = first positive row; last = last positive row. E3 onset = move day.
  - Duration (rows), number of positive rows, maximum Family-A return over the event's positive rows.
  - Close confirmation: any B10/+100 or B-max10/+100 positive among the event's rows.
  - Raw price, dollar volume and period at onset.
  - **Incomplete:** an invalid label (−1), or the segment end, within 10 rows after the last positive row. Such an
    event might have continued.
  - **Ambiguous:** an E1 episode that E2 would merge with its neighbour (E1 split a chained run).

## 4. Event-level evaluation (test events = onset 2021-01-01 .. 2025-12-31)
- **Association:** a selected row (signal) belongs to an event of the same segment if it lies in
  [onset − 10, last].
  - Pre-onset part: [onset − 10, onset − 1]. In-event part: [onset, last].
  - Rows in both a pre-window and an earlier event's in-event range are assigned to the in-event range.
  - Signals are associated with events of any onset date, so there are no boundary artefacts at 2020/2021 and
    2025/2026.
- **Capture** (per model, k, definition): share of test events with ≥ 1 signal in the association window.
  - Split into pre-onset capture (≥ 1 signal before onset) and in-event-only capture.
  - The rest have no signal at all.
- **Event precision:**
  - share of signals (test rows) associated with any event;
  - unique captured events per signal;
  - unassociated signals per captured event;
  - repeated signals per captured event;
  - share of signals that repeat an already-flagged event;
  - securities with ≥ 2 signals and no event.
- **Event ranking:**
  - an event's pre-score is the maximum daily percentile rank in its pre-onset window;
  - its placebo score is the same quantity in [onset − 40, onset − 31] of the same security (within-security
    control);
  - reported: median pre-score; share of events where pre-score > placebo score; the event-vs-placebo AUC.

## 5. Deduplication rules (per security, in date order, using only past information)
- **N0:** all signals (benchmark).
- **C10 / C20:** keep a signal only if no kept signal exists in the previous 10 / 20 sessions.
- **CW:** keep a signal only if there was no selection at all, kept or not, in the previous 10 sessions. A new
  signal episode starts after 10 quiet sessions.
- **CE:** keep only the first signal per associated event, plus C10 for unassociated signals. CE uses future
  event information, so it is a retrospective benchmark only and is never deployable.
- **Reported per rule:** signals, captured events, capture, event precision, false signals, repeats removed,
  lead-time quantiles, signals per year. No rule is selected on the test.

## 6. Lead time
- **Windows before onset:** 1–2, 3–5, 6–10, 11–20 and 21–40 sessions. A window cut by the segment start or by
  the scoring start counts as "no data" and is reported.
- **Reported per window:** share of events with ≥ 1 top-k signal in the window. Also: before onset (1–40),
  in-event only, none in [onset − 40, last].
- **Families:** A, B and B-max with E1, plus E3 relative to the move day.
- **First-signal lead:** sessions from the first signal in [onset − 40, onset − 1] to onset.
- **Lead and magnitude** (k = 1 % and 5 %): groups pre-signal (1–10), in-event-only and none, plus lead buckets.
  Compared on:
  - maximum Family-A return;
  - close confirmation;
  - adverse move before the target = min adjusted LOW from onset+1 up to the first +100 % day / reference − 1;
  - raw price and dollar volume at onset.

## 7. Tradability, outcomes, robustness, concentration
- **Strata:**
  - raw price at t: < 0.10 / 0.10–0.49 / 0.50–0.99 / 1–2.99 / 3–4.99 / 5–9.99 / ≥ 10 $;
  - dollar volume at t: < 100k / 100–500k / 500k–1M / 1–5M / 5–10M / > 10M;
  - ATR/price, realised-vol (rv20) and PIT market-cap deciles. Cut-offs come from 2006–2020 rows, never the
    test; market cap missing is its own category;
  - six combined price × dollar-volume cells, as in the brief.
- **Signals inside strata:** selected by the global S4-rank, then counted inside each stratum.
- **Filters:** min price {0.10, 0.50, 1, 2, 5} × min dollar volume {100k, 250k, 500k, 1M, 5M}.
  - Rows are re-ranked inside the filtered universe.
  - Each filter is reported on validation (MODEL-split RF) and test (TEST RF).
  - No filter is chosen.
- **Pre-declared tradable segments for §9:**
  - S0: price ≥ 1 $ and dollar volume ≥ 100k;
  - S1: price ≥ 1 $ and dollar volume ≥ 500k;
  - S2: price ≥ 5 $ and dollar volume ≥ 1M.
- **Outcomes** of selected rows, from the same bars; adjusted ratios relative to adjusted OPEN(t+1):
  - maximum high or close return over 10 / 20 sessions;
  - close at t+5 / t+10 / t+20;
  - minimum low over 10 / 20 sessions (adverse);
  - time to the maximum, and first day hitting +50 / 100 / 200 %;
  - an incomplete window (delisting / segment end / data end) is reported as its own category, never dropped.
- **Execution data:** audited in QC (minute trade bars, extended hours, minute quote bars) on deterministic
  hash samples of signals and move days. Spreads are claimed only if quote data exist.
- **Robustness:** event-level metrics for universes A, A-strict, A-ex-ADR, A-fund and B (re-ranked inside each
  universe) × families A, B and B-max.
- **Concentration and regimes:**
  - regime variables use past data only: SPY 20-day realised vol, IWM 20-day return, cross-sectional median r20
    of the panel;
  - tercile cut-offs come from 2006–2020.

## 8. Statistics
- **Bootstrap:** Poisson cluster resampling by security, fixed seeds.
  - 2,000 resamples for the primary paired model comparisons;
  - a two-way security × date bootstrap (product weights) for the main comparisons with ≥ 1,000 resamples where
    run time allows;
  - event-level metrics: 2,000 resamples by security.
- **Paired differences** on the same rows / events: RF − volume LR, full-A LR − volume LR, GBM − volume LR,
  full models − price LR, full models − momentum LR. Model differences are never inferred from overlapping or
  non-overlapping individual CIs.

## 9. Stage 5 decision criteria (confirmatory, fixed now)
- **C1 Reproduction:** RF and volume-LR test PR-AUC, P@1/5/10 %, R@10 %, base rate, positives and rows
  reproduce TEST v1 exactly (S3-rank).
- **C2 Discrepancy:** the Stage 3 1,296 vs 1,263 discrepancy is reconciled from code and output.
- **C3 Event-level evaluation:** completed for E1, E2 and E3.
- **C4 Pre-event signal (E1, family A, RF, top 5 %).** Both must hold:
  - (a) pre-onset capture in sessions 1–10 is ≥ 20 % of test events;
  - (b) it exceeds the same-length placebo window [onset − 40, onset − 31], with a paired event-level
    bootstrap 95 % CI of the difference above 0 and a ratio ≥ 1.5.
- **C5 Robust across definitions:** C4 also holds for E2, and for E3 relative to the move day (window
  move − 10 .. move − 1 vs move − 40 .. move − 31).
- **C6 Tradability:** inside S1 (re-ranked), RF top-1 % primary precision ≥ 3 × the S1 base rate in validation
  AND test, with ≥ 100 E1 test events in S1, and top-5 % event capture in S1 ≥ 30 %.
- **C7 Downside:** outcome distributions for the RF selections are quantified, failures included. Information
  only, plus a flag:
  - FLAG if, among RF top-1 % selections in S1, the share with close(t+10) ≤ −50 % exceeds the share reaching a
    +100 % close in the window.
- **C8 Uncertainty:** paired bootstrap with ≥ 1,000 resamples completed for the primary comparisons.
- **C9 Integrity:** no unresolved data-integrity defect.

**Decision mapping:**
- **A (proceed):** C1–C9 pass, S1 passes C6 and C7 is not flagged.
- **B (proceed with restrictions):** C1–C5, C8 and C9 pass, S1 fails C6 or C7 is flagged, but S2 or S0 meets the
  C6 conditions. The simulation would be restricted to that segment.
- **C (further research):** C4 or C5 fails, while the row-level ranking lift persists and C1, C2, C9 pass.
- **D (do not proceed):** C1, C2 or C9 fails; or pre-onset capture is not above placebo AND ≥ 80 % of captured
  events are captured only in-event; or S0, S1 and S2 all have top-1 % precision < 2 × their base rate in test.
- A positive decision only justifies a separate trading simulation. It says nothing about profitability.

## Amendments
(none yet)
