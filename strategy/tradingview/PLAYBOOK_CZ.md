# Playbook – Lucid Flex 50K (stav 23. 10. 2026)

Všechno níže je návrh z backtestů 2018–2025 (laděno na 2018–21, ověřeno na
2022–25). Výsledky v minulosti nezaručují budoucí. Rozhoduješ ty.

## 0. Nejdřív: nahraj nové verze indikátorů

Lucid 1, 2, 6 a 7 byly 23. 10. upravené (shoda s backtestem, denní hodnoty
z posledního dokončeného dne). Lucid 8 beze změny, Lucid 9 je nový.

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
Po první prohře se v backtestu pokračuje stejně dál (zbývá ~100 $ do
drawdownu, takže další prohra účet ukončí); po bustu kup novou evaluaci.
Volba po první prohře (`results/sprint_reset.txt`, 2018–21 | 2022–25):
- **pokračovat na stejném účtu** (výchozí): RS 12,7 / 10,0 dne, 213 / 174 $;
- **vzdát a hned koupit novou evaluaci**: RS 10,9 / 8,5 dne, 382 / 298 $.
Vzdání je o ~1,5–2 dny rychlejší, ale o ~125–170 $ dražší (u 09:31 o ~200 $). Stejný sprint kopírovat na víc účtů nemá smysl.

## 2. Funded – kniha, 3 MNQ na každou nohu

| Noha | Indikátor | Graf | Poznámka |
|---|---|---|---|
| ORB | **Lucid 1 – S1 ORB (nový)** | MNQ **5 min** | trail 20-EMA jen z RTH, re-entry po každém exitu, ne ve středu |
| VWAP pásmo | **Lucid 2 – VWAP Band (nový)** | MNQ **5 min** | průraz VWAP ±0,20 %, SL 25 / TP 100 b., 1× denně, ne ve středu |
| Noise momentum | **Lucid 6 (nový, stop 0,50 %)** | 1 / 5 / 30 min | rozhodnutí jen v :00 a :30 |
| RS noha (kandidát) | Lucid 8 s **Target 1,25 / Stop 1,25** | MNQ 1 min | přidává hlavně v letech 2018–21 |

- Velikost: **3 MNQ na každou nohu** (ne ladder). Simulace s časy obchodů:
  ~12 100 / 29 100 $ na účet za 24 měsíců (2018–21 | 2022–25), ladder
  400/500 jen 2 300 / 20 500 $.
- **Riziko:** k první výplatě dojde ~40–51 % funded účtů, zbytek přijde
  o drawdown dřív. Vyplácí se to jen proto, že nová evaluace sprintem je
  levná (~180 $, ~11 dní). Počítej s tím.
- Denní stop výsledek nezlepšuje; jako pojistka −600 $ nevadí.
- Filtr volatility v indikátorech nech zapnutý (20denní volatilita NQ < 30 %).

## 3. Čeká na tvoje rozhodnutí

- **Overnight long po 3+ červených dnech** (Lucid 9): +28,6 / +19,0 bp za
  noc, kladné všech 8 let, ~20× ročně. Jen pokud Lucid dovoluje držet přes noc.
- Aukce dluhopisů: blokované (chybí kalendář aukcí).

## 4. Kde co je

- Indikátory: `strategy/tradingview/lucid_*.pine`
- Plán s čísly: `strategy/tradingview/FINAL_PLAN.md`
- Ranní report: `brain/reports/2026-10-23.md`
- Panel: https://claude.ai/artifact/7aNv2n8i8JqZZg4dp25DUK
