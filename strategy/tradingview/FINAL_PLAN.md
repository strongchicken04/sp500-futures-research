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
