# Brain state

heartbeat: 2026-10-22T21:36Z (shift 2026-10-23 active)
last shift: 2026-10-23 (running)

## Queue (top = next). Move finished items to registry.md.
2. RS signal for the funded book (not only sprint): bracket grid + trailing
   exit; does it add to noise momentum + VWAP band?
4. Treasury auction effect (ZN): needs an auction calendar 2018-2025
   (research it); short before 13:00 auction, long after.
5. Month-end ZN long (last trading day 09:00-15:00): run zn_daily_exporter.py.
7. Noise momentum ES/YM versions (needs an exporter run; exits done).

## Done this shift
- 3. Regime map: no regime filter survives both halves (results/regime_map.txt).
  Fixed: vol-gate panel ended 2025-07, 132 days of 2025 were silently gated out;
  rescore_all.rvol now fills from results/rv20_mfeat.csv. Book +1 pp, unchanged otherwise.
- 6. Overnight long after 3+ down closes: candidate, +28.6 / +19.0 bp/night, all years positive;
  ask the owner whether overnight holds are allowed on Lucid Flex.
- 7. Noise exits: hard stop 0.50% adopted in Lucid 6 (same edge, worst trade -128 vs -221 pt);
  targets and partial targets lower the edge. Regime filter: none (item 3).
- 4. Treasury auctions: BLOCKED, api.fiscaldata.treasury.gov refused by the network policy;
  ZN daily exporter (zn_daily_exporter.py) written for month-end and auctions once a calendar exists.
- 5. Turn-of-month NQ: rejected (TOM days not better than other days in 2022-25).
- 1. RS variants: none better than the live rule in both halves; independent export
  replicates the live RS sprint (alignment and fills confirmed). Plan unchanged.
- 8. Live-spec audit DONE: Lucid 2 rewritten to the band break (+3.6 / +3.0 vs +2.3 / +0.7 pt);
  noise live rules replicate; book on fixed live rules median $68k vs $51k. Old note: Lucid 2 trades a plain VWAP cross once a day, the book used a 0.20% band
  break up to twice a day. live_spec_exporter (LSVWAP, LSNOISE) + ZNDAY running on QC;
  score with scripts/score_live_spec.py.

## Notes for the next shift
- Credentials: QC_USER_ID / QC_API_TOKEN from the environment (or
  ~/.lean/credentials in an old container). If neither exists, skip QC runs.
