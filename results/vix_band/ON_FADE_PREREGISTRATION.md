# Preregistrace: ON Level Fade (finalní konfigurace)

**Datum preregistrace:** 2026-09-02 (commit PŘED live/paper deploymentem)

## Motivace

Silné empirické zjištění napříč NQ 2018-2025: fade prvního dotyku
overnight extrémů (ONH short, ONL long) a fade prvního průchodu
midpointem (ve směru k RTH openu) má strukturální edge. Signál drží
in-sample i out-of-sample, přes VIX kvintily, po letech, na bracket
plateau. Prošel Bonferroni-korekci přes ~108 konfigurací testovaných
v této session.

Tato preregistrace fixuje **jedinou konfiguraci** pro live/paper
validaci. Žádné další ladění po zveřejnění výsledků.

## Pravidla (zamražená, žádné tweakování)

### Overnight session

- **ON okno:** 18:00 ET předchozího dne → 9:30 ET dnes (Globex reopen
  po CME maintenance breaku 17:00-18:00)
- **ONH** = high overnight session
- **ONL** = low overnight session
- **ONM** = (ONH + ONL) / 2

### Vstupní signály (během RTH 9:31-15:59 ET, close-based 1min)

1. **ONH touch → SHORT** at ONH
   - Trigger: první 1min bar kde `bar.High >= ONH`
   - Entry: ONH (limit sell na hladině)
   - TP: ONH − 15 pts
   - SL: ONH + 15 pts

2. **ONL touch → LONG** at ONL
   - Trigger: první 1min bar kde `bar.Low <= ONL`
   - Entry: ONL (limit buy na hladině)
   - TP: ONL + 15 pts
   - SL: ONL − 15 pts

3. **ONM cross → fade k RTH open** at ONM
   - Trigger: první 1min bar obsahující ONM (`high >= ONM AND low <= ONM`)
   - Směr fixován v 9:30 podle otevírací pozice:
     - RTH open > ONM → **LONG** at ONM, TP=ONM+15, SL=ONM−15
     - RTH open < ONM → **SHORT** at ONM, TP=ONM−15, SL=ONM+15
     - RTH open == ONM → skip
   - Entry: ONM (limit ve fade směru)

### Filtry (must-pass)

- **ONrange >= 65 pts** — když je overnight range menší, žádné obchody
  (identifikováno v regime analysis: Q1 range width má z=−0,78)

### Exit

- Vždy 1:1 bracket (B = 15 pts) — TP hit nebo SL hit → exit
- **Konvence:** pokud v jedné 1min svíčce padne TP i SL → počítá se SL
  (konzervativní same-bar rule)
- **EOD safety:** 15:59 ET flat pokud ani TP ani SL nepadne

### Provozní

- Max **1 trade na level na den** (celkem max 3 pozice simultánně)
- Poslední vstup 15:00 ET (neotevírat trade pokud zbývá < 60 min do close)
- Náklady: 0,75 pts/trade (komise + 1 tick skluz)

## Pass kritéria pro paper/live validaci (fix PŘED běh)

Konfigurace **PROJDE**, pokud přes minimum 60 obchodních dní:

1. **Combined avg pts/trade > 0** (net po nákladech)
2. **Combined z-stat > 1,5** (méně přísné než backtest z=+10,87
   protože paper má menší sample; ale nulu vyloučit)
3. **Ne víc než 2 sub-strategie ze 3 (ONH/ONL/ONM) záporné** — asymetrie
   OK (očekáváme silnější ONL a ONM než ONH kvůli NQ drift bias)

Sekundární (nerozhodují o PASS/FAIL, jen kontextové):

- Backtest ratio: očekáváme ~0,7-1,0× backtestového výsledku
  (backtest avg +3,26 bps s filtrem, live avg > +2 bps je konzistentní)
- Win rate cca 58-63 % pro combined
- Bez pozice = simulační bias; kontrolovat že fill % ≈ backtest expect

## Závazky

- **Jedna konfigurace, jeden live běh.** B=15, filter range>=65, tak
  jak popsáno. Žádné "co kdybychom místo 15 dali 12" po zhlédnutí
  paper výsledků. Ladění mřížky = fit.
- **FAIL → rodina uzavřena.** Žádné pokusy o záchranu přes regime
  switcher, přidání dalších filterů, změnu ON okna, atd.
- **PASS → přechod na real money.** Malá size (1 MNQ per signal na
  začátek), postupné škálování dle equity performance.
- **Multiple-testing paper trail:** ~108 konfigurací testováno napříč
  session (VIX band, ORB variants, ON strategie, HAR-RV, fade family).
  Bonferroni z threshold = 3,50 pro α=0,05. Backtest hodnota z=+10,87
  prošla s velkou rezervou; paper cíl z > 1,5 je dostatečně nad
  Bonferroni-per-single-live-test (~1,96).
- **Portfolio integration:** ON fade je nekorelovaný s existujícím
  VWAP TP100/SL75 (ρ=−0,107) a HAR-RV breakout (ρ=−0,014). Jde
  paralelně, ne switch/replace.

## Historická evidence (co už máme)

**Full 8-year NQ 2018-2025, honest intraday first-touch TP/SL (žádný
same-day-both-hit artefakt):**

| konfigurace | n | avg pts | z | win % | total |
|---|---:|---:|---:|---:|---:|
| Combined (no filter) | 4 004 | +2,50 | +10,87 | 60,7 % | +10 012 |
| **Combined + range≥65** | **3 163** | **+3,26** | **+12,71** | **63,3 %** | **+10 319** |
| ONH short | 1 308 | +1,20 | +2,95 | 56,3 % | +1 570 |
| ONL long | 1 155 | +3,35 | +7,90 | 63,5 % | +3 865 |
| ONM fade-to-open | 1 541 | +2,97 | +8,07 | 62,2 % | +4 577 |

**OOS split (bez preregistrace, jako pre-check):**

- In-sample 2018-2022: z=+6,00
- **Out-of-sample 2023-2025: z=+10,11** (silnější než IS — velmi
  vzácný pozitivní signál)

**Bracket plateau (B=12–17 všechny z > 9,5)** — B=15 uprostřed
plateau, ne spike. Robustnost potvrzena.

**Correlation s existujícím portfoliem:**

- vs VWAP TP100/SL75: ρ=−0,107 (diverzifikace ✓)
- vs HAR-RV breakout: ρ=−0,014 (diverzifikace ✓)

**Portfolio (VWAP + ON fade + HAR-RV):**

- Total +33 584 pts, MDD −1 529 pts, **Return/MDD = 22:1**
- Portfolio Sharpe 1,97 (equal weight); ON fade solo Sharpe 3,65

## Odkazy na kód a data

- Strategie: `strategy/quantconnect/on_level_fade_first_hit.py`
- Bracket grid: `strategy/quantconnect/on_fade_bracket_grid.py`
- TradingView indikátor: `strategy/tradingview/nq_on_fade.pine`
- Data: `results/vix_band/on_fade_firsthit.json` (2 064 dní)
- Bracket data: `results/vix_band/on_fade_bracket_grid.json`
- Portfolio dashboard: `results/vix_band/portfolio_dashboard.png`
- Backtest: QC project 36011421, backtest `8176b978b35fca6201f3b408fc052f03`

---

**Připraveno k paper trading.** Další commit po tomto = paper start.
