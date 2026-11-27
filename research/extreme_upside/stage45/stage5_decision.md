# Stage 4.5 decision — evaluated strictly by the pre-registered criteria (protocol §9–10)

**Decision: C — FURTHER RESEARCH REQUIRED. A Stage 5 trading simulation is NOT justified.**

- Criteria and mapping were fixed in `protocol.md` (commit 0b80fe8) before any Stage 4.5 run.
- Amendments 1–6 changed no criterion.
  - Amendments 1 and 4 add diagnostics.
  - Amendments 2, 3 and 5 are technical (memory, data revision, network).
  - Amendment 6 fills in the frozen cost formula.
- All numbers come from VALID runs (`results.md` §0).

## Criteria
| # | Criterion | Result | Status |
|---|---|---|---|
| C1 | Integrity | Every primary run VALID: S4 CHECK on the canonical revised panel (6,027,629 rows / 24,428 events), S45 CHECK on 3,094,930 rows. Leakage F1 0 / F2 0 mismatches. Move days = E1 episodes (4,216 / 4,216). Invalid runs (AUDIT v1 memory, FEATURE v1 data revision, ROBUST v1 local polling crash) are retained and repeated | **PASS** |
| C2 | Timing improvement over STATE (S1-P5, ONSET_3, E1, 2021–25) | Pre-event capture 69.3 % vs 26.7 % of 303 eligible events, Δ +42.6 pp. Security CI [34.5, 49.8], two-way [28.6, 54.9]. 2021–22 +31.2, 2023–25 +49.0. LOGO +41.3 … +42.2 | **PASS** (see qualification 1) |
| C3 | Within-security placebo | E1 unmatched 54.2 vs 12.4 % (n 225), ratio 4.36, CI [34.1, 49.5]. E1 matched 55.2 vs 12.7 % (n 212), ratio 4.33, CI [34.4, 50.9]. E2 matched ratio 5.25, E3 matched 5.05 | **PASS** (see qualification 1) |
| C4 | Capturable target | CB5_50: 3.74 % vs base 1.73 % (5,492 signals), CI of difference [1.32, 2.71] pp, lifts 1.55 / 2.47, P(L5 ≤ −50 %) 1.52 % < 3.74 %. All Family C brackets fail the adverse condition (FC5_30_10: success 12.8 % vs adverse-first 57.3 %) | **PASS** (one target only; see qualification 2) |
| C5 | Downside | P(CB5 ≥ +20 %) 17.1 % < P(L5 ≤ −20 %) 25.0 %. Median close t+5 −3.38 %. P(close t+5 ≤ −30 %) 4.69 % | **FAIL** |
| C6 | Liquidity | C2 and C4 pass in S1. S2 direction: C2 +10.1 pp [2.1, 19.3]; CB5_50 lift ×2.17 | **PASS** |
| C7 | Cost | Neutral payoff proxy −2.96 % [−3.52, −2.43] (two-way [−3.69, −2.21]). Conservative −4.91 %, optimistic −1.61 %, implied gross −0.56 % | **FAIL** |
| C8 | Robustness of the C2 direction | All 10 items positive: E2 +41.5, E3 +40.6, 2021–22 +31.2, 2023–25 +49.0, RF +44.2, A-strict +42.7, same-day rule +42.5, S2 +10.1, price $1–5 +27.3, price ≥ $5 +9.7 | **PASS** |
| C9 | Statistical integrity | Paired event-level comparisons on identical eligible events. Security-cluster + two-way bootstraps (2,000). Hyperparameters chosen on 2020 only. No test tuning. All deviations in amendments. No INVALID output used | **PASS** |

## Mapping (protocol §10)
- **A** requires C1–C9. It fails on C5 and C7.
- **B** requires C1, C2, C3, C4, C7 and C9. It fails on **C7**.
- **C** requires C1 and C9 plus at least one of C2 / C3 / C4. All three pass. **→ C.**
- **D** does not apply: C1 and C9 pass, and C2–C4 pass.

## Qualifications the decision rests on (plain language)
1. **"Timing" is mostly detection of a move already under way.**
   - At the first L2 signal before a captured event, the stock is a median 65 % above its 10-session low open.
   - 71 % of captured events are already ≥ 50 % up.
   - The move-day definition (first +100 % high) lets such rows count as "pre-event", and the placebo window a
     month earlier contains no run-up, which inflates the C3 ratio.
   - In the strict pre-move population (run-up < 50 %), the capture gain is +21.0 pp [11.0, 31.1], at event
     precision 2.26 % (STATE 1.71 %).
   - Genuine pre-event timing exists, but it is weak.
2. **The capturable gain is the state, not the timing.**
   - On every capturable target, the L2 timing signals perform the same as the frozen STATE signals: CB5_50
     +0.17 pp [−0.82, 1.13]; FC5_30_10 +0.12 pp [−1.33, 1.53].
   - C4 passes because the S1-P5 population is ranked, not because of timing.
3. **The economics are negative.**
   - From the next open, signals lose a median 3.4 % in 5 sessions and 5.4 % in 10.
   - 42 % touch −20 % within 10 sessions.
   - The bracket proxy is negative before any cost (−0.56 %) and in every cost scenario and period. The
     population, STATE signals and timing signals are all alike.
   - Removing chased run-ups (Amendment 4) does not help (neutral −3.18 %).
4. **Liquidity.** In liquid or higher-priced names (S2, S5M, price ≥ $5), the frozen state alone captures about
   70 % of eligible events. The timing gain is +7 to +10 pp, and S5M is not significant.

## What is NOT justified
- A Stage 5 trading simulation of the timing signals, long from the next open, in any universe.
- Any claim of profitability, or of predictable move onset beyond weak pre-move timing.
