# 2026-10-23 — FUNDED: výhrady k velikosti flat 3

- **Denní stop je součást výsledku:** simulace končí den při ztrátě
  75 $ + 75 $ × jednotky, u flat 3 tedy **−300 $ za den = konec obchodování
  ten den**. Bez toho čísla neplatí.
- **ORB pořád pomáhá i při flat 3:** s ORB 11 500 / 43 000 $, bez ORB
  9 500 / 26 900 $ na účet za 24 měsíců (`scripts/funded_orb_check.py`).
- **Opravená citlivost simulace:** obchody stejného dne se dřív řadily podle
  pořadí, v jakém se nohy knihy spojily, a to měnilo výsledek až o ~25 %.
  Teď se řadí podle typického času vstupu (ORB → VWAP → noise → RS)
  v `prop_sim.merge`; čísla výše už platí s touto opravou.

# 2026-10-23 — FUNDED: velikost pozic agresivněji (flat 3 MNQ na nohu)

`scripts/funded_sizing.py`: evaluace se dělá sprintem, takže bust funded
účtu stojí jen novou evaluaci (~180 $ a ~11 dní). Za takových podmínek se
ve funded fázi vyplácí větší velikost. Průměrná hotovost na účet za 24 měsíců
(2018–21 | 2022–25):

| velikost | opravená kniha | opravená + RS |
|---|---|---|
| ladder 400/500 (dosavadní plán) | 6 400 $ / 31 700 $ | 19 000 $ / 51 900 $ |
| **flat 3 MNQ na nohu** | **11 500 $ / 43 000 $** | **27 300 $ / 60 600 $** |
| flat 4 | 14 400 $ / 45 900 $ | 30 500 $ / 49 500 $ |
| ladder K300/250 | 13 400 $ / 37 600 $ | 24 800 $ / 47 800 $ |

Pořadí platí v obou obdobích, plato je kolem 3–4 MNQ. Doporučení: ve funded
fázi 3 MNQ na každou nohu knihy (ORB, VWAP pásmo, noise, případně RS),
bez ladderu. Rozhodneš ty.

# 2026-10-23 — kniha: průměr místo mediánu (medián u kopírovaných účtů skáče)

Medián simulace 5 kopírovaných účtů skáče po 5 × 1 800 $, proto
`scripts/book_compare.py` počítá **průměrnou hotovost za 24 měsíců na jeden
účet** (po poplatcích 90 $, ±60 $ šum simulace):

| kniha | pass eval | průměr na účet | bez výplaty |
|---|---|---|---|
| výzkumná kniha | 55,6 % | 11 300 $ | 10,6 % |
| živá se starým Lucid 2 | 62,4 % | 11 500 $ | 12,0 % |
| **živá opravená** (Lucid 2 pásmo, Lucid 6 se stopem) | 61,3 % | **13 100 $** | 7,9 % |
| opravená + RS noha | 56,9 % | **16 400 $** | 0 % |
| opravená + RS + ONL gap-up 2 MNQ | 57,1 % | 18 300 $ | 0 % |

RS noha přidává konzistentně. ONL gap-up po opravě řazení obchodů knihu
samo nezlepší (1 MNQ 10 700 $, 2 MNQ 11 600 $ proti 13 100 $) – nedoporučuji.

# 2026-10-23 — EVALUACE: RS sprint se stopem 0,30 % je asi o 2 dny rychlejší

`scripts/rs_sprint_shape.py` (stejný RS signál, velikost tak, aby stop stál
~1 900 $): target 0,20 % / stop 0,30 % → pass 48,8 % / 48,7 %, **10,6 / 10,8
obchodního dne** do passu, poplatky 185 / 185 $. Současné 0,20 / 0,40 %:
47,9 % / 51,5 %, 13,4 / 13,0 dne, 188 / 175 $. Sousední buňky (0,25 / 0,30,
0,30 / 0,40) to potvrzují. Návrh: v Lucid 8 nastav **Stop (% of price) =
0,30** (velikost se přepočítá sama, výhra ~1 270 $, pass = 3 výhry).
Výchozí hodnoty indikátoru jsem neměnil – rozhodneš ty.

# 2026-10-23 — EVALUACE: dva účty = rychlejší první funded, ale dražší

`scripts/two_account_sprint.py` (každý účet po bustu kupuje novou evaluaci 90 $):

| varianta | dní do prvního funded (2018–21 / 2022–25) | poplatky |
|---|---|---|
| RS sprint, 1 účet | 14,2 / 12,3 | 193 / 165 $ |
| sprint 09:31 (50denní trend), 1 účet | 11,9 / 12,6 | 217 / 227 $ |
| **RS + 09:31 na dvou účtech** | **7,8 / 8,7** | 301 / 311 $ |
| RS zkopírovaný na 2 účty | 14,2 / 12,3 | 387 / 329 $ |

Dva účty s RŮZNÝMI signály zkrátí cestu k prvnímu funded asi o 5 dní za
~130 $ navíc (a druhý účet pak často dojde taky). Kopírovat stejný sprint na
víc účtů se nevyplatí.

# 2026-10-23 — FUNDED kandidát: RS signál jako další noha knihy

Stejný signál jako RS sprint (Lucid 8), ale s širokým bracketem +1,25 % /
−1,25 % (vybráno jen na 2018–21), jinak výstup v 15:55: +4,6 / +9,6 bodu na
obchod (t 1,8 / 2,2), kladné 7 z 8 let. Přidaný k opravené knize po 1 MNQ na
jednotku: 5 účtů × 24 měsíců medián 74 000 $ místo 68 000 $, p10 12 000 $
místo 5 000 $; pass evaluace samotnou knihou klesne z 61 na 57 % (evaluace
se ale jede sprintem). V Lucid 8 nastav Target 1,25 a Stop 1,25. Rozhodnutí
je na tobě.

# 2026-10-23 — FUNDED: Lucid 2 opraven (VWAP pásmo), kniha změřená na živých pravidlech

`live_spec_exporter.py` přepočítal indikátory přesně tak, jak jsou napsané:
- **Lucid 2 (starý)**, prosté křížení VWAP: +2,3 / +0,7 bodu na obchod
  (2018–21 / 2022–25, s náklady a filtrem volatility), na 1min grafu ≈ 0.
- **Lucid 2 (nový)**, průraz pásma VWAP ±0,20 % na 5min grafu, jen první obchod
  dne: +3,6 / +3,0 bodu. Indikátor je přepsaný, **používej 5min graf**.
- **Lucid 6** živá pravidla sedí s výzkumem (+5,1 / +8,9); se stopem 0,50 %
  +5,7 / +8,7 a nejhorší obchod −128 místo −218 bodů.

Kniha ORB + VWAP + noise, ladder 400/500/400, 5 účtů 24 měsíců:
starý Lucid 2 medián 51 000 $ (p10 −3 000 $), **opravená kniha medián
68 000 $ (p10 +5 000 $)**, pass evaluace knihou 61 %.

# 2026-10-23 — FUNDED: noise momentum s pevným stopem 0,50 %

`scripts/noise_variants.py`: pevný stop 0,50 % od vstupu ponechá edge
(+6,1 / +9,2 bodu na obchod v 2018–21 / 2022–25 proti +5,5 / +9,4 bez stopu)
a nejhorší obchod zmenší z −221 na −128 bodů (1. percentil −157 → −107).
Profit target edge naopak snižuje (TP 20–50 bp: +1,3 až +4,8). Lucid 6 má
nový vstup „Hard stop“ (výchozí 0,50 %); po stopu indikátor nový vstup
nedá, dokud by původní obchod normálně neskončil (stejně jako backtest).

Mapa režimů (`scripts/regime_map.py`): VIX, 20denní volatilita, trend ani
den v týdnu nedávají filtr platný v obou obdobích, kniha zůstává beze změny.

# 2026-10-22 — EVALUACE: RS sprint (lepší než sprint v 9:31)

`multi_feature_exporter.py` + `score_multi_feature.py`: z předem sepsaných
pravidel (VIX, VWAP, RSI, EMA, volume profile, relative strength) obstálo
jen **relative strength NQ vs ES + VWAP**: v 10:00/11:00/13:00/14:30 první
okamžik, kdy NQ od otevření vede nad ES o > 0,15 % a je nad VWAP → long
(obráceně short). Sprint bracket +0,20 % / −0,40 %. Pass na pokus 48 % /
52 % (2018–21 / 2022–25) proti 36 % u longu v 9:31, ~13 dní do funded.
Kladné ve všech variantách prahu a času. Indikátor `lucid_8_rs_sprint.pine`.
Ostatní pravidla (pullback, momentum, RSI(2), value area, VIX režim) a model
ze všech indikátorů: bez stabilní hrany.

# 2026-10-21 — EVALUACE: sprint, ne kniha

Rozhoduje očekávaný čas a cena do funded účtu, ne pass na pokus
(`scripts/eval_speed.py`). Evaluace stojí $90.

- **Sprint:** každý den long NQ na close svíčky 09:30–09:31, cíl +0,20 %,
  stop −0,40 %, velikost tak, aby ztráta ≤ $1 900 (výhra ~$1 000), jinak
  flat 15:55. 3 výhry = pass (nejlepší den ~33 % → konzistence OK), jedna
  ztráta = konec pokusu. ~35 % pass na pokus, ~5 dní na pokus →
  **~13,5 obchodních dní a ~$260 poplatků do funded** (kniha: ~93 dní, ~$110).
- Indikátor `lucid_7_eval_sprint.pine` (1min graf MNQ).
- Copytrading stejného sprintu na víc evaluací nic nepřidá (stejný výsledek);
  souběžné pokusy jen s různými vstupy.
- Funded fáze: kniha (ORB 5min graf + VWAP pásmo + noise momentum), velikost
  rezerva ÷ 700, max 3 jednotky.

# ⚠️ OPRAVA 2026-10-21 — ORB byl v backtestu nadhodnocen

Backtest ORB (NQ i Dow) zavíral obchod na trailing stopu za cenu stopu i
tehdy, když 20-EMA byla nad posledním close – tedy nad trhem. Ve skutečnosti
se pozice zavře za open další svíčky. Po opravě (`*_fill.py`):

| | před opravou | po opravě |
|---|---|---|
| ORB NQ, body/obchod 2018–21 / 2022–25 | +2,4 / +5,7 (t 5,4 / 6,5) | +0,6 / +1,6 (t 1,4 / 1,8) |
| ORB Dow, $/MYM 2018–21 / 2022–25 | +2,2 / +6,0 | +0,5 / +3,3 |

Celá kniha (ORB + VWAP pásmo + Dow + noise momentum), `book_after_fix.py`:
nejlepší velikost je žebříček rezerva ÷ 700, max 3 jednotky: eval 81,5 % za
~40 dní, první funded 79 %, výplaty 88 %, medián 5 účtů / 24 m ≈ $88k,
p10 ≈ $7k. Noise momentum je teď nosná část knihy.

ORB na 1min grafu (trailing 20-EMA na 1 min) obchoduje ~20× denně a po
nákladech prodělává (pass 8–17 %). Používat jen 5min graf. Indikátor
`lucid_1_s1_orb.pine` opraven (výstup za open, ne za stop).

# 2026-10-20 (večer) — velké hledání denních strategií: výsledek

Testováno ~40 000 kombinací signál × filtr × cíl/stop (`cond_bracket_*`,
`score_cond_bracket.py`, `score_plateau.py`) + kandidáti z veřejných zdrojů
(dva výzkumní agenti). Hlavní zjištění:

- **Vysoký winrate bez hrany pass nezvedá** (~40 % na pokus, potvrzeno
  simulací i literaturou). Gap fill, střed overnight range, IB statistiky
  apod. mají winrate jen na úrovni náhody.
- **Nejlepší denní strategie: noise-area momentum** (Zarattini, Aziz & Barbon
  2024), long i short, ~1 obchod denně, WR ~40 %, +5,5 b./obchod 2018–21 a
  +9,4 b. 2022–25 (t ≈ 3 v obou), 7 z 8 let kladných. Indikátor
  `lucid_6_noise_momentum.pine`.
- Přidáno ke knize 1 MNQ na jednotku: eval 91,6 % (místo 94,7 %) ale za
  31 dní místo 45; první funded 98,6 %; medián 5 účtů / 24 m $161k místo
  $116k, p10 $53k místo $26k.
- Lunch effect, poslední půlhodina (Baltussen), gap fill: na NQ nefungují.

# 2026-10-20 — myšlenka: rychlý pass evaluace sázkou s negativním RR

`scripts/payoff_shape.py` (čistá pravidla), `daily_bracket_exporter.py` +
`scripts/score_bracket.py` (NQ 2018–2025, 1 sázka denně, stop uvnitř DD čáry,
max 40 MNQ, náklady $1/MNQ).

- Bez hrany nejde pass zvýšit tvarem výplaty nad ~45 %. Nejlepší tvar pro
  pravidla Lucid: výhra ~$1 000, ztráta ~$1 900 (WR 66 %) → 45,5 % za 3 dny.
  Velmi negativní RR (1:5) i pozitivní RR jsou horší (27–35 %).
- Na skutečných datech NQ: nejlepší sázky 33–41 % na pokus (OOS), 3–8 dní.
- Očekávání na jeden úspěšný pass (poplatek $150):

| postup | pass/pokus | pokusů | poplatky | obchodních dní |
|---|---|---|---|---|
| sázka long 10:00, $750, TP 20 bp / SL 50 bp | 39,7 % | 2,5 | $378 | 15 |
| sázka long 9:31, $1 450, TP 30 bp / SL 40 bp | 35,4 % | 2,8 | $424 | 11 |
| kniha, žebříček (současný plán) | 93,7 % | 1,07 | $160 | 61 (průměr) |
| kniha, pevně 6 jednotek | 54,2 % | 1,8 | $277 | 21 |

Jen pro evaluaci (bust stojí jen poplatek); funded vždy kniha. Ověřit, že
Lucid takový styl a velikost (až 40 MNQ) povoluje.

# ⚠️ AKTUALIZACE 2026-10-20 — zprávy (CPI, NFP, FOMC): fade velké svíčky

Testováno 2018–2025 na NQ, ES a YM (`news_fade_exporter.py`, `score_news.py`).

- **Fade 08:30 svíčky (CPI, NFP, PPI…) — žádná hrana** na žádném indexu, ani
  k open, ani k 50 %, s žádným stopem/časem. Fade libovolné velké svíčky
  (climax) také ne. Fade svíčky FOMC prohlášení ve 14:00 také ne.
- **Fade první 5min svíčky tiskové konference FOMC (14:30–14:35 ET) — ANO.**
  Kladný v každé variantě stopu i výstupu, v obou obdobích a na všech třech
  indexech (NQ IS +10 až +26 b., OOS +27 až +76 b.; ES i YM stejně).
  Pravidlo: vstup proti svíčce na jejím close (14:35), stop za jejím
  extrémem + 0,25 × rozpětí, výstup 15:35. NQ: 63 obchodů, 41 % výher,
  průměr +51 b., medián −7 b., 6 z 8 let kladných. Malý vzorek (8×/rok),
  zisk dělá pár velkých reverzí.
- FOMC je vždy středa, kdy zbytek knihy neobchoduje → žádný překryv.
  Doporučení: **1 MNQ na jednotku** (v evaluaci tedy 2 MNQ). Indikátor
  `lucid_5_fomc_fade.pine`.
- Poslední půlhodina (Gao a kol.) a drift před FOMC: nevýznamné.

# ⚠️ AKTUALIZACE 2026-10-18 (skutečné komise) — platí přednostně před vším níže

Čitelná verze plánu je v Claude Docs („Lucid Flex 50K — finální plán").

Komise účtu na mikro a obchod: MNQ/M2K/MYM $0,50, MGC $0,80. Se skluzem
1 tick (`scripts/real_costs.py`):

| kniha (žebříček, max 4 jednotky) | eval · funded · výplaty | medián 5 účtů / 24 m |
|---|---|---|
| NQ (K400/500/400) | 88,8 · 87,9 · 96,0 | $116 250 |
| **NQ + 2 MYM na MNQ (K700/800/700)** | **93,7 · 95,4 · 99,5** | **$125 250** |
| NQ + 2,33 M2K (K500/600/500) | 88,1 · 87,3 · 93,4 | $133 500 |
| NQ + 2 MYM + 2,33 M2K | 91,5 · 92,2 · 98,8 | $143 250 |
| zlato long+short, samostatný účet | 82,3 · 81,0 · 88,3 | $62 250 |

**Rozhodnutí: přidat ORB na Dow (2 MYM na každý MNQ).** Zvedá pass ve všech
fázích i bez skluzu i s dvojnásobnou komisí. Russell zvedá medián, ale snižuje
pass v evaluaci a prvním funded — vynechán. Zlato vynecháno.

# ⚠️ AKTUALIZACE 2026-10-18 (večer) — platí přednostně před vším níže

## 0. Oprava: náklady

Všechny dřívější simulace počítaly bez poplatků a skluzu. Teď je v nich
**$1 komise + 1,5 ticku skluzu na mikrokontrakt a obchod** (MNQ ≈ $1,75).
Kniha dělá v průměru 4,6 obchodu denně, takže náklady seberou zhruba čtvrtinu
hrany. Všechna čísla níže už jsou po nákladech (`scripts/cost_check.py`).

$1,75 je konzervativní odhad. V sim prostředí propky bude skluz spíš menší
(tržní příkaz ale pořád platí spread, stop se plní až za spouští). Citlivost
na náklady za MNQ a obchod:

| náklad / MNQ | pevně 3/2/3: eval · funded · výplaty · medián 5 účtů | žebříček 400/500/400: eval · funded · výplaty · medián |
|---|---|---|
| $0,00 | 77,4 · 91,1 · 93,6 · $131 250 | 92,2 · 92,4 · 98,5 · $152 250 |
| $0,50 | 74,1 · 87,8 · 91,4 · $132 000 | 89,9 · 90,2 · 97,5 · $134 250 |
| $1,00 | 70,3 · 85,6 · 89,2 · $114 000 | 88,8 · 87,9 · 96,0 · $116 250 |
| $1,75 | 60,5 · 72,6 · 81,0 · $87 000 | 77,4 · 80,2 · 88,4 · $97 500 |

Žebříček vyhrává při každé úrovni nákladů. Russell a zlato jsou na
nákladech závislé úplně — přepočítat, až bude známa skutečná komise.

## 1. Co neobchodovat

- **Reverzace po gapu dolů** — artefakt backtestu (stop se nekontroloval
  v první svíčce), hrana nulová.
- **Pondělí/Pátek** — široké stopy, kniha je bez nich stejná nebo lepší.
- **Russell (M2K)** — hrana +$2,46 na M2K a obchod, náklady ~$2,2 → po
  nákladech skoro nula. Pravděpodobnost projití fází nezvedá.
- **Zlato (MGC)** — ORB funguje long i short (short zrcadlo kladné všech 8 let,
  takže to není jen růst zlata), ale hrana $4,6 / $3,9 na MGC a obchod po
  nákladech ~$3,5 skoro mizí; se skluzem 2 ticky je zlatý účet ztrátový.

## 1b. Kandidát: ORB na Dow (MYM) — rozhodnout podle skutečných nákladů

ORB na YM: hrubě +$3,88 na MYM a obchod, kladný všech 8 let, denní korelace
s NQ knihou 0,42. Přidán ke knize (2 MYM na 1 MNQ, žebříček rezerva ÷ 700 /
÷ 800, max 4 jednotky):

| náklad / mikro | bez YM: eval · funded · výplaty · medián | s YM: eval · funded · výplaty · medián |
|---|---|---|
| $0,50 | 89,9 · 90,2 · 97,5 · $134 250 | 100 · 100 · 100 · $152 250 |
| $1,00 | 88,8 · 87,9 · 96,0 · $116 250 | 93,7 · 95,4 · 99,5 · $125 250 |

Na 2018–21 (při $1) eval 81,9 → 86,8 %. Zlepšení je v obou obdobích, ale
hrana na obchod je malá, takže zavést až po ověření skutečné komise a skluzu.
S&P (MES) zamítnut — po nákladech ztrátový 2018–2020.

## 2. Kniha — beze změny

ORB 15 min long + VWAP pásmo (SL 25 / TP 100) na MNQ, volatilitní brána 0,30,
středa ne. Obě strategie mají po nákladech kladnou hranu
(ORB +$6,1, VWAP +$6,6 na MNQ a obchod).

## 3. Velikost — podle vzdálenosti od DD čáry

`rezerva = zůstatek − DD čára` (dokud se čára nezamkne, je to $2 000 minus
propad od maxima).

| fáze | pravidlo | rezerva → MNQ | pass / bust | medián dní |
|---|---|---|---|---|
| evaluace | rezerva ÷ 400, max 4 | ≥1 600: 4 · 1 200–1 599: 3 · 800–1 199: 2 · pod 800: 1 | **77,5 % / 22,5 %** | 27 |
| první funded | rezerva ÷ 500, max 4 | ≥2 000: 4 · 1 500–1 999: 3 · 1 000–1 499: 2 · pod 1 000: 1 | **80,3 % / 19,7 %** | 53 |
| další výplaty | rezerva ÷ 400, max 4 | jako evaluace | **88,4 % / 11,6 %** | 14 |

Pro srovnání: pevně 3 MNQ v evaluaci = 60,5 % / 39,5 %. Žebříček vyhrál
v evaluaci i bez nákladů (86,6 % vs 73,9 %), takže tohle je robustní.

Opatrnější první funded: **pevně 1 MNQ = 95,7 % / 0 %**, ale medián ~134
obchodních dní (~6 měsíců).

## 4. Pět účtů, 24 měsíců, po nákladech

Žebříček 400/500/400: p10 $24 000 · **medián $105 750** · p90 $179 250.
Dřívější čísla ($178 500 atd.) byla bez nákladů a neplatí.

## 5. Zamítnuto

Reverzace po gapu, fade overnight levelů, 1min mikro-propad (tři artefakty
backtestu), ROD momentum, ropa kolem EIA, zlato přes asijskou seanci,
Pondělí/Pátek, dvě dávky nových signálů na NQ, shorty, „lab" archiv, Russell
ORB a zlatý ORB (hrana nepřežije náklady).

---

# Lucid Flex 50K — final plan

Five copytraded accounts. Every number below comes from simulating the actual
strategy book through the actual account rules over NQ 2018-2025, charging
every evaluation fee and every rebuild.

---

## The rules this is built on

All confirmed against the live account:

- **No time limit.**
- Drawdown is **$2,000 below the highest end-of-day balance**, ratcheting up
  only — close at $50,600 and the line is $48,600; fall to $50,200 and it
  stays at $48,600.
- The line **locks at $50,100** once an EOD close clears $52,100, and **stays
  locked after a withdrawal**.
- Consistency (evaluation only): best day ≤ 50% of final profit. It gates the
  upgrade, it does not kill the account, and extra profit dilutes it.
- Funded: **+$4,000** unlocks the first payout — withdraw half, Lucid takes
  10%, you receive **$1,800**. Afterwards the balance sits at $52,000 against
  the locked $50,100, so each further payout needs only **+$2,000**.
- **Payouts every 5 days. Copytrading permitted.**

---

## The book

Four strategies, all on NQ/MNQ, all flat by 15:55 ET, all skipping Wednesday.

| | strategy | entry | stop | exit |
|---|---|---|---|---|
| 1 | **ORB 15m long** | after 09:45, close > OR high *and* > VWAP | max(OR low, close − OR range) | 20-EMA trail, or 15:55 |
| 2 | **VWAP band** | close breaks ±20bps band | 25 pt | TP 100 pt, or 15:55 |
| 3 | **Mon/Fri hold** | first 5m bar vs EMA12 — Mon long, Fri short | that bar's wick | 15:55 |
| 4 | **Gap reversal** | RTH open ≥ 0.25% below prior close | **0.05% of price** | 15:55 |

**Two rules that matter more than any entry:**

- **Do not trade when 20-day realised volatility is above 30% annualised.**
  It blocks about 17% of sessions, and it lifts pass rate while roughly
  halving bust. Wired into all four indicators.
- **ORB re-enters freely.** Capping it at one trade per day drops its
  standalone pass rate from 46% to 9%. Later entries are the better ones —
  hit rate climbs from 37% on the first to 61% by the seventh.

Maximum two positions open at once. If a third fires in the same direction,
skip it.

---

## Sizing — 3 / 2 / 3 MNQ

| stage | need | what a bust costs | size | survives | median |
|-------|------|-------------------|------|----------|--------|
| evaluation | +$3,000 | one $150 fee | **3 MNQ** | 75.9% | 20 days |
| first funded cycle | +$4,000 | **the seat** | **2 MNQ** | **92.2%** | 56 days |
| repeat cycles | +$2,000 | the seat | **3 MNQ** | 88.0% | 13 days |

Daily loss stop **$300** at 3 MNQ, **$240** at 2 MNQ. Day profit cap $1,450.

The middle stage is the one that deserves caution, and it is the only one.
An evaluation bust costs a fee, so haste there is nearly free. A repeat cycle
starts at $52,000 against a **frozen** $50,100 line — $1,900 of cushion that
can no longer chase you — so it survives 88% even at 3 MNQ. The first funded
cycle has neither property: the line is still trailing, the target is the
largest of the three at +$4,000, and losing it costs a seat worth $1,800
every two weeks thereafter.

Easing that stage from 3 to 2 MNQ pays for itself twice over:

| | 3 / 3 / 3 | **3 / 2 / 3** | 3 / 1 / 3 |
|---|---|---|---|
| median, 24 months | $112,500 | **$123,000** | $96,000 |
| p10 | $68,250 | **$78,750** | $51,750 |
| first payout | 4.1 mo | 4.6 mo | 6.8 mo |
| rebuilds | 4.75 | **2.38** | 1.70 |

Going further, to 1 MNQ, overshoots: survival reaches 100% but the stage takes
5.5 months, and the delay into the repeat loop costs more than the safety is
worth.

A ramp that sizes up once the line locks at +$2,100 was also tested and is
dominated — at 1 MNQ it takes so long to reach the lock that flat 2 MNQ beats
it on survival *and* on time.

## What to expect over 24 months

Five accounts, all fees and rebuilds charged:

| | 2 MNQ throughout | **3 MNQ throughout** |
|---|---|---|
| median profit | $124,500 | **$148,500** |
| p10 (bad run) | $70,500 | **$96,000** |
| p90 (good run) | $179,250 | $203,250 |
| first payout, median | month 4.3 | **month 3.6** |
| P(reach a payout) | 100% | **100%** |
| P(net loss at 24 months) | 0% | **0%** |
| evaluation rounds bought | 1.9 | **5.4** |

3 MNQ is better at every percentile, including the bad tail. The cost is
churn: **about 27 evaluations over two years**, roughly $4,000 in fees, and
the accounts dying and being rebuilt perhaps five times.

**If that churn is intolerable, run 2 MNQ.** It gives up around 16% of the
median and buys a far quieter two years — 1.9 rounds of evaluations instead
of 5.4. The money is similar; the experience is not.

---

## Daily routine

| time ET | |
|---|---|
| 09:25 | Check the volatility badge. Red → **no trading today** |
| 09:30 | Gap ≤ −0.25%? → long the open, stop 0.05% of price |
| 09:30 | Mon/Fri only: first 5m bar vs EMA12 |
| 09:40+ | VWAP band breaks live |
| 09:45–15:00 | ORB window — re-enter as often as it triggers |
| 15:55 | **Flat everything** |
| after close | Log the balance; check whether the line has locked yet |

Stop for the day at **−$300** or **+$1,450**.

---

## What this rests on, and where it could be wrong

**The book is long-biased.** ORB is long-only and so is the gap reversal, and
four separate attempts to build a short side all failed — shorting fights
NQ's drift. Expect the whole thing to do better in a rising market.

**Sub-period spread, 80-day evaluation windows:** 58% / 84% / 99% / 83% across
2018-2020, 2020-2022, 2022-2024 and 2024-2026. The headline figures sit near
the middle of that range, not at the top.

**The gap reversal is a lottery ticket.** Roughly 85% of its entries stop out
small and 15% run to the close, several above +300 points. Expectancy is good
(+8.91 pt per trade over 2021-2025) but it arrives in a handful of days. Do
not widen its stop after a losing streak — the winners run to the close
regardless of stop width, so width only sets what the losers cost.

**The honest benchmark is not zero.** A driftless walk passes at 40%; leveraged
long NQ with a stop, risk-matched to this book, passes at roughly 37% over 80
days and 61% over 120. This book clears that, but it is an edge, not a
machine.

**Two modelling assumptions worth watching in the first live cycle:** that
busted seats can be replaced promptly at the quoted fee, and that the repeat
cycle really does restart at $52,000 against the locked line. If either is
wrong the repeat-cycle numbers are the ones that move.
