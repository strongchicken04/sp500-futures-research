# Stage 4 — data availability audit

Status of every data item that the Stage 4 brief asks about, as verified in QC. The minute and quote rows are
filled from the S4EXEC runs (`results/xup_s4_exec_raw.txt`, v1 and v2).

| Item | Available in QC for this panel? | Verified how | Used in Stage 4 |
|---|---|---|---|
| Daily OHLCV, adjusted + raw (AlgoSeek) | yes, 2005-10 .. 2026-08-27 | Stages 1–3; S4AUDIT reproduces Stage 3 exactly | all modes |
| Segment / gap structure | yes (derived) | 3,541 segments in the 2,947-security sample (S4AUDIT) | event clock, association, dedup |
| Forward-path outcomes (max / min / close at t+5 / 10 / 20, threshold days) | yes (derived from daily bars) | `mh10` equals Stage 3 `R` on every row: 6,022,604 rows (S4AUDIT v1) and 6,028,644 rows (every revised-panel run), 0 mismatches | S4OUTC, events |
| Zero-volume days | yes (`zero20` feature, raw volume) | Stage 3 feature audit | strata, coverage |
| Missing-session flag (halt / no-trade proxy) | yes (`miss20`) | Stage 3 feature audit | strata |
| Official trading halts | **no** | Stage 1 audit: no halt dataset in QC | the halt proxy is missing sessions only |
| Daily high-low range | yes | — | reported as a range, never as a spread |
| Minute trade bars, regular session | **yes**, for 88–90 % of sampled days (105 / 120 signal entry days, 107 / 120 move days, 54 / 60 controls) | S4EXEC v1 / v2; NY-local time stamps; minute $vol ≈ daily bar $vol (median ratio 1.00–1.06) | S4EXEC |
| Pre-market / after-hours minute bars | **yes** (bars 04:00–20:00 present for the same items) | hour-of-day histogram (S4EXEC v2) | S4EXEC |
| Minute quote bars (bid / ask) | **yes**, for the same 88–90 % | `history(QuoteBar, …)`; median spread 1.06 % on signal entry days, 0.17 % on controls | S4EXEC (spreads reported) |
| Tick-level quotes / depth | not requested (too heavy for 1 CPU, and not needed to answer feasibility) | — | — |
| Delisting price / recovery value | partial: QC stops at exchange delisting with the LEAN delisting price; OTC continuation is not covered | Stage 2 V2 | incomplete outcome windows are counted, not valued |
| PIT market cap | yes, weekly snapshots (≤ 40 days old) | Stage 2–3 | market-cap strata (68 % coverage on A rows) |
| SPY, IWM daily (regime variables) | yes | S4CONC | regimes |

## Consequences
- **Halts:** official halts are not observable. The halt proxy is missing sessions inside a segment, plus the
  segment split at gaps > 10 market sessions.
- **Spreads:** minute quote bars exist, so spreads are measured from quotes on the hash samples. A full-population
  spread model is a Stage 5 task.
- **Delistings:** after a delisting, the realised liquidation value is unknown. Downside statistics therefore
  report incomplete 20-day windows separately ("segment end"); they are not imputed.
