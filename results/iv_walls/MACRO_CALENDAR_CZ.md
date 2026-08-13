# Makro kalendář (FOMC) jako filtr — verdikt: SMĚROVĚ ANO, DŮKAZNĚ NE

**Data:** FOMC rozhodovací dny 2018–2025 (64 dat, verifikace: range na FOMC
1,09× vyšší, 63/64 v obchodních dnech). Denní P&L finální VWAP strategie.

| typ dne | n obchodů | avg bps | win % |
|---|---|---|---|
| FOMC | 24 | **−4,5** | **21 %** |
| den před | 31 | +6,2 | 39 % |
| den po | 39 | +16,5 | 44 % |
| běžný | 811 | +8,3 | 39 % |

z(FOMC vs běžný): −1,1 (avg) až −1,8 (win rate) → pod laťkou (n=24).
Gaty už FOMC dny částečně samy blokují (obchodují 38 % vs 46 % běžných).

**Závěr:** žádný průkazný efekt; "skip FOMC" lze přijmout jen jako OPERAČNÍ
risk pravidlo z priorů (14:00 oznámení popírá trend-day premisu; cena ~3
obchody/rok), ne jako datově doložené vylepšení — do backtestů se zpětně
nemontuje. CPI netestováno (kalendář release dat nedostupný přes egress;
doplnit při dodání seznamu).

Multiple-testing počítadlo regime testů na stejném P&L: gaty (produkce),
walls-pos (hypotéza v zásobě), VIX TS (mrtvá), FOMC (operační volba).
