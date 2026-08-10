# 🐹 Zuzanky deník

Malý útulný deníček, ve kterém žije jeden mazlíček. Zapisuješ si svoje dny —
jídlo, školu, judo, spánek a fotky — a každý zápisek tvého mazlíčka
nakrmí. On pak pomaličku roste a proměňuje se: z malinkého křečka bude jednou
krásná kočka… a pak? To se uvidí. ✨

**Pro mojí Zuzanku k svátku 2026 💛**

---

## 📦 Instalace na Android (hotová APK — nejjednodušší)

Appka se dá nainstalovat naostro, bez počítače:

1. Na GitHubu otevři **Releases** tohoto repozitáře a u nejnovějšího vydání
   „Zuzanky deník — Android APK" stáhni soubor **`zuzanky-denik.apk`**
   (klidně rovnou v telefonu, nebo ho do telefonu pošli např. messengerem).
2. Ťukni na stažený soubor. Android se zeptá, jestli povolit **instalaci
   z neznámých zdrojů** (u prohlížeče/aplikace, ze které instaluješ) — povol to.
3. Nainstaluj — na ploše se objeví ikonka křečka **Zuzanky deník**. 🐹

> Novou verzi APK kdykoli sestavíš na GitHubu: záložka **Actions** →
> workflow **Build Zuzanky deník APK** → **Run workflow** (větev
> `claude/zviraatkovy-denik-app-x0gmd7`). Hotová APK se objeví v Releases.
> Podepisuje se klíčem `credentials/android.keystore`, takže nová verze
> jde nainstalovat **přes** starou a všechna data v deníčku zůstanou.

## 🍏 Instalace na iPhone (TestFlight)

iOS nedovoluje instalaci „ze souboru" — potřebuješ [Apple Developer Program](https://developer.apple.com/programs/)
(99 USD/rok) a appka se pak instaluje přes **TestFlight**:

1. Zaplať a aktivuj členství (nejsnáz přes aplikaci „Apple Developer" v iPhonu).
2. Na počítači ve složce `zviratkovy-denik`:

   ```bash
   npm install -g eas-cli
   eas login                      # účet z expo.dev
   eas build -p ios --profile production   # build v cloudu, ptá se na Apple ID
   eas submit -p ios --latest              # nahraje build do TestFlightu
   ```

3. Na [appstoreconnect.apple.com](https://appstoreconnect.apple.com) → aplikace
   → **TestFlight** přidej testerku (její Apple ID e-mail) — přijde jí pozvánka.
4. Ona si z App Storu nainstaluje **TestFlight**, přijme pozvánku a appku má.

> ⏳ TestFlight buildy platí **90 dní** — před vypršením stačí znovu spustit ty
> dva příkazy (`eas build` + `eas submit`); číslo buildu se zvedá samo a data
> v telefonu zůstávají.

## 🌐 Webová verze (PWA) — „Přidat na plochu" na iPhonu

Appka umí běžet i jako webová aplikace: v Safari se otevře adresa, dá se
**Sdílet → Přidat na plochu** a chová se jako nainstalovaná aplikace (ikona,
celá obrazovka, offline, data v telefonu — zápisky v localStorage, fotky
v IndexedDB).

- Build: `node scripts/build-web.mjs` → statický web ve složce `dist/`
  (obsahuje service worker pro offline režim a `404.html` pro GitHub Pages).
- Hostuje se na GitHub Pages z veřejného repozitáře `zuzanky-denik`
  (adresa `https://<účet>.github.io/zuzanky-denik/` — musí sedět s
  `experiments.baseUrl` v `app.json`).
- Nasazení nové verze = spustit build a pushnout obsah `dist/` do toho
  repozitáře.

> ⚠️ Ať si smaže Safari data jen s rozmyslem — „Vymazat historii a data webů"
> by smazalo i deníček. Aplikace přidaná na plochu má úložiště trvalé.

## 📱 Jak appku spustím přes Expo Go (pro vývoj a zkoušení)

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
- Když aplikaci smažeš (nebo v Expo Go smažeš projekt), smažou se i data
  deníčku — tak pozor na to. 💛 Obyčejná aktualizace na novější verzi appky
  data nemaže.

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
- **Standalone APK:** built by the repo-root GitHub Actions workflow
  (`.github/workflows/build-apk.yml`): `expo prebuild` + Gradle
  `assembleRelease`, ABIs limited to `armeabi-v7a`/`arm64-v8a`, published as a
  GitHub Release. App id `cz.zuzanka.denik`, display name "Zuzanky deník".
  Release builds are signed with the committed `credentials/android.keystore`
  (alias `androiddebugkey`, password `android` — a personal-gift key, not a
  store key), so newer builds install over older ones without losing data.
  Bump `android.versionCode` in `app.json` when shipping an update.
- **Scripts:** `npm start` (Expo dev server), `npm run typecheck`.
