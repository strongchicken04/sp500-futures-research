# Stage 4.5 — conditional timing, capturable targets, liquid-universe validation

**Decision: C — further research required. No Stage 5 simulation** (`stage5_decision.md`).
**Final report:** `stage45_report.txt`.

## Documents
| File | Content |
|---|---|
| `protocol.md` | pre-registration (hypotheses, targets, splits, thresholds, C1–C9, mapping) + Amendments 1–6 |
| `repository_audit.md` | code and data lineage, constraints, gaps from Stage 4 |
| `feature_audit.md` | feature definitions, leakage tests, coverage, exploratory univariate AUCs |
| `event_definitions.md` | move day, ONSET_k labels, eligibility, placebo windows |
| `timing_methodology.md` | conditional population, models, folds, signals, C2 / C3 / C8 |
| `capturable_targets_methodology.md` | Families A / B / B-max / C / D, C4, C5, payoff proxy |
| `liquidity_methodology.md` | S0 / S1 / S2 / S5M / A, re-ranking, membership-matched placebo |
| `execution_cost_methodology.md` | minute-quote samples, s30, frozen cost formulas |
| `results.md` | every result with counts, denominators and CIs |
| `limitations.md` | data gaps, prior exposure, execution limits, deviations |
| `stage5_decision.md` | C1–C9 and the decision |

## Code
`strategy/quantconnect/inqc/`:
- `xup_s45_core.py`
- `xup_s45_modes_a.py`: AUDIT, FEATURE
- `xup_s45_modes_b.py`: MODEL, PLACEBO
- `xup_s45_modes_c.py`: ROBUST(A/B), GRIDA/B, EXEC
- `xup_s45_modes_d.py`: OUTCOME

How the modules attach:
- They attach to the unchanged Stage 3 panel (`xup_s3_panel_inqc.py`) and the Stage 4 modules (`xup_s4_*.py`).
- `run_s45.sh` builds a temporary main file. It sets MODE and attaches the Stage 4 and Stage 4.5 methods.

## Reproduction
Requirements:
- QC credentials in the environment (`QC_USER_ID`, `QC_API_TOKEN`) or `~/.lean/credentials`. Never printed or
  committed.
- QC project 38061541 (forced via `QC_PROJECT_ID`; QC allows 50 new projects per day).
- A node with ≥ 8 GB RAM (B-MICRO, 7.8 GB, was enough after Amendments 2 and 5).

```
export QC_PROJECT_ID=38061541
bash strategy/quantconnect/run_s45.sh S45AUDIT   v2
bash strategy/quantconnect/run_s45.sh S45FEATURE v2
bash strategy/quantconnect/run_s45.sh S45MODEL   v1
bash strategy/quantconnect/run_s45.sh S45PLACEBO v1
bash strategy/quantconnect/run_s45.sh S45ROBUSTA v1   # or the single S45ROBUST run used here (v1-collected; mode existed before Amendment 5)
bash strategy/quantconnect/run_s45.sh S45ROBUSTB v1
bash strategy/quantconnect/run_s45.sh S45GRIDA   v1
bash strategy/quantconnect/run_s45.sh S45GRIDB   v1
bash strategy/quantconnect/run_s45.sh S45EXEC    v1   # -> s30; set S30 in xup_s45_core.py (Amendment 6)
bash strategy/quantconnect/run_s45.sh S45OUTCOME v1   # refuses to run while S30 is None
bash strategy/quantconnect/run_s4.sh  S4DIAG s45rev2  # per-year breakdown of the data revision
```

Run behaviour:
- Each run appends to `results/xup_s45_<mode>_raw.txt` (`results/xup_s4_diag_raw.txt` for DIAG).
- Each line carries a VALID / INVALID verdict: mode line, S4 CHECK (exact canonical counts), S45 CHECK, no error
  statistic.
- The single-run S45ROBUST mode was split into ROBUSTA / ROBUSTB after it had run. To reproduce it exactly, check
  out commit 43cf6e5 for `xup_s45_modes_c.py` (same variants, same code path).

## Data handling
- All security-level data, scores, event histories and predictions stay in QC.
- Only aggregate statistics leave QC: counts, rates, quantiles, metrics and bootstrap CIs.
- No ticker or identifier appears in any output.
