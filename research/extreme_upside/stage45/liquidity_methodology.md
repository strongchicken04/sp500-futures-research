# Stage 4.5 — liquidity methodology

## 1. Universes (membership at t from data through the close of t)
| Universe | Raw close | Median raw dollar volume t−19..t (trailing rule) |
|---|---|---|
| S0 | ≥ $1 | ≥ $100k |
| **S1 (primary)** | ≥ $1 | ≥ $500k |
| S2 | ≥ $5 | ≥ $1M |
| S5M | ≥ $5 | ≥ $5M |
| A | none | none |

- **Same-day rule (sensitivity):** dollar volume of session t only (the Stage 4 definition). It reacts to the
  volume surge itself; the trailing median is less so.
- **Suffix variants** (`_s45_umask`):
  - `/strict`: excludes unresolved instrument classes (A-strict);
  - `/h120`: ≥ 120 sessions of history in the segment;
  - `/px1_5`: price < $5;
  - `/px5`: price ≥ $5.
- **Grid (S45GRID):** price ≥ {1, 2, 5} × median dollar volume ≥ {250k, 500k, 1M}.

## 2. Re-ranking
In every population, the frozen RF percentile is recomputed inside that universe each day. Timing models are
retrained on that population's training rows (same folds and frozen hyperparameters). Signals are the per-day top
10 % inside the population. No universe is selected on test results. All are reported.

## 3. Membership-matched placebo
- Liquid-universe membership itself rises before events, because dollar volume increases.
- An unmatched pre/placebo contrast can therefore reflect entry into the universe rather than timing.
- The matched analysis keeps only events whose security is an S1 member on every row of both windows.
- The number of events lost to matching is reported.

## 4. What is reported per population
- rows, positives and base rate; eligible events and all events;
- capture for STATE and for the timing model, the paired difference and its CI;
- event precision, signals per day and turnover (share of signals not signalled the day before);
- median price and median dollar volume of the signals;
- false signals per captured event; signals per security.
