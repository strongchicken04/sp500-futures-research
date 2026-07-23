# TradingView indicator — NQ 5-min ORB (regime-filtered)

Pine Script v5 indicator that draws the **entry, stop-loss and 10R target** for the
5-minute Opening Range Breakout on NQ and decides on its own whether the day
qualifies, using the regime filter.

File: [`nq_orb_indicator.pine`](nq_orb_indicator.pine)

## Install
1. TradingView → **Pine Editor** → paste the contents of `nq_orb_indicator.pine`.
2. **Add to chart**. Use it on an **NQ futures chart at 5-minute** resolution
   (1-minute also works; higher timeframes than the OR window will not).

## What it draws
For every day the filter accepts, at **09:35 ET** it draws **three clear horizontal
lines that extend to the right edge**, each with a live price tag pinned to the
right so you can place paper orders straight off them:
- **ENTRY** (blue) at the 09:35 price,
- **STOP-LOSS** (red) at the opposite extreme of the 09:30–09:35 opening range,
- **TAKE-PROFIT** (green) at **10R**,
- plus the opening-range **box** (09:30–09:35), and a **✔ TP hit / ✖ SL hit** marker
  when price reaches a level.

Lines are cleared automatically at the next cash open, so the chart always shows the
current day's trade. Days the filter rejects simply draw nothing.

## Filter modes (input)
- **Best (v3)** *(default)* — the best risk-adjusted build:
  `(rvol20 > 0.156 OR |gap| > 0.30%) AND trend50 ≤ 4.06%`.
- **Re-fit (v4)** — the later re-fit: `(|gap| > 0.33% OR rvol20 < 0.122)`, and on
  **gap-down days it takes shorts only**.

`rvol20` = 20-day annualised realised vol, `gap` = 09:30 open vs previous close,
`trend50` = previous close vs its 50-day SMA — all from daily data, as of the prior
completed session (non-repainting).

## Notes / caveats
- **Levels only.** Position sizing / **volatility targeting** (the money-management
  layer, see the repo README) is deliberately not part of this indicator — it does
  not change the entry/SL/TP levels, only how many contracts you trade.
- Daily features use the chart symbol's daily bars; if your chart shows the full
  Globex (ETH) session, the daily open/close differ slightly from the 09:30/16:00
  cash values used in the research (immaterial for 20/50-day features).
- `ta.stdev` is population (biased); the research used sample stdev — a negligible
  difference at the filter threshold.
- This is a research / decision-support indicator, **not** financial advice. Confirm
  fills and model slippage before trading (see the repo's open items).
