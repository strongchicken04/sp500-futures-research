# 🐹 Zvířátkový deník

Malý útulný deníček, ve kterém žije jeden mazlíček. Zapisuješ si svoje dny —
jídlo, zásilky, školu, judo, spánek a fotky — a každý zápisek tvého mazlíčka
nakrmí. On pak pomaličku roste a proměňuje se: z malinkého křečka bude jednou
krásná kočka… a pak? To se uvidí. ✨

**Pro mojí Zuzanku k svátku 2026 💛**

---

## 📱 Jak si appku spustím na mobilu

Appka běží přes **Expo Go** — nic se nikam neinstaluje „naostro“, stačí telefon
a počítač na stejné Wi‑Fi.

1. **Na telefonu** si nainstaluj aplikaci **Expo Go**:
   - iPhone: [App Store](https://apps.apple.com/app/expo-go/id982107779)
   - Android: [Google Play](https://play.google.com/store/apps/details?id=host.exp.exponent)
2. **Na počítači** potřebuješ [Node.js](https://nodejs.org) (stačí LTS verze).
3. Otevři terminál ve složce `zviratkovy-denik` a spusť:

   ```bash
   npm install
   npx expo start
   ```

4. V terminálu se objeví **QR kód**:
   - **iPhone:** naskenuj ho obyčejnou aplikací Fotoaparát a ťukni na odkaz.
   - **Android:** otevři Expo Go a naskenuj QR kód přímo v ní.
5. Appka se načte do telefonu — a je to! 🐾

> 💡 Když telefon a počítač nejsou na stejné Wi‑Fi (nebo se QR kódu nedaří),
> zkus `npx expo start --tunnel`.

> 💡 Kdyby Expo Go hlásilo, že projekt je pro jinou verzi SDK, spusť ve složce
> projektu `npx expo install expo@latest` a potom `npx expo install --fix`.

## 🔒 Kde jsou moje data?

**Všechno zůstává jen v tvém telefonu.** Zápisky, fotky i tvůj mazlíček se
ukládají pouze do paměti aplikace v mobilu — žádný internet, žádné účty, žádné
přihlašování, žádný cloud. Appka funguje úplně offline.

- Fotky, které do deníku přidáš, si appka zkopíruje k sobě, takže zůstanou
  i kdybys je smazala z galerie.
- Když aplikaci (Expo Go) smažeš, smažou se i data deníčku — tak pozor na to. 💛

## 🐾 Malý návod

- **Domovská obrazovka** — tvůj mazlíček a moře s ostrůvky. Každý ostrůvek je
  jedna činnost.
- **Ťukni na ostrůvek** → uvidíš svoje zápisky a tlačítko **+ Přidat zápisek**.
- **Zápisek** — vždycky napiš pár slov (to je to hlavní!), ostatní políčka
  i fotka jsou nepovinné. Na ostrůvku **Fotky** se přidává fotka s popiskem.
- **Každý uložený zápisek mazlíčka nakrmí** — sleduj, jak se mění. Nikdy není
  hotový, pořád je na cestě něco dalšího. 🌱
- Ťuknutím na mazlíčka otevřeš jeho stránku, ♡ nahoře schovává vzkaz pro tebe.

---

## 🛠 Technical notes (English)

- **Stack:** Expo SDK 57 (managed), React Native + TypeScript, `expo-router`
  (file-based routes in `src/app/`), React Native Reanimated, `react-native-svg`.
- **Data:** 100% local. Entries, pet state and settings are JSON in
  `AsyncStorage`; photos are copied into the app's document directory
  (`expo-file-system`) so they survive restarts. No backend, no accounts.
- **The pet is drawn parametrically** in `src/components/PetAvatar.tsx` —
  every feature (body shape, ears, tail, whiskers, eyes, fur colour, patterns,
  accessories) is computed from the pet's level, so the transformation is
  smooth and effectively infinite. No art assets.
- **Progression:** each saved entry grants XP (`src/lib/xp.ts`). The XP needed
  for the next stage grows as `round(30 * 1.15^level)` — early changes come
  fast, later ones slower, but they never stop. The UI deliberately never
  shows level numbers, totals or "MAX": only a soft ring that keeps refilling.
  Cosmetics unlock every 2 levels forever (cycling with new colour variants).
- **Personalization:** everything personal (her name, pet default name, the
  love note) lives in `src/config/personal.ts`. Islands are config-driven in
  `src/config/activities.ts` — adding a new island is adding one object there.
- **Scripts:** `npm start` (Expo dev server), `npm run typecheck`.
