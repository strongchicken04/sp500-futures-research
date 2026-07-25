# "EMA(9) + VWAP wick" (Instagram day-trading strategy) — test

Rules (from an Instagram transcript): EMA(9) + session VWAP (OHLC4 source), 3-min
chart. Enter when a candle *wicks through* VWAP (bounce/rejection); exit when a
candle closes beyond the EMA9. No stop specified.

Tested on NAS100 (NQ proxy) 3-min, 2016–2020 (~7.6 trades/day):

| variant | cost/side | trades | win% | avg bps | total | Sharpe | MaxDD |
|---|---|---|---|---|---|---|---|
| bounce, no stop (as described) | 0 (gross) | 8454 | 38% | +0.53 | +53% | 1.05 | −11% |
| **bounce, no stop** | **1 bp** | 8454 | 30% | **−1.47** | **−72%** | **−2.93** | −73% |
| bounce + wick stop | 1 bp | 9296 | 25% | −1.67 | −79% | −3.97 | −80% |
| breakout reading | 1 bp | 5358 | 30% | −1.39 | −53% | −2.03 | −57% |

**Verdict: textbook cost trap.** Gross there's a *whisper* of a mean-reversion edge
(+0.53 bps/trade, Sharpe ~1.0) — which is likely why it "feels" like it works. But at
~7.6 trades/day the round-trip cost (~2 bps, and that's optimistic for filling on a
fast wick) is **4× the gross edge**, so net it loses **−72% and is negative in every
single year**. Adding a stop or using the breakout reading only makes it worse.

This is a live demonstration of the VWAP-Trend journal's *Lesson 1: costs decide;
for high-frequency strategies they are life-and-death.* Any backtest of this without
realistic costs is a fairy tale.
