# Stage 4.6: decision

**B — H-NEXT NOT SUPPORTED.**

Do not proceed to Stage 5. Do not start a controlled execution study for this rule.

- The rule and gate were pre-registered (`protocol.md`, commit 2e229f8). Amendments are technical only:
  1. the canonical panel after QC's data revision;
  2. a quote price-normalization defect, found, diagnosed (S46DIAG) and fixed; the affected runs are kept as
     INVALID.
- **Primary result** (S46MAIN v2, backtest 7a585d96…, VALID):

  | Measure | Value |
  |---|---|
  | L2 signals triggered (of 5,497) | 859 (15.6 %) |
  | Complete trades | 857 |
  | Mean net payoff, neutral cost | −3.13 % (security CI [−4.21, −2.12]; two-way [−4.91, −1.35]) |
  | Gross payoff | −0.73 % |
  | Target first | 12.1 % |
  | Adverse first | 60.0 % |

- **L2 vs STATE with the same rule:** +1.76 pp [0.03, 3.35]. Both are negative. L2 is not better than matched
  controls (+0.46 pp [−1.39, 2.15]) or the volume-only baseline (+0.32 pp).
- **Robustness:** negative in every period, leave-one-out, security group and secondary threshold or window variant.
- **Why it fails:**
  - The confirmation does select a somewhat better subset: at the next open it earns −1.02 % vs −2.91 % for all L2
    signals.
  - But waiting for a breakout above the prior high with $1M early volume moves the entry a median 4.6 % above the
    prior close. These stocks then mean-revert: median close t+5 is −4.5 % from the entry, and the −10 % limit is hit
    first in 60 % of trades.
- **The five claims:**

  | Claim | Verdict |
  |---|---|
  | Detects a continuation | partly (trigger 15.6 % vs 5.8 % for STATE) |
  | Obtains a better entry | no (−2.1 pp vs the next open for the same subset) |
  | Positive gross payoff | no |
  | Positive net payoff | no |
  | Robust strategy | no |

## Recommendation
Close the long-side extreme-upside line for daily-signal-based entries, in both the next-open and the
intraday-confirmation forms.
- The shadow log framework exists (S46SHADOW). Running it prospectively is only worth it if a new, separately
  pre-registered hypothesis is formulated.
- The prospective sample needed for one is about 304 triggered trades, about 1.8 years on the 20 % sample.
- The selected stocks drift down after signals. That points to a short-side hypothesis, but it needs borrow
  availability and fee data that QC does not provide here. It is not proposed as a next step without that data.
