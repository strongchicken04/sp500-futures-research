# Lucid Flex 50K — final plan

Five copytraded accounts. Every number below comes from simulating the actual
strategy book through the actual account rules over NQ 2018-2025, charging
every evaluation fee and every rebuild.

---

## The rules this is built on

All confirmed against the live account:

- **No time limit.**
- Drawdown is **$2,000 below the highest end-of-day balance**, ratcheting up
  only — close at $50,600 and the line is $48,600; fall to $50,200 and it
  stays at $48,600.
- The line **locks at $50,100** once an EOD close clears $52,100, and **stays
  locked after a withdrawal**.
- Consistency (evaluation only): best day ≤ 50% of final profit. It gates the
  upgrade, it does not kill the account, and extra profit dilutes it.
- Funded: **+$4,000** unlocks the first payout — withdraw half, Lucid takes
  10%, you receive **$1,800**. Afterwards the balance sits at $52,000 against
  the locked $50,100, so each further payout needs only **+$2,000**.
- **Payouts every 5 days. Copytrading permitted.**

---

## The book

Four strategies, all on NQ/MNQ, all flat by 15:55 ET, all skipping Wednesday.

| | strategy | entry | stop | exit |
|---|---|---|---|---|
| 1 | **ORB 15m long** | after 09:45, close > OR high *and* > VWAP | max(OR low, close − OR range) | 20-EMA trail, or 15:55 |
| 2 | **VWAP band** | close breaks ±20bps band | 25 pt | TP 100 pt, or 15:55 |
| 3 | **Mon/Fri hold** | first 5m bar vs EMA12 — Mon long, Fri short | that bar's wick | 15:55 |
| 4 | **Gap reversal** | RTH open ≥ 0.25% below prior close | **0.05% of price** | 15:55 |

**Two rules that matter more than any entry:**

- **Do not trade when 20-day realised volatility is above 30% annualised.**
  It blocks about 17% of sessions, and it lifts pass rate while roughly
  halving bust. Wired into all four indicators.
- **ORB re-enters freely.** Capping it at one trade per day drops its
  standalone pass rate from 46% to 9%. Later entries are the better ones —
  hit rate climbs from 37% on the first to 61% by the seventh.

Maximum two positions open at once. If a third fires in the same direction,
skip it.

---

## Sizing — 3 MNQ throughout

| stage | need | what a bust costs | survives | median |
|-------|------|-------------------|----------|--------|
| evaluation | +$3,000 | one $150 fee | **75.9%** | 20 days |
| first funded cycle | +$4,000 | the seat | **73.1%** | 26 days |
| repeat cycles | +$2,000 | the seat | **88.0%** | 13 days |

Daily loss stop **$300**. Day profit cap **$1,450**. Never exceed 3 MNQ —
at 4 MNQ and beyond the extra bust rate outruns the extra speed, and past
5 MNQ the 5-day payout floor caps the gain anyway.

The repeat cycle survives far better than the other two because it starts at
$52,000 against a **frozen** $50,100 line: $1,900 of cushion that can no
longer chase you upward. It is the easiest barrier in the lifecycle.

---

## What to expect over 24 months

Five accounts, all fees and rebuilds charged:

| | 2 MNQ throughout | **3 MNQ throughout** |
|---|---|---|
| median profit | $124,500 | **$148,500** |
| p10 (bad run) | $70,500 | **$96,000** |
| p90 (good run) | $179,250 | $203,250 |
| first payout, median | month 4.3 | **month 3.6** |
| P(reach a payout) | 100% | **100%** |
| P(net loss at 24 months) | 0% | **0%** |
| evaluation rounds bought | 1.9 | **5.4** |

3 MNQ is better at every percentile, including the bad tail. The cost is
churn: **about 27 evaluations over two years**, roughly $4,000 in fees, and
the accounts dying and being rebuilt perhaps five times.

**If that churn is intolerable, run 2 MNQ.** It gives up around 16% of the
median and buys a far quieter two years — 1.9 rounds of evaluations instead
of 5.4. The money is similar; the experience is not.

---

## Daily routine

| time ET | |
|---|---|
| 09:25 | Check the volatility badge. Red → **no trading today** |
| 09:30 | Gap ≤ −0.25%? → long the open, stop 0.05% of price |
| 09:30 | Mon/Fri only: first 5m bar vs EMA12 |
| 09:40+ | VWAP band breaks live |
| 09:45–15:00 | ORB window — re-enter as often as it triggers |
| 15:55 | **Flat everything** |
| after close | Log the balance; check whether the line has locked yet |

Stop for the day at **−$300** or **+$1,450**.

---

## What this rests on, and where it could be wrong

**The book is long-biased.** ORB is long-only and so is the gap reversal, and
four separate attempts to build a short side all failed — shorting fights
NQ's drift. Expect the whole thing to do better in a rising market.

**Sub-period spread, 80-day evaluation windows:** 58% / 84% / 99% / 83% across
2018-2020, 2020-2022, 2022-2024 and 2024-2026. The headline figures sit near
the middle of that range, not at the top.

**The gap reversal is a lottery ticket.** Roughly 85% of its entries stop out
small and 15% run to the close, several above +300 points. Expectancy is good
(+8.91 pt per trade over 2021-2025) but it arrives in a handful of days. Do
not widen its stop after a losing streak — the winners run to the close
regardless of stop width, so width only sets what the losers cost.

**The honest benchmark is not zero.** A driftless walk passes at 40%; leveraged
long NQ with a stop, risk-matched to this book, passes at roughly 37% over 80
days and 61% over 120. This book clears that, but it is an edge, not a
machine.

**Two modelling assumptions worth watching in the first live cycle:** that
busted seats can be replaced promptly at the quoted fee, and that the repeat
cycle really does restart at $52,000 against the locked line. If either is
wrong the repeat-cycle numbers are the ones that move.
