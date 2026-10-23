# Research brain — runbook

Every night 23:00-12:00 Europe/Prague a scheduled wake-up resumes this work.
Read this file, then `brain/STATE.md` (queue + heartbeat) and
`brain/registry.md` (everything tested so far). Work until 12:00 Prague or
until usage runs out; the next hourly wake-up continues where you stopped, so
always leave STATE.md accurate and everything committed.

Owner: a Czech NQ prop trader (Lucid Flex 50K). Write every message to them
in correct Czech, plainly, numbers first. Code comments and commit messages in
English.

## Account rules (confirmed by the owner)
- Evaluation: +$3,000 target; $2,000 end-of-day trailing drawdown that locks
  at +$100 once an EOD balance clears +$2,100; best day <= 50% of total
  profit; day profit cap ~$1,450; fee $90 per evaluation; no time limit.
- Funded: a payout is <= 50% of the profit, max $2,000, min $500, split
  90/10; each payout cycle needs five days with >= $150 profit (count resets
  after a payout); no consistency rule. Plan: withdraw $2,000 at +$4,000
  ($1,800 to the owner); the profit above stays on the account; drawdown
  stays locked at +$100. (Third-party summaries 2026-10; owner to confirm.)
- Max 4 NQ minis (40 MNQ). Copytrading allowed. NO overnight holds (owner,
  2026-10-23): every strategy must be flat by the session close.
- Plan: evaluation = sprint (one big bracket trade a day, three wins pass);
  funded = the book. Evaluation success is measured as EXPECTED TRADING DAYS
  AND FEES TO A PASS (failed attempts included), not pass rate per attempt.

## The six spheres (one shift runs them in this order, repeatedly)
1. **Importer** — pick the next idea from STATE.md "queue", or research new
   ones (WebSearch; WebFetch is usually blocked, rely on snippets and say so;
   research subagents may be used). Write each as exact rules: market, entry
   trigger and time, direction, stop, target/exit, filters. Add to registry
   as `idea`.
2. **Backtester** — implement with the closest template:
   `strategy/quantconnect/cond_bracket_exporter.py` (event entries + bracket
   grid), `multi_feature_exporter.py` (decision times + indicator features),
   `orb_trail_exporter.py` (path-dependent exits), `xmkt_exporter.py`
   (other CME markets). Run with `brain/bin/qc_run.sh NAME:path.py`
   (one QC node: ~15-20 min per run; max ~10,000 order tags per run; reuse the
   slot project). Data: `brain/bin/restore_data.sh` unpacks all tags to
   $BRAIN_DATA (default /tmp/brain_data); scorers take that dir.
3. **Optimiser** — book and funded sizing questions go through
   `scripts/timed_book.py` (time-aware: trades realised in exit order, day
   stop only blocks later entries); older sequential sims overstate day stops.
   Prop-specific versions: sprint bracket for the evaluation
   (`scripts/eval_speed.py`, `scripts/bias_sprint.py`), sizing for funded
   (`scripts/book_after_fix.py`, ladder/flat via `scripts/final_lifecycle.py`
   helpers, `ladder_sim.outcomes`, `mixed_accounts.sim_groups`).
4. **System manager** — when a strategy works and when not (2018-21 vs
   2022-25, by year, VIX/realised-vol regime, trend vs range, weekday), and
   the best combination for the book across regimes.
5. **Coder** — when a strategy is adopted or changed, update/create the Pine
   v5 indicator in `strategy/tradingview/` (first line `// @version=5`;
   simple identifiers; entries/stop/target lines and labels; exits filled at
   min(stop, open) for longs) and include the full code in the report.
6. **Interpreter** — at the end of each shift (or when usage is nearly gone)
   write `brain/reports/YYYY-MM-DD.md` in Czech: what was tested, numbers,
   verdicts, what changed in the plan, next steps; post the same summary as
   the session reply. Update `strategy/tradingview/FINAL_PLAN.md` top section
   when the recommendation changes.

## Guardrails — a result counts only if ALL hold
1. Rules fixed before looking at results; tune only on 2018-2021; report
   2022-2025 untouched. Prefer pre-specified rules over grid winners.
2. Realistic fills: entry at the signal bar's close and tracking from the
   NEXT bar; a bar touching stop and target = stop; a trailed stop above the
   market fills at the bar open (this bug inflated ORB by ~75%); costs $1 per
   micro round trip plus 1 tick slippage on entry and on stops.
3. Robust across the parameter neighbourhood (average over a block of
   brackets/thresholds), not one lucky cell; positive in most years.
4. Beat the random-walk baseline for the same bracket (win rate S/(T+S)) and
   the plain 09:31-long sprint for evaluation use.
5. Big claims get an adversarial re-check (look-ahead, same-bar, roll days,
   cost) before they are reported as findings.
6a. Third period (since 2026-10-23): anything that would change the plan must
   also hold in 2010-2017 (never tuned; exports *_OLD, B2_0A/B, CBA_OLD,
   MFEAT_OLD). Compare eras in GROSS bp of price (NQ was ~4-6x lower then, so
   fixed point costs and dollar results are not comparable; scripts/bp_eras.py).
   Sprints: compare the win rate of RESOLVED trades (target or stop hit) with
   the random-walk rate stop/(target+stop), never counting unresolved as losses.
6b. Funded book / sizing decisions: use scripts/funded_model.py (since
   2026-10-24: all RTH days, five-profitable-day rule, excess profit kept after
   a payout; mc_book.py / timed_book are superseded) with its paired block
   bootstrap (24-month paths of 20-day blocks, all variants on the same
   blocks; template scripts/funded_v2.py) plus the first payout rate. Era
   check for dollar questions: 2010-17 trades re-priced at today's NQ
   (scripts/funded_scaled_old.py). The one-history walk
   (timed_book life()) moves $3-5k with the calendar alone - not for
   differences under ~$5k. The book at flat 3 is at the drawdown edge: new
   legs with small edges add busts; scale with more accounts (copies) instead.
7. Nothing goes live without the owner; you recommend, they decide.

## Shift mechanics
- Times: take every timestamp (heartbeat, db status / log, report date) from
  `date -u`, never estimate it (2026-10-23 night: estimated times ran 8 hours
  ahead of the clock).
- Start: `git pull`, read STATE.md. If `heartbeat` is under 50 minutes old
  and you did not write it in this context, another shift is active: reply
  briefly and stop.
- Update `heartbeat` in STATE.md at least every 45 minutes and after each
  finished item; commit and push after every finished item (branch
  `claude/strategy-replication-backtest-yppz7e`; restore
  `qc_result_MSXB_1792352605.json` before committing).
- Mozek panel (owner's live view, formerly Jarvis): https://claude.ai/artifact/7aNv2n8i8JqZZg4dp25DUK
  (source `brain/jarvis.html`). Keep its database in sync with the ArtifactData
  tool (load it via ToolSearch; read a doc first, then write with `if_version`).
  Owner (2026-10-23): no constant phone approvals - write the db in ONE batch at
  most every ~2 hours and at the end of the shift (status + log + new docs together):
  - `brain/status` at shift start, on every sphere change and with each
    heartbeat: `{phase: working|report|idle|blocked, sphere: importer|backtester|
    optimiser|manager|coder|interpreter, task (Czech, one line), heartbeat (UTC
    ISO), qc: ok|missing, runs, shift}`; set `phase: idle` when the shift ends.
  - `brain/log`: `{events: [{t, sphere (Czech label), text (Czech)}]}`, newest
    first, keep at most 60; append on every finished step.
  - `queue/qN`: `{order, title, note, status: waiting|running|done}` mirrors
    STATE.md; `strategies/sNN`: `{order, status, name, result, files}` mirrors
    registry.md (status values as in the registry), plus for the kill funnel
    `reached` (last gate passed) or, if rejected, `diedAt` (gate where it
    failed), gates: idea, is, cost, plateau, random, oos, years, audit, live;
    `audit: true` while a live strategy is under review (counts as an
    incident); optional `isVal`, `oosVal`, `unit`, `years {yyyy: value}`,
    `yearsUnit`, `note`; for live-funded parts `edge` + `short` (book bars).
  - `indicators/iN`: `{order, name, file, status: live|backup|audit|off, role,
    chart, note}` for the TradingView indicators. The final strategies also
    carry `group: eval|funded`, `slot` (e.g. "Účet A", "Funded"), `settings
    [[label, value]]`, `result`, optional `extra`, and `code` = the full Pine
    source. Whenever a Pine file in the plan changes, write its new text to
    `code` (the Mozek page shows it with a copy button).
  - `brain/stats`: `{dataSets}` = number of files in data/tags;
    `brain/account`: `{rules: [[label, value], ...]}` (account rules).
  - `brain/metrics.eval` also has `p` (pass per attempt), `fee`, `rules`.
  - `brain/metrics`: `{eval|book: {caption, tiles: [{label, value, sub, tone:
    arc|gold|ok|bad}]}}` whenever the recommended plan's numbers change.
  - `reports/YYYY-MM-DD`: `{date (ISO, e.g. 2026-10-23 or 2026-10-23T22:00 - nothing else), title, summary (Czech, plain text), verdicts:
    [{name, status}]}` with the morning report.
- At the end of each shift refresh the offline copy: ArtifactData `list` of
  brain, strategies, queue, indicators and reports with
  `out_dir=brain/snapshot`, then `python3 brain/bin/build_offline.py`, commit
  `brain/jarvis_offline.html` (works as a plain file with the embedded data).
- Never print, log or commit QC credentials.
- Stop starting new QC runs after 11:30 Prague; by 12:00 the report must be
  written and pushed.
- If QC credentials are missing, do research/scoring on existing data and
  say in the report that backtests are blocked.
