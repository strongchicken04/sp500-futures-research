# 10:00 open level (Powell Trades) — verdikt: OBYČEJNÁ ČÁRA

**Hypotéza (jádro setupu Powell Trades):** open 1m svíčky 10:00 ET je
významná úroveň s reaktivitou a prediktivní silou.

**Test:** reálné NQ 2018–2025 (QC), 1 998 dní. Level M = open 10:00 svíčky
(sledování 10:01–16:00) vs placebo úrovně A = open 9:45 a B = open 10:15
(stejné stáří při startu sledování). Projekt `NQ_10am_Level` (35167837),
backtest `39f9e64a...`, 5 994 záznamů.

| test | M (10:00) | placebo | z |
|---|---|---|---|
| překřížení/den | 8,73 | 8,96 | −1,1 |
| odraz 15 min po návratu (≥20bp odchod) | −0,7 bps | −0,8 bps | +0,1 |
| odraz 30 min | −0,4 bps | −0,6 bps | +0,1 |
| úroveň drží po doteku | 50,7 % | 48,6 % | — |
| pozice 10:30 → zbytek dne (spread) | −1,4 bps | +0,3 / −7,0 | −0,3 |

## Závěr

Žádná metrika neodlišuje 10:00 open od openu náhodné minuty. Nejsilnější
výsledek celé tabulky má PLACEBO úroveň 10:15 (spread −7 bps, z=−1,5) —
učebnicový podpis šumu při testování více čar. Základ setupu nenese
informaci → nadstavby nemají co zesilovat. Neřešíme dál (dle předem
stanoveného kritéria uživatele).

Pátý „úroveň bude respektována" claim v řadě, pátý rozpad na base rate:
wickless 4H, 10pm open, fib golden zone, Hougaard situational, 10am open.
