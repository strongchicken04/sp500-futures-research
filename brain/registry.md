# Strategy registry

Status: `live-eval` / `live-funded` (in the plan), `candidate`, `rejected`,
`idea`. Numbers: NQ 2018-2021 | 2022-2025, costs included unless noted.

| strategy | status | key result | notes / files |
|---|---|---|---|
| RS sprint: NQ-ES return since open > 0.15% & above VWAP (mirror short), first of 10:00/11:00/13:00/14:30, +0.20%/-0.40% | live-eval | sprint pass/attempt 48% / 52%, ~13 trading days to pass | lucid_8_rs_sprint.pine, score_multi_feature.py |
| 09:31 sprint, bias 50-day trend, +0.20%/-0.40% | live-eval (fallback) | pass 39% / 39%, ~13 days | lucid_7_eval_sprint.pine, bias_sprint.py |
| Noise-area momentum (Zarattini 2024), long+short, hard stop 0.50% (2026-10-23) | live-funded | +6.1 / +9.2 pt/trade with the stop (+5.5 / +9.4 without), worst trade -128 vs -221 pt; profit targets lower the edge | lucid_6_noise_momentum.pine, score_noise_tod.py |
| VWAP band 0.20% break on a 5-min chart, SL 25 / TP 100 pt, first trade a day (Lucid 2 rewritten 2026-10-23) | live-funded | live-spec +3.6 / +3.0 pt/trade gated (old Lucid 2 plain cross: +2.3 / +0.7) | lucid_2_vwap.pine, live_spec_exporter.py, score_live_spec.py |
| ORB 15m long + VWAP, 20-EMA 5m trail, re-entry | live-funded (weak) | after fill fix +0.6 / +1.6 pt gross; ~0 net 2018-21 | lucid_1_s1_orb.pine (5-min chart only), s1_true_vwap_fill.py |
| Dow ORB (MYM) | candidate (weak) | after fill fix +$0.5 / +$3.3 per MYM gross | s1_YM_fill.py |
| RS signal as a funded leg: live RS rule, bracket +1.25% / -1.25% (chosen on 2018-21 by smoothed score) else 15:55 | candidate | +4.6 / +9.6 pt/trade (t 1.8 / 2.2), 7/8 years positive; added at 1 MNQ/unit to the fixed live book: 5 accounts 24m median $74k (p10 $12k) vs $68k ($5k); book-eval pass 57% vs 61% | rs_book.py, results/rs_book.txt; Lucid 8 with target 1.25 / stop 1.25 |
| FOMC press-conference fade 14:30-14:35 candle | candidate | positive every cell, NQ/ES/YM; 8/yr | lucid_5_fomc_fade.pine |
| Overnight-low touch on gap-up day, long | candidate | WR 74%, +12 pp over random; 25/yr | onl_gapup_book.py |
| Overnight long after 3+ down closes (NQ, 15:55 close to 09:30 open) | candidate | +28.6 / +19.0 bp per night net (t 2.5 / 1.7), positive all 8 years, ~20/yr; no roll artefact (ex-roll +29.3 / +17.6). Needs: does Lucid allow overnight holds? | overnight_after_downs.py |
| Wide VWAP band 60 bp, TP 15% ATR / SL 20-30% ATR | candidate (small) | WR 61-68%, +1.5% ATR both halves | score_vwap_atr.py |
| Book (ORB+VWAP+noise), ladder room/700 max 3 | live-funded sizing | eval 80% (59% / 98%), lifecycle median ~$70k (research exports). On the fixed live rules, ladder 400/500/400: eval 61%, 5 accounts 24m median $68k, p10 $5k (old Lucid 2: $51k, p10 -$3k) | book_after_fix.py, book_live_spec.py |
| Regime filters for the book (VIX level, 20d realised-vol tercile, 50-day trend, weekday) | rejected | no split holds in both 2018-21 and 2022-25; ORB net -0.4 / +0.9 pt but the book without it: lifecycle median ~$13k vs ~$67k | regime_map.py, results/regime_map.txt |
| Turn of month NQ (last day + first 3 days; RTH or 4-day hold) | rejected | TOM days +3.8 / +13.2 bp RTH vs +1.6 / -1.6 other, close-close TOM not better in 2022-25; 4-day hold +49 / +14 bp, t 1.3 / 0.4 | turn_of_month.py |
| RS sprint variants: 5-min / 30-min / 10-11 checks, vol-scaled threshold, EMA21 instead of VWAP, vs YM, vs RTY, breadth (all 3), avg of 3 | rejected | none beats the live rule in both halves (block avg over thr 10-25 bp): live 45.4% / 52.1% pass, 16.3 / 13.9 days; 5-min faster (14.3 / 11.7 d) but lower pass 42.1%; RTY worst. Independent export replicates live RS (thr 15: 46.2% / 52.3%) | score_rs_variants.py, results/rs_variants.txt |
| Month-end Treasury long (ZN last trading day 09:00-15:00) | rejected | +2.6 / +0.5 ticks (t 1.5 / 0.2), negative 2023-2025; ZN RTH drift on other days -1.0 / -2.1 ticks (idea: bonds fall in the US day session) | zn_month_end.py, zn_daily_exporter.py |
| Intraday momentum (Gao et al. 2018): sign of prior close to 10:00 (or 10:00-15:30) return, trade 15:30-15:55 | rejected | both agree +3.3 pt (t 2.3) in 2018-21 but -2.6 pt (t -1.4) in 2022-25; single predictors also flip sign | intraday_momentum.py |
| Noise momentum on ES / YM (Lucid 6 live rules, hard stop) | rejected | per micro net: NQ +$11.3 / +$14.1, ES +$6.1 / +$3.9 (t 2.6 / 1.3, daily corr with NQ 0.69 - little diversification), YM +$0.8 / -$0.8 | noise_markets.py, live_spec_exporter.py (ls_noise_ES/YM) |
| ORB with 1-min EMA trail | rejected | ~20 trades/day, pass 8-17% | score_orb_trail.py |
| Gap-down reversal, Mon/Fri hold, ON-level fade, 1-min micro-drop | rejected | backtest artefacts | |
| Small-gap fill, ON midpoint rule, IB stats, lunch effect, last half hour, pre-FOMC drift, FOMC relief rally | rejected | at/below random baseline | |
| Fading 08:30 news candles, 14:00 statement fade, climax fade | rejected | no edge | score_news.py |
| Adaptive TP from candle/ATR on VWAP band; tiny targets 1-5% ATR | rejected | ~random baseline after costs | score_vwap_feat.py, score_vwap_fine.py |
| RSI(2) reversion, trend pullback, momentum confluence, VIX regime switch, value-area acceptance, all-indicator logistic model | rejected | no stable edge | score_multi_feature.py |
| ES / gold / crude / Russell / 10y / NQ overnight brackets; ML trade selection; 190k-rule streak scans | rejected | edges do not survive 2022-25 | score_xmkt_streak.py, ml_streak.py |
