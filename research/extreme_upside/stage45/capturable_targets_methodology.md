# Stage 4.5 — capturable targets and downside

All returns are measured from the adjusted OPEN(t+1), the first executable price after a close-of-t signal, using
daily bars. Code: `_s45_extras` (`xup_s45_core.py`) and `mode_s45outcome` (`xup_s45_modes_d.py`).

## 1. Families
| Family | Definition | Grid |
|---|---|---|
| A | max HIGH(t+1..t+h) / OPEN(t+1) − 1 ≥ thr | h 1/3/5/10 × +50/100/200 % |
| B | CLOSE(t+h) / OPEN(t+1) − 1 ≥ thr | h 1/3/5/10 × +20/50/100 % |
| B-max | max CLOSE(t+1..t+h) / OPEN(t+1) − 1 ≥ thr | same as B |
| C | +u (HIGH) reached before −d (LOW), sessions scanned in order; same-session touch of both = AMBIGUOUS (never success); day 1 includes the open-to-close range | u 20/30/50 % × d 5/10/15 % × h 1/3/5 |
| D (VWAP) | not computed for all rows (minute data infeasible) | only first-5/15/30-min VWAP vs open in S45EXEC samples |

- **Family C outcomes:** success / adverse-first / ambiguous / neither / incomplete.
- **Incomplete windows:** excluded and counted, never negative.
- **Groups (2021–25):**
  - G0: unconditional S1 rows;
  - G1: S1-P5 conditional population;
  - G2: STATE signals;
  - G3: L2 timing signals (per-day top 10 %).

## 2. Short list and C4
- **Short list:** CB3_20, CB5_50, FC3_20_10, FC5_30_10 (primary bracket), FC5_50_15.
- **C4 passes** if at least one short-list target satisfies all of:
  - (i) P(G3) ≥ 1.5 × P(G1), and the security-bootstrap CI of P(G3) − P(G1) > 0;
  - (ii) lift ≥ 1.2 in both 2021–22 and 2023–25;
  - (iii) adverse condition:
    - C: P(success) > P(adverse) + P(ambiguous);
    - B-max: P(target) > P(min LOW over h ≤ −thr);
  - (iv) C only: ≥ 50 % of successes also close at or above the threshold within h.
- A Family-A-only result cannot pass.
- **Secondary targets:** BH at q = 0.05 within each family (G3 vs G1).

## 3. Downside (C5 and tables)
- **C5**, on G3:
  - P(M5 ≥ +20 %) > P(L5 ≤ −20 %);
  - median close(t+5) return ≥ 0;
  - P(close(t+5) ≤ −30 %) ≤ 5 %.
- **Tables per group:**
  - close-to-entry at 1/3/5/10 and quantiles;
  - min LOW at 1/3/5/10;
  - touch shares of −5/−10/−20/−30/−50 % within 10 sessions;
  - close shares ≤ −10/−20/−30/−50 % at t+5 and t+10;
  - drawdowns within 5/10 sessions;
  - max favourable excursion;
  - time to the min LOW and to the max HIGH.
- **Success / failure split** of FC5_30_10 (price, median dollar volume, run-up xr, close t+10).

## 4. Payoff proxy (C7) — not a trading simulation
- **Per signal row**, on the FC5_30_10 bracket, minus the round-trip cost:
  - target first: +30 %;
  - adverse first: −10 %;
  - ambiguous: −10 %;
  - neither: close(t+5) return;
  - incomplete: excluded.
- **Costs:** the frozen formulas of `execution_cost_methodology.md`.
- **Reporting:**
  - mean with a security-bootstrap CI (two-way for neutral);
  - a dedup variant (no signal of the same security in the previous 5 sessions);
  - STATE and population references, and per-period means.
- **Caveats:** overlapping positions and capacity are not modelled, and daily bars cannot order intraday touches
  beyond the ambiguity rule.
