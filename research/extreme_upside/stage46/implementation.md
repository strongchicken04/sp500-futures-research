# Stage 4.6: implementation

The protocol is `protocol.md`, commit 2e229f8. It was committed before any code ran in QC.

## Code (`strategy/quantconnect/inqc/`)

| File | Content |
|---|---|
| `xup_s46_core.py` | Wrapper around the Stage 4.5 `_security` wrapper (no Stage 3 / 4 / 4.5 array is changed). It stores raw daily O / H / L / C and the adjustment factor (adjusted / raw close) per row from 2020-06-01. Also: the S46 CHECK, frozen groups (`_s46_groups`: Stage 4.5 `_s45_primary` + `_s45_models` + `_s45_signals`), matched controls (`_s46_controls`), minute-data access (`_s46_minute`: RAW, regular hours, fill-forward off, bar-label convention detection), the trigger (`_s46_trigger`), the entry proxies (`_s46_entry`), the daily-window completeness check (`_s46_complete`) and the bracket (`_s46_bracket`). |
| `xup_s46_modes.py` | Per-observation engine `_s46_run` (security-level records stay in memory inside QC). Statistics: security-cluster and two-way bootstrap (`_s46_bm`), dedup, BH. Modes: S46AUDIT, S46MAIN, S46ROBUST, S46SHADOW. |

- **Runner:** `strategy/quantconnect/run_s46.sh MODE label` → `results/xup_s46_<mode>_raw.txt`.
- **Collector:** `s4_collect.py` additionally requires S46 CHECK OK for S46 modes.

## Engine, per observation (row i = signal at the close of t)
1. **Daily window check:**
   - rows i..i+5 lie in the same segment;
   - raw OHLC is finite;
   - the adjustment factor is stable within 0.5 %. Otherwise the case is incomplete (`window` / `daily` / `corp`).
2. **Minute data for t+1:**
   - minute TradeBars (RAW, regular hours);
   - bars with zero volume are dropped;
   - bars are labelled by end time (09:31..16:00). If QC labels bars by start time, a +1 minute shift is applied.
     The shift is decided by majority over all fetched days.
3. **Triggers:** all 8 pre-registered variants are evaluated on the same bars.
   - Cumulative Σ close × volume uses completed bars only.
   - Breakout = HIGH > H_t (or CLOSE > H_t for the BCLOSE variant).
   - m* = later of the two confirmation bars; trigger if m* ≤ 09:30 + window.
4. **QuoteBars for t+1** are fetched only if some variant triggers.
5. **Entry price (P_e):**
   - quote-based: ask-open (else ask-close) of the first quote bar ending in (m*, m*+2], valid if spread ≤ 20 %;
   - otherwise minute proxy: (open + high) / 2 of the first trade bar ending after m*.
6. **Bracket:**
   - t+1: minute bars from the entry bar onward;
   - t+2..t+5: daily raw bars with gap rules; a same-session double touch is resolved with that session's minute
     bars (cached), otherwise ambiguous.

## Synthetic tests (scratchpad harness, fake minute bars built from the daily OHLC)
- S46AUDIT, S46MAIN, S46ROBUST and S46SHADOW run without errors.
- Unit test of the QC DataFrame parsing:
  - end-labelled and start-labelled bars both normalise to 571..960;
  - trigger at the later confirmation;
  - entry at the next-minute ask.
- Synthetic numbers are meaningless.

## Runs (QC project 38061541; all results under `results/`)
| Run | Backtest | Verdict | File |
|---|---|---|---|
| S46AUDIT v1 | b3a06dff05c512f59606e39a4c8bcd01 | INVALID (third QC data revision → Amendment 1) | xup_s46_audit_raw.txt |
| S46AUDIT v2 | b65bd5cd3581d1a1dce4a3f95f07e85e | VALID | xup_s46_audit_raw.txt |
| S46MAIN v1 | 4281450f24886ccff9e03b1f207e62bd | INVALID (quote normalization defect → Amendment 2) | xup_s46_main_raw.txt |
| S46ROBUST v1 | 7e2272513f00f2b0d0dbb01831ad6494 | INVALID (same defect) | xup_s46_robust_raw.txt |
| S46DIAG v1 | a921a976494f4b56ba792335f387aaec | VALID (defect diagnosis) | xup_s46_diag_raw.txt |
| **S46MAIN v2** | **7a585d96a518aaaa36092ab205a3ec25** | **VALID (primary)** | xup_s46_main_raw.txt |
| S46ROBUST v2 | d2c2494ba3f1a679b04128409e0979cc | VALID | xup_s46_robust_raw.txt |
| S46SHADOW v1 | d7d1b68cf919601d89c0c8a33843d21a | VALID (0 prospective sessions; ObjectStore unavailable) | xup_s46_shadow_raw.txt |

S46MAIN v2 was collected from the QC API after a container restart interrupted local polling (`s4_collect.py` with
project and backtest ID).

## Reproduction
```
export QC_PROJECT_ID=38061541     # QC credentials from the environment, never printed
bash strategy/quantconnect/run_s46.sh S46AUDIT   v2
bash strategy/quantconnect/run_s46.sh S46MAIN    v2
bash strategy/quantconnect/run_s46.sh S46ROBUST  v2
bash strategy/quantconnect/run_s46.sh S46DIAG    v1
bash strategy/quantconnect/run_s46.sh S46SHADOW  v1
```
