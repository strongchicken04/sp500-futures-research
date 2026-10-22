# Brain state

heartbeat: 2026-10-22 (set up; no shift has run yet)
last shift: none

## Queue (top = next). Move finished items to registry.md.
1. RS sprint robustness and variants: relative strength vs ES AND YM/RTY
   (sector breadth), 5-minute checks instead of 4 fixed times, threshold
   scaled by realised volatility, VWAP condition vs EMA condition; adversarial
   re-check of fills (entry at the check bar close, ES/NQ bar alignment).
2. RS signal for the funded book (not only sprint): bracket grid + trailing
   exit; does it add to noise momentum + VWAP band?
3. Regime map (system manager): for each live strategy, results by VIX level
   and 20-day realised-vol tercile, trend (above/below 50-day) and year; build
   a regime switch for the book.
4. Treasury auction effect (ZN): needs an auction calendar 2018-2025
   (research it); short before 13:00 auction, long after.
5. Month-end Treasury long (ZN last trading day 09:00-16:00) and turn-of-month
   ES/NQ (Carchano & Pardo).
6. Overnight long after 3 down closes (NQ, futures 1-minute data).
7. Noise momentum variants: regime filter, partial target, ES/YM versions.
8. Re-verify VWAP band and noise momentum exports with an independent
   exporter (fills, costs) — the book's remaining edge rests on them.

## Notes for the next shift
- Credentials: QC_USER_ID / QC_API_TOKEN from the environment (or
  ~/.lean/credentials in an old container). If neither exists, skip QC runs.
