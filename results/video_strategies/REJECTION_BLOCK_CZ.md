# Rejection block: kvalifikace a měření odrazů — verdikt: ODOLNĚJŠÍ ČÁRA, NE GENERÁTOR ODRAZŮ

**Mechanická kvalifikace (formulováno předem):** 5m fraktální pivot (2/2)
+ knot ≥ 50 % rozsahu svíčky + sweep likvidity (knot přestřelil extrém
předchozích ~12 barů). Zóna = [tělo, konec knotu]. Event = první same-day
retest nemitigované zóny; měřeno close-based od close retest baru do
violace (close za knotem) nebo EOD. Kontrola = plain pivoty (knot < 30 %,
bez sweepu).

**Data:** NQ 5m, 2018-01 až 2022-01 (10 001 eventů; QC 10k order limit
uťal 2022–2025). Projekt `NQ_Rejection_Block` (35172079).

## Výsledky — kvalitní RB

| metrika | hodnota |
|---|---|
| odraz ≥ 10 / 20 / 30 bps | 44,4 / 29,7 / 21,9 % |
| avg MFE / medián MFE | 20,2 / **7,4** bps |
| violace zóny | **69,3 %** |

## Q vs plain pivot

| | Q | plain | z |
|---|---|---|---|
| P(odraz ≥ 20) | 29,7 % | 27,4 % | +1,3 (šum) |
| avg MFE | 20,2 | 19,6 | +0,4 (šum) |
| violace | 69,3 % | **77,6 %** | **−5,2** ✓ |

Komponenty: knot ≥ 50 % nese malý efekt trvanlivosti; **sweep likvidity
nepřidává nic** (P(odraz≥20): 28,8 vs 29,6 %). Fade na retestu s TP 20 /
exit na violaci: −6 bps/obchod hrubě u obou tierů.

## Závěr

„Kvalita" rejection blocku měřitelně znamená jen o ~8 p.b. nižší šanci na
proražení — NE častější či delší odrazy. Definující vlastnost RB
(odmítnutí ceny při retestu) je statisticky nerozlišitelná od obyčejného
pivotu; medián odrazu 7 bps a 70% violace. Mechanicky obchodovatelný edge:
žádný. Limity: 4 roky (order cap), same-day retesty, mechanická definice
vs diskrece autora — ale právě diskrece je nefalzifikovatelná.
