# Premarket Range Sweep & Reclaim — verdikt: ŽÁDNÁ HRANA

**Pravidla:** range 8:12–9:12 NY → sweep jedné strany → vstup na silné svíčce
(tělo ≥ 50 %) zavírající zpět uvnitř range → TP = protější strana, SL = polovina
(RR 2:1), 1 obchod/den, EOD flat. Reálné NQ na QuantConnect, 2018–2025,
1 kontrakt, $100k. Projekt `NQ_Sweep_Reclaim` (34560719), backtest
`35e820f53a039f6b8c7ff0703ef0e359`.

## Výsledek

| metrika | hodnota |
|---|---|
| obchodů | 1 696 (~212/rok) |
| win rate | **34,2 %** (breakeven pro RR 2:1 = 33,3 % + náklady) |
| avg/obchod | **−2,17 b** |
| Sharpe | −0,40 |
| Net profit | **−75,8 %** |
| Max DD | −78,8 % |
| poplatky | $7 387 |

## Proč to nefunguje

Win rate 34,2 % je **přesně** náhodná úroveň pro trade s TP 2× dál než SL.
Sweep + silná reclaim svíčka nemá na NQ žádnou prediktivní hodnotu — pattern
jen mechanicky vyrábí strukturu výplat 2:1 s pravděpodobností 1/3, tedy hrubou
nulu, a poplatky + slippage z ní dělají jistou ztrátu. Stejná rodina iluzí jako
ORB scalper z dřívějšího auditu (tam 80% win rate z RR 1:4 — zrcadlový efekt).

Rozpad podle podmnožin — nikde nic k záchraně:

- **Long vs short:** −2,78 b vs −1,60 b (obojí záporné)
- **Roky:** 7 z 8 záporných; jediný kladný 2024 (+1,74 b/obchod) je v pásmu šumu
- **Velikost range (tercily):** malý −2,28 / střední −1,36 / velký −2,86 b

## Závěr

Netestovat dál, nevylepšovat parametry (STRONG, okno, cutoff) — na nulové hrubé
hraně není co optimalizovat. Případný „hezký backtest" z videa bude výběr období
(např. právě 2024) nebo hindsight výběr obchodů.
