# Fibonacci „golden zone" + FVG — verdikt: PŘESNĚ NÁHODA

**Pravidla (video #4):** fib úrovně 0 / 0.618 / 0.706 / 0.79 / 1; golden zone
0.618–0.79 retracementu impulsu; konfluence s FVG uvnitř zóny → „high
probability reversal". Mechanizace: 5m fraktální pivoty (2/2), impuls ≥ 0,15 %
ceny, FVG z impulsní nohy překrývající zónu, vstup na 5m close v zóně,
TP = extrém impulsu, SL = opačný konec, 1 obchod/den, EOD flat. Reálné NQ
2018–2025, 1 kontrakt, $100k. Projekt `NQ_Fib_GoldenZone` (34653895),
backtest `0105209d5bb069be54f79c5efb6cb0d3`.

## Výsledek

| metrika | hodnota |
|---|---|
| obchodů | 1 208 |
| win rate | **32,5 %** |
| náhodná základna pro medián RR 2,11 | **32,2 %** |
| avg/obchod | −0,34 b hrubě |
| Net profit (vč. poplatků) | **−13,4 %** |
| Sharpe | −0,37 |
| Max DD | −33,7 % |

## Rozpad

- **Long +2,50 b/obchod, short −1,92 b** — rozdíl je čistě drift NQ nahoru
  (long cokoli na NQ 2018–2025 vydělávalo), ne kvalita setupu; „reversal"
  logika sama je prázdná.
- Po letech: ±, bez trendu, vše v pásmu šumu.
- Exity: TP 29 %, SL 66 %, EOD 5 %.

## Interpretace

Win rate 32,5 % vs náhodných 32,2 % pro dané RR — golden zone + FVG
konfluence nepřidávají **žádnou** informaci. „Reversals happen most often in
the golden zone" je geometrická tautologie: zóna 0.618–0.79 pokrývá širokou
oblast hlubokého pullbacku, kam se cena dostane často, a „stack the odds"
s FVG je jen další podmínka, která výběr nijak nezlepšila. Video prodává
vizuální rituál, ne hranu.

## Skóre video strategií: 0/4

sweep & reclaim −76 % · wickless 4H = baseline · 10pm open −58 % (pod
náhodou) · fib golden zone = náhoda (−13 % po nákladech).
