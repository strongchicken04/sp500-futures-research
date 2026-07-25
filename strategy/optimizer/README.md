# Parameter Optimization Machine — charta

*Optimalizátor parametrů, který z principu nemůže vybrat overfit. Postaven na
lekcích z deníku Strong Chicken (plošina > vrchol, noise floor, předregistrace).*

## Proč obyčejná optimalizace = overfitting

Vezmi 288 konfigurací, vyber tu s nejvyšším Sharpe — a máš skoro jistě šum.
Vlastní měření (viz `results/optimizer/`): stejný výběrový proces na **náhodných
datech bez jakéhokoli edge** si „vyrobí" nejlepší IS Sharpe klidně přes 1,0.
Argmax na mřížce je stroj na sebeklam.

## Čtyři obranné vrstvy (zakódované, ne volitelné)

1. **Střed plošiny místo vrcholu.** Každá konfigurace se hodnotí průměrem Sharpe
   celého svého okolí v mřížce (sama + všichni sousedé v každém rozměru).
   Osamělý vrchol stáhnou dolů špatní sousedi; vyhrává jen souvislá plošina.
2. **Walk-forward = poctivé očekávání.** Klouzavě: 4 roky trénink → výběr
   pravidlem plošiny → obchoduj následující rok. Sešité roční OOS segmenty jsou
   *jediné* číslo, které se smí prezentovat jako očekávání. IS číslo je iluze.
3. **PBO (Probability of Backtest Overfitting)** — CSCV metoda (Bailey, López de
   Prado): dny se rozdělí do 12 bloků; pro všech 924 vyvážených půlení se vybere
   IS vítěz a změří jeho pořadí na druhé půlce. PBO = podíl půlení, kde vítěz
   skončil pod mediánem. **PBO ≥ 50 % ⇒ výběr je šum ⇒ REJECT.**
4. **Noise floor.** Celá mašina se pustí na syntetická GBM data (nulový drift,
   žádná intradenní struktura ⇒ žádný edge z konstrukce). Reálný walk-forward
   Sharpe musí být **nad maximem** toho, co mašina vyrobí ze šumu.

**Verdikt (automatický):** PASS ⇔ WF Sharpe > 0,3 ∧ PBO < 50 % ∧ WF Sharpe > max(šum).

## Pravidla použití (charta — neměkčit)

- Mřížka se definuje **předem**, hrubá, jedna. Žádné zjemňování po nahlédnutí na
  výsledky, žádná druhá návštěva dat.
- Rohy mřížky musí obsahovat „vypnuto" (např. gap_pct=0, trend_pct=100), aby
  mašina mohla filtr i **nevybrat**.
- Prezentuje se **walk-forward** výsledek; IS číslo jen jako kontext s popiskem
  „optimistické".
- Skutečné OOS (u nás 2018–2020/05) zůstává zamčené — mašina ho nikdy nevidí.
- Nová strategie = nový **adapter** (~40 řádků), jádro se nemění.

## Jak přidat strategii (kontrakt adapteru)

```python
def build_DR(days, dates, ...):
    return DR, grid, dates
# DR   : np.ndarray (n_konfigurací, n_dní) ČISTÝCH denních výnosů (0.0 = bez obchodu)
# grid : [(jmeno_parametru, [hodnoty]), ...] ve stejném pořadí os jako reshape DR
# Den t smí použít JEN informace dostupné do dne t (rolling percentily past-only).
```

Pak: `machine.pick_plateau`, `machine.walk_forward`, `machine.cscv_pbo`,
`machine.verdict` — viz `run_opt.py` jako vzor celé pipeline včetně grafů.

## Soubory

| soubor | co dělá |
|---|---|
| `machine.py` | generické jádro: plošina, walk-forward, CSCV/PBO, verdikt |
| `adapter_vwap_gates.py` | adapter pro VWAP pásmo + brány; generátor syntetických dat |
| `run_opt.py` | orchestrátor: běh + 5 diagnostických grafů + JSON |

Výstupy: `results/optimizer/` — `vwap_gates_optimization.json`, heatmapa s plošinou,
walk-forward equity (poctivá vs IS iluze), stabilita parametrů po foldech,
PBO histogram, noise floor.
