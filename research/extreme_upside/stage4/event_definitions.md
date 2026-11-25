# Stage 4 — event definitions

All events are built inside QC by `strategy/quantconnect/inqc/xup_s4_core.py` (`_s4_events`).

Events are **retrospective labels for evaluation only**. They are never model features, and the frozen Stage 3
models are not refit on them.

## Common clock and inputs
- **Session:** one of the security's consecutive eligible daily bars inside one data segment.
  - Segments split at gaps > 10 market sessions (Stage 2/3 rule).
  - Missing bars inside a segment (≤ 10 market sessions) are not sessions. The Stage 3 labels use exactly this
    clock ("the security's next h sessions").
- **Returns:** QC ADJUSTED prices (ratios only).
- **Nominal price and dollar volume:** RAW close and RAW close × RAW volume on the onset day, from the Stage 3
  features `lpx` / `ldv`.
- **Panel:** the Stage 3 fixed-hash 20 % sample of universe A: 2,947 securities, 6,022,604 eligible rows,
  2006-02-01 .. 2026-08-27.
- **Horizon:** h = 10 everywhere in Stage 4. The primary family is A10/+100 %.

## E1 — Stage 3 canonical episodes (benchmark)
- **Built from:** positive rows of the label (A10/+100 % unless stated), in panel order (security, date).
- **Rule:**
  - an episode starts at a positive row when the security differs from the previous positive row's security,
    OR the row distance to the current episode's start is ≥ 10;
  - otherwise the row joins the episode.
- **Identical to Stage 3 `_episodes`.** Like Stage 3, E1 counts row distance and ignores segment boundaries. A
  positive row at the end of one segment and one at the start of the next can share an episode; this is rare.
- **Onset** = first positive row; **last** = last positive row joined.
- **Over-counting:** a long run of positive days (a slow, chained move) is split every 10 rows into several
  episodes. The "ambiguous" count reports how many E1 episodes E2 would merge.
- **Under-counting:** a second, separate move starting < 10 sessions after an episode start is absorbed into
  the first episode.

## E2 — merged forward windows
- **Built from:** the same positive rows, but segment-aware.
- **Rule:**
  - a positive day t opens the forward window [t+1, t+10];
  - the next positive day t′ of the same segment joins the event if t′ ≤ current window end, and the window end
    becomes max(end, t′+10);
  - a new event starts only after the window has expired.
- **Onset / last:** as E1.
- **Under-counting:** two genuine moves separated by fewer than 10 quiet sessions merge into one event.
- **Never over-counts** relative to E1. E2 ≤ E1 by construction (within segments).

## E3 — price-path excursions (independent of the label rows)
- **Excursion day τ:** adjusted HIGH(τ) ≥ 2 × min adjusted OPEN over the sessions [τ−9, τ] of the same segment.
  This needs 10 sessions of history in the segment.
- **Clustering:** excursion days of a segment that are ≤ 10 sessions apart form one event.
- **Move day** = first excursion day; the event's reference price is that minimum open.
- **Relation to the labels:** a Family-A label at t is positive when some day in t+1..t+10 has HIGH ≥
  2 × OPEN(t+1). So τ is an excursion day exactly when some label in τ−10..τ−1 crosses at τ, provided all bars
  exist. E3 dates the move itself, not the earliest day from which it could be predicted.
- **Timing:** E3 timing is measured relative to the move day. A "pre-move" signal in [τ−10, τ−1] may sit on a
  row whose Family-A label is already positive. It is still a warning before the price excursion happens.
- **Close confirmation:** not reported for E3, because the B labels at excursion days refer to later windows.
- **Over-counting:** a single wild intraday print can create an excursion day; the minute-data audit
  (S4EXEC) checks how often daily highs are thin.
- **Under-counting:** moves that build over more than 10 sessions without doubling inside any 10-session span.

## E4 — close-confirmed populations
- **Built from:** E1 and E2 applied to the B10/+100 % labels (close at t+10 ≥ 2 × OPEN(t+1)) and the
  B-max10/+100 % labels (any close in t+1..t+10 ≥ 2 × OPEN(t+1)).
- **Kept separate.** These are separate populations and are never merged with Family A.

## Event attributes (all definitions)
| Attribute | Definition |
|---|---|
| onset date | panel date of the onset row (E3: move day) |
| duration | last − onset + 1 rows |
| positive days | number of positive rows (E3: excursion days) in the event |
| max return | max Family-A return (`R`, h = 10) over the event's positive rows (E3: max excursion ratio) |
| close confirmation (A family, E1 / E2) | any B10/+100 or B-max10/+100 positive row inside [onset, last] |
| incomplete | an invalid label (−1) or the segment end within 10 rows after the last positive row. The event may have continued after delisting or a data gap, or past the data end. |
| ambiguous (E1) | E2 merges the episode with a neighbouring E1 episode |
| adverse before target | min adjusted LOW from onset+1 to the first day reaching +100 % (by HIGH), divided by adjusted OPEN(onset+1), minus 1 |
| overlap | the next event of the same security starts ≤ 10 rows after this event's last row |

## Event periods
- **Test events:** onset 2021-01-01 .. 2025-12-31.
- **2026 YTD:** onset 2026-01-01 .. 2026-08-27. Reported separately; incomplete windows are expected because
  of the data end.
- **Validation events (filter study only):** onset 2017-01-01 .. 2020-12-31.
