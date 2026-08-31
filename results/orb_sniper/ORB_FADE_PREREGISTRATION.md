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
