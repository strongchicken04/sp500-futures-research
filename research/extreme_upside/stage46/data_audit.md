# Stage 4.6: data and model audit (S46AUDIT v2, VALID)

Source: `results/xup_s46_audit_raw.txt`.
- **v2:** backtest b65bd5cd…, VALID.
- **v1:** backtest b3a06dff…, INVALID only because of the count constants. Its output is identical line for line.
- **No trigger and no outcome were computed in this audit.**

## 1. Canonical panel (Amendment 1)
- QC revised its data again (third revision in the project). The fixed-hash sample now has 2,989 securities
  (2,949 with data), up from 2,986 (2,947).
- **Canonical Stage 4.6 panel:**
  - 6,030,760 rows / 24,429 primary events / 3,543 segments;
  - two independent builds (AUDIT v1 and v2) are identical.
- **Checks:**
  - S4 CHECK OK (`mh10 == R`, date order);
  - S45 CHECK OK: 3,098,061 rows ≥ 2016-06, 0 path-outcome mismatches;
  - S46 CHECK OK: 1,984,316 rows ≥ 2020-06 with raw OHLC; raw close vs panel price 0 mismatches; 0 missing.
- The Stage 4.5 panel (6,027,629 rows) cannot be rebuilt in QC: that would need the security-ID list, which must not
  leave QC.

## 2. Frozen models and groups (2021–25)
| Item | Stage 4.6 | Stage 4.5 |
|---|---|---|
| S1-P5 population rows | 49,802 | 49,697 |
| L2 / STATE / VOLU signals | 5,497 each | 5,492 |
| L2 C (validation 2020) | 0.01 | 0.01 |
| RF timing leaf | 20 (not used in 4.6) | 100 |

**Overlaps:**

| Pair | Rows |
|---|---|
| L2 ∩ STATE | 1,171 |
| L2 ∩ VOLU | 2,410 |
| STATE ∩ VOLU | 1,598 |

**Matched controls:** 5,497 (0 L2 rows unmatched). Union of all groups: 17,128 rows.

**Balance** (medians; price, trailing median $vol, ATR / price):

| Group | Price | Trailing $vol | ATR / price |
|---|---|---|---|
| L2 | $4.63 | $2.27M | 12.9 % |
| CONTROL | $4.28 | $2.17M | 12.6 % |
| STATE | $1.87 | $1.66M | 19.7 % |
| VOLU | $2.48 | $1.64M | 11.4 % |
| Population | $2.43 | $1.85M | 11.2 % |

The matched control is close to L2 on all three. STATE signals are cheaper and more volatile.

**Daily window t..t+5:**

| Group | Complete | Beyond segment / data end | Corporate action |
|---|---|---|---|
| L2 | 5,461 / 5,497 | 31 | 5 |
| STATE | 5,465 / 5,497 | 32 | 0 |
| CONTROL | 5,484 / 5,497 | 6 | 7 |

## 3. Minute and quote data (hash samples of 80 per group, session t+1; RAW, regular hours)
| Group | t+1 with trade bars | Median bars | With quote bars | Median quote bars | Quote bars in first 30 min (median) | Valid bid / ask | Sizes present |
|---|---|---|---|---|---|---|---|
| L2 | 74 / 80 | 320 | 74 | 334 | 29 | 100 % | 93 % |
| STATE | 71 / 80 | 308 | 71 | 294 | 28 | 100 % | 92 % |
| CONTROL | 75 / 80 | 311 | 75 | 300 | 28 | 100 % | 93 % |

- **Bar labels:** with regular hours requested, the earliest bar is labelled 09:31 (220 / 220 days) and the latest
  16:00 (218 days). No bar falls outside 09:31–16:00, so labels are bar END times. Shift = 0, as pre-registered.
- **Reference level:** the maximum of the day-t minute highs equals the daily-bar high to within 4·10⁻⁸ (p10 / p90
  ±3·10⁻⁶ %). The trigger and the reference level are consistent.
- **Missing coverage:** about 7–11 % of sampled t+1 sessions have no regular-session minute bars. These are counted as
  "no minute data" (never a trade). Quotes are present whenever trades are.
- **Granularity:** minute bars give open / close bid and ask, not every quote update (see limitations).
- **Speed:** 0.05 s per minute request. The full minute pass over 17,128 rows is feasible in one run.
