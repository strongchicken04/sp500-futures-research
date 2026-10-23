# Brain state

heartbeat: 2026-10-23T07:31Z (shift 2026-10-23 active)
last shift: 2026-10-23 (running)

## Queue (top = next). Move finished items to registry.md.
4. Treasury auction effect (ZN): needs an auction calendar 2018-2025
   (research it); short before 13:00 auction, long after.

13. Overnight long after 3 down closes: waiting for the owner (overnight holds allowed?).

## Done this shift
- Sprint after a first loss: abandoning is ~1.5-2 days faster but ~$125-200 dearer (option in the playbook).
- PLAYBOOK_CZ.md written (exact settings for eval and funded). 09:31 sprint: vol gate off (gate = 18-21 days).
- Noise RS-agreement filter: rejected at account level (trade-level looked good, book worse).
- 09:31 sprint shape: target 0.25% / stop 0.40% (~2 days faster); two accounts then 6.8 / 6.5 days.
- Lucid 9 (overnight long after 3 down closes) written, waiting for the owner.
- Multi-account sprint: RS(0.30) + 09:31 on two accounts is the sweet spot (7.1 / 7.3 days, ~$300);
  a third account (noise sprint) adds ~0.3 day for ~$100.
- Funded risk view: flat 3 reaches the first payout in 40% / 51% of funded accounts (ladder 40% / 58%,
  slower). Said plainly in FINAL_PLAN and the report.
- RS sprint 0.30% stop independently confirmed (11.1 / 11.0 days vs 13.8 / 12.9; fees +$0 / +$15).
- Funded size by stage: no robust gain over flat 3 (keep it simple).
- 12. Time-aware sim (timed_book.py): flat 3 confirmed ($12.1k / $29.1k vs ladder $2.3k / $20.5k),
  day stop neutral at -$600 and worse at -$300, RS leg +$7.4k / +$1.5k, ORB keeps its place.
  Use timed_book.py for all book/sizing questions from now on.
- Day stop: tighter looked better only because sequential sims see losses of still-open trades
  (cross-leg after-loss -$31/-$54 per MNQ, t -6/-8). Without a stop: flat 3 still beats ladder;
  RS funded leg uncertain (adds in 2018-21 only). FINAL_PLAN corrected.
- ORB at flat 3: adds +$2.0k / +$16.1k per account. FIXED: prop_sim.merge now orders same-day trades
  by typical entry time (ENTRY_RANK); before, results depended on merge argument order (~25%).
  Day stop in sims = $75 + $75 x units (flat 3: -$300).
- Funded sizing: flat 3 MNQ per leg beats the ladder in both halves (+$5k / +$11k per account, 24m).
- 11. Importer (WebSearch): the two best-known published intraday NQ/QQQ systems are already
  tested (noise momentum, Zarattini/Aziz/Barbon 2024-25 = live; VWAP trend, Zarattini & Aziz
  = rejected). An arXiv 2026 MNQ study (Mesfin; 14 signal families, 5-min data 2021-25) found
  none robust under realistic execution - consistent with our rejections. Snippets only
  (WebFetch blocked). Next importer pass: prop-specific ideas (sprint shapes, account mix).
- 10. Book add-ons: RS leg +$3.3k mean per account (robust); ONL gap-up lowers the mean after the merge fix;
  FOMC fade too rare. Lifecycle medians are lumpy: use book_compare.py means from now on.
- Two accounts with RS 0.20/0.30 + 09:31: first funded 7.1 / 7.3 days, fees ~$300.
- RS + 14:30 fallback: rejected (unstable fallback).
- RS sprint shape: 0.20% / 0.30% is ~2 days faster than 0.20/0.40 in both halves, same fees (recommendation).
- Two-account sprint (RS + 09:31): first funded ~8 days vs ~13, fees ~$300 vs ~$180 (new eval option).
- 9. VWAP trend (Zarattini & Aziz): rejected, OOS t<=1.5, corr 0.5 with noise momentum.
- 7. Noise on ES/YM: rejected (ES weaker and 0.69 correlated with NQ; YM no edge).
- Intraday momentum (Gao et al. 2018): rejected, flips sign in 2022-25.
- 2. RS as funded leg: candidate, +4.6 / +9.6 pt/trade with a 1.25%/1.25% bracket; book median
  $74k vs $68k, p10 $12k vs $5k. Owner decides; Lucid 8 can trade it (target 1.25, stop 1.25).
- 3. Regime map: no regime filter survives both halves (results/regime_map.txt).
  Fixed: vol-gate panel ended 2025-07, 132 days of 2025 were silently gated out;
  rescore_all.rvol now fills from results/rv20_mfeat.csv. Book +1 pp, unchanged otherwise.
- 6. Overnight long after 3+ down closes: candidate, +28.6 / +19.0 bp/night, all years positive;
  ask the owner whether overnight holds are allowed on Lucid Flex.
- 7. Noise exits: hard stop 0.50% adopted in Lucid 6 (same edge, worst trade -128 vs -221 pt);
  targets and partial targets lower the edge. Regime filter: none (item 3).
- 4. Treasury auctions: BLOCKED, api.fiscaldata.treasury.gov refused by the network policy;
  ZN daily exporter (zn_daily_exporter.py) written for month-end and auctions once a calendar exists.
- 5. Month-end ZN: rejected (+2.6 / +0.5 ticks). Turn-of-month NQ: rejected (TOM days not better than other days in 2022-25).
- 1. RS variants: none better than the live rule in both halves; independent export
  replicates the live RS sprint (alignment and fills confirmed). Plan unchanged.
- 8. Live-spec audit DONE: Lucid 2 rewritten to the band break (+3.6 / +3.0 vs +2.3 / +0.7 pt);
  noise live rules replicate; book on fixed live rules median $68k vs $51k. Old note: Lucid 2 trades a plain VWAP cross once a day, the book used a 0.20% band
  break up to twice a day. live_spec_exporter (LSVWAP, LSNOISE) + ZNDAY running on QC;
  score with scripts/score_live_spec.py.

## Notes for the next shift
- Credentials: QC_USER_ID / QC_API_TOKEN from the environment (or
  ~/.lean/credentials in an old container). If neither exists, skip QC runs.
