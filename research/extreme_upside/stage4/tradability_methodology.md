# Stage 4 — tradability, outcome and execution-data methodology

Code: `xup_s4_modes_c.py` (S4TRAD, S4FILT, S4EXEC), `xup_s4_modes_e.py` (S4OUTC) and `xup_s4_core.py`
(forward-path outcomes). This is a research-level feasibility study, not a trading simulation. No profit is
computed or claimed.

## Strata (values at prediction day t)
- **Raw price** (RAW close): < 0.10 / 0.10–0.49 / 0.50–0.99 / 1–2.99 / 3–4.99 / 5–9.99 / ≥ 10 $.
- **Dollar volume** (RAW close × RAW volume, day t): < 100k / 100–500k / 500k–1M / 1–5M / 5–10M / > 10M $.
- **ATR/price and realised volatility** (rv20): deciles with cut-offs from universe-A rows 2006-02 .. 2020-12.
  Test-period deciles are therefore not equal-sized; that shows the drift.
- **PIT market cap** (`lmcap`): the same decile rule. Missing (no Morningstar snapshot ≤ 40 days) is an 11th
  category.
- **Combined cells:**
  - px < 1 & $vol < 100k;
  - px < 1 & $vol ≥ 100k;
  - px 1–5 & $vol < 100k;
  - px 1–5 & $vol ≥ 100k;
  - px ≥ 5 & $vol ≥ 100k;
  - px ≥ 5 & $vol ≥ 1M (nested in the previous cell).
- **Per stratum (S4TRAD):**
  - test valid rows, positives, base rate;
  - top-1/5/10 % precision of the GLOBAL daily selection, counted inside the stratum;
  - E1 test events with onset in the stratum and their capture at top 1/5/10 %;
  - event precision of the stratum's signals;
  - median price and dollar volume;
  - missing-data coverage: share of rows with any missing full-A feature, and share without market cap.
- **Same population:** all strata use the same period (2021–2025), the same models and the same daily
  selection, so they differ only in population.

## Conservative liquidity filters (S4FILT)
- **Grid:** min price {0.10, 0.50, 1, 2, 5} $ × min dollar volume {100k, 250k, 500k, 1M, 5M}, plus each
  dimension alone and no filter (36 cells).
- **Procedure:** the filter is applied at prediction time, and the frozen RF scores are re-ranked inside the
  filtered universe each day.
- **Events:** E1 events whose onset row passes the filter.
- **Periods:**
  - validation 2017–2020, using the MODEL-split RF (trained to 2016 minus 60 days; scored from 2016-11-01);
  - test 2021–2025, using the TEST-split RF.
- **No filter is selected.** The pre-declared segments S0, S1 and S2 (protocol §7) are evaluated for C6.
- **Reported per cell:**
  - rows and events retained;
  - base rate; top-k precision; lift at 1 %;
  - capture at 1 / 5 % and pre-onset capture at 5 %; event precision at 1 %;
  - unique signals and unique events at 1 %;
  - median price and dollar volume of the top-1 % signals.

## Forward-path outcomes (S4OUTC)
- **Computation:** from the same adjusted daily bars, relative to adjusted OPEN(t+1), the earliest Stage 3 entry
  reference.
- **Quantities:**
  - max HIGH and max CLOSE over 10 / 20 sessions;
  - CLOSE at t+5, t+10, t+20;
  - min LOW over 10 / 20 sessions (adverse excursion);
  - day of the max HIGH;
  - first day reaching +50 / 100 / 200 % by HIGH;
  - first day with a +100 % CLOSE;
  - min LOW before the first +100 % day.
- **Incomplete windows** (segment end = delisting or data gap, or data end) give NaN. They are counted and
  split into "segment end" and "data end", never dropped silently. Daily data cannot show what a holder
  recovered after a delisting; that value is unknown.
- **Selected sets:**
  - all test rows (unconditional);
  - top 1 / 5 / 10 % of RF, price-only LR and volume-only LR;
  - RF top 1 % split into failures (A10/+100 = 0) and successes;
  - RF top 1 % re-ranked inside S1 (C7 flag).
- **Limitation:** daily bars cannot reconstruct the intraday path. A day's HIGH may precede its LOW or follow
  it, and both are reported per day only.

## Execution-data audit (S4EXEC)
- **Samples** (deterministic md5 of security id + date; nothing about them leaves QC):
  - 120 RF top-1 % test signals, examined on the entry day t+1;
  - 120 E3 test move days;
  - 60 control rows outside the RF top 10 %, examined on t+1.
- **Data:** QC minute history per item and day, with extended hours and RAW prices: trade bars and, where
  available, quote bars.
- **Measures:**
  - minutes with trades;
  - pre-market bars;
  - regular-session and first-30-minute dollar volume;
  - median quoted relative spread (ask − bid) / mid over regular-session minutes, also the first 30 minutes;
  - share of minutes with spread > 5 %;
  - whether the day's high was printed outside regular hours;
  - number of minutes trading within 5 % of the high;
  - share of volume at ≥ 90 % of the high.
- **Spreads** are reported only from quote bars; high-low ranges are never presented as spreads.
- **Limits:** a 40-minute runtime cap in QC; error counts are reported by exception type only, so no identifiers
  appear.
