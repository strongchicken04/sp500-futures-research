# TradeX ORB Sniper — rekonstrukce a test celé rodiny exitů

**Zdroj:** invite-only closed-source indikátor (TradeX ORB Sniper V3 / strategy
v3.6). Vendor sám uvádí: 4 režimy range (premarket / 5min / 15min /
volume-adaptivní), breakout = **close svíčky za range** ("Get Ready Candle"),
Risk Box + Reward Box odvozené z range. Přesné konstanty TP/SL jsou skryté.

**Rekonstrukce (ze screenshotu + popisu):** range = high/low 9:30–9:45 ET
(~135 b na ukázkovém dni), vstup = close 5m svíčky za range, max 1 long +
1 short/den, vstupy do 15:00, EOD exit 16:00. TP/SL = násobky velikosti
range R (velikost se den ode dne liší → potvrzeno).

**Test:** místo hádání jedné konstanty testována **celá rodina** — pro každý
obchod zaznamenáno MFE dosažené *před* zásahem každého kandidátního SL, což
umožní vyhodnotit libovolnou kombinaci. Reálné NQ 2018–2025, projekt
`NQ_ORB_Sniper` (35871591), backtest `f6a7c9d7...`, **2 707 obchodů**
(338/rok), náklady 0,75 b/obchod (komise + 1 tick skluz).

## Výsledek: mřížka 4 × 7 = 28 kombinací

| SL | TP | RR | win % | náhodná báze | avg b | z |
|---|---|---|---|---|---|---|
| 0,15R | 0,15R | 1,0 | 49,1 | 50,0 | −1,06 | **−4,6** |
| 0,25R | 0,35R | 1,4 | 43,0 | 41,7 | −0,23 | −0,5 |
| 0,25R | 0,50R | 2,0 | 35,1 | 33,3 | +0,23 | +0,4 |
| 0,25R | 1,50R | 6,0 | 13,4 | 14,3 | +0,63 | **+0,7 (max)** |
| 0,35R | 1,00R | 2,9 | 25,4 | 25,9 | +0,42 | +0,5 |
| 0,50R | 0,15R | 0,3 | 76,7 | 76,9 | −0,97 | **−2,3** |

- **Win rate kopíruje náhodnou bázi ve všech 28 buňkách** (rozdíl ≤ 2 p.b.).
- Nejlepší buňka: **z = +0,7** (nic). Jediné signifikantní buňky (|z| > 2) jsou
  **záporné** — malé TP, kde náklady sežerou celý cíl.
- 12/28 buněk kladných = přesně to, co dělá mince.
- Konfigurace ze screenshotu (SL 0,25R / TP 0,35R): **−0,23 b/obchod,
  −623 b za 8 let**, žádná stabilita po letech.

## Proč exit nemůže rodinu zachránit

Medián **MAE = 0,99 × R** — typický breakout jde v průběhu dne o celou
velikost range proti pozici. SL jako zlomek R je tedy zasažen u většiny
obchodů bez ohledu na umístění; a protože win rate = náhodná báze, vstup
nenese na scalpovacím horizontu žádnou směrovou informaci. Exit umí jen
přerozdělit win rate proti payoffu, ne vyrobit hranu.

## Jediné kladné číslo v celé studii (a je to opak scalpingu)

Držení do EOD **bez TP a SL**: +3,03 b/obchod net, celkem +8 212 b,
denní Sharpe 0,35 (IS). Po letech: 2018 +264 · 2019 −18 · **2020 −2 806** ·
2021 +1 015 · 2022 +2 833 · 2023 +1 574 · 2024 +1 819 · 2025 +3 531.
Se SL 0,5R jako pojistkou: +2,99 b (z = +1,9).

Není to k obchodování: z = +1,4 (nesignifikantní), jeden rok maže třetinu
zisku, a tahle rodina (ORB + EOD exit) už dvakrát prošla mašinou a spadla —
naposledy Holmberg s WF Sharpe 0,003 na 2010–2025.

## Poznámky k rozdílu vůči TradingView křivce

1. **Intrabar pořadí:** TP i SL jsou zlomky R → často padnou do téže 5m
   svíčky. TV bez tikových dat pořadí odhaduje; náš test rozhoduje na 1min
   a při nejednoznačnosti počítá **stop**.
2. **Délka historie:** TV Premium = 20 000 barů → na 5m NQ ≈ 72 dní (ETH)
   až ~1 rok (RTH), pokud nebyl zapnutý Deep Backtesting.
3. **Éra:** některé buňky byly kladné 2020–2022 a záporné 2024–2025.

## Limity rekonstrukce

SL/TP měřeny **od vstupní ceny**. Pokud vendor umisťuje stop na hranu range
nebo na opačnou stranu range, je to jiná geometrie (tento export ji
nepokrývá) — strukturální závěr (vstup bez směrové informace, MAE ~1,0R) ale
platí nezávisle na umístění stopu.
