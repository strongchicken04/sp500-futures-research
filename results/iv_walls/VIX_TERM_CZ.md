# VIX term structure jako regime feature — verdikt: NULA, uzavřeno

**Data:** 2 009 dní 2018–2025 (QC): VIX spot + VX1/VX2 futures v 9:35 ET,
kontango slope normalizované na 30 dní, basis VX1/VIX. Projekt `NQ_VIX_Term`
(35149967). Join s denním P&L finální VWAP strategie (911 obchodních dní).

| feature | tercily avg bps | hi−lo | z |
|---|---|---|---|
| VIX úroveň | +7,0 / +11,7 / +5,7 | −1,3 | −0,24 |
| kontango | +8,2 / +10,5 / +5,7 | −2,5 | −0,44 |
| basis | +5,7 / +12,9 / +5,8 | +0,1 | +0,02 |
| backwardace vs kontango | +8,2 vs +8,1 | — | +0,02 |

**Závěr:** žádný vztah, žádná monotonie. Hlavní důvod: corr(VIX, rvol20)
= +0,78 — volatilitní informace už je v gatech strategie obsažená z vlastních
cen NQ. Term structure nepřidává nic inkrementálního. Rodina uzavřena bez
jediného hraničního nálezu (na rozdíl od IV walls). Čtvrtá regime rodina
testovaná na stejném P&L — multiple-testing počítadlo: gaty (v produkci),
walls pos (hypotéza v zásobě), VIX TS (mrtvá).
