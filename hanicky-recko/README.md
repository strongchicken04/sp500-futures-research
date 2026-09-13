# ☀️ Haničky Řecko

Jednoduchý deníček z řecké dovolené. Čtyři kategorie — **Fotky**, **Jídlo**
(i s kaloriemi), **Pokémoni** a **Aktivita** — a všechno zůstává jen v telefonu.

---

## 📦 Instalace na Android (hotová APK)

1. Na GitHubu otevři **Releases** tohoto repozitáře a u nejnovějšího vydání
   „Haničky Řecko — Android APK" stáhni soubor **`hanicky-recko.apk`**.
2. Ťukni na stažený soubor, povol **instalaci z neznámých zdrojů** a nainstaluj.
3. Na ploše se objeví ikonka s řeckým domečkem **Haničky Řecko**. 🏛️

> Novou verzi sestavíš na GitHubu: **Actions** → **Build Haničky Řecko APK** →
> **Run workflow**. Hotová APK se objeví v Releases. Podepisuje se stejným
> klíčem, takže nová verze jde nainstalovat přes starou a data zůstanou.

## 🌐 Webová verze („Přidat na plochu" na iPhonu)

Appka běží i jako webová aplikace: otevři adresu v Safari a dej
**Sdílet → Přidat na plochu**. Pak se chová jako nainstalovaná aplikace —
ikona, celá obrazovka, funguje offline.

- Build: `node scripts/build-web.mjs` → statický web ve složce `dist/`.
- Adresa musí odpovídat `experiments.baseUrl` v `app.json`.

## 🔒 Kde jsou data?

**Všechno zůstává jen v telefonu.** Zápisky i fotky se ukládají do paměti
aplikace — žádný účet, žádný cloud, funguje offline. Fotky si appka zkopíruje
k sobě, takže zůstanou, i kdyby zmizely z galerie.

## 🏖️ Jak to funguje

- **Fotky** — galerie vzpomínek, ke každé se dá napsat popisek (na zápisek jde
  přidat až 8 fotek).
- **Jídlo** — co jsi jedla, nepovinně kalorie; nahoře v kategorii se ukazuje
  **součet kalorií za dnešek**.
- **Pokémoni** — stačí odkliknout, jestli jsi něco chytila, a přidat fotky.
- **Aktivita** — jen volný text, co jsi dnes dělala (plus fotky).
- Na úvodní obrazovce běží řecká scéna (ťukni na ni 😉), počítadlo dne pobytu
  a počet vzpomínek.

---

## 🛠 Technical notes (English)

- **Stack:** Expo SDK 57 (managed), React Native + TypeScript, `expo-router`
  (file-based routes in `src/app/`), Reanimated, `react-native-svg`.
- **Data:** entries are JSON in `AsyncStorage`; photos are copied into the app's
  document directory (`expo-file-system`), or downscaled into IndexedDB on web
  (`src/lib/photos.web.ts`). No backend.
- **Categories are config-driven** (`src/config/categories.ts`): adding one is
  adding an object — fields support `text`, `number` (with suffix) and `picker`.
  Entry validation is per category: the photo gallery needs a photo, everything
  else needs at least one filled thing.
- **Scene:** `src/components/GreeceScene.tsx` is a parametric SVG (sun, sea,
  whitewashed houses, drifting boat) — no image assets.
- **Scripts:** `npm start` (Expo dev server), `npm run typecheck`,
  `node scripts/build-web.mjs` (PWA build with offline service worker).
