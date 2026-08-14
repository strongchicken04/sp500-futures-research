# VWAP mean reversion na NQ — verdikt: NEEXISTUJE (+ lekce o fillech)

**Otázka uživatele:** které bps pásmo od session VWAP má po doteku nejvyšší
šanci na cross celého range? Obecně: dá se na VWAP reverzi postavit MR noha
portfolia?

**Data:** reálné NQ 2018–2025 (QC), pásma 20–100 bps, první dotek dne,
~8 000 pozorování. Projekt `NQ_VWAP_MR` (35168376), 3 běhy
(mapa `5e75213c`, touch-sequenced `af5aa938`, close-based `64a42691`).

## 1. Mapa (odpověď na otázku)

| pásmo | doteků/rok | P(návrat VWAP) | P(full cross) | fade EOD avg |
|---|---|---|---|---|
| 20 | 249 | 93,7 % | 74,4 % | −2,4 bps |
| 40 | 215 | 75,6 % | 42,3 % | −2,3 bps |
| 60 | 154 | 61,1 % | 26,4 % | −1,3 bps |
| 100 | 68 | 44,2 % | 13,9 % | −8,2 bps |

P(cross) je monotónní geometrie — žádný sweet spot. Fade do EOD záporný
všude; nejhorší poledne (z=−2,2) a fade rally (drift proti).

## 2. Touch-based TP na VWAPu: FATA MORGÁNA

Sekvencovaná mřížka pásmo × stop s fillem na doteku knotu: VŠE kladné,
nejlepší buňka +10,5 bps net, z=+19,5, všech 8 let kladných (~+35 % p.a.).

## 3. Close-based pravda

Stejná mřížka, vstup/exit na close svíček (market filly, konvence živé
strategie): **všech 12 buněk záporných** (−2,3 až −4,9 bps net,
z −1,9 až −6,1). Fill na knotu vyráběl ~13–15 bps/obchod z ničeho —
adverse selection pasivních fillů (dotek bez průrazu tě nenaplní; průraz
= pokračování proti tobě).

## Závěry

1. **VWAP MR na NQ po nákladech neexistuje** — žádné pásmo, žádný stop,
   žádný čas dne. Konzistentní s tím, proč funguje trend jádro: NQ je
   intradenně trendový trh.
2. **LEKCE (nejcennější výstup): z=+19,5 lze vyrobit jediným optimistickým
   předpokladem o fillech.** Touch-fill limitek je nejčastější zdroj
   falešných MR edge v retail backtestech. Vždy přepočítat close-based.
3. MR nohu portfolia hledat jinde (jiný mechanismus/instrument), ne na
   intradenním NQ kolem VWAP.
