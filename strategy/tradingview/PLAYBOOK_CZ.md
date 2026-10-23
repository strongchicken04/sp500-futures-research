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

**Evaluace a funded účty zároveň** (noc 23./24. 10.): zákaz platí i mezi
funded knihou a evaluačním sprintem. Pravidlo: **funded kniha nevstupuje
proti otevřenému sprintu na evaluaci** (vstup vynech, na všech kopiích).
RS sprint (účet A) se s knihou skoro nepotká (~1 % dní). Proti 09:31 sprintu
(účet B) chce kniha vstoupit ~12–13 % dní; ty vynechané obchody jsou spíš
ziskové (+11 / +18 $ na MNQ), takže to stojí řádově stovky dolarů ročně na
funded místo – jen v době, kdy běží evaluace B (`results/cross_hedge.txt`).

## 2. Funded – kniha, 3 MNQ na každou nohu

| Noha | Indikátor | Graf | Poznámka |
|---|---|---|---|
| ORB | **Lucid 1 – S1 ORB (nový)** | MNQ **5 min** | trail 20-EMA jen z RTH, re-entry po každém exitu, ne ve středu |
| VWAP pásmo | **Lucid 2 – VWAP Band (nový)** | MNQ **5 min** | průraz VWAP ±0,20 %, SL 25 / TP 100 b., 1× denně, ne ve středu |
| Noise momentum | **Lucid 6 (nový, stop 0,50 %)** | 1 / 5 / 30 min | rozhodnutí jen v :00 a :30 |
| RS noha (kandidát) | Lucid 8 s **Target 1,25 / Stop 1,25** | MNQ 1 min | přidává hlavně v letech 2018–21 |

- Velikost: **3 MNQ na každou nohu** (ne ladder); **doporučení z noci
  23./24. 10.: 4 MNQ na nohu** (rozhoduješ ty, FINAL_PLAN nahoře).
- **Riziko:** k první výplatě dojde ~40 % funded účtů (při 4 MNQ ~37 %),
  zbytek přijde o drawdown dřív. Vyplácí se to jen proto, že nová evaluace
  sprintem je levná (~180–270 $, ~7–11 dní). Počítej s tím.
- Denní stop nepoužívej: s otevřenými pozicemi v simulaci výsledek zhoršuje ve všech obdobích (−600 $ i −1 500 $; `results/daystop_v2.txt`).
- Očekávání (kniha bez ORB, opravený model `scripts/funded_model.py`
  a `mtm_check.py`, 24 měsíců, evaluace odečtené, 2018–21 / 2022–25):
  při 3 MNQ ~750–810 / 1 200–1 330 $ měsíčně na funded místo, při 4 MNQ
  ~900–1 000 / 1 400–1 550 $ (nižší číslo = přísná kontrola drawdownu
  i s otevřenými pozicemi).
  V klidném trhu může být méně. Víc peněz = víc účtů se stejnou knihou (kopie).
- **Pravidlo výplaty:** v každém výplatním cyklu potřebuješ 5 dní se ziskem
  aspoň 150 $ (dny nemusí jít po sobě, po výplatě se počítají znovu). Výplatu
  si řekni při +4 000 $ (vybereš 2 000 $, dostaneš 1 800 $); zisk nad 4 000 $
  nech na účtu. Dřívější ani pozdější výplata nevychází lépe
  (`results/payout_policy.txt`).
- Filtr volatility v indikátorech nech zapnutý (20denní volatilita NQ < 30 %).

## 3. Čeká na tvoje rozhodnutí

- **Funded kniha bez ORB (Lucid 1)** (denní směna 23. 10., FINAL_PLAN nahoře):
  první výplata u 40 / 41 % funded účtů místo 34 / 32 % (opravený model),
  v penězích zhruba neutrální; ORB nemá edge ani v nezávislém období
  2010–2017. Prakticky: Lucid 1 nepoužívat, zbytek beze změny.

- **Funded 4 MNQ na nohu místo 3** (noc 23./24. 10.): +4 900 / +5 000 $ na
  funded místo za 24 měsíců, lepší i v 2010–17 přepočteném na dnešní cenu
  (+3 200 / +4 000 $; s přísnou kontrolou drawdownu i s otevřenými
  pozicemi +3 500 / +4 300 $ a +2 600 / +2 500 $); první výplata o 2–5 bodů
  méně často.
- Volitelně: open drive (Lucid 10, 5min graf) jako čtvrtá noha, 4 MNQ –
  s přísnou kontrolou drawdownu přidá jen ~+600 $ ve třech obdobích ze čtyř.

- Overnight long (Lucid 9) vyřazen: Lucid Flex nedovoluje držet přes noc.
  Všechny strategie v plánu jsou do 15:55 ET flat.
- Aukce dluhopisů: blokované (chybí kalendář aukcí).

## 4. Kde co je

- Indikátory: `strategy/tradingview/lucid_*.pine`
- Plán s čísly: `strategy/tradingview/FINAL_PLAN.md`
- Ranní report: `brain/reports/2026-10-23.md`
- Panel: https://claude.ai/artifact/7aNv2n8i8JqZZg4dp25DUK
