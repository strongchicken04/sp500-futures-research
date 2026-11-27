# Stage 4.5 — limitations

1. **Not an untouched test.** 2021–2025 and 2026 YTD were examined in Stages 3–4. Every Stage 4.5 number is a
   historical out-of-sample replication under prior research exposure. Genuine confirmation requires prospective
   shadow data after 2026-08-27.
2. **QC data revisions.** QC's historical data changed twice during this project:
   - Stage 4 Amendment 1: 6,022,604 → 6,028,644 rows;
   - Stage 4.5 Amendment 3: → 6,027,629 rows / 24,428 primary events (−1,015 rows, all in 2021–2026).

   Comparisons inside Stage 4.5 are within one build. Stage 4 and Stage 4.5 numbers can differ slightly for that
   reason.
3. **Sample.** A fixed-hash 20 % sample of US equities (2,947 securities with data). Absolute event counts scale
   with it. Concentration on a few securities is handled by security-cluster bootstraps, not removed.
4. **Short training history for the second stage.** Training starts in 2017 so that state scores are
   out-of-sample (protocol §5).
   - Fold a trains on four years.
   - Hyperparameters are chosen on 2020 only, an unusual year.
5. **Daily bars.**
   - Family C ordering inside a session is unknown. Same-session touches are counted as ambiguous (never success),
     which is conservative for the success rate. It is not conservative for "neither" outcomes, which use the
     close.
   - Entry at the adjusted open of t+1 assumes the open is tradable at the printed price.
6. **VWAP (Family D)** is measured only on minute-data samples (S45EXEC), not as a target on all rows.
7. **Costs.**
   - Quoted spreads, not effective spreads; no size or impact.
   - Samples of 60–150 items.
   - The cost formulas are fixed scenarios, not estimates of a fill model.
   - Borrow and short constraints are not relevant (long only); halts and LULD pauses are not modelled.
8. **Payoff proxy ≠ simulation.**
   - Each signal row is an independent bracket. Overlapping positions in the same security are counted again (a
     dedup-5 variant is reported).
   - No capital, capacity, position limit or portfolio constraint.
   - Stage 5 would be required for any trading claim.
9. **Universe membership** uses the trailing 20-session median dollar volume through t. It is still correlated
   with the pre-event volume rise; the membership-matched placebo addresses this for C3 only.
10. **Move-day anchoring.**
    - "Onset" is the first +100 % high (or close for B / M).
    - A stock already up strongly can count as pre-event.
    - Amendment 1 adds a run-up diagnostic and a strict pre-move sensitivity. It is not a criterion.
11. **Multiple comparisons.** BH within each target family. The C-criteria are pre-registered conjunctions;
    secondary universes and horizons are descriptive.
12. **Memory constraints** (1 CPU / 7.8 GB in QC) forced storage changes (Amendment 2) and splitting the
    robustness grid into a separate run. These changes do not alter any value used by a criterion.
