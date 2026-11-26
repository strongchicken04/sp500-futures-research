# Stage 4.5 — event definitions and onset labels

Code: `strategy/quantconnect/inqc/xup_s45_core.py` (`_s45_moves`, `_s45_onset`, `_s45_capture`, `_s45_window`).

## 1. Move day (event onset)
Stage 4 events were label episodes: runs of rows whose forward 10-session window contains a +100 % excursion.
The first positive label row can therefore precede the price move by up to 10 sessions. Stage 4.5 anchors every
event to the **first session of the actual excursion**, called the move day τ.

| Definition | Events | Move day τ |
|---|---|---|
| **E1 (primary)** | Stage 3/4 E1 episodes of label A10 / +100 % | min over the episode's positive rows r of r + t100(r). t100(r) is the first session whose HIGH ≥ 2 × OPEN(r+1) |
| E2 | Stage 4 E2 events (merged forward windows) | same rule on E2 |
| E3 | Stage 4 E3 price-path excursions | first session with HIGH ≥ 2 × min OPEN of τ−9..τ |
| B | E1 grouping of B10 / +100 % | min r + tc100(r), the first CLOSE ≥ 2 × reference |
| M (B-max) | E1 grouping of M10 / +100 % | same as B |

- Families are never merged, and each event counts once.
- Events whose positive rows have no finite crossing offset are dropped and counted in S45AUDIT (L1 compares
  move days with episodes).

## 2. ONSET_k(t) labels, k ∈ {1, 2, 3, 5}
- **1:** a move day of the same security and segment lies in t+1..t+k.
- **0:** no such move day, and t+k is inside the segment.
- **−1 (invalid):** t+k is beyond the segment end or the data end. Never treated as negative.
- **−2 (excluded, ex-ante):** a move day lies in t−10..t. The move has already started; this exclusion uses only
  past prices.
- **Primary target:** ONSET_3 with E1.
- A prediction made at the close of t is credited only for move days t+1..t+k. A signal on τ itself is an
  "onset-session" detection and is not credited.

## 3. Event-level quantities
- **Eligible event:** at least one row of τ−3..τ−1 belongs to the conditional population (universe, state, not
  excluded, scored).
- **All events (second denominator):** every move day in the period whose security is in the universe at τ−1.
- **Pre-event capture:** the share of eligible events with ≥ 1 signal in τ−3..τ−1 (first-signal lead 1 / 2 / 3).
- **Event precision:** the share of signal rows followed by a move day within 3 sessions (ONSET_3 = 1).
- **Placebo:** the same security, detection in τ−33..τ−31 vs τ−3..τ−1. Secondary pairs: 1–5 vs 41–45, and 1–3 vs
  61–63.
  - Each window must lie inside the same segment and the signal period.
  - **Membership-matched:** S1 membership on every row of both windows.

## 4. Amendment 1 — run-up diagnostic
- A "pre-event" signal can sit on a stock already up strongly; it crosses +100 % only on τ. S45MODEL therefore
  reports, at the first signal row:
  - xr = HIGH(t) / min OPEN(t−9..t) − 1, and the shares ≥ 30 % and ≥ 50 %;
  - a strict pre-move sensitivity, with population xr(t) < 50 %, re-ranked.
