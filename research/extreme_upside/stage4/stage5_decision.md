# Stage 5 decision (Stage 4J) — evaluated strictly by the pre-registered criteria (protocol §9)

**Decision: C — FURTHER RESEARCH REQUIRED. A trading simulation (Stage 5) is NOT justified now.**

The criteria and the decision mapping were fixed in `protocol.md` (commit `3fa2c5f`) before any Stage 4 result
was seen. The amendments made afterwards changed no criterion. The numbers below come from the QC runs listed in
`results.md`.

## Criteria
| # | Criterion | Result | Evidence | Status |
|---|---|---|---|---|
| C1 | Stage 3 benchmark reproduced exactly | All six models reproduce TEST v1: RF PR-AUC 0.0596, P@1/5/10 % 7.74 / 5.31 / 3.96 %, R@10 % 68.5 %; volume LR 0.0460 / 7.02 %; base 0.580 %; 9,300 positives; 1,604,540 rows | S4AUDIT v1 (built before the QC data revision) | **PASS** |
| C2 | 1,296 vs 1,263 discrepancy reconciled | 1,296 / 16,749 = RF P@1 %. 1,263 / 16,749 = GBM P@1 %, because the Stage 3 `_tradability()` was coded on `fullA GBM`. The Stage 3 §H tradability profile is GBM's; RF's own profile: median $0.46, 78 % < $1 | code + S4AUDIT A1 / A2 | **PASS** |
| C3 | Event-level evaluation for E1, E2, E3 | Completed for 6 models × top 1 / 5 / 10 % (E1) and RF / volume LR (E2, E3), plus B / B-max populations | S4EVAL v2, S4LEAD v1 | **PASS** |
| C4 | Pre-event signal (E1, RF top 5 %): pre-onset capture ≥ 20 % AND above the same-security placebo window with CI > 0 AND ratio ≥ 1.5 | 57.0 % vs placebo 49.8 %, Δ +7.2 pp [4.8, 9.6], **ratio 1.14** | S4LEAD v1 | **FAIL** (ratio) |
| C5 | C4 also for E2 and E3 | E2: 53.1 vs 47.9 %, ratio 1.11. E3 (before the move day): 61.2 vs 48.5 %, Δ +12.7 pp [9.9, 15.4], ratio 1.26 | S4LEAD v1 | **FAIL** |
| C6 | Tradable segment S1 (px ≥ $1, $vol ≥ 500k, re-ranked): P@1 % ≥ 3× base in validation and test, ≥ 100 test events, top-5 % capture ≥ 30 % | Lift 22.7× (validation) / 21.5× (test), 457 events, capture 76.1 %. S0 and S2 also pass | S4FILT v1 | **PASS** |
| C7 | Downside quantified; FLAG if, in S1, share of close(t+10) ≤ −50 % > share reaching a +100 % close | 3.82 % vs 3.06 %. Median close t+10 −8.5 %, t+20 −14.2 % for S1 selections | S4OUTC v1 | quantified, **FLAG** |
| C8 | Paired bootstrap ≥ 1,000 resamples | 2,000 security-cluster + 1,000 security × date | S4BOOT v1 | **PASS** |
| C9 | No unresolved data-integrity defect | A QC historical-data revision was detected by the run check and diagnosed (two projects, identical fingerprints). It is documented (Amendment 1) and moves Stage 3 metrics by ≤ 0.0005 PR-AUC. No other defect: `mh10 = R` on all rows, all runs deterministic (EVAL v2 = v1 line for line) | S4DIAG, S4AUDIT v2 | **PASS** (resolved, disclosed) |

## Mapping (protocol §9)
- **A** needs C1–C9 to pass, S1 to pass and C7 not to be flagged. It fails on C4, C5 and C7.
- **B** needs C1–C5, C8 and C9. It fails on C4 and C5.
- **D** would apply if C1, C2 or C9 failed (none did); or if pre-onset capture were not above placebo while
  ≥ 80 % of captured events are in-event only (pre-onset is above placebo, and in-event-only events are 7.4 % of
  test events = 12 % of captured events); or if S0, S1 and S2 all had lift < 2× (they have 17–41×). None applies.
- **C** applies when C4 or C5 fails while the row-level ranking lift persists and C1, C2 and C9 pass. **→ C.**

## What the evidence says (plain language)
1. **The ranking is real, robust and out-of-sample.**
   - RF beats the volume-only baseline in paired tests: PR-AUC +0.0139 [0.0080, 0.0195]; event capture at top
     5 % +12 pp.
   - This holds in 2021–22, 2023–25 and 2026 YTD, in all universes and for A / B / B-max events.
   - At the very top (P@1 %), RF and the volume baseline are statistically indistinguishable.
2. **It identifies a persistent state, not the timing of a move.**
   - An event is about as likely to have a signal 21–40 sessions before onset as 1–2 sessions before.
   - The same stock was flagged in the placebo window a month earlier in about 50 % of cases.
   - Earlier signals do not predict larger or better-confirmed moves.
3. **Inside liquid segments the ranking survives** (lift 17–45×). But absolute precision is only 3.5–5.3 % at the
   top 1 %, and event precision is about 12 %.
4. **The selected stocks lose money on average** from the next open, in every segment and for every model:
   - RF top 1 %: median close −7.1 % at t+10 and −12.4 % at t+20;
   - 8 % lose half their value within 20 sessions;
   - 14 % touch a −50 % low.
   
   Family-A "events" are often intraday highs that are not held: only 29 % of top-1 % events close ≥ +100 % at
   t+10.
5. **Execution costs are measurable.** Median quoted spread on the entry day after a signal is about 1.1 % (first
   30 minutes about 1.7 %). Minute quote coverage is about 88 % of sampled items. A cost model for a later
   simulation is therefore feasible.

## Exploratory lead (S4XSEG; cannot change the decision)
- **Result inside the liquid segments S0 / S1 / S2:** the RF pre-event contrast against the same-security placebo
  is much stronger than in the full universe:
  - S1, E1 top 5 %: 63.7 vs 42.9 %, ratio 1.49;
  - top 1 %: 32.6 vs 15.0 %, ratio 2.17;
  - S2, E3: ratio 2.06 at top 5 % and 2.57 at top 1 %.
- **Confounder:** segment membership depends on rising dollar volume before events. Until it is removed with a
  membership-matched placebo, this is a lead, not evidence.

## What "further research" should address before any Stage 5 (recommendations, not results)
1. **A timing target, not a state target.** For example, the probability of a move in the next 1–3 sessions,
   conditional on already being in the high-volatility state. Evaluated against a within-security placebo,
   **membership-matched** inside liquid segments (S4XSEG lead).
2. **A target that reflects what can be captured.** For example, a close-based or VWAP-based excursion with an
   explicit stop or adverse-move constraint, because Family A is dominated by unheld intraday highs and the
   selected names drift down.
3. **Restrict research to S1 / S2-type liquid segments**, where spreads and quotes are measurable.
4. **Only if a pre-registered timing criterion passes**, run a Stage 5 simulation with minute-level entry, quoted
   spreads, halts, position limits and the downside documented here.
