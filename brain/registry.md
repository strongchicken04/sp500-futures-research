# Strategy registry

Status: `live-eval` / `live-funded` (in the plan), `candidate`, `rejected`,
`idea`. Numbers: NQ 2018-2021 | 2022-2025, costs included unless noted.

| strategy | status | key result | notes / files |
|---|---|---|---|
| RS sprint: NQ-ES return since open > 0.15% & above VWAP (mirror short), first of 10:00/11:00/13:00/14:30, +0.20%/-0.40% | live-eval | sprint pass/attempt 48% / 52%, ~13 trading days to pass | lucid_8_rs_sprint.pine, score_multi_feature.py |
| 09:31 sprint, bias 50-day trend, +0.20%/-0.40% | live-eval (fallback) | pass 39% / 39%, ~13 days | lucid_7_eval_sprint.pine, bias_sprint.py |
| Noise-area momentum (Zarattini 2024), long+short | live-funded | +5.5 / +9.4 pt/trade, t~3 both | lucid_6_noise_momentum.pine, score_noise_tod.py |
| VWAP band 20 bp, SL 25 / TP 100 pt, 1/day | live-funded | +3.7 / +3.7 pt/trade (t 2.6/2.1) | lucid_2_vwap.pine |
| ORB 15m long + VWAP, 20-EMA 5m trail, re-entry | live-funded (weak) | after fill fix +0.6 / +1.6 pt gross; ~0 net 2018-21 | lucid_1_s1_orb.pine (5-min chart only), s1_true_vwap_fill.py |
| Dow ORB (MYM) | candidate (weak) | after fill fix +$0.5 / +$3.3 per MYM gross | s1_YM_fill.py |
| FOMC press-conference fade 14:30-14:35 candle | candidate | positive every cell, NQ/ES/YM; 8/yr | lucid_5_fomc_fade.pine |
| Overnight-low touch on gap-up day, long | candidate | WR 74%, +12 pp over random; 25/yr | onl_gapup_book.py |
| Wide VWAP band 60 bp, TP 15% ATR / SL 20-30% ATR | candidate (small) | WR 61-68%, +1.5% ATR both halves | score_vwap_atr.py |
| Book (ORB+VWAP+noise), ladder room/700 max 3 | live-funded sizing | eval 80% (59% / 98%), lifecycle median ~$70k | book_after_fix.py |
| ORB with 1-min EMA trail | rejected | ~20 trades/day, pass 8-17% | score_orb_trail.py |
| Gap-down reversal, Mon/Fri hold, ON-level fade, 1-min micro-drop | rejected | backtest artefacts | |
| Small-gap fill, ON midpoint rule, IB stats, lunch effect, last half hour, pre-FOMC drift, FOMC relief rally | rejected | at/below random baseline | |
| Fading 08:30 news candles, 14:00 statement fade, climax fade | rejected | no edge | score_news.py |
| Adaptive TP from candle/ATR on VWAP band; tiny targets 1-5% ATR | rejected | ~random baseline after costs | score_vwap_feat.py, score_vwap_fine.py |
| RSI(2) reversion, trend pullback, momentum confluence, VIX regime switch, value-area acceptance, all-indicator logistic model | rejected | no stable edge | score_multi_feature.py |
| ES / gold / crude / Russell / 10y / NQ overnight brackets; ML trade selection; 190k-rule streak scans | rejected | edges do not survive 2022-25 | score_xmkt_streak.py, ml_streak.py |
