# Playbook – Lucid Flex 50K (stav 23. 10. 2026)

Všechno níže je návrh z backtestů 2018–2025 (laděno na 2018–21, ověřeno na
2022–25). Výsledky v minulosti nezaručují budoucí. Rozhoduješ ty.

## 0. Nejdřív: nahraj nové verze indikátorů

Lucid 1, 2, 6 a 7 byly 23. 10. upravené (shoda s backtestem, denní hodnoty
z posledního dokončeného dne). Lucid 8 beze změny. Lucid 9 nepoužívej (držení přes noc není povolené).

## 1. Evaluace – dva účty, každý jiný sprint

Cíl: projít co nejrychleji a nejlevněji. Na každém účtu **jeden obchod
denně**, tři výhry ≈ pass (nejlepší den drží consistency 50 %).

| | Účet A | Účet B |
|---|---|---|
| Indikátor | **Lucid 8 – RS Sprint** | **Lucid 7 – Eval Sprint (09:31)** |
| Graf | MNQ, 1 min | MNQ, 1 min |
| Kdy | první signál z 10:00 / 11:00 / 13:00 / 14:30 ET (16:00 / 17:00 / 19:00 / 20:30 Praha) | vstup na close svíčky 09:30 ET (15:31 Praha) |
| Směr | long když NQ od otevření o > 0,15 % silnější než ES a nad VWAP; short zrcadlově | podle 50denního trendu (výchozí „Auto“) |
| Nastavení | **Target 0,20 %, Stop 0,30 %**, Max loss 1 900 $ | **Target 0,25 %, Stop 0,40 %**, Max loss 1 900 $, **Volatility gate VYPNOUT** |
| Velikost | indikátor spočítá sám (stop ≈ 1 900 $) | indikátor spočítá sám |

Časy v Praze platí při rozdílu 6 h; mezi koncem letního času v Evropě
(25. 10.) a v USA (1. 11.) je rozdíl 5 h (RS kontroly 15:00 / 16:00 / 18:00 /
19:30, vstup 09:31 ET = 14:31). Lucid 7 s filtrem volatility je pro sprint
mnohem pomalejší (18 / 21 dní místo 11), proto ho na evaluaci vypni.

Očekávání (backtest): první funded účet za **~6,5–7 obchodních dní**
(v každém roce 2018–2025 mezi 5,7 a 8,2 dne, nejhorší 2019),
poplatky ~**300 $** (oba účty dohromady). Jeden účet s RS: ~11 dní, ~190 $.
Rozptyl (`results/eval_spread.txt`, s pojistkou proti hedgingu): medián 6 dní /
270 $; v 8 z 10 případů do 10 dní / 360 $; v 19 z 20 do 15–17 dní /
630–720 $; nejhorší start 2018–2025 trval 31–35 dní a stál 1 440 $.
> **Pozor (25. 10.):** čísla evaluace v této sekci jsou spíš optimistická.
> Lucid ukončí účet, jakmile se zůstatek **během dne** dotkne drawdownu, ne
> až na konci dne. S touto kontrolou projde RS sprint ~34 % evaluací místo
> ~54 % (2022–25), poplatky ~265 $ místo ~165 $, dny skoro stejné
> (`results/paper_barrier.txt`). Po první plné prohře zbývá ~50 $, takže
> účet je prakticky ztracený. Přepočet všech čísel evaluace běží.

Po první prohře se v backtestu pokračuje stejně dál (zbývá ~100 $ do
drawdownu, takže další prohra účet ukončí); po bustu kup novou evaluaci.
Volba po první prohře (`results/sprint_reset.txt`, 2018–21 | 2022–25):
- **pokračovat na stejném účtu** (výchozí): RS 12,7 / 10,0 dne, 213 / 174 $;
- **vzdát a hned koupit novou evaluaci**: RS 10,9 / 8,5 dne, 382 / 298 $.
Vzdání je o ~1,5–2 dny rychlejší, ale o ~125–170 $ dražší (u 09:31 o ~200 $). Stejný sprint kopírovat na víc účtů nemá smysl.

**Dokončovací obchod (nové 23. 10.):** v Lucid 7 i Lucid 8 vyplň „Eval profit so
far“ (zisk evaluace podle včerejšího EOD). Jakmile máš ≥ 2 100 $ (drawdown je
zamčený na +100 $) a do 3 000 $ chybí nejvýš jedna výhra, indikátor sám zmenší
velikost tak, aby výhra právě dotáhla na 3 000 $ (+60 $) a prohra nemohla účet
ukončit. Dva účty pak dojdou k prvnímu funded za 6,9 / 6,3 dne místo 7,6 / 6,9
(v 2010–17 ještě víc). Zisk po každém dni do indikátoru přepiš.

**Pojistka proti hedgingu (Lucid zakazuje opačné pozice i mezi tvými účty):**
když má účet B ještě otevřený obchod z 09:31 a Lucid 8 dá na účtu A signál
OPAČNÝM směrem, signál na A **přeskoč** (ten den už A neobchoduje). Stává se to
~7 % dní (~14× za rok); první funded pak za 7,0 / 6,9 dne místo 6,8 / 6,5
(`results/hedge_check.txt`). Signál stejným směrem nebo po zavření obchodu na B je v pořádku.

**Evaluace a funded účty zároveň** (aktualizováno 24. 10.): zákaz platí i mezi
funded knihou a evaluačním sprintem. Jednoduché pravidlo: **kdo přijde druhý,
vynechá** – vstup, který by šel proti už otevřené pozici na kterémkoli tvém
účtu, nedělej (na funded vynech na všech kopiích). RS sprint (účet A) se
s knihou VWAP pásmo + noise + RS skoro nepotká (~1 % dní); s novou nohou VWAP
10:00 musí A vynechat ~4–7 % dní. Proti 09:31 sprintu (účet B) chce kniha
vstoupit ~12–19 % dní; vynechané obchody stojí řádově stovky dolarů ročně na
funded místo, jen dokud běží evaluace B (`results/cross_hedge.txt`).

## 2. Funded – kniha (3 MNQ na nohu; návrh: bez ORB)

| Noha | Indikátor | Graf | Poznámka |
|---|---|---|---|
| ORB | **Lucid 1 – S1 ORB (nový)** | MNQ **5 min** | trail 20-EMA jen z RTH, re-entry po každém exitu, ne ve středu |
| VWAP pásmo | **Lucid 2 – VWAP Band (nový)** | MNQ **5 min** | průraz VWAP ±0,20 %, SL 25 / TP 100 b., 1× denně, ne ve středu |
| Noise momentum | **Lucid 6 (nový, stop 0,50 %)** | 1 / 5 / 30 min | rozhodnutí jen v :00 a :30 |
| RS noha | Lucid 8 s **Target 1,25 / Stop 1,25, Fixed contracts 3, Volatility gate ZAPNOUT** | MNQ 1 min | přidává ve všech obdobích; nová verze 24. 10. – dřív strop výhry 1 450 $ ořízl nohu na ~2 MNQ a chyběl filtr volatility |
| VWAP 10:00 (jen kandidát) | Lucid 12 s Target 0,30 / Stop 0,50, Fixed contracts 4, Volatility gate ZAPNOUT | MNQ 1 min | 2010–2025 přidávala ve všech 4 obdobích, ale v roce 2026 (leden–červenec) ztrátová → **zatím nepřidávat** |

**Denní rozvrh funded knihy** (Praha; v závorce 26.–30. 10., kdy je rozdíl
jen 5 h, protože USA přechází na zimní čas až 1. 11.):

| ET | Praha | co |
|---|---|---|
| 09:30 | 15:30 (14:30) | otevření; Lucid 2 hlídá průraz VWAP pásma od první 5min svíčky |
| 10:00 | 16:00 (15:00) | první rozhodnutí noise (Lucid 6), první kontrola RS (Lucid 8); (VWAP 10:00 jen kandidát) |
| 10:30–15:30 | každou :00 a :30 | rozhodnutí noise (Lucid 6) |
| 11:00 / 13:00 / 14:30 | 17:00 / 19:00 / 20:30 (16:00 / 18:00 / 19:30) | další kontroly RS (jen první signál dne) |
| 15:55 | 21:55 (20:55) | **vše flat** (nic přes noc) |

- Velikost: **3 MNQ na každou nohu** (ne ladder). Při dnešní ceně NQ
  (~28 500) je to správně; noční „4 MNQ“ platilo pro nižší ceny a je zrušeno.
  Pravidlo: MNQ na nohu ≈ 90 000 / cena NQ, zaokrouhleno dolů.
- **Riziko:** při dnešní ceně NQ dojde k první výplatě jen ~16–22 % funded
  účtů (jeden RS stop 1,25 % při 3 MNQ je ~2 140 $ = víc než drawdown);
  zbytek přijde o drawdown dřív. Vyplácí se to jen proto, že nová evaluace
  sprintem je levná (~150–270 $, ~6–8 dní). Počítej s ~8–10 funded účty na
  jedno funded místo za 2 roky.
- Denní stop nepoužívej: s otevřenými pozicemi v simulaci výsledek zhoršuje ve všech obdobích (−600 $ i −1 500 $; `results/daystop_v2.txt`).
- Očekávání (kniha bez ORB, 3 MNQ, opravený model s otevřenými pozicemi,
  vše přepočteno na dnešní cenu NQ, evaluace odečtené; `results/size_today.txt`):
  ~33 000 / 36 000 $ na funded místo za 24 měsíců (2018–21 / 2022–25),
  ~23 000 / 25 500 $ v klidnějších letech 2010–13 / 2014–17; 1 z 10 míst
  pod ~6 000–13 000 $. Rok 2026 (leden–červenec, nezávislý test):
  kniha +8 700 $ při 3 MNQ.
  V klidném trhu může být méně. Víc peněz = víc účtů se stejnou knihou (kopie).
- **Pravidlo výplaty:** v každém výplatním cyklu potřebuješ 5 dní se ziskem
  aspoň 150 $ (dny nemusí jít po sobě, po výplatě se počítají znovu). Výplatu
  si řekni při +4 000 $ (vybereš 2 000 $, dostaneš 1 800 $); zisk nad 4 000 $
  nech na účtu. Dřívější ani pozdější výplata nevychází lépe
  (`results/payout_policy.txt`).
- Filtr volatility v indikátorech nech zapnutý (20denní volatilita NQ < 30 %).

## 3. Čeká na tvoje rozhodnutí

- **Funded kniha bez ORB (Lucid 1)** (denní směna 23. 10., FINAL_PLAN nahoře):
  s přísnou kontrolou drawdownu (i otevřené pozice) je kniha s ORB horší ve
  všech čtyřech obdobích i v roce 2026 (−3,90 $ na MNQ a obchod; první
  výplata 17 z 85 startů místo 28) a k první výplatě dojde méně účtů; ORB
  nemá edge ani v nezávislém období 2010–2017. Prakticky: Lucid 1 nepoužívat.

- ~~Funded 4 MNQ na nohu~~ – zrušeno 24. 10.: při dnešní ceně NQ (~28 500)
  je správně 3 MNQ (FINAL_PLAN nahoře).
- Volitelně (malé): open drive (Lucid 10, 5min graf) jako čtvrtá noha.

- Overnight long (Lucid 9) vyřazen: Lucid Flex nedovoluje držet přes noc.
  Všechny strategie v plánu jsou do 15:55 ET flat.
- Aukce dluhopisů: blokované (chybí kalendář aukcí).

## 4. Kde co je

- Indikátory: `strategy/tradingview/lucid_*.pine`
- Plán s čísly: `strategy/tradingview/FINAL_PLAN.md`
- Ranní report: `brain/reports/2026-10-23.md`
- Panel: https://claude.ai/artifact/7aNv2n8i8JqZZg4dp25DUK
