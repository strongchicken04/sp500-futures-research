# Stage 4.6: limitations

1. **Not an untouched test.** 2021–2025 and 2026 YTD were examined in Stages 3–4.5. The daily-bar behaviour of the
   same L2 signals (negative after costs from the next open) was known when H-next was formulated.
   - The intraday rule is new, so the result is a narrowly defined historical replication.
   - Confirmation needs the prospective shadow log.
2. **Execution prices are proxies, not fills.**
   - The quote-based entry is the first minute-QuoteBar ask after confirmation. Minute quote bars give the
     ask / bid at the bar open / close, not every quote update; the true first ask after the confirming trade can
     differ within the minute.
   - The minute-bar proxy ((open + high) / 2 of the next trade bar) is a convention.
   - Size, queue position and market impact are not observed.
3. **Exits.**
   - The bracket exits at exactly +30 % / −10 % (frozen convention). Gap-throughs are covered only by the
     gap-realistic sensitivity.
   - The close exit uses the official daily close; closing-auction costs are not modelled beyond the frozen cost.
4. **Intraday ordering.**
   - On t+1, minute bars order the touches.
   - On t+2..t+5, daily bars are used. A same-session double touch is resolved with that session's minute bars, and
     is otherwise ambiguous.
   - A bar touching both levels is ambiguous and counted as −10 % (conservative).
   - MAE / MFE use full-session ranges on the exit session (approximation).
5. **Corporate actions.** Windows with a split or dividend (adjustment factor changing > 0.5 %) are excluded as
   incomplete and enter only the conservative sensitivity.
6. **Sample.** 20 % fixed-hash sample of US equities. Overlapping signals of the same security are counted per
   signal; the dedup-5 variant is reported.
7. **Costs.**
   - Frozen formulas from Stage 4.5 (s30 measured on 150 next-open entry days). The quote-informed sensitivity
     uses the observed entry-time spread.
   - Neither captures impact or adverse selection at the breakout moment beyond the formula.
8. **Controls** are matched on date, price, trailing dollar volume and ATR only. Market cap is unavailable for part
   of the universe.
9. **Prospective shadow.** The QC data end at 2026-08-27, so no prospective session exists yet. The framework is
   built and dry-run on historical sessions. Prospective results require re-running as QC data extend.
