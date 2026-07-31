# Holmberg, Lönnbark & Lundström: vol-škálovaný ORB — replikace na NQ

**Paper:** „Assessing the profitability of intraday opening range breakout
strategies" (Umeå University). ORB s prahem ρ = μ̂ + σ̂·z_α z rozdělení denních
open→close log výnosů; long při P ≥ Po·e^ρ, short zrcadlově; exit na close,
bez SL. Na ropě 1983–2011 (denní OHLC, prahy ex post, nulové náklady) našli
signifikantní výnosy rostoucí s hloubkou chvostu; přiznávají, že výsledek
táhne volatilní subperioda 2001–2011.

**Naše replikace (poctivější):** reálné NQ 2018–2025, minutová data, prahy
z rolling 250 dní past-only, gap-safe fill, 5 hladin α paralelně, 1 obchod/
den/kniha. Projekt `NQ_Holmberg_ORB` (34687252), backtest
`944dfe10f96a5ad2172dddb908f6e88d`, 1 125 obchodů.

## Výsledky (hrubě, bez nákladů)

| α | N | win % | avg bps | avg pts | boot p |
|---|---|---|---|---|---|
| 10 % | 552 | 52,4 | +6,6 | +9,5 | 0,108 |
| **5 %** | 307 | 53,1 | **+13,1** | +20,4 | **0,051** |
| 1 % | 118 | 61,9 | +13,6 | +30,0 | 0,203 |
| 0,5 % | 93 | 59,1 | +13,1 | +29,6 | 0,244 |
| 0,1 % | 55 | 49,1 | **−29,6** | −15,0 | 0,822 |

Long vs short: longy nesou většinu efektu (5 %: +20,0 vs +9,4 bps; 0,5 %:
+68 vs −6; 0,1 %: +29 vs **−51,5**). Po letech (α=10 %): kladné 2018, 2022,
2025 — volatilní roky; 2019/2021 záporné.

## Závěry

1. **Chvostová monotonie z paperu se nereplikuje** — na NQ vrchol u α≈5 %,
   nejhlubší chvost záporný. Den s pohybem >3σ se na NQ do close spíš odráží
   (crash-reversal), zejména dolů — shorty v hlubokém chvostu jsou nejhorší
   buňka tabulky.
2. **Slabé breakout momentum na NQ existuje** (+13 bps hrubě, p≈0,05 na α=5 %),
   ale po nákladech (~2 bps) a při ~38 obchodech/rok to samostatně nestačí;
   koncentrace do volatilních let = potvrzení našeho regime závěru
   (ORB je long volatilita).
3. Rozdíl vůči paperu vysvětlují: in-sample prahy (look-ahead), perfektní
   fill z denních OHLC, nulové náklady, jiný trh a éra.

**Verdikt:** metodologicky nejpoctivější materiál z celé série testů; efekt
směrově potvrzen, obchodně no-go standalone — konzistentní se Zarattini ORB
závěrem. α=5% práh si zapisujeme jako kandidátní feature pro regime přístupy.


## Dodatek: kombinace s regime filtrem (OOS)

Filtr z našeho regime výzkumu — `(rvol20 > medián) ∨ (|gap| > medián) ∧
trend50 ≤ q75` — prahy fitované na reálném NQ **2009–2017**, aplikované na
obchody 2018–2025 (plně out-of-sample; vzorec filtru pochází z dřívější
výzkumné linie, panenské jsou prahy a aplikace).

| α=5 % | N | win % | avg bps | boot p |
|---|---|---|---|---|
| bez filtru | 303 | 53,1 | +12,1 | 0,060 |
| s filtrem | 249 | 55,8 | **+15,5** | 0,052 |
| zablokované dny | 54 | 40,7 | **−3,2** | — |

**Zablokované dny jsou záporné ve všech 5 α-knihách** (−4,5/−3,2/−24,9/−24,0/
−75,5 bps) — 5/5 shoda znaménka; filtr systematicky odřezává dny bez paliva,
nejen šum. Čtvrtá nezávislá konfirmace: ORB = long volatilita.

Obchodně: nejlepší buňka (α=5 % + filtr) ≈ +13,5 bps/obchod po nákladech,
~31 obchodů/rok → roční přínos ~4 % nominálu. Satelit, ne jádro portfolia;
proti VWAP strategii (Sharpe 1,23) doplněk s nízkou korelací (breakoutové
dny vs pásmové dny), nikoli náhrada.


## Dodatek 2: Parameter Optimization Machine — VERDIKT FAIL

Grid 160 konfiguraci (alpha x vol_gate x gap_gate x trend_cap), obchody
2018-2025, naklady 2 bps, WF foldy 2022-2025, PBO S=12, noise = plna pipeline
na 3 GBM svetech (vol-clustering, nulovy drift).

| kriterium | hodnota | prah | vysledek |
|---|---|---|---|
| WF Sharpe (plateau) | 0,38 | > 0,3 | OK (tesne) |
| PBO (plateau) | 59 % | < 50 % | FAIL |
| nad noise floorem | 0,38 vs max sum 0,82 | WF > sum | FAIL |

Zero-edge svet umi z teto pipeline vyrobit WF Sharpe 0,82 - vic nez realna
data. Pri ~31 obchodech/rok neni vyber konfigurace statisticky ukotveny.

**Zaver: do portfolia NEZARAZOVAT.** Efekt zustava zapsany jako konfirmace
regime hypotezy (blocked days zaporne 5/5), ne jako obchodni system. Jedina
legitimni cesta dal: prodlouzit data (QC export 2010-2025 -> 8 WF foldu),
zadne dalsi ladeni parametru.
Soubory: holmberg_optimization.json, holmberg_heatmap/walkforward/pbo/
noise_floor.png v results/optimizer/.


## Dodatek 3: Finální test na plné éře 2010–2025 — FAIL potvrzen, případ uzavřen

Prodloužený export (QC, 2009-06 až 2025, 2 557 obchodů, stejná mřížka beze
změn) → mašina s 12 walk-forward foldy (2014–2025):

| kritérium | 2018–2025 | 2010–2025 | práh |
|---|---|---|---|
| WF Sharpe (plateau) | 0,38 | **0,003** | > 0,3 |
| PBO (plateau) | 59 % | **57 %** | < 50 % |
| max noise WF | 0,82 | **0,74** | pod WF |

Walk-forward přes 12 let = nula (tot −3,3 %, MDD −31 %). Hraniční výsledek
z éry 2018–2025 byl artefakt jedné éry; delší data slabý signál nezachránila,
ale odhalila. **Případ uzavřen: Holmberg ORB (i s regime gaty) do portfolia
nepatří.** Vědecká hodnota zůstává: blocked-days asymetrie potvrzuje regime
hypotézu, ale nositelný edge z ní na NQ nevzniká.

Backtest `a08a09018c56c6c8841c75ec7929e4db`, obchody v
holmberg_orb_trades_full.json, mašina: results/optimizer/holmberg_*.{json,png}.
