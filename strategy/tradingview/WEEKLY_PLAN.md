# Lucid Flex 50K — Plan v2

Rebuilt after a round of literature research and a corrected barrier simulator.
Several conclusions from v1 were wrong; what changed and why is at the bottom.

---

## The three rules that actually govern this account

**1. The drawdown line locks.** It trails the highest *end-of-day* balance, but
once an EOD close clears **$52,100** it freezes at **$50,100** permanently.
At that moment you hold $2,000 of room with only $900 left to target.
→ *Sprint to a $52,100 close, then coast.* The last $900 is near-risk-free.

**2. Consistency is a ratio, not a dollar cap.** Largest single day must be
≤ 50% of **final** profit. It gates the upgrade, it does not kill the account,
and **overshooting relaxes it**. If your best day was $1,800, finish at $3,600
rather than grinding ten more small days.

**3. There is no published time limit.** Lucid documents no deadline for
LucidFlex. The 8-week window in v1 was self-imposed — and it is the single most
expensive assumption in the whole plan. ⚠️ **Verify this with Lucid before
anything else.** It changes the optimal size by a factor of two.

---

## The volatility gate — biggest single improvement found

**Do not trade when 20-day realised volatility is above 30% annualised.**

Stops are set in points, so the same rule risks far more dollars per trade in
a high-volatility regime and the trailing drawdown arrives much sooner. Sitting
out those days costs little and buys a lot:

| | pass | bust |
|---|------|------|
| no gate | 76.1% | 15.5% |
| **gate at 30%** | **79.7%** | **9.0%** |

It blocks about **17% of sessions** and holds up in both halves of the sample.
The gate is wired into the indicators; the badge turns red and shows the
current reading when a day is blocked.

The exact threshold should not be trusted to two decimals — anything from
0.22 to 0.30 improves things, 0.28 scored best, and 0.30 is the robust pick.

---

## Sizing — depends entirely on rule 3

Measured on the full portfolio, conditional on your current state (+$200 banked):

| Size | 39 days left | 79 days left | 119 days left |
|------|--------------|--------------|---------------|
| 1 MNQ | 0% | 11% | 35% |
| **2 MNQ** | 29% | **62%** | **70%** |
| 3 MNQ | **44%** | 67% | 66% |

**If the 8-week deadline is real → 3 MNQ.** Nothing else reaches the target in time.
**If there is no deadline → 2 MNQ and take as long as needed.**

With the volatility gate on, flat 2 MNQ reaches **85.3% pass / 10.6% bust**
over 120 days. Two sizing ideas were tested and rejected: scaling up after the
drawdown line locks (it adds bust faster than it shortens the run), and sizing
proportional to cushion (better than flat only when the deadline is short —
55.9% vs 48.9% at 40 days, but behind it at 120).

This follows Pestien & Sudderth (1985): maximising P(reach goal before ruin)
means maximising μ/σ², and since size scales drift linearly but variance
quadratically, the smallest workable size wins whenever you have a real edge
and no clock. 1 MNQ has a **0% bust rate at every window tested** — it cannot
fail, it can only run out of time.

Daily loss stop: **$240 at 2 MNQ, $300 at 3 MNQ**. Tighter stops beat looser
ones in every sweep. Day profit cap: **stop at +$1,450**.

---

## The book

| # | Strategy | Edge | Status |
|---|----------|------|--------|
| 1 | **S1 ORB 15m long** | the workhorse, 46% pass alone | ✅ tested |
| 2 | **VWAP band SL25/TP100** | +11pp on top of S1 | ✅ tested, **SL changed from 15 to 25** |
| 4 | **Overnight gap reversal** | +10pp, *new* | ✅ tested |
| 3 | Mon/Fri EOD hold | +1pp, marginal | ✅ tested, keep |

Combined, 2 MNQ, 80-day window: **~61% pass / 19% bust** on the overlap sample.

### Daily schedule

| Time ET | What |
|---------|------|
| **09:30** | Gap ≤ −0.25% vs prior close? → **long the open**, hard stop 15 pt |
| **09:30** | Mon/Fri only: first 5m bar vs EMA12 → enter, stop at that bar's wick |
| **09:40+** | VWAP ±20bps band breaks → enter, **SL 25 / TP 100** |
| **09:45–15:00** | ORB: close > OR high *and* > VWAP → long, trail 20-EMA. **Re-enter freely** |
| **15:30** | *(S6, once backtested)* ROD ≤ −0.20% → short into the close |
| **15:55** | Flat everything |

Skip Wednesday. Max two positions at once; if a third fires in the same
direction, skip it.

---

## How much of this to believe

The headline numbers above are averages over 2018-2025, and that average hides
a wide spread. Same configuration, same rules, split by period:

| Period | pass | bust |
|--------|------|------|
| 2018-2020 | 50% | 0% |
| 2020-2022 | 98% | 0% |
| 2022-2024 | 98% | 0% |
| 2024-2026 | 67% | 28% |

The book is long-biased — ORB is long-only, the gap reversal is long-only — so
it feasts in a bull market and grinds in anything else. **Plan on ~65%, not
~85%.** The 85% is a bull-market number.

The drop in the most recent period is *not* edge decay. Per-trade edge is
stable or improving: S1 averaged +1.73 pt in 2018 and +4.26 pt in 2025. What
changed is that 2025 was volatile enough that the gate sat out most of it —
233 qualifying trades versus 605 in 2024. The filter costs time, not money,
which is survivable if rule 3 holds and expensive if it does not.

Worth keeping in view: a driftless walk passes this challenge at
L/(L+T) = 40%, and ~35% once costs and the trailing floor are modelled
(Villahermosa, SSRN 7445798). That is the bar. A 65% planning figure is a real
edge over it; it is not a sure thing.

---

## What changed from v1, and why

**S1 ORB must re-enter.** v1's indicator allowed one trade per day. That is
wrong: the backtest averages 4.5 entries per day, and capping it at one drops
the standalone pass rate **from 46% to 9%**. Later entries are the better ones
— hit rate climbs from 37% on the first to 61% by the seventh, because the
trend has declared itself. *The indicator has been fixed.*

**VWAP stop moves 15 → 25.** v1 picked SL15/TP100 by total points. Re-scored on
pass rate, **SL25/TP100 wins (57.7% vs 52.7%)**. Total points is a bad proxy:
the most profitable cell in the whole grid (SL60/TP200, 10,819 pts) passes only
44% — worse than running S1 alone.

**The old 64% was measured against the wrong rules** — no MLL lock, and the
consistency rule modelled as a flat $1,500 kill rather than a 50% ratio that
dilutes with more profit. The lock makes things better; the ratio makes them
worse. Current numbers supersede it.

**Drop the "reversal after a large down day" idea.** Published in JAM 2011, but
it does not replicate on NQ: **−6.33 pt per trade**, and it subtracts 8.7pp from
the portfolio. Turn-of-month is also near-worthless here (+0.8pp).

**There is no usable short side in NQ daily data.** Four candidates were built
and tested to balance the long bias: gap-up fade (+0.52 pt, stable but too
small to matter), downtrend bounce fade (+0.42 overall but negative in both
recent sub-periods), four-day-streak exhaustion (−2.11) and down-day
follow-through (−3.96). Shorting fights the instrument's structural drift. The
long bias is a property of NQ, not a bug in the book — the only short worth
testing is the intraday ROD leg, which needs minute data.

**Zero-edge benchmark: 40%.** A driftless walk passes at L/(L+T) = 2000/5000.
With trailing floors and costs, Villahermosa (SSRN 7445798) measures ~35%.
Anything we build has to beat that bar to be worth anything, which is the right
way to read the numbers above.

---

## Still untested

Three strategies are coded and queued but could not be backtested — this
session's container has no QuantConnect credentials and the egress policy
blocks market-data hosts:

- **S6 ROD momentum** (`prop_s6_rod_momentum.py`) — the best-evidenced
  candidate found. Baltussen et al., *JFE* 142(1) 2021: NQ t = 7.97. Short leg
  only, for decorrelation from the long-only ORB. 29 minutes of exposure a day.
- **S7 gap fade** (`prop_s7_gap_fade.py`) — practitioner evidence only, no
  peer-reviewed backtest. Queued on shape, not proof.
- **Lunch drift 11:00–14:00** — Vojtko & Dujava, SSRN 4934614. Not yet coded.

Restore QC credentials and these can be measured in an afternoon.
