# NQVwapTrendSC — NinjaTrader 8 automatizace (Lucid Trading)

NinjaScript port finální konfigurace **VWAP Trend** (pásmo 20 bps + gap gate 25 +
trend gate 60, 1 obchod/den, exit opačné pásmo / EOD, fixní SL 150 b jako
katastrofická pojistka — resting stop u brokera, chrání i při výpadku spojení).

## Instalace

1. NinjaTrader 8 → **New → NinjaScript Editor → Strategies** → pravý klik → New
   Strategy… zruš průvodce, vlož obsah `NQVwapTrendSC.cs`, **Compile** (F5).
   (Alternativně soubor nakopíruj do `Documents\NinjaTrader 8\bin\Custom\Strategies\`.)
2. Graf: **NQ nebo MNQ, 1 minuta**, Properties →
   **Trading hours = „US Equities RTH"** (09:30–16:00 ET) — nutné, session
   logika (gaty, VWAP reset, EOD) se řídí session šablonou,
   **Days to load ≥ 450** — brány si při zapnutí samy dopočítají historii
   (plná věrnost od ~250 RTH dní).
3. Pravý klik na graf → **Strategies…** → NQVwapTrendSC → účet:
   nejdřív **Sim101**, potom Lucid (Rithmic) připojení. Enable.

## Před ostrým nasazením (nepřeskakovat)

- **Týden na Sim/Market Replay** a porovnat signály s TradingView v7 indikátorem
  (BUY/SELL/EXIT/NO TRADE DAY se musí shodovat den po dni).
- Zkontrolovat v Strategies tabu, že po načtení historie panel hlásí správné
  „NO TRADE DAY" dny (Output okno tiskne verdikt bran každé ráno).
- Lucid: automatizace je povolena (HFT ne — tahle strategie je 1 obchod/den,
  hluboko mimo definici). Přesto si nech od supportu písemně potvrdit
  unattended provoz. Trailing drawdown challenge řiď velikostí pozice.

## Věrnost vs výzkumný backtest (drobné, dokumentované rozdíly)

| věc | backtest | NinjaTrader |
|---|---|---|
| vstup | close signální svíčky | market po close = fill na dalším ticku (≈ open další svíčky, jako TV) |
| band exit | close svíčky | market po close (1 tick skluz nastaven) |
| EOD | close 15:59–16:00 svíčky | **15:59** (o minutu dřív — flat před 16:00, bezpečnější pro prop) |
| SL 150 b | přesný fill | resting stop-market u brokera (reálný skluz při gapu) |

Sizing: fixní počet kontraktů (input). VT15 vol-targeting řeš úpravou počtu
kontraktů na úrovni účtu — do strategie záměrně nezakódován.
