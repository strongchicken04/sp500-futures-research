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
3. **Amendment 2.** S4XSEG (exploratory) and S4EXEC v2 (diagnostics) were added after results were seen. Neither
   can change the decision.
4. **Failed and invalid runs, kept in the raw files.**
   - S4CALIB v1 ended in QC without producing any output; the status stayed "In Progress". It was re-run as v2
     and that run was valid.
   - S4EVENTS v1 and S4EVAL v1-orphan were built on the revised panel before Amendment 1, so the check marked them
     invalid. They are identical to the valid v2 runs.

## Data limitations
- **Daily bars only for outcomes.** The intraday order of HIGH and LOW within a day is unknown. Family-A
  excursions may be single prints. Minute data are audited only on samples (S4EXEC).
- **No official halt data.** The halt proxy is missing sessions inside a segment and segment splits at gaps
  > 10 market sessions.
- **Delisting / OTC continuation.** QC stops at exchange delisting. What a holder realised afterwards is
  unknown, so incomplete 20-session windows are counted (as segment end or data end), not valued.
- **Spreads.** Measured from minute quote bars on hash samples: 300 items, 88–90 % with quotes. They are not
  measured for every signal. The first-30-minute dollar volume from minute bars is implausibly small relative
  to the full session; it is unexplained and not used. Some figures in QC runtime statistics were cut by the
  ~200-character limit: the volume share at the high (S4EXEC) and the 2025 ECE (S4CALIB K2).
- **Exploratory segment-timing result.** S4XSEG is confounded by segment membership: dollar volume rises before
  events, so the placebo window has fewer in-segment rows. Not evidence until a membership-matched test is run.
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
