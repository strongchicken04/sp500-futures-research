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


## Dodatek: NQ/ES intradenní spread reverze — MRTVÁ

Spread s(t) = (NQ/NQ_930)/(ES/ES_930) − 1; prahy 10–60 bps, close-based,
náklady 4 bps (obě nohy). Projekt `NQ_ES_Spread` (35168865), backtest
`1cecbbcb...`, 7 048 obchodů.

Všech 15 buněk (práh × stop/EOD) záporných: −4,2 až −7,1 bps net,
z −2,8 až −13,2; všech 8 let záporných; obě strany záporné. Klíč:
P(návrat spreadu na 0) klesá 61 % → 10 % s prahem — intradenní divergence
NQ/ES je faktorový pohyb (tech vs broad), který PERZISTUJE, ne šum.
Beta se ve spreadu vyruší, faktorový trend ne. Zrcadlové momentum na
spreadu ≈ 0 po nákladech.

**Uzávěr MR kampaně:** intradenní indexový komplex 2018–2025 je trendově
dominantní ve všech měřených podobách (outright, VWAP pásma, cross-market
spread). MR hledat na delších horizontech / jiných aktivech, ne zde.


## Dodatek 2: Z-score pairs NQ/ES (denní horizont) — NULA

Uživatelova myšlenka „korelované assety se po rozchodu vrací k sobě"
refinovaná do standardní podoby (Gatev et al.): spread = kumulativní
(ret NQ − ret ES), z-score vs rolling L dní (past-only), vstup |z| ≥ Z na
close, exit z přes 0 / |z| ≥ 3,5 / time-stop H dní, náklady 4 bps.
Data: denní closes 2010–2025 (4 097 dní), projekt `NQ_ES_DailyCloses`
(35169190). Předregistrovaná mřížka L{20,60} × Z{1,5;2;2,5} × H{5,10}.

Výsledek: z-staty −1,3 až +0,8 napříč 12 buňkami, win 46–52 %. Nejlepší
buňka n=80/16 let, roky ±140 bps. Jediná asymetrie = long-NQ strana
(+26 bps, n=32) — sekulární tech drift, ne konvergence.

**MR na indexovém páru NQ/ES definitivně uzavřeno v obou patrech:**
intradenně divergence perzistuje (faktorový trend), denně konverguje
příliš líně na náklady dvou nohou. Literaturní edge (akciové páry
1962–2002) je post-2002 z velké části vytěžený; NQ/ES relativní hodnotu
drží HFT. Akciové páry = jiná infrastruktura, mimo futures prop rámec.


## Dodatek 3: Poslední dva kandidáti — crash bounce a noční fade — MRTVÉ

**Crash bounce** (long na −k·σ20 intradenním propadu, exit 15:59, 229
eventů): k=2,0: +8,1 bps (z=+0,7); k=2,5: −3,0 (z=−0,3); k=3,0: +3,1
(z=+0,2). Roky ±90 bps. Holmbergův chvostový náznak (−51 bps shorty) se
do pravidla nepřenesl — jiná definice prahu, hrstka extrémů, šum.

**Noční VWAP fade** (18:00–03:00, close-based, 5 726 eventů, náklady
2,5 bps): stopové varianty z −4 až −10 (noční extenze = kroky globálního
trendu), hold do 2:55 na nule (+0,3 bps, z=+0,2).

## UZÁVĚR MR KAPITOLY

Proměřeno na NQ futures: RTH VWAP pásma (touch i close), noční seance,
crash chvosty, NQ/ES spread (intraday + denní pairs), gap fade, lunch
fade, odpolední reverze, Bollinger, RSI(2). Jednotný výsledek: reverzní
edge dostupný z minutových dat na tomto trhu NEEXISTUJE. Je to tatáž
vlastnost trhu, která živí trend jádro. Další MR testy na NQ = p-hacking;
kapitola uzavřena. Projekt `NQ_MR_Duo` (35169641).
