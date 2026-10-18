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

**3. There is no time limit.** Confirmed with the account. The 8-week window
in v1 was self-imposed, and dropping it is the largest single improvement
available — it is what makes the small-size policy below possible.

---

## The full lifecycle — sizing per phase

All four account rules are now confirmed: no time limit, the drawdown line
locks at $50,100 once an EOD close clears $52,100, it **stays** locked after a
withdrawal, and payouts come every 5 days.

That last pair changes everything about the funded phase, because the barrier
problem is a different shape in each stage:

| stage | what a bust costs | barrier | size | survives | time |
|-------|-------------------|---------|------|----------|------|
| evaluation | **one $150 fee** | hard | **2 MNQ** | 94% | **1.6 mo** |
| first funded cycle | **the seat** | hard | 1-2 MNQ | 100% / 93% | 4.9 / 2.4 mo |
| repeat cycles | the seat | **easy** | **3 MNQ** | 88% | **13 days** |

Size should follow the cost of failing multiplied by how hard the barrier is,
and those two move in opposite directions across the lifecycle. **An
evaluation bust costs a fee. A funded bust costs the seat** — and the seat is
worth $1,800 every 13 days thereafter. Being equally careful in both is the
mistake the earlier version of this plan made.

In the evaluation, caution is close to worthless:

| eval size | pass | median | expected months | expected fees (×5) |
|-----------|------|--------|-----------------|--------------------|
| 1 MNQ | 97.3% | 71 d | 3.44 | $771 |
| **2 MNQ** | **94.1%** | **33 d** | **1.63** | **$797** |
| 3 MNQ | 75.9% | 20 d | 1.13 | $988 |

Dropping to 1 MNQ buys 3.1 percentage points of pass rate for **1.8 extra
months**. Going past 2 MNQ costs real money: 3 MNQ saves another half month
for $190 in extra fees and a pass rate down in the seventies. Ramps were
tested too and none beat flat 2 MNQ.

Timeline, five copytraded accounts: **1.6 months of evaluation, 2.4 months to
the first payout, then $9,000 roughly every 13 trading days.** First money at
about month four, against month 7.4 under the all-1-MNQ plan.

The repeat cycle is the easiest barrier in the whole lifecycle and it is where
being timid costs the most. You start with **$1,900 of cushion against a
frozen line** and need only $2,000 — the line cannot chase you upward any
more. Running 1 MNQ there buys a 100% survival rate that is not worth having:

| size on repeats | survives | median | $/account/month |
|-----------------|----------|--------|-----------------|
| 1 MNQ | 100% | 55 d | $687 |
| 2 MNQ | 94.3% | 22 d | $1,418 |
| **3 MNQ** | **88.0%** | **13 d** | **$1,703** |
| 4 MNQ | 81.9% | 9 d | $1,644 |
| 1 NQ | 68.3% | 3 d (5 d floor) | $1,147 |

Those figures already charge each bust the replacement cost — the eval fee
plus 2.5 months of re-qualifying. The 5-day payout floor does not bind until
past 5 MNQ, so it is the bust rate that caps aggression, not the schedule.

Across five accounts: **$8,515/month at 3 MNQ against $3,436 at 1 MNQ.** Over
two years that is roughly $153,000 versus $66,000, from one change that leaves
the evaluation and first cycle conservative.

**Stagger the five starts by about a month.** Five accounts trading one
strategy from the same day are not five bets — identical trades give identical
outcomes, so it is one bet at five times the size. Staggering leaves expected
passes unchanged (3.7 of 5) while dropping the chance that *nothing* works
from 26% to under 2%.

⚠️ Still unverified and capable of voiding all of it: whether Lucid permits
near-identical trading across several accounts. Many firms restrict it. Check
before buying the extra evaluations.

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

## Sizing — the answer, now that rule 3 is settled

**Run 1 MNQ until banked profit reaches $800, then switch to 2 MNQ. Never go
above 2.**

Conditional on the current state (+$200 banked), over a 200-day horizon:

| policy | pass | bust | median days |
|--------|------|------|-------------|
| 1 MNQ throughout | 93.5% | **0.0%** | 67 |
| **1 → 2 MNQ at $800** | **96.1%** | **1.5%** | 49 |
| 1 → 2 MNQ at $600 | 95.1% | 2.4% | 43 |
| 2 MNQ throughout | 94.4% | 5.6% | 33 |
| 3 MNQ throughout | 77.0% | 23.0% | 20 |

Flat 1 MNQ **never busts anywhere in the 2018-2025 sample**, at any window
length tested. It cannot fail, it can only run long. The ramp keeps nearly all
of that safety and finishes about three weeks sooner, because the busts happen
early, while the cushion is thin and the trailing line is close behind.

Three MNQ is where it comes apart: a quarter of attempts die. Resist it.

By sub-period the ramp passes at 86.5% / 100% / 98.9% across 2018-2021,
2021-2024 and 2024-2026, so even the worst stretch clears 85%.

Daily loss stop: **$150 on 1 MNQ, $240 on 2 MNQ**. Day profit cap $1,450.

### Where the drawdown line sits

It ratchets to $2,000 below the highest **end-of-day** balance and never
retreats: close at $50,600 and the line is $48,600; fall back to $50,200 the
next day and it stays at $48,600. Once an EOD close clears $52,100 it locks at
$50,100 for good — $2,000 of room with $900 left to run.

The lock is worth little at the recommended size (96.1% with it, 94.7%
without) and a lot at 3 MNQ (77.0% versus 68.9%), which is one more reason not
to go there.

------|--------------|--------------|---------------|
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
| 1 | **S1 ORB 15m long** | the workhorse | ✅ verified 2018-2025 |
| 2 | **VWAP band SL25/TP100** | +11pp on top of S1 | ✅ verified, **SL changed from 15 to 25** |
| 4 | **Overnight gap reversal** | +4pp | ✅ verified on minute data |
| 3 | Mon/Fri EOD hold | +1pp, marginal | ✅ keep |

Combined, 2 MNQ, vol-gated: **82% pass / 8% bust at 80 days**, 90% / 8% at 120.

### Rejected after testing

| Candidate | Why |
|-----------|-----|
| **ROD momentum** (Baltussen, *JFE* 2021) | best-evidenced idea in the whole review, NQ t = 7.97 — and it has decayed. Positive 2018-2022, then −1.39 pt in 2023 and −4.46 in 2024. Their sample ends 2020. Costs 2.8pp. |
| **Gap fade** | −8.27 pt per trade, negative in seven of eight years |
| Reversal after large drop (*JAM* 2011) | −6.33 pt on NQ, costs 8.7pp |
| Turn-of-month | +0.8pp, noise |
| Four short-side rules | all weak or negative; shorting fights NQ's drift |
| All twenty lab-archive strategies | best is 34.8% pass at 64% bust |

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

Headline numbers are averages over 2018-2025. Split by period, at 80 days:

| Period | pass | bust |
|--------|------|------|
| 2018-2020 | 58% | 22% |
| 2020-2022 | 84% | 0% |
| 2022-2024 | 99% | 0% |
| 2024-2026 | 83% | 16% |

That spread is much tighter than the previous version of this book managed
(50 / 98 / 98 / 67), and the gain came from the volatility gate and the tight
percentage stops rather than from new strategies. **Plan on ~60%, the worst
observed period**, and treat anything above it as the market cooperating.

The book is long-biased — ORB is long-only, the gap reversal is long-only —
because four separate attempts to build a short side all failed. That bias is
a property of NQ's drift, not a gap in the research.

Two benchmarks worth holding in view, because they frame what "good" means:

- A driftless walk passes at L/(L+T) = 40%, or ~35% with costs and the
  trailing floor modelled (Villahermosa, SSRN 7445798).
- **Leveraged long NQ with a stop, risk-matched to this book, passes at
  roughly 37% over 80 days and 61% over 120.** That is the honest bar, not
  the 40%. This book beats it clearly at 80 days and by less at 120. An
  earlier comparison appeared to show buy-and-hold winning outright; that was
  an artefact of comparing at equal contract count rather than equal risk —
  the buy-and-hold leg was running 3.6× the daily volatility.

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

**Express every stop as a percentage, never a point count.** The gap
reversal's 15-point stop was fitted on a panel where NQ traded near 5,000,
making it 0.30% of price. At 22,000 the same number is 0.07% — the rule
silently tightened fourfold while looking unchanged. Sweeping every stop
definition against recorded excursions, tighter is emphatically better here:

| stop | pass (80d) | bust |
|------|-----------|------|
| **0.05% of price** | **82.2%** | 7.7% |
| 0.10% of price | 81.5% | 7.9% |
| 0.35% of price | 73.1% | 18.0% |
| 0.25 × ATR | 68.4% | 22.9% |
| 1.00 × ATR | 59.6% | 34.7% |

ATR-scaled stops are the worst of the lot. The reason the tight stop wins is
that the winners run to the close regardless of how wide the stop is, so stop
width only sets what the losers cost. **Do not widen it after a losing
streak.** At 30,000 the 0.05% rule is about 15 points.

**The gap reversal is a lottery ticket — expect it to feel bad.** About 85% of
entries stop out small; the remaining 15% run to the close, several above
+300 points. Earlier daily testing suggested a 35% win rate; on real minute
data it is 15%. The expectancy is fine (+8.91 pt per trade over 2021-2025)
but it arrives in a handful of days.

**The whole lab archive is unusable.** All twenty previously-backtested
strategies were re-scored on pass rate: the best manages 34.8% with a 64% bust
rate, against 46% for ORB alone. The reason is one column — every one of them
averages between −30 and −175 points on a losing trade, against −13 for ORB.
On a trailing-drawdown account a wide stop is disqualifying regardless of how
good the entry is. **Average loss under ~20 points is the screening test** any
new idea has to pass before it is worth simulating.

**The stop width cliff is sharp.** Same gap-reversal rule, varying only the
stop: 15 pt gives 18.7% bust, 20 pt gives 34.2%. Nearly double, for five
points of room.

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
