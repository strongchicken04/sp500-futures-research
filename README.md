# ORB (Opening Range Breakout) on NQ — strategy replication & backtest

Replication of the **5-minute Opening Range Breakout (ORB)** strategy from

> **Zarattini, C. & Aziz, A. (2023)** — *Can Day Trading Really Be Profitable?
> Evidence of Sustainable Long-term Profits from Opening Range Breakout (ORB)
> Day Trading Strategy vs. Benchmark in the US Stock Market.*
> SSRN **4416622**.

The paper trades **QQQ** with leverage over 2016–2023. Here we take the *same
mechanical rules* and apply them to the **Nasdaq-100 future (NQ)**, then backtest
on **QuantConnect** with real NQ minute data. Full rules: [`strategy/rules.md`](strategy/rules.md).

**TL;DR — the raw edge is real but marginal; it does *not* replicate the paper's
success on NQ and, as sized, badly underperforms simply holding NQ. Recommendation:
do not trade as-is → [Conclusion](#conclusion--go--no-go).**

---

## What was tested

| | Primary (definitive) | Supporting (robustness) |
|---|---|---|
| **Engine** | QuantConnect LEAN (cloud) | Standalone Python (`strategy/orb_backtest.py`) |
| **Instrument** | **NQ E-mini future** — real QC data | OANDA **NAS100** 1-min (NQ proxy) |
| **Window** | 2016-01 → 2024-01 (8y, covers paper) | 2005 → 2020-05 (incl. cost sweep) |
| **Sizing** | 5-min ORB L/S, **1% risk, 4× cap, 10R target** | identical rules |
| **Code** | [`strategy/quantconnect/main.py`](strategy/quantconnect/main.py) | [`strategy/orb_backtest.py`](strategy/orb_backtest.py) |

The two engines implement identical logic and agree closely (win rate ~24%,
profit factor ~1.05), which cross-validates the result.

---

## Primary result — QuantConnect, real NQ futures (2016–2024)

$1,000,000 start · 5-min ORB long+short · 1% risk / 4× leverage cap / 10R target.

![NQ ORB equity curve](results/qc_equity_curve_nq.png)

| Metric | Value |
|---|---|
| Total return | **+66.9%** (8 years) |
| CAGR | **6.6%** |
| Max drawdown | **−33.2%** |
| Sharpe / Sortino | **0.23** / 1.11 |
| Annualised vol | 24.4% |
| Win rate | 24.0% |
| Avg win / avg loss | +2.76% / −0.81% |
| Profit / loss ratio | 3.41 |
| **Profit factor** | **1.05** |
| Trades | 2,035 (~1 / day) |
| Max consecutive losses | **30** |
| Total fees | $272,224 |

The payoff profile is textbook ORB — **you lose small often (76% of trades,
median hold ~29 min stopped out) and win big rarely (winners run ~6 h to the 10R
target or the close)**. But the aggregate profit factor is only **1.05**.

### Per-year (real NQ)

| Year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|
| Return | +37.5% | −13.7% | +36.6% | +2.8% | −8.4% | +19.1% | +9.6% | **−16.2%** |
| Win rate | 25% | 24% | 24% | 23% | 22% | 27% | 24% | 22% |

Notably the strategy **lost 16% in 2023**, a year NQ rallied ~+54% — it does not
capture the very trend it is supposed to exploit.

### Versus buy & hold

| 2016–2023 | Strategy (ORB/NQ) | Buy & hold NQ¹ | Buy & hold SPY² |
|---|---|---|---|
| CAGR | **6.6%** | ~18% | ~14% |
| Total | +67% | ~+280% | +176% |

¹ NQ/QQQ rose roughly +280% over the window. ² SPY = QuantConnect's default
benchmark in the backtest. **Holding the index beat the strategy by ~3× with
comparable drawdown.**

> ⚠️ QuantConnect applied its per-contract fee model but **no explicit slippage**.
> Real ORB entries (09:35 market orders) and stop-outs slip; the proxy sweep below
> shows the edge is destroyed by ~3 bp/side of cost. **The 6.6% CAGR is therefore
> an optimistic upper bound.**

---

## Supporting result — cost sensitivity (NAS100 proxy, standalone engine)

Same rules, Python engine, OANDA NAS100 1-min. The edge is razor-thin and lives
entirely inside the first few basis points of transaction cost:

| Scenario | Window | Cost/side | Expectancy | Profit factor | CAGR | Sharpe | MaxDD |
|---|---|---|---|---|---|---|---|
| Gross | 2016–2020 | 0 bp | +0.216 R | 1.29 | +44.2% | **1.43** | −19% |
| Realistic | 2016–2020 | 1.5 bp | +0.216 R | 1.06 | +8.6% | 0.43 | −36% |
| Higher cost | 2016–2020 | 3 bp | +0.216 R | **0.88** | **−18.2%** | −0.56 | −71% |
| Full history | 2005–2020 | 1.5 bp | +0.109 R | 0.86 | −10.8% | −0.28 | **−90%** |

(Full matrix: [`results/summary_matrix.md`](results/summary_matrix.md),
chart: [`results/equity_curve_2016_2020.png`](results/equity_curve_2016_2020.png).)

Takeaways: (1) a **positive gross edge exists** (Sharpe 1.43 gross), but (2) it is
**consumed by realistic costs**, (3) it is **strongly regime-dependent** (great in
2008/2016/2018, negative in the low-vol grinds of 2017/2010/2012/2015), and (4)
leveraged compounding through the bad stretches produces **~90% drawdowns**.

---

## Why this doesn't match the paper

The paper's headline profits come from things the *plain index ORB does not have*:
1. **Leveraged-ETF compounding** (TQQQ ≈ 3× daily) stacked on the 4× intraday cap,
   in a **specific 2016–2023 equity bull regime**.
2. A later, stronger variant (**SSRN 4729284**) adds a **relative-volume / ATR
   filter and stock selection** — i.e. it trades only a minority of high-quality
   setups, not one index every day.
3. Applied to a single index future with whole-contract sizing and realistic
   futures costs, the raw signal is a ~1.05 profit-factor coin-flip-with-fat-tails.

---

## Conclusion — go / no-go

**No-go as-is.** On NQ the mechanical 5-min ORB is *not* a deployable standalone
edge:

- Profit factor ≈ **1.05**, Sharpe ≈ **0.23**, drawdown **−33%**, up to **30
  consecutive losers** — and that is *before* realistic slippage, which the proxy
  shows flips it negative around 3 bp/side.
- It **underperforms buy-and-hold NQ by ~3×** over the paper's own window and even
  **lost money in the 2023 rally**.

**Worth further research only with material changes** (in rough priority):
1. **Model slippage properly** before anything else — it is the make-or-break variable.
2. **Trade-selection filter** (relative volume / ATR / gap), per the follow-up
   paper — skip the low-expectancy low-vol days that bleed the equity curve.
3. **De-risk sizing** — drop the 4× cap toward volatility-target / fixed-fractional
   to cut the 33–90% drawdowns; use **MNQ** for granularity at retail size.
4. **Exit research** — the 10R target is hit on only ~2–5% of trades; test lower
   targets, trailing stops, or partial profit-taking.

---

## Reproduce

```bash
# 1. Standalone proxy backtest (data auto-clonable; see data/README.md)
python3 strategy/orb_backtest.py --data-dir <NAS100_dir> --start-year 2016 --end-year 2020 --out results/orb
python3 strategy/run_matrix.py   --data-dir <NAS100_dir> --out-dir results

# 2. QuantConnect (real NQ): open strategy/quantconnect/main.py in a QC project and Backtest.
#    A ready project already exists in the connected account: project 34424955.
```

Artifacts: [`results/`](results/) — QC statistics & equity JSON, proxy matrix,
charts. Extracted rules: [`strategy/rules.md`](strategy/rules.md).

*Backtests are historical simulations, not investment advice. The QC run excludes
slippage and is an optimistic bound.*
