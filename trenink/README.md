# 💪 Hanička fitko

Trénink A / B — odškrtávání sérií a zápis vah. Webová aplikace, která jde připnout na plochu
telefonu a funguje offline. Všechno se ukládá jen v telefonu.

**Adresa:** https://strongchicken04.github.io/zuzanky-denik/trenink/

Na iPhonu: Safari → **Sdílet** → **Přidat na plochu**.

## Co umí

- **Trénink A / B** v záložkách, u každé je vidět, kdy byl naposledy.
- **Odškrtávání sérií** velkými tlačítky + ukazatel postupu.
- **Váhy:** u každého cviku svítí *Minule 20 kg* i s tím, jak je to dlouho.
  Dnešní váhu zapíšeš ručně nebo tlačítky − / + po 2,5 kg; když dáš víc než
  minule, ukáže se zelená šipka s rozdílem.
- **Ukončit trénink** → dnešní váhy se uloží jako „minule", odškrtnutí se smaže,
  trénink se zapíše do historie a appka přepne na druhý trénink.
- Když se na ukončení zapomene, **další den se to srovná samo** — váhy se
  přesunou do „minule" a nový trénink začíná s čistým štítem.
- **Historie** posledních tréninků (datum, který trénink, kolik sérií).

## Jak upravit cviky

V `index.html` v poli `PLAN` — každý cvik má stabilní `id`, takže přejmenování
nebo přeházení pořadí nikdy nezahodí uložené váhy. `kg: true` zapne řádek s
váhami, `sets` je počet sérií.

## Nasazení

Soubory se kopírují do složky `trenink/` v repozitáři `zuzanky-denik`
(GitHub Pages). Po změně `index.html` zvyš `CACHE` v `sw.js`, ať si telefony
stáhnou novou verzi.
