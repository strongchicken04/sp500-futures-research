# Lucid Flex 50K — Weekly Plan

**3 strategies, 3 indicators, one plan.**
Target: $3000 before -$2000 EOD trailing DD, 8-week window, $1500/day consistency cap.

---

## Day-by-day

| Day | Strategies active | Window (ET) | Max trades |
|-----|------------------|-------------|------------|
| **MON** | Mon-LONG + S1 ORB + VWAP | 09:30 → 15:55 | 3 |
| **TUE** | S1 ORB + VWAP | 09:45 → 15:55 | 2 |
| **WED** | **SKIP — no trades** | — | 0 |
| **THU** | S1 ORB + VWAP | 09:45 → 15:55 | 2 |
| **FRI** | Fri-SHORT + S1 ORB + VWAP | 09:30 → 15:55 | 3 |

### Strategy rules recap

- **Mon-LONG** (indicator 3): 09:30 5m bar closes > EMA12 → long at close, SL = bar low, hold to 15:55
- **Fri-SHORT** (indicator 3): 09:30 5m bar closes < EMA12 → short at close, SL = bar high, hold to 15:55
- **S1 ORB** (indicator 1): after 09:45, close > OR_high AND > VWAP → long, SL = max(OR_low, close − OR_range), trail 20-EMA, exit 15:55
- **VWAP** (indicator 2): close crosses VWAP during RTH → both ways, SL 15pt / TP 100pt, exit 15:55
- **All strategies**: FLAT @ 15:55 ET, no exceptions. Skip Wednesday entirely.

---

## Sizing — tiered by account cushion

Cushion = current equity − trailing DD trigger line.

| Phase | Cushion | Size per trade | Daily loss stop |
|-------|---------|----------------|-----------------|
| **1 — Build** | $0 → $400 | **2 MNQ** ($4/pt) | $400 |
| **2 — Grow** | $400 → $1000 | **3 MNQ** ($6/pt) | $500 |
| **3 — Push** | $1000 → $3000 | **1 NQ** ($20/pt) | $600 |

- Only step UP a phase after a green day closes the cushion above the threshold.
- If a day closes below the previous threshold, step DOWN.
- **Never size up intraday** — phase change applies to next session's trades.
- Max 1 contract active per strategy (don't stack).

---

## Daily routine

1. **08:30 ET** — Check economic calendar. Red-folder event in first hour? Skip VWAP + ORB until 10:30.
2. **09:30 ET** — Mon/Fri: watch first 5m bar close for trigger (indicator 3).
3. **09:45 ET** — ORB window opens (indicator 1). VWAP already active (indicator 2).
4. **Entry** — Place MKT at close of trigger bar, bracket OCO (SL + TP where applicable).
5. **Day stop** — If daily loss hits phase limit, FLAT and done for the day.
6. **15:55 ET** — Close everything manually if any strategy still holding.
7. **End of day** — Log cushion, re-check phase for tomorrow.

---

## Pass math (backtest 2018-2025)

- **Combined pass rate ~64%** over 8-week windows
- Standalone S1 ORB: 50.8% pass
- Standalone Mon/Fri + VWAP: 32% pass
- Combined (3 strategies): **64.1% pass / ~5% bust**
- 2nd attempt EV: **87%** · 3rd attempt EV: **95%**

---

## Indicator files

- `lucid_1_s1_orb.pine` — paste into TradingView, 15m NQ chart
- `lucid_2_vwap.pine` — paste into TradingView, 1m or 5m NQ chart
- `lucid_3_monfri.pine` — paste into TradingView, 5m NQ chart

Run all three in parallel panes (same symbol, different TFs) or stack as separate indicators on one chart.
