# Powell Trades: key opens + fib — verdikt: JÁDRO ZÁPORNÉ, uzavřeno

**Zdroj:** YouTube video (transkript), setup: 10am key open (open 4h svíčky),
manipulace → agresivní 5m reverz-close skrz open → retest = vstup, stop
10–25 b, RR 4–6,6; + midnight open (manipulace/magnet, „90–95 %").
Diskreční vrstvy (rejection/order blocky, „dobré vs špatné") netestovatelné.

**Test:** reálné NQ 2018–2025 (QC), projekt `NQ_Powell_KeyOpen` (35168105).
Test 1: 1 062 mechanických setupů, MFE-před-stopem → mřížka stop × target
vs náhodná základna 1/(1+RR). Test 2: 1 952 dní midnight open, podmíněný
návrat vs distance-matched baseline.

## Test 1: mřížka (výběr)

| stop | target | RR | win % | náhoda | z |
|---|---|---|---|---|---|
| 15 | 30 | 2,0 | 35,2 | 33,3 | +1,3 |
| 15 | 60 | 4,0 | 17,9 | 20,0 | −1,8 |
| 15 | 100 | 6,7 | **9,4** | 13,0 | **−4,0** |
| 25 | 100 | 4,0 | 14,1 | 20,0 | −5,5 |
| 25 | 150 | 6,0 | **7,6** | 14,3 | **−8,2** |

V jeho vlastním RR pásmu (4–6+) je mechanika VÝRAZNĚ POD náhodou — retest
entry s mikro stopem (15 b ≈ 6 bps) umírá na šum dřív, než doběhne velký
target. Nejsilnější negativní signál celé série testů. EOD varianty ~0.
Jediná kladná buňka (15/30, z=+1,3) = šum tažený 2022.

## Test 2: midnight open magnet

| overnight manipulace | RTH návrat | baseline |
|---|---|---|
| malá (jeho podmínka) | **60,7 %** | 66,3 % |
| velká | 74,9 % | 69,3 % |

Podmínka funguje OBRÁCENĚ: bez manipulace = trendový den = menší šance
návratu. „90–95 %" je šestý „úroveň bude navštívena" claim bez base rate,
tentokrát s obráceným znaménkem.

## Závěr

Mechanické jádro nulové až záporné → případné zisky autora sedí celé
v diskreci a výběrové paměti. Nestavíme. Skóre „respektovaných úrovní":
0/6 (wickless 4H, 10pm open, golden zone, Hougaard, 10am open, midnight).
