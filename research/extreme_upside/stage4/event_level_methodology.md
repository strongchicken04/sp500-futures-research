# Stage 4 — event-level evaluation, deduplication and lead-time methodology

Code: `xup_s4_core.py` (`_s4_flags`, `_s4_assoc`, `_s4_capture`, `_s4_dedup`) and `xup_s4_modes_b.py`
(modes S4EVAL, S4LEAD).

## Scores
- **Specifications:** the six frozen Stage 3 specifications, refit with the TEST split exactly as in Stage 3:
  full-A RF (primary), volume LR, price LR, momentum LR, full-A LR, full-A GBM.
  - Same code (`ModesM._fit`, `_train_rows`), seeds and training rows: universe A, 2006-02-01 .. 2020-12-31
    minus 60 days. RF uses `random_state=7`, `n_jobs=1`.
  - S4AUDIT checks that the refit reproduces the TEST v1 metrics.
- **Scored rows:** universe A, 2020-11-02 .. 2026-08-27, all out of the purged training window.

## Daily selection (S4-rank)
- Each day, every scored row of the evaluated universe is ranked by score. Rows whose future label is invalid
  are included, because validity is future information.
- Top k % = the ceil(k · n_day) highest scores; ties are broken by row order. k = 1, 5, 10 %.
- A selected row is a **signal**.
- Stage 3 ranked only valid-label rows (S3-rank). That ranking is reproduced in S4AUDIT, and the difference is
  reported.

## Association of signals and events
- **Window:** a signal at row i is associated with event e of the same security segment if
  i ∈ [onset(e) − 10, last(e)].
- **Parts:** pre-onset is [onset − 10, onset − 1]; in-event is [onset, last].
- **Overlaps:** pre-onset windows are assigned first; in-event ranges then overwrite them. A row inside an
  earlier event's in-event range therefore belongs to that earlier event.
- **No boundary artefacts:** signals are associated with events of any onset date, so there is no edge effect
  at 2021-01-01 or 2025-12-31.

## Capture (per model, k, event definition; test events only)
| Metric | Definition |
|---|---|
| capture | event has ≥ 1 signal in [onset − 10, last] |
| pre-onset capture | ≥ 1 signal in [onset − 10, onset − 1]. A signal on the onset day is NOT pre-onset. |
| in-event only | no pre-onset signal, ≥ 1 in-event signal |
| none | no signal in the association window |
| event-level recall | = capture |

## Signal-side precision (signals in 2021–2025 rows)
| Metric | Definition |
|---|---|
| event precision | share of signals associated with any event |
| unique events per signal | distinct associated events / signals |
| false signals per captured event | unassociated signals / captured test events |
| repeated signals | associated signals beyond the first per event |
| repeat share | repeated signals / all signals |
| securities ≥ 2 signals without event | securities with ≥ 2 test signals, none of them associated |

## Event ranking (score dynamics before onset)
- **Pre-score:** max daily percentile rank, 1 = top, in [onset − 10, onset − 1].
- **Placebo score:** the same quantity in [onset − 40, onset − 31] of the same security. It is defined only if
  that window lies inside the segment and the scored period.
- **Reported:**
  - median pre-score and placebo score;
  - share of events with pre-score > placebo score, ties counted ½;
  - Mann–Whitney AUC of pre-scores vs placebo scores.
- **Interpretation:** the within-security placebo controls for "this stock is always top-ranked". A signal
  that merely tracks permanently volatile penny stocks has pre ≈ placebo.

## Lead time
- **Windows before onset:** 1–2, 3–5, 6–10, 11–20 and 21–40 sessions.
  - A window is evaluated only if it lies inside the segment and the scored period; otherwise it is "no data"
    and excluded from that window's denominator.
- **Before onset (1–40):** ≥ 1 signal in [onset − 40, onset − 1].
- **In-event only:** none before onset (1–40), ≥ 1 in-event.
- **None:** neither.
- **First-signal lead:** onset − (first signal row in [onset − 40, onset − 1]).
- **Definitions covered:** A / B / B-max (E1), A (E2) and A (E3, relative to the move day).
- **Lead and magnitude** (A, E1, RF, k = 1 and 5 %): events split into pre-signal (1–10), in-event-only and
  none, and by first-signal lead bucket (1–2, 3–5, 6–10, 11–40). Compared on:
  - max return;
  - B / B-max confirmation;
  - adverse move before target;
  - onset price / dollar volume.

## C4 / C5 test (confirmatory, protocol §9)
- **Quantity:** RF, top 5 %. Pre-onset capture (1–10) minus placebo-window capture (31–40), over test events
  whose placebo window exists.
- **CI:** paired event-level difference, Poisson bootstrap by security, 2,000 resamples, seed 404.
- **Reported:** also for k = 1 and 10 %, and for "clean" events with no earlier event of the same security
  reaching into [onset − 40, onset − 1].
- **E3** uses the move day as onset.

## Deduplication (deployable rules use past information only)
| Rule | Keep a signal if … |
|---|---|
| N0 | always (benchmark) |
| C10 / C20 | no KEPT signal of the same segment in the previous 10 / 20 sessions |
| CW | no selection at all (kept or not) in the previous 10 sessions, i.e. a new signal episode after 10 quiet sessions |
| CE | first signal associated with each event (+ C10 for unassociated). **Retrospective benchmark, not deployable** |

- **Cooldown state** starts at the first scored session (2020-11-02), so the state on 2021-01-01 is realistic.
- **Reported per rule:**
  - signals; capture; pre-onset capture; event precision; false signals;
  - signals removed per captured event (relative to N0);
  - first-signal lead quantiles;
  - signals per calendar year.
- No rule is selected.
