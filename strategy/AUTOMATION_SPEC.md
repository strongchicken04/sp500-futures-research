# Automation spec (route-neutral)

> Česky: přesná pravidla všech strategií v plánu jako podklad pro automatizaci
> (NinjaScript i TradingView + webhook). Nic z toho samo neobchoduje; co pustit
> naživo, rozhoduješ ty. Stav k noční směně 23./24. 10. 2026.

Instrument: MNQ (front month), $2 per point. Times are US Eastern (ET). RTH
09:30-16:00. Every position is flat by the close of the 15:55 bar (no
overnight holds). Fill rules used in all backtests (keep them in code):
entry at the close of the signal bar; exits checked from the NEXT bar; a bar
that touches both stop and target counts as the stop; a stop fills at the
worse of the stop price and the bar open.

Daily inputs always come from the last COMPLETED session (no look-ahead):
- `rv20` = stdev of the last 20 daily close-to-close returns of NQ x sqrt(252).
- `trend50` = sign(prior close - 50-day SMA of closes).
- Vol gate: trade a leg only if `rv20 < 0.30`.

## Account roles

| account | stage | runs |
|---|---|---|
| A | evaluation | RS sprint (Lucid 8) |
| B | evaluation (optional since 2026-10-26: RS alone earns more per funded seat) | 09:31 trend sprint (Lucid 7) |
| F1..F5 | funded | the book, identical copies (VG + Z + RS leg; ORB dropped if the owner agrees) |

### Cross-account hedge guards (Lucid bans opposite positions across own accounts)
1. A skips its RS signal when B holds an open 09:31 position in the opposite
   direction (A does not trade later that day).
2. General rule (2026-10-24): an entry that would be OPPOSITE to a position
   already open on any other own account is skipped - "whoever comes second
   skips" (funded copies skip together; exits are never blocked).

## Evaluation sprints (one trade a day per account)

Common sizing (per trade):
```
lossPer = |entry - stop| * 2          # $ per MNQ at the stop
winPer  = |target - entry| * 2
n = min(40, max(1, min(floor(1900 / lossPer), floor(1450 / winPer))))
# finishing trade (evalPnl = evaluation profit so far, closed, in $):
if evalPnl >= 2100 and 3000 - evalPnl <= 1450:
    fin  = max(1, ceil((3000 - evalPnl + 60) / (winPer - 2)))
    safe = max(1, floor((evalPnl - 100 - 50) / (lossPer + 3)))
    n = min(n, fin, safe)
# intraday drawdown (2026-10-25): Lucid breaches as soon as the INTRADAY
# balance touches the line (line = -2000 at the start, best EOD profit - 2000,
# +100 once an EOD balance cleared +2,100). Every trade must fit the room:
stopPer = lossPer + 0.75 * 2 + 1                  # stop slippage + costs as in the sims (Pine: lossPer + 3)
fit = floor((evalPnl - line - 50) / stopPer)
if fit < 1: no trade - the account is dead, start a new evaluation
else: n = min(n, fit)
```
Stop the evaluation account after it reaches +$3,000 with the best day <= 50%
of the profit; a bust (balance at the trailing drawdown) ends it.

**RS sprint (account A, Lucid 8).** Checks at the closes of the bars ending
10:00, 11:00, 13:00 and 14:30. `rs = (NQ / NQ_open0930 - 1) - (ES / ES_open0930 - 1)`.
LONG if `rs > +0.0015` and NQ close > session VWAP; SHORT if `rs < -0.0015`
and close < VWAP. Only the first signal of the day. Target +0.20%, stop
-0.30% of the entry price; else flat 15:55. No vol gate.

**09:31 trend sprint (account B, Lucid 7).** At the close of the 09:30-09:31
bar: direction = `trend50` (long above the 50-day SMA, short below). Target
+0.25%, stop -0.40%; else flat 15:55. Vol gate OFF.

## Funded book (each leg: MNQ = floor(90,000 / NQ price) - 3 at NQ ~28,500)

Payout plan: request $2,000 when the profit is >= $4,000 and the cycle has
five days with >= $150 profit; leave the rest on the account. No day stop.

**VG - VWAP band break (Lucid 2), 5-min bars.** Band = RTH VWAP x (1 +/- 0.20%).
Entry when the previous 5-min close was inside the band and this close is
outside: above -> LONG, below -> SHORT. First trade of the day only; not on
Wednesdays; vol gate on. Stop 25 pt, target 100 pt from entry; else flat 15:55.

**Z - noise momentum (Lucid 6), decisions at :00 and :30 from 10:00 to 15:30.**
`sigma(t)` = mean over the last 14 sessions of |price at time t / 09:30 open - 1|.
Upper = max(open, prior close) x (1 + sigma), lower = min(open, prior close) x
(1 - sigma). At a decision time: close > upper -> long; close < lower -> short;
an opposite signal reverses. A long exits at a decision time when the close is
below max(upper, VWAP); a short when above min(lower, VWAP). Hard stop 0.50%
from the entry, checked on every bar after the entry bar. Flat 15:55. Vol
gate on.

**RS leg (Lucid 8 with Target 1.25 / Stop 1.25).** Same signal as the RS
sprint (first signal of 10:00 / 11:00 / 13:00 / 14:30), fixed size, symmetric
bracket +/-1.25%, else flat 15:55. Vol gate on.

**V10 - VWAP side at 10:00 (Lucid 12 as funded leg; CANDIDATE only - lost in the 2026 holdout).**
At the close of the 09:59-10:00 bar: long if the close is above the RTH VWAP,
short if below. Target +0.30%, stop -0.50% of the entry; else flat 15:55.
Fixed size, vol gate on.

**Not in the plan:** ORB (Lucid 1, recommended to drop), open drive (Lucid
10, optional 4th leg at the same size: at 10:00, if the 09:30-10:00 low >=
open x (1 - 0.05%) and the close >= open x (1 + 0.15%) -> long, mirror short;
stop open -/+ 0.05%, flat 15:55, vol gate on).

## Checks an implementation must pass before going live
- Replay 2022-2025 and compare the trade list with the research exports
  (`data/tags`, scorers in `scripts/`): same days, directions and exit
  reasons for >= 95% of trades.
- Paper-trade the hedge guards for at least two weeks with all accounts.
- Respect LucidFlex scaling on funded accounts (20 MNQ until +$1,000 profit,
  30 until +$2,000, then 40) and the 40 MNQ evaluation limit.
