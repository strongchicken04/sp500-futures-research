# 5-minute Opening Range Breakout (ORB) — extracted rules

Source paper:

> **Zarattini, C. & Aziz, A. (2023).** *Can Day Trading Really Be Profitable?
> Evidence of Sustainable Long-term Profits from Opening Range Breakout (ORB)
> Day Trading Strategy vs. Benchmark in the US Stock Market.*
> SSRN Working Paper **4416622**.

The paper trades **QQQ** (Nasdaq-100 ETF) intraday over 2016–2023 and reports
large, leverage-driven outperformance vs buy & hold. This repo takes the **same
mechanical rules** and applies them to the **Nasdaq-100 future (NQ)**.

---

## The mechanical rules (5-minute ORB, long & short)

| Element | Rule |
|---|---|
| **Session** | US equity cash session, 09:30–16:00 America/New_York (RTH). |
| **Opening range (OR)** | The **first 5-minute candle**, 09:30–09:35 ET. |
| **Direction** | `OR.close > OR.open` → **long**; `OR.close < OR.open` → **short**; equal → **no trade** (doji). |
| **Entry** | Market order at the **open of the 2nd 5-minute candle (09:35 ET)**, in the OR direction. |
| **Initial stop** | Opposite extreme of the OR — **long: OR low, short: OR high**. |
| **R (unit risk)** | `R = |entry − stop|`. If `R = 0`, skip the day. |
| **Profit target** | **10 R** (`entry ± 10·R`). |
| **Time exit** | If neither stop nor target is hit, **flatten at the session close (16:00 ET)**. |
| **Frequency** | **At most one trade per day.** |

## Position sizing (the paper's model)

```
Shares/contracts = min( riskPct · Equity / R ,  maxLev · Equity / EntryPrice )
```

* `riskPct = 1%` of current equity risked per trade (so a full stop-out ≈ −1R ≈ −1% *when the risk cap binds*).
* `maxLev = 4×` — the Reg-T pattern-day-trader intraday buying-power cap used in the paper.
* Equity **compounds** trade to trade.
* The `min(...)` means the position is the **smaller** of the risk-based size and
  the leverage-based size. When the opening range is small relative to price
  (common on an index), the **leverage cap binds** and the position risks *more*
  than 1% per trade.

For a **future** the multiplier replaces share price:

```
contracts = floor( min( riskPct · Equity / (R · mult) ,  maxLev · Equity / (Price · mult) ) )
```

with NQ E-mini `mult = $20 / index point` (Micro MNQ = `$2 / point`).

## Costs

The paper reports results **net of commissions**. Here, on futures:
* QuantConnect applies its per-contract fee model (~$1.85–2.10 / contract / side for NQ).
* The standalone Python engine applies `cost_bps_per_side` (default 1.5 bp of
  notional per side) as combined slippage + commission.

---

## Key adaptation notes: QQQ → NQ

1. **Instrument.** QQQ (cash ETF, Reg-T 4× intraday) → NQ E-mini future
   ($20/pt, ~23 h Globex session, futures margin allows far more than 4×).
   We deliberately **keep the paper's 4× cap** for a faithful replication.
2. **Opening range time.** NQ trades almost around the clock, but the ORB edge
   is tied to the **09:30 ET equity cash open**. The opening range is therefore
   defined on the 09:30–09:35 ET window and the rest of the Globex session is
   ignored — exactly as an equity-open ORB would be traded on the future.
3. **Fractional exposure.** QQQ allows fractional-share precision; NQ trades in
   whole contracts. With a $1M book the integer-rounding error is small; at
   retail size the **Micro (MNQ)** gives back the granularity.
4. **Leverage realism.** The paper's outperformance leans heavily on leverage
   (up to 4×, or 3× via TQQQ → effectively much more). On NQ the same 4× cap is
   applied; higher futures leverage would scale both returns *and* drawdowns.

See `../README.md` for backtest results and the go/no-go conclusion, and
`quantconnect/main.py` for the QuantConnect implementation.
