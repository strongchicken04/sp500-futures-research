# Preregistrace: jednorázové odemčení OOS 2018-01 – 2020-05 (lab)

**Datum preregistrace:** 2026-07-31 (committed PŘED spuštěním OOS testu)

## Motivace

Rozšíření portfolia o nekorelovanou nohu k jádru (VWAP pásmo+gaty, intradenní
trend). Osa „jiné trhy" vyřešena (ES: edge přenosný, korelace 0,5, přínos ~0).
Zbývá osa „jiný horizont": overnight risk premium a gap mean-reversion.

## Kandidáti (zmražené konfigurace z labu, IS 2005–2017, beze změn)

1. **s16 Overnight hold** — nákup close 16:00 → prodej open 9:30, každý den,
   bez stopu. IS: Sharpe 0,43, CAGR 4,1 %, MDD −26,2 %, 258 obchodů/rok.
   Hypotéza: overnight riziková prémie indexů (akademicky doložená).
2. **s14 Gap fade** — jen dny |gap| > 20 bps, vstup proti gapu na openu,
   cíl = včerejší close (zaplnění), stop 40 bps, exit EOD. IS: Sharpe 0,37,
   CAGR 2,2 %, MDD −13,2 %, 162 obchodů/rok.
   Hypotéza: overnight přestřelení bez objemu koriguje RTH likvidita.

Žádné jiné strategie z labu se v tomto odemčení netestují. Parametry se
nemění. Náklady 1 bp/side (konvence labu).

## OOS okno

2018-01-01 až 2020-05-31 (konec lokálních dat) — drženo zamčené od vzniku
labu, toto je jeho PRVNÍ a JEDINÉ použití.

## Kritéria PASS (stanovená před pohledem na data)

Strategie projde, pokud na OOS současně:
1. **Sharpe ≥ 0,30**
2. **průměr na obchod > 0 bps net**

Sekundární (pro portfoliovou hodnotu, nerozhoduje o PASS/FAIL):
3. korelace denních výnosů s jádrem (VWAP pásmo+gaty, reálné NQ) < 0,4

## Závazky

- Jeden běh, žádné úpravy parametrů po zhlédnutí výsledků.
- FAIL → rodina uzavřena (stejně jako Holmberg).
- PASS → následuje (a) optimalizační mašina na plných datech s mřížkou
  definovanou před spuštěním, (b) validace na reálném NQ přes QC exporter,
  (c) teprve pak úvaha o zařazení. OOS okno se už nikdy znovu nepoužije.


---

# VÝSLEDEK (doplněno po jednorázovém běhu, tentýž den)

| kritérium | s16 Overnight | s14 Gap fade |
|---|---|---|
| OOS Sharpe ≥ 0,30 | **0,20** ✗ | **−0,36** ✗ |
| avg net > 0 bps | +1,39 ✓ | −1,43 ✗ |
| **PASS** | **NE** | **NE** |

Detaily: s16 roky 2018 +7,3 % / 2019 +6,6 % / 2020(do 05) −8,3 %, MDD −28,8 %
(COVID); s14 2018 −2,8 % / 2019 −10,1 % / 2020 +6,5 %, MDD −18,8 %.

**Rodina overnight/gap-fade uzavřena dle závazku.** COVID v OOS okně není
polehčující okolnost — okno bylo definováno včetně něj a overnight prémie
se platí právě expozicí na noční chvosty. OOS okno 2018–2020/05 je tímto
SPOTŘEBOVÁNO a nesmí být použito pro žádný další výběr.
