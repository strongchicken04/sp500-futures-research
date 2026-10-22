# Brain state

heartbeat: 2026-10-22T21:13Z (shift 2026-10-23 active)
last shift: 2026-10-23 (running)

## Queue (top = next). Move finished items to registry.md.
1. RS sprint robustness and variants: relative strength vs ES AND YM/RTY
   (sector breadth), 5-minute checks instead of 4 fixed times, threshold
   scaled by realised volatility, VWAP condition vs EMA condition; adversarial
   re-check of fills (entry at the check bar close, ES/NQ bar alignment).
2. RS signal for the funded book (not only sprint): bracket grid + trailing
   exit; does it add to noise momentum + VWAP band?
4. Treasury auction effect (ZN): needs an auction calendar 2018-2025
   (research it); short before 13:00 auction, long after.
5. Month-end Treasury long (ZN last trading day 09:00-16:00) and turn-of-month
   ES/NQ (Carchano & Pardo).
6. Overnight long after 3 down closes (NQ, futures 1-minute data).
7. Noise momentum variants: regime filter, partial target, ES/YM versions.
8. Re-verify VWAP band and noise momentum exports with an independent
   exporter (fills, costs) — the book's remaining edge rests on them.

## Done this shift
- 3. Regime map: no regime filter survives both halves (results/regime_map.txt).
  Fixed: vol-gate panel ended 2025-07, 132 days of 2025 were silently gated out;
  rescore_all.rvol now fills from results/rv20_mfeat.csv. Book +1 pp, unchanged otherwise.
- 1. RS variants: exporter rs_variants_exporter.py (rsvar/rs_var_A/B.py) running on QC.

## Notes for the next shift
- Credentials: QC_USER_ID / QC_API_TOKEN from the environment (or
  ~/.lean/credentials in an old container). If neither exists, skip QC runs.
