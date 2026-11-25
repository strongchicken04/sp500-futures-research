# Stage 3 — feature availability and leakage audit (deliverable 1)

All features are computed inside QC by `strategy/quantconnect/inqc/xup_s3_panel_inqc.py`.

**Common rules for every feature:**
- Daily bars come from `history(..., fill_forward=False)`. A bar dated t is the session of day t, stamped at
  16:00 ET (precise end time), so it is known at the close of t.
- Every window is trailing and includes t, and none crosses a segment boundary (gap > 10 market sessions).
- Relative features (returns, distances, ratios) use QC ADJUSTED prices: ratios only, never levels.
- Level features (price, volume, dollar volume, strata) use RAW prices and volumes of t.
- Empirical leakage unit test (AUDIT mode, A4):
  - For 12 random securities and 2 dates each, every feature at t is recomputed from data truncated at t and
    compared with the full-data value.
  - Any difference beyond float rounding means the feature uses data after t, and the feature is then rejected.

## Price / momentum / volatility (universe A; source QC daily OHLCV, AlgoSeek)

| Feature | Definition (t = decision close) | Window | Missing treatment | Look-ahead risk |
|---|---|---|---|---|
| r1 r2 r3 r5 r10 r20 | log adj close change over k sessions | k+1 sessions | NaN when fewer sessions in the segment (eligibility needs ≥ 20 prior, so only r20 at the edge) | none |
| dhi5/10/20/60 | adj close / max adj high over the last k sessions − 1 | k | NaN when fewer than k sessions | none |
| dlo5/20/60 | adj close / min adj low over the last k − 1 | k | as above | none |
| up_streak, dn_streak | consecutive up / down closes ending at t | ≤ segment | 0 at segment start | none |
| gap | adj open(t) / adj close(t−1) − 1 | 2 sessions | NaN on the first bar | none (open of t is known at the close of t) |
| intraday | close(t) / open(t) − 1 | 1 | — | none |
| clv | (close − low) / (high − low); 0.5 if high = low | 1 | — | none |
| rv5/10/20 | std of daily log returns | k | NaN if fewer than k | none |
| atr_p | 14-session mean true range (adj) / adj close | 15 | NaN if fewer than 14 | none |
| range_p | (high − low) / close | 1 | — | none |
| lpx, lpx_prev | log raw close of t, of t−1 | 1–2 | NaN if raw close ≤ 0 | none (raw = as traded) |
| pstrat | raw close < $1 / $1–5 / > $5 | 1 | — | none |

## Volume / liquidity (A)

| Feature | Definition | Window | Missing | Risk |
|---|---|---|---|---|
| lvol | log(1 + raw volume of t) | 1 | — | none |
| rvol5/10/20 | adj volume(t) / mean adj volume(t−k .. t−1) | k+1 | NaN if the base is 0 or too short | none |
| ldv | log(1 + raw close × raw volume) | 1 | — | none |
| rdv20 | dollar volume(t) / mean(t−20 .. t−1) | 21 | NaN if the base is 0 | none |
| vtrend | mean adj volume 5 / mean 20 | 20 | NaN if too short | none |
| pv | r1 × log(rvol20) | 21 | NaN with rvol20 | none |
| zero20 | any zero-volume day in the last 20 sessions | 20 | — | none |
| miss20 | any missing market session (halt / suspension proxy) in the last 20 sessions | 20 | — | none |

## Point-in-time fund-likeness flag (A-fund sensitivity only)

`fundlike`:
- Definition: idiosyncratic volatility vs SPY < 0.006 and share of |r| > 8 % ≤ 0.025.
- Window: trailing 120 sessions; SPY returns are taken on the same session dates.
- Missing: NaN for fewer than 120 sessions; NaN means not flagged.
- Calibrated in Stage 2 (44 % fund recall, 1.5 % of common stocks flagged).
- Look-ahead risk: none. Only the threshold calibration used labelled data, and it does not use outcomes.

## Market cap / PIT shares (B; source Morningstar via the QC Fundamental universe)

**Snapshot timing:**
- A snapshot is the weekly Fundamental record at 00:00 of the snapshot date. It holds market cap, raw price,
  shares outstanding and float as known before that day's open.
- A row at t uses the latest snapshot dated ≤ t, and only if that snapshot is ≤ 40 days old.

| Feature | Definition | Missing | Risk |
|---|---|---|---|
| lmcap | log(snapshot market cap × adj close(t) / adj close of the last session before the snapshot) | NaN without a fresh snapshot (row leaves B) | low. Market cap is PIT (Stage 1–2 checks). Scaling by the adjusted price ratio handles splits after the snapshot; the dividend part of the adjustment is negligible. |
| lds | log(PIT market cap / raw close(t)) = PIT shares | as above | low. Validated in Stage 2: 90 % within 5 % of SO × split factor; jumps on the ex-date in 83 % of splits. |
| dds250 | DS(t) / DS(t − 250 sessions) − 1 (issuance / buybacks) | NaN if no DS 250 sessions earlier | low |
| mstrat | PIT market cap < $50M / 50–300M / 0.3–2B / > 2B | with lmcap | low |

**Never used:** current market cap, Morningstar SharesOutstanding or Float as levels (restated for later
splits), delisting date / reason, share class status.

## Float (C, 2011–; uncertain — Stage 2 section 4.2)

| Feature | Definition | Missing | Risk |
|---|---|---|---|
| float_ds | Morningstar Float / SharesOutstanding from the snapshot | NaN if either is ≤ 0 | the ratio is stale (updated with 22 % of SO changes) and inconsistent in cases (AMC); definitional (large holders excluded) |
| lfloat | log(float_ds × DS(t)) | with float_ds | as above |
| fratio_age | days since the ratio last changed (snapshot history ≤ t) + snapshot age | — | none |
| ds_mismatch | the snapshot's DS moved > 50 % against a split implied by raw / adj prices between snapshots (Stage 2 FS check) | — | none |
| f_implaus | float_ds < 0.1 or > 1.01 | — | none |

## Short interest (D, 2018-01-11 .. 2026-08-27; source FINRA via QC)

**Availability:**
- A record is available on its QC delivery date (end_time, 00:00). That is ≥ 1 trading day after FINRA
  publication (Stage 2 V4).
- The row at t uses the latest record delivered ≤ t. No extra delay is added.

| Feature | Definition | Missing | Risk |
|---|---|---|---|
| si_ds | short interest / PIT shares (DS from B; NaN outside B) | missing if value age > 35 days, a duplicate-record day, or not delivered for 5 days | none known |
| dtc | FINRA days to cover | as above | none |
| si_chg | short_interest / previous_short_interest − 1 | as above | none |
| si_age | days since the value last changed | — | none |
| si_amb | latest delivery day had duplicate records with different values | — | none |
| si_miss | no usable value at t (defines D) | — | none |

## Labels (never used as features)

A / B / B-max for h ∈ {5, 10, 20} and thr ∈ {50, 100, 200 %}. The reference is adj open(t+1). The labels are
the only quantities that use data after t.

## Coverage (filled from the AUDIT run)

See `results/xup_s3_audit_raw.txt` (section FEATURE COVERAGE) and the Stage 3 report.
