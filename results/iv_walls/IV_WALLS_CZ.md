# Opční zdi (call/put wall z QQQ OI) — verdikt: BEZ HRANY, 1 hypotéza do zásoby

**Data:** 1 979 dní 2018–2025, zdi z QQQ opčního řetězce v 9:35 ET (OI ze
včerejšího settle, expirace ≤ 25 dní), přepočtené do NQ bodů; denní RTH OHLC
NQ. Projekt `NQ_IV_Walls` (35147969), backtest `82c68282...`. Medián
vzdálenosti: call wall 123 bps, put wall 171 bps.

## Claim testy (proti distance-matched baseline)

| test | výsledek | baseline | závěr |
|---|---|---|---|
| dotek call wall | 25,9 % | 28,6 % | slabá bariéra (−2,7 p.b., hraniční) |
| dotek put wall | 20,7 % | 21,6 % | nic |
| odraz od call wall (close vs zeď) | +1 bps | +1 bps | nic |
| odraz od put wall | −5 bps | +5 bps | spíš pokračování než support |

Magnet efekt: ŽÁDNÝ (doteků je méně než u náhodné úrovně, ne více).
Odraz: ŽÁDNÝ. → Standalone strategie na zdech: NESTAVĚT.

## Regime náznak (jediný pozitivní nález)

P&L VWAP strategie podle pozice spotu mezi zdmi (tercily):
+13,1 / +8,2 / **+3,0** bps — monotónně klesá směrem k call wall; šířka
range podobně (úzké zdi lepší). z ≈ 1,8, korelace −0,05 → POD důkazní
laťkou. Konzistentní s dealer-hedging teorií (pinning tlumí trend pod
call wall), ale nepoužívat — riziko data-miningu (lekce Holmberg).

## PŘEDREGISTROVANÁ HYPOTÉZA (k jednorázovému ověření na budoucích datech)

„Denní výnos VWAP strategie je vyšší, když NQ v 9:35 otevírá v dolním
tercilu put–call wall range, než v horním tercilu."
Ověřit NEJDŘÍVE na datech od 2026-08 dál (min. 12 měsíců nových dat),
jedním testem, bez ladění definic. Do té doby NEPOUŽÍVAT v obchodování.
