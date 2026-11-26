# Stage 4.5 — repository audit (state before Stage 4.5 runs)

Date: 2026-11-26. Branch `claude/strategy-replication-backtest-yppz7e`.

## 1. What already exists
| Area | Location | Content | Status |
|---|---|---|---|
| Stage 3 panel | `strategy/quantconnect/inqc/xup_s3_panel_inqc.py`, `xup_s3_const.py`, `xup_s3_modes_*.py`, `xup_ic_*.py` | Security-day panel built in QC: fixed-hash 20 % sample of US equities, adjusted/raw daily bars, features, labels A/B/M × h × threshold, universes A / A-strict / A-exADR / A-fund / B / C / D, Stage 3 models (RF, GBM, LR …) | frozen; not modified |
| Stage 4 extension | `xup_s4_core.py`, `xup_s4_modes_a..e.py` | `_security` wrapper adds Stage 4 path outputs (OUT: mh10, c5, c10, mc10, ml10, xr, t100, tc100 …), price/dollar volume, segments (SEG0/SEG1/GS), event builders E1/E2/E3 (`_s4_events`), frozen-RF refit + scoring (`_s4_score`), day ranks, bootstrap helpers (`_boot_W`, `_ap_sorted`, `_ci`, `_pval`), minute-data helpers (`_minute`, `_hsel`) | frozen; reused as-is |
| Stage 4 runner / collector | `strategy/quantconnect/run_s4.sh`, `s4_collect.py`, `deploy_long.py` | one QC backtest per mode, aggregates only (runtime statistics ≤ ~45 × 198 chars, log ≤ 10 KB), automatic VALID / INVALID verdict | reused; collector extended by an S45 CHECK requirement |
| Stage 4 results | `results/xup_s4_*_raw.txt`, `research/extreme_upside/stage4/*` | decision C (ranking real; timing not shown; outcomes negative on average; S1 lift 17–45×; spreads ≈ 1.1 % median) | input to Stage 4.5 |
| Canonical panel counts | Stage 4 Amendment 1 | 6,028,644 rows / 24,426 primary events (QC data revision handled) | checked in every run (S4 CHECK) |

## 2. What Stage 4.5 adds (new files only)
| File | Content |
|---|---|
| `inqc/xup_s45_core.py` | `_security` wrapper around the Stage 4 wrapper: 19 new trailing features, 22 forward-path outcomes (A/B/M/L by horizon, drawdowns, timing of min/max), 27 Family C codes; move-day events; ONSET_k labels; universes S0/S1/S2/S5M/A (+ suffix variants strict / h120 / price buckets); frozen-RF state percentile inside the universe + transition features; event-history features; timing-model training (L2 LR / LR / RF) on rolling-origin folds; signals; capture and placebo helpers; memory helpers |
| `inqc/xup_s45_modes_a.py` | S45AUDIT (events, labels, populations, denominators), S45FEATURE (leakage tests, coverage, exploratory univariate AUC on training only) |
| `inqc/xup_s45_modes_b.py` | S45MODEL (C2, row metrics, LOGO, 2026 diagnostic, other horizons, run-up diagnostic), S45PLACEBO (C3; unmatched and membership-matched) |
| `inqc/xup_s45_modes_c.py` | S45ROBUST (C8, S2 direction), S45GRID (price × dollar-volume grid, same-day rule), S45EXEC (minute quotes, s30) |
| `inqc/xup_s45_modes_d.py` | S45OUTCOME (Families A/B/B-max/C, C4, C5, C7, downside, Family A vs B/C, S2 lifts) |
| `run_s45.sh` | runner (temporary main copy with Stage 4 + 4.5 attachments) → `results/xup_s45_<mode>_raw.txt` |

No Stage 3 or Stage 4 array is modified: the S45 CHECK verifies on every row ≥ 2016-06 that the new path outcomes
equal the Stage 4 ones (A10 = mh10, B5 = c5, B10 = c10, M10 = mc10, L10 = ml10).

## 3. Constraints carried over
- All security-level data, event histories, scores and predictions stay inside QuantConnect; only aggregate
  statistics leave QC. No ticker, identifier or individual observation is written to the repository.
- QC ToS: no data exports (order-tag exports were flagged earlier); not circumvented.
- 1 CPU / 7.8 GB QC node (B-MICRO), files ≤ 32k characters, ≤ 50 new projects per day (runs use project 38061541).
- Prior exposure: 2021–2025 and 2026 YTD were examined in Stages 3–4 (protocol §0). Results are historical
  replication, not an untouched test.

## 4. Gaps identified before Stage 4.5 (and how they are addressed)
| Gap from Stage 4 | Stage 4.5 response |
|---|---|
| Timing vs persistent state not separated | two-stage design: frozen state (S1-P5), second-stage onset model vs the STATE ranking (C2) |
| Liquid-segment placebo lead confounded by membership | membership-matched placebo (C3) |
| Family A "events" often not held | capturable targets: B, B-max, adverse-constrained C (C4) |
| Downside negative on average | C5 downside criteria; payoff proxy with frozen cost formulas (C7) |
| Spreads measured only for RF top-1 % | S45EXEC on S1/S2 timing signals, controls, move days; s30 feeds the cost formulas |
