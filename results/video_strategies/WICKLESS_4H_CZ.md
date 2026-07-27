# 4H svíčka bez knotu — verdikt: PRAVDIVÝ CLAIM, NULOVÁ INFORMACE

**Claim z videa:** 4H svíčka bez spodního knotu „je téměř vždy pohlcena" —
cena se vrátí na její low (žádná manipulace → imbalance se musí zaplnit).
Doporučený obchod: označit low, počkat na LTF konfirmaci, targetovat low.

**Test:** reálné NQ 2018–2025 (QC), 4H buckety kotvené 18:00 ET, extended
hours. Wickless = knot ≤ max(1 tick, 3 % rozsahu). Baseline = každý 10. běžný
4H bar. Sledování návratu do 30 dalších 4H barů (~1 týden). Projekt
`NQ_Wickless_4H` (34561698), backtest `704135b039ae47a19eaf7e922dae5852`,
4 315 eventů.

## Výsledek

| úroveň | n | návrat ≤ 30 barů | ≤ 1 bar | ≤ 6 barů | medián útěku proti |
|---|---|---|---|---|---|
| **wickless low (≤3 %)** | 808 | **87,4 %** | 57,4 % | 74,3 % | 64 b |
| **baseline low (běžná svíčka)** | 1 233 | **86,4 %** | 55,6 % | 74,0 % | 81 b |
| **wickless high (≤3 %)** | 1 041 | **89,8 %** | 63,9 % | 77,7 % | 43 b |
| **baseline high (běžná svíčka)** | 1 233 | **92,0 %** | 64,2 % | 82,2 % | 60 b |

Striktní verze (knot ≤ 1 tick): bottom 88,5 % (n=252), top 86,0 % (n=243) —
stejný obrázek. Po letech: rozdíl BW−LB skáče mezi −5,8 a +4,3 p.b. bez
jakéhokoli trendu (šum).

## Interpretace

Video říká pravdu — a přesně proto je bezcenné:

- Low wickless svíčky se do týdne dočká návratu v **87 %** případů…
- …jenže low **JAKÉKOLI** 4H svíčky se dočká návratu v **86 %** případů.
  U high dokonce baseline (92 %) wickless svíčky (90 %) lehce poráží.
- Rozdíl 1 p.b. je hluboko v šumu (SE ≈ 1,2 p.b.). „Chybějící manipulace"
  a „imbalance" nenesou žádnou informaci navíc — trh se prostě vrací na
  nedávné úrovně skoro vždy, protože 4H range je malý vůči týdenní volatilitě.

Klasický **base-rate trik**: divák nikdy nevidí kontrolní skupinu, takže 87 %
vypadá jako magie wickless svíčky, ačkoli je to vlastnost všech svíček.

K obchodovatelnosti: medián útěku ceny proti targetu před návratem je 43–64 b
a 10–13 % úrovní se nedočká vůbec — bez definovaného SL none z „high
probability" nezbývá. LTF konfirmace (sweep/BOS/FVG) z videa nejsou
definované a nemají co zachraňovat: filtr nad nulovou informací je pořád
nulová informace.

## Závěr

Netestovat dál. Do sbírky lekcí: **každé „X se stane skoro vždy" je bezcenné,
dokud nezměříš, jak často se X stane bez podmínky.**
