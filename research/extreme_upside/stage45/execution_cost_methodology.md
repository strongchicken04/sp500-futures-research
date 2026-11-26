# Stage 4.5 — execution and cost methodology

## 1. Minute-data samples (S45EXEC)
Hash-sampled (md5 of security id and date, fixed salts), test period 2021–25:

| Sample | n | Day examined |
|---|---|---|
| S1 L2 timing signals | 150 | entry day t+1 |
| S2 L2 timing signals | 80 | entry day t+1 |
| S1 conditional-population rows without signal (control) | 60 | t+1 |
| S1 E1 move days | 80 | τ |

- **Data:** QC minute trade bars (RAW) and quote bars, read inside QC. Times are New York local and refer to bar
  end times; the regular session is 09:31–16:00 bar ends.
- **Measured per item:**
  - relative quoted spread (ask − bid) / mid, as medians over regular-session minutes: full session, first 5,
    first 15 and first 30 minutes;
  - minutes to the first valid two-sided quote and to the first trade;
  - first-5/15/30-minute VWAP (typical price × volume) vs the first regular-session open;
  - regular-session and first-30-minute dollar volume;
  - price buckets $1–5 and ≥ $5.
- **Reported:** p25 / 50 / 75 / 90 across items, and coverage (items with trades or quotes).

## 2. Cost scenarios (formulas frozen in the protocol)
s30 = median first-30-minute relative quoted spread of the S1 timing-signal sample.

| Scenario | Round trip |
|---|---|
| optimistic | 1.0 × s30 + 0.10 % |
| **neutral** | 2.0 × s30 + 0.50 % |
| conservative | 3.0 × s30 + 1.50 % |

- **Rationale:** one spread is paid per round trip at mid-to-touch on both legs. The neutral scenario doubles it
  for size and adverse selection on volatile names, plus 0.5 % for slippage, fees and borrow / locate-free
  frictions. The conservative scenario adds a stressed early-session impact.
- **Procedure:** s30 is written into `xup_s45_core.py` (`S30`) by an amendment after S45EXEC and before
  S45OUTCOME. S45OUTCOME refuses to run (ERR statistic, INVALID) while `S30` is unset.

## 3. Limits
- Quoted spreads are not effective spreads. Size and impact are not observed; the scenarios bracket them.
- Samples are small (150 / 80 / 60 / 80), and percentiles at the tails are imprecise.
- Capacity (dollar volume at the open) is reported, not modelled.
