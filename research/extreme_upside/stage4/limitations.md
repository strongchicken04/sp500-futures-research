# Stage 4 — limitations and deviations

## Deviations from the Stage 4 protocol (all recorded as amendments)
1. **Amendment 1, QC data revision.** QC revised its historical daily data on 2026-11-25 (~15:45–16:15 UTC).
   - Effect: the identical code now builds 6,028,644 rows / 24,426 primary events instead of 6,022,604 /
     24,371.
   - Reproduction: exact reproduction of Stage 3 (C1) rests on S4AUDIT v1, built before the revision. All other
     Stage 4 numbers come from the revised panel, and S4AUDIT v2 quantifies the shift.
   - Persistence: the Stage 3 panel cannot be rebuilt bit-for-bit in QC any more. This is a property of the
     data vendor / platform, not of the code.
2. **Project reuse.** QC limits project creation to 50 per day. After that, runs reuse an existing project. The
   DIAG runs show the project has no effect.

## Data limitations
- **Daily bars only for outcomes.** The intraday order of HIGH and LOW within a day is unknown. Family-A
  excursions may be single prints. Minute data are audited only on samples (S4EXEC).
- **No official halt data.** The halt proxy is missing sessions inside a segment and segment splits at gaps
  > 10 market sessions.
- **Delisting / OTC continuation.** QC stops at exchange delisting. What a holder realised afterwards is
  unknown, so incomplete 20-session windows are counted (as segment end or data end), not valued.
- **Spreads.** Spreads are reported only where minute quote bars exist (S4EXEC sample). Otherwise no spread
  claim is made, and high-low ranges are not spreads.
- **Sample.** A 20 % fixed-hash sample of securities. Selections per day (top k %) refer to that sample; the
  full universe would have about 5× as many simultaneous names.
- **Old penny-stock data.** Probable bad prints in 2006–09. Not in the test period, but present in the
  training data of the frozen models.

## Method limitations
- **Event definitions** (see event_definitions.md):
  - E1 splits chained moves and absorbs nearby separate moves;
  - E2 merges moves separated by fewer than 10 quiet sessions;
  - E3 is sensitive to single extreme highs.
  - Results are therefore given for all of them.
- **Association window.** Onset − 10 .. last is a choice made in the protocol and not tuned. Longer horizons are
  covered by the lead-time windows up to 40 sessions.
- **Placebo window.** 31–40 sessions before onset, same security. It controls for "always-flagged" stocks but
  not for slow build-ups that start more than 30 sessions before an event.
- **Bootstrap.**
  - Poisson weights approximate the cluster bootstrap.
  - The two-way security × date scheme uses product weights, a standard approximation that is mildly
    conservative.
  - Per-period PR-AUC CIs use 300 resamples.
- **Frozen models.** The frozen models were trained on Family A only. Their B / B-max event evaluation measures
  transfer, not a model built for those targets.
- **Calibration experiment.** Uses the MODEL-split RF (trained to 2016), which is not the TEST refit.
