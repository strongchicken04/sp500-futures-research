# Port finální VWAP konfigurace na ES — strukturální OOS test

**Setup:** pravidla 1:1 z NQ verze (pásmo 20 bps, gap gate 25, trend gate 60,
vstup od 9:31, 1. obchod dne, exit opačné pásmo / EOD), žádný refit. Reálné ES
2010–2025 (QC), 1 743 obchodů, náklady 2 bps/obchod. Projekt `ES_VWAP_Trend`
(34688230), backtest `cefa9ce0130ebaf98a179e49f9825426`.

## Výsledky

| éra | n | win % | avg net bps | Sharpe* |
|---|---|---|---|---|
| 2010–2017 | 872 | 40,0 | **+0,2** | 0,03 |
| **2018–2025** | 871 | 42,9 | **+4,1** | **0,74–0,99** |
| NQ 2018–2025 (ref.) | 913 | 38,7 | +10 | 1,22–1,67 |

*rozsah podle metodiky paddingu neobchodních dnů; relativní srovnání konzistentní.

Nejlepší roky ES: 2018 (+10,3), 2022 (+13,9), 2023 (+7,1) — tytéž jako NQ.
Long +1,4 / short +2,7 bps. Band exity −29 bps, EOD exity +33 bps (drží
vítěze do konce dne — stejný mechanismus jako na NQ).

## Korelace a portfolio

- korelace denních výnosů ES × NQ verze: **0,50** (jen společné obchodní dny 0,65)
- tangency váha ES: **~12 %**; přírůstek kombinovaného Sharpe: **+0,01**
- 50/50 by Sharpe snížilo (1,58 vs 1,67 samotné NQ)

## Závěry

1. **Edge strukturálně přenosný** — kladný na ES se zmraženými parametry,
   stejné dobré roky. Intradenní VWAP trend není NQ kuriozita.
2. **Ale ~60 % slabší a korelace 0,5** — oba systémy žijí ze stejných
   trendových dnů. Chudá diverzifikace: portfolio se nezlepší.
3. **ES 2010–2017 = nula** — edge na obou trzích žije až v éře 2018+.
   Připomínka era-závislosti; VT15 a risk management nejsou volitelné.

**Doporučení:** ES nepřidávat jako rovnocennou nohu; nanejvýš ~10–15% MES
satelit jako operační pojistka / early-warning na slábnutí edge. Skutečnou
diverzifikaci hledat na jiném horizontu (overnight / gap-fade rodina z labu
se zamčeným OOS 2018–2020/05).
