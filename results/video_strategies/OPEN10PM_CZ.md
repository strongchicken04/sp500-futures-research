# „10 p.m. open" retest — verdikt: HORŠÍ NEŽ NÁHODA

**Pravidla (video #3 + doplnění):** open 22:00 ET, breakout ≥ 10 b od úrovně,
limit vstup na retestu openu ve směru breakoutu, SL 15 b / TP 45 b (1:3),
vstupní okno do 01:00 ET, 1 obchod/noc, flat 09:25 ET. Reálné NQ 2018–2025,
1 kontrakt, $100k. Projekt `NQ_Open10pm` (34580983), backtest
`0c94b75f930271bb0708a2d92eb24642`.

## Výsledek

| metrika | hodnota |
|---|---|
| obchodů | 857 |
| win rate | **22,5 %** (breakeven pro 1:3 = 25 %) |
| avg/obchod | **−3,16 b** |
| Net profit | **−57,8 %** |
| Sharpe | −1,25 |
| Max DD | −62,3 % |
| exity | TP 21 % · SL 77 % · ranní flat 2 % |

## Proč to nefunguje

1. **Win rate POD náhodnou úrovní** (22,5 % vs 25 %): retest openu po
   breakoutu nese mírně zápornou informaci — návrat ceny až na úroveň openu
   znamená, že breakout už je částečně popřený. Vstup „na krásné čáře" je
   vstup přesně v momentě selhání momenta.
2. **SL 15 b je sběrač knotů**, éra-závislý: 2018 ~21 bps NQ, 2025 ~7 bps.
   Noční šum NQ je větší — 77 % obchodů umírá na stopce.
3. Rozpad: long −2,0 b, short −4,3 b; 7 z 8 let záporných. Jediný kladný rok
   2023 (+4,2 b, n=87) = šťastné okno, ze kterého se stříhají reels.

## Závěr

Netestovat dál. Skóre video strategií: sweep & reclaim −76 %, wickless 4H
= baseline (nulová informace), 10pm open −58 % (pod náhodou). Anekdota
„$600 z jednoho obchodu" = 1 vydařený TP ze ~4,4 pokusů, které divák nevidí.
