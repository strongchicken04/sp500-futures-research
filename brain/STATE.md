# Brain state

heartbeat: 2026-10-26T11:09Z (day shift 2026-10-26 BIG: E7 done, E11 in-QC running)
last shift: 2026-10-26 day shift (running)

## Queue (top = next). Move finished items to registry.md.
Day shift 2026-10-26 (owner: "spusť zase na celý den, i research"; hourly 12:07-22:07 Prague, report brain/reports/2026-10-26-den.md):
E1. DONE (rejected, keep 0.20/0.30): Eval bracket SHAPE under the intraday rule (fixed before results): RS sprint with target >= stop
    (0.30/0.20, 0.25/0.25, 0.30/0.30, 0.40/0.30, 0.50/0.40) vs the plan 0.20/0.30 and 0.25/0.40; two-win sizing
    (win <= $1,450, loss <= $1,950, every trade fits the room). Idea: a loss that leaves room for a second trade.
    Adopt only if faster AND cheaper in all four eras + 2026; random-direction check <= 40%.
E2. DONE: QC data now ends 2026-07-28 (+2 days, not worth a re-run; re-check ~weekly). QC build now needs
    new ticker names (fixed in all exporters). Was: does the data extend past 2026-07-24? If yes, re-run the *26 exports (holdout, Z watch).
E3. Importer: web research for new intraday NQ/ES ideas (2025-26 studies), each as exact rules -> registry.
E3a. DONE midday fade (rejected). E3b. CANCELLED: RS vs YM / RTY was already rejected (registry 'RS sprint variants').
E3c. DONE: RS funded leg exit variants (VWAP exit, breakeven stop) rejected.
QC 2026-10-26: our data exports were flagged as a Terms of Service violation -> NO QC runs. Owner: keep
    researching on the existing local data ("pokračuj takhle"). New data only from a licensed source.
E5. DONE (no change; RS10 = lower tail risk, same mean): RS leg by signal strength |rs| bucket and by check time (10:00 / 11:00 / 13:00 / 14:30), four eras
    + 2026 -> sizing by strength or dropping a check only if monotonic / consistent in all eras.
E3d. STOPPED: RS spread NQ-ES (2018-25 t 2.8) - the 2010-17 / 2026 ES panels cannot be exported.
E8. DONE: big-trades bubbles (owner idea; BVC proxy on 5-min OHLCV): follow loses at all horizons, fade only in
    event averages, as a strategy ~0 / negative -> rejected. A real test needs tick data with the aggressor side.
E9. DONE: absorption / delta divergence proxies rejected; RS x session volume: high-volume days weakest everywhere
    but skipping them in the book is mixed -> rejected.
E11. RUNNING: big trades with REAL aggressor side inside QC (inqc/bubbles_YYYY.py, runner in scratchpad
    run_inqc.sh, output results/bubbles_inqc_raw.txt), years 2024, 2023, 2022, 2025, 2026, 2021..2018.
E12. QUEUED: RS x real order flow (cum delta) inside QC, after E11 (runner run_rsd.sh).
E10. NEXT fresh ideas (owner wants many): e.g. 1-min-free order-flow ideas are exhausted on OHLCV; try
    volatility-regime timing of the whole book (rv20 / VIX buckets), weekday x RS, holiday-week, month-start flows.
E6. NEXT: RS leg hedged with MES (NQ long + ES short on the RS signal, 1:1 and 1:1.25 notional) in the
    funded model, 2018-25 only (no ES panel for 2010-17 / 2026 -> information only; Lucid hedging rule to be
    checked by the owner before any use).
E7. DONE (passes 6c; offer as lower-risk option): RS10 as a risk option - check timing 6c (MFEAT*_M5 / _P5: 09:55 / 10:05) and 2026 before offering it.
E4. Test the best E3 ideas (four eras, 6c timing, funded via funded_model + mtm_check at today's NQ).
Night 2026-10-24/25:
N1. DONE: V11 plateau at today's NQ -> fragile (only exact 11:00 works) -> rejected as plan B.
Day shift 2026-10-24 (owner: "jeď to zase dnes celý den"; until 22:00 Prague, report brain/reports/2026-10-24-den.md):
D1. DONE: small-edge legs re-tested on the open-P&L model -> VWAP side 10:00 (V10) candidate leg (Lucid 12 funded mode).
D2. DONE: integrated seat model - eval plan choice moves 24-month cash per seat by only -0.5k..+2.5k
    (09:31 alone clearly worse); ~50 evaluations per seat in 24 m with a pair (~25 single) -> plan unchanged.
D3. DONE: book with V10: 4 > 3 everywhere, 5 > 4 everywhere but smaller and lower first payout -> keep 4; all legs stay.
D4. New ideas: done so far - V11 optional, MOM30/MOM60/OD/NR4 on the V10 book no, V10 gap filter no, payout
    timing unchanged, edge-decay risk view, size to the scaling cap (start 4, then 5).
D5. DONE: true 2026 holdout (Jan - Jul 24): book VG+Z+RS +$11.6k at 4 MNQ, first payout 27% as simulated;
    RS leg strong, VG weak (seen before), V10 worst year of 17 -> V10 stays a candidate, not added.
    Data *26 cover 2025-01..2026-07; re-run the 2026 exports when QC data extends.
P1. 2026-10-25 (owner sent SSRN 7445798, barrier model of prop challenges): DONE check
    (results/paper_barrier.txt) -> our evaluation sim tested the drawdown only on closed trades; Lucid
    breaches intraday. With the intraday check (2022-25): RS sprint passes 34% of evaluations, not 54%;
    fees to a pass $265, not $165; days to a pass about the same (7.9 vs 8.7); random direction 26%
    (ceiling 40% holds). After a first full loss the evaluation is practically dead (~$50 room).
P2. DONE (night 25/26; registry): re-run every evaluation result on attempt_intra (guardrail 6d): two-win / finishing trade,
    pair of accounts + hedge guard, sprint_reset (continue vs new evaluation), eval_spread, 2026 eval
    holdout, integrated seat (eval cost per funded seat), PLAYBOOK eval numbers. Then test eval sizing
    under the intraday rule (full size won vs half size in every era; try "after a loss buy a new one").
    Result: RS alone on one account recommended (beats the pair by $1.0-1.3k per seat); Lucid 7/8 got
    "Drawdown line now"; playbook + FINAL_PLAN updated.
P3. DONE (night 25/26): AUTOMATION_SPEC room cap; funded_model eval cost 10 d / $265 (headline unchanged:
    $33.4k / $36.3k); funded 'sprint to the lock' REJECTED (-4k..-22k); Mozek eval metrics p / fee updated.
    Withdrawal-order idea of the paper is about the consistency rule (funded has none) -> not tested.
17. Waiting for the owner: (a) funded size: STAY at 3 MNQ per leg at NQ ~28,500 (night's 4 withdrawn 24.10;
    rule MNQ per leg ~ 90,000 / NQ price), (b) drop ORB (recommended),
    (c) confirm LucidFlex funded rules (five profitable days >= $150, 50% / $2,000 payout cap, scaling
    20 MNQ below $1,000 profit, 5-payout cap), (d) automation route (NinjaScript on own PC or TradingView
    webhook) -> then code the eval sprints (Lucid 8 + Lucid 7 with both hedge guards) first.
    (e) NEW 25/26: re-upload Lucid 7 + Lucid 8 ("Drawdown line now" input), evaluation = RS alone on one
    account (recommended; the pair is 1-2 days faster but $1.0-1.3k worse per seat), (f) check the Lucid
    agreement: pooling/hedging clause vs copy-trading, review of 'excessive single-day profits'.
18. WATCH: noise momentum (Z) flat since 2025-01 (t -2.0 vs history); rule: Z mean 2025-26 <= 0 at end of 2026 ->
    cut Z to 2 MNQ; still <= 0 mid-2027 -> drop. V11 as a replacement REJECTED (night 24/25: only the exact
    11:00 bar works, 10:55 / 11:05 flip - fragile). No replacement leg for now.
    Re-run the *26 exports when QC data extends.
19. Ideas only if new data/insight; any new idea must pass the four-era check (BRAIN.md 6a); funded
    questions on funded_model.py + mtm_check.py (open P&L), 2010-17 re-priced at today's NQ.
4. Treasury auction effect (ZN): BLOCKED (treasury.gov and fiscaldata refused by the network policy).

## Done this shift
- Night 24/25: V11 plan B rejected (timing-fragile); RS and noise pass the +/-5 min timing check (rs_timing.py,
  z_timing.py); guardrail 6c added.
- Day 24.10: 2026 holdout (Jan-Jul): plan holds, ORB drop confirmed, V10 not added; eval pair 5.9 days.
  SIZE AT TODAY'S PRICE (NQ 28,530): 3 MNQ per leg is right, 4 is not -> night's '4 MNQ' withdrawn.
  IMPORTANT for all future funded dollar questions: re-price every era at the current NQ level (size_today.py).
- Day 24.10: integrated seat model (eval plan unchanged); size: flat 5 > flat 4 in all eras, scaling-max worse ->
  start 4, go 5 after live check; V10 by year 11/16 positive, minute-data cross-check positive in all eras;
  second-round add-ons: V11 optional only. PLAYBOOK: funded schedule in Prague time (DST gap 26-30 Oct).
- Day 24.10: D1 small-edge legs on the open-P&L model: V10 (VWAP side 10:00, +0.30/-0.50) adds in all four eras
  and on the plateau (10:00 / 11:00 x 3 brackets), survives worse fills -> candidate; Lucid 12 funded mode added.
- Night: importer pass (WebSearch): nothing new testable on NQ data (Aleti-Bollerslev-Siggaard needs a stock panel).
- Night: lenient open-P&L bound (close marks) gives the same conclusions (flat 4, no ORB, OD optional).
- Night: AUTOMATION_SPEC.md (route-neutral rules); Lucid 8 audit: funded RS leg needs fixed size + vol gate (added).
- Night: vol gate per leg on the open-P&L model: no ungated variant better in all eras -> keep the gate.
- Night: ORB on the open-P&L model at 4 MNQ: worse in all four eras -> drop recommendation stronger.
- Night: leg contribution at 4 MNQ (open-P&L): VG, Z and RS each add in all four eras.
- Night: calendar effects (pre-holiday, month-end rebalancing) rejected in the four-era check.
- Night: flat 4 survives worse fills (+$1 / +$2 per MNQ per trade) in all four eras.
- Night: cross-account hedge book vs eval sprints: RS ~1% of days, 09:31 ~12-13% -> rule in PLAYBOOK (book skips
  entries against an open eval sprint). LucidFlex funded scaling 20 MNQ below $1,000 profit: book at 4 MNQ uses <= 12-16.
- Night: day stop on the open-P&L model rejected in all eras (PLAYBOOK: no day stop).
- Night: size by stage (3->4, 4->5, 5->4 ...) on the open-P&L model: nothing clearly beats flat 4 -> keep it simple.
- Night: RS funded-leg bracket at 4 MNQ (open-P&L check): no width better in all eras -> keep 1.25%.
- Night: open-P&L drawdown check (mtm_check.py): flat 4 still beats flat 3 in all eras (+3.5k / +4.3k /
  +2.6k / +2.5k); OD on top only +0.6k in 3 eras -> optional. Use the open-P&L check for size questions.
- Night: OD (Lucid 10) at 4 MNQ adds in all four eras on funded_model (+3.1k / +2.0k / +1.8k / +1.9k),
  robust to dearer evaluations -> proposed with flat 4 (FINAL_PLAN). NR4 no (2010-13).
- Night: funded model v2 (funded_model.py) - mc_book dropped the profit above +$4,000 at each payout,
  skipped ~21% of days and ignored the five-profitable-day rule. Results on v2 (funded_v2.py,
  funded_scaled_old.py for 2010-17 re-priced at today's NQ): flat 4 beats flat 3 in all four eras
  (+4.9k / +5.0k / +3.2k / +4.0k) -> new recommendation (owner decides); ORB cash-neutral but lower first
  payout -> still drop; F2/P2, funded sprint, payout timing, Z without gate rejected. Earlier night
  rows (income2, payout_size, book_recheck) superseded. USE funded_model.py FOR ALL FUNDED QUESTIONS.
- Night: book decisions re-checked on the corrected model: flat 3, RS in, ORB out all confirmed.
- Night (superseded): payout-aware funded sizing looked like a small option on the old model
  +0.9k / +2.0k, not confirmed in 2010-17 (PLAYBOOK section 3).
- Night: vol-scaled sprint bracket rejected; funded sprint to the first payout rejected (LucidFlex
  five-profitable-day payout rule); income model corrected (all days + five-day rule): no-ORB book
  $13.3k / $17.5k per seat in 24 m, first payout 40 / 41% (income2.py). Use the all-days calendar
  and F.PD_RULE (funded_sprint.run_path) for funded questions from now on.
- Day: 2010-2017 third period (never tuned): gross edges of noise / VWAP band positive but ~half;
  ORB ~0 gross, negative net -> recommendation narrowed to dropping ORB (first payout 44/42% vs 37/36%).
  Z without gate and OD/NR4 add-ons not confirmed. RS sprint edge in all four eras; 09:31 none.
- Day: ICT (Silver Bullet, London/Asia/prior-week sweeps), retail indicators (EMA/Supertrend/MACD/Bollinger),
  Yu-Rentzler-Wolf regimes, OD in the sprint, prior-week break, smaller extra legs, profit lock, FOMC skip: all rejected.
  Note: lifecycle mean moves ~$3k with the calendar alone - treat smaller differences as noise.
- Day: hedge guard for the two-account eval (clash 7% of days, costs 0.2-0.4 day) -> PLAYBOOK. Volume filters
  (opening RVOL, first-bar RVOL ORB, volume spike, 14:00 trend) rejected; open drive weak on ES.
- Day 12. Level lab (BARS5A/B): volume-profile rules all rejected (80% rule, outside value, POC, naked POC,
  narrow/wide value); PD/ON level breaks and sweeps rejected; IB break weak and worse in the book;
  open drive = candidate signal (+7.1 / +22.6 pt, robust plateau) but does not add to the funded book.
- Owner: Lucid Flex does not allow overnight holds -> overnight long rejected; Lucid 9 retired.
- Two-account plan by start year: 5.7-8.2 days every year (worst 2019). Final report written.
- Pine audit: daily lookups (Lucid 7 bias SMA50, vol gates in Lucid 1/2/6/7) switched to ([expr])[1] +
  lookahead_on so live trading uses the last completed day, as the backtests do.
- ORB live-spec audit: Lucid 1 rules give -0.47 / +0.41 pt/trade (old export -0.12 / +0.61); book effect
  mixed without RS, positive with RS. Keep ORB, lowest priority leg.
- Lucid 1 (ORB) audit: EMA trail now RTH-only and restarted daily, no stop test on the entry bar (as the exporter).
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
