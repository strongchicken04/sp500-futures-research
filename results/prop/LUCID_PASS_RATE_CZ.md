# Pass rate na LucidFlex 50K — Monte Carlo finální VWAP strategie

**Pravidla (ověřeno 8/2026):** target +$3 000; max loss $2 000 **EOD trailing**
(floor = EOD peak − $2 000, zamyká se na startovní hodnotě $50 000); žádný
denní limit; žádné minimum dní; konzistence: nejlepší den ≤ 50 % zisku při
žádosti o pass; max 4 minis / 40 micros. Naše strategie je 1 obchod/den,
flat EOD → EOD trailing měří přesně naši denní P&L řadu (simulace exaktní).

**Metoda:** block bootstrap (bloky 10 dní) z reálné distribuce denních výnosů
finální konfigurace na NQ (913 obchodů 2018–2025, gaty aktivní, 2 bps
náklady, SL 150 b cap ≈ −60 bps/den na dnešní ceně). 20 000 cest / velikost,
NQ ≈ 25 600.

## Výsledky

| velikost | pass | breach | medián dní | p90 dní |
|---|---|---|---|---|
| **1 MNQ** | **69 %** | 31 % | 95 | 197 |
| 2 MNQ | 48 % | 52 % | 43 | 110 |
| 3 MNQ | 39 % | 61 % | 34 | 95 |
| 5 MNQ | 30 % | 70 % | 28 | 88 |
| 10 MNQ (1 NQ) | 20 % | 80 % | 24 | 84 |

Robustnost: distribuce 2022–2025 dává tatáž čísla (±1 p.b.).

## Interpretace

- Challenge = závod target (+$3 000) vs trailing floor (−$2 000 od peaku).
  Velikost pozice škáluje oba konce, ale floor je blíž a trailing ho táhne
  za peakem → **pass rate monotónně klesá s velikostí.**
- Konzistenční pravidlo prodlužuje pass na malé velikosti (velký den > 50 %
  zisku → nutný další grind); v simulaci zahrnuto.
- Očekávané pokusy: 1 micro ≈ 1,4; 2 micros ≈ 2,1; 1 mini ≈ 5.
- Škálování s cenou NQ: drž `micros × cena ≤ ~26 000` (dolarová hodnota
  1 bps určuje efektivní velikost buferu).

## Doporučení

1. **Eval jet na 1 MNQ** (69 %), případně 2 MNQ jako časově efektivní
   kompromis při levných resetech. Mini kontrakty na 50k NEpoužívat.
2. Platí předpoklad trvání edge 2018–2025 → nejdřív dokončit validační
   týden na Sim101, pak challenge.
3. Po fundingu (bez konzistence) přehodnotit sizing zvlášť — eval sizing
   a funded sizing jsou dva různé optimalizační problémy.

Zdroje pravidel: phidiaspropfirm.com/education/lucidflex-review,
proptradingvibes.com/blog/lucid-trading-lucidflex-account,
lunefi.com/blog/lucid-trading-complete-guide-to-rules-and-payouts


## Dodatek: TP 100 / SL 75 verze — vyšší pass rate na každé velikosti

Rekonstrukce bracketu z MAE záznamů (TP100 exporter; konzervativně: TP i SL
v téže minutě = SL). 942 obchodů 2018–2025, win 42 %, avg +6,65 b net,
SL rate 9,8 %, TP rate 28,6 %.

| velikost | pásmová | TP/SL | medián dní (TP/SL) |
|---|---|---|---|
| 1 MNQ | 69 % | **87 %** | 369 |
| 2 MNQ | 48 % | **66 %** | 131 |
| 3 MNQ | 39 % | **55 %** | 65 |
| 5 MNQ | 30 % | **47 %** | 27 |
| 10 MNQ | 21 % | **39 %** | 13 |

Éra 2022–2025: stejná čísla (−2 p.b.). Mechanismus: EOD trailing trestá
volatilitu, ne nízký výnos — bracket ořezává oba chvosty → hladší schody
→ floor se posouvá bezpečněji. Doporučení: **eval s TP/SL verzí (2–3 MNQ)**,
po fundingu zvážit přepnutí na pásmovou (vyšší dlouhodobý výnos). Výhrada:
fixní body → éra-závislost; kontrola na 2022–2025 konzistentní.
Graf: lucid_pass_rate_comparison.png.
