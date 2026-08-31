# Preregistrace: ORB fade test

**Datum preregistrace:** 2026-08-31 (commit PŘED spuštěním backtestu)

## Motivace

Uživatelův nápad. ORB scalper (breakout ve směru průrazu) na NQ 2018–2025
nemá hrubou hranu, ale poslední 3 roky rostl. Hypotéza: rodina obchodů je
strukturálně "vs breakout" a v trendovém režimu prohrává, v choppy zisková.
Fade verze (proti breakoutu) by měla mít zrcadlový profil.

## Pravidla (zamražená)

- Range = high/low 9:30–9:45 ET (RTH), na 1min chartu
- Signál: **1min close VENKU** za range, následně **1min close ZPĚT UVNITŘ**
- Vstup: close reclaim svíčky
- Směr: **proti** breakoutu (up-break → short, down-break → long)
- TP: entry ± 0,5 × R (50 % velikosti range, ve směru fade)
- SL: entry ∓ 0,5 × R (**1:1 RR**)
- Max 1 fade na stranu/den, EOD 15:59 flat, vstupy do 15:00
- Close-based rozhodnutí, žádné knotové filly
- Náklady 0,75 pts/obchod (komise + 1 tick skluz)
- Data: reálné NQ 2018–2025 (QC)

## Pass kritéria (fixovaná před testem)

Rodina PROJDE, pokud OBĚ:
1. **avg bps/obchod > 0** net přes celých 8 let
2. **z > 1,0**

Sekundární (kontext, nerozhoduje o PASS/FAIL):
- Ne víc než 2 z 8 let horších než −2 bps
- Symetrie long/short (obě strany kladné)

## Závazky

- **Jeden běh, jedna konfigurace.** Žádné "co kdybychom místo 50 % dali 40 %"
  po zhlédnutí výsledků. Ladění mřížky = fit.
- FAIL → rodina uzavřena, nedělá se regime switcher.
- PASS → následuje:
  (a) test závislosti výnosu na denním režimu (VIX, gap size, otevírací
      pohyb) — jen jako feature study, ne jako selekce parametrů
  (b) plný běh optimalizační mašinou (WF + PBO + noise floor)
  (c) teprve pak úvaha o zařazení a diskuze o regime switcheru

---

# VÝSLEDEK (doplněno po jednorázovém běhu)

**Data:** reálné NQ 2018–2025 (QC), projekt `NQ_ORB_Fade_TEST` (35896166),
backtest `cf0c1f29708feb24a76f0902f57aa9be`. **2 657 fade obchodů**
(~332/rok, long 1 310 / short 1 347).

## Souhrn

| metrika | hodnota |
|---|---|
| win rate | 50,7 % |
| exit mix | TP 49,7 % · SL 48,5 % · EOD 1,8 % |
| **avg net / obchod** | **+0,07 b · +0,04 bps** |
| **z-stat** | **+0,06** |
| total net (8 let) | −176 pts |

## Pass kritéria

| kritérium | práh | výsledek | verdikt |
|---|---|---|---|
| avg bps > 0 | > 0 | **+0,04** | ✓ formálně splněno |
| z > 1,0 | > 1,0 | **+0,06** | ✗ **FAIL** |

**Verdikt: FAIL.** Průměr sice těsně kladný v bps (nula v bodech, protože
diff vzniká z era-renormalizace), ale z-statistika je 0,06 — čistá mince.
Náhoda by dala kladné číslo v ~50 % běhů.

## Po letech (bps net)

2018 +0,15 · 2019 −0,93 · 2020 −0,59 · **2021 +1,58** · **2022 +1,81** ·
2023 +0,27 · 2024 −0,94 · **2025 −1,02**

Střední třetina (2021–2023) kladná, okraje záporné. Poslední rok (2025)
prohrává jako první — přesně opačný profil než ORB scalper (poslední léta
kladná). To zapadá do teze uživatele (**fade a scalper jsou zrcadlové**),
ale ani jedna strana samostatně nemá edge.

## Long vs short

- **long fade** (buy after down-break reclaim): n=1 310, +0,32 bps, z=+0,34
- **short fade** (sell after up-break reclaim): n=1 347, −0,23 bps, z=−0,25

Šum, žádná strukturální asymetrie.

## Závěr dle preregistrace

Rodina fade uzavřena. Regime switcher se nestaví — přesně dle závazku:
"Fail → rodina uzavřena, nedělá se regime switcher." Poznatek zapsán:
fade a breakout jsou zrcadlové, což vylučuje, aby ORB v jakékoli podobě
byl standalone edge na NQ 2018–2025.
