/**
 * XP, levels, hidden milestone forms and the endless cosmetic schedule.
 *
 * Design rule: the progression must FEEL endless and must never surface
 * "X / Y total", "MAX" or any finish line. Levels are internal only.
 */

export const XP_PER_ENTRY = 10;

const BASE_XP = 30;
const GROWTH = 1.15;

/** XP needed to go from `level` to `level + 1` — ever-growing curve. */
export function xpToLevelUp(level: number): number {
  return Math.round(BASE_XP * Math.pow(GROWTH, level));
}

export type LevelInfo = {
  level: number;
  /** xp already inside the current level */
  into: number;
  /** xp needed for the next little change */
  need: number;
  /** 0..1 progress toward the next little change */
  progress: number;
};

export function levelFromXp(xp: number): LevelInfo {
  let level = 0;
  let rest = Math.max(0, Math.floor(xp));
  while (rest >= xpToLevelUp(level) && level < 999) {
    rest -= xpToLevelUp(level);
    level += 1;
  }
  const need = xpToLevelUp(level);
  return { level, into: rest, need, progress: Math.min(1, rest / need) };
}

/* ------------------------------------------------------------------ */
/* Hidden milestone forms (never shown with numbers or totals)         */
/* ------------------------------------------------------------------ */

const FORMS: { min: number; label: string }[] = [
  { min: 0, label: 'malinký křeček' },
  { min: 2, label: 'chlupatý křečík' },
  { min: 4, label: 'křečík s kočičíma ušima' },
  { min: 6, label: 'zvědavé koťátko' },
  { min: 8, label: 'hravé kotě' },
  { min: 10, label: 'elegantní kočička' },
  { min: 13, label: 'krásná kočka' },
];

/** Endless adjective cycle for forms beyond "krásná kočka". */
const FORM_ADJECTIVES = [
  'zářivá',
  'hvězdná',
  'květinová',
  'duhová',
  'sametová',
  'měsíční',
  'sluneční',
  'perleťová',
  'kouzelná',
  'pohádková',
];

export function formForLevel(level: number): string {
  if (level < 16) {
    let label = FORMS[0].label;
    for (const f of FORMS) if (level >= f.min) label = f.label;
    return label;
  }
  // Beyond 16: a new adjective every 3 levels, forever (combining once the cycle wraps).
  const i = Math.floor((level - 16) / 3);
  const a = FORM_ADJECTIVES[i % FORM_ADJECTIVES.length];
  if (i >= FORM_ADJECTIVES.length) {
    const b = FORM_ADJECTIVES[(i + 3) % FORM_ADJECTIVES.length];
    if (b !== a) return `${a} ${b} kočka`;
  }
  return `${a} kočka`;
}

/* ------------------------------------------------------------------ */
/* Cosmetics — a new little something every 2 levels, forever          */
/* ------------------------------------------------------------------ */

export type CosmeticId =
  | 'bow'
  | 'sparkles'
  | 'flower'
  | 'star'
  | 'crown'
  | 'glow'
  | 'scarf'
  | 'butterfly'
  | 'heart'
  | 'moon';

export type CosmeticInstance = {
  id: CosmeticId;
  /** grows each time the cycle wraps → new color variant, endlessly */
  variant: number;
  key: string;
  label: string;
  emoji: string;
};

const COSMETIC_CYCLE: CosmeticId[] = [
  'bow',
  'sparkles',
  'flower',
  'star',
  'crown',
  'glow',
  'scarf',
  'butterfly',
  'heart',
  'moon',
];

const COSMETIC_LABELS: Record<CosmeticId, string> = {
  bow: 'mašlička',
  sparkles: 'třpytky',
  flower: 'kytička za uchem',
  star: 'hvězdička',
  crown: 'korunka',
  glow: 'zářivá aura',
  scarf: 'šálička',
  butterfly: 'motýlek',
  heart: 'létající srdíčko',
  moon: 'měsíček',
};

export const COSMETIC_EMOJI: Record<CosmeticId, string> = {
  bow: '🎀',
  sparkles: '✨',
  flower: '🌸',
  star: '⭐️',
  crown: '👑',
  glow: '🌟',
  scarf: '🧣',
  butterfly: '🦋',
  heart: '💛',
  moon: '🌙',
};

const FIRST_COSMETIC_LEVEL = 2;
const COSMETIC_EVERY = 2;

/** All cosmetics unlocked at `level`, in unlock order. Endless by design. */
export function cosmeticsForLevel(level: number): CosmeticInstance[] {
  const out: CosmeticInstance[] = [];
  for (let lv = FIRST_COSMETIC_LEVEL; lv <= level; lv += COSMETIC_EVERY) {
    const i = (lv - FIRST_COSMETIC_LEVEL) / COSMETIC_EVERY;
    const id = COSMETIC_CYCLE[i % COSMETIC_CYCLE.length];
    const variant = Math.floor(i / COSMETIC_CYCLE.length);
    out.push({
      id,
      variant,
      key: `${id}:${variant}`,
      label: variant > 0 ? `${COSMETIC_LABELS[id]} v nové barvě` : COSMETIC_LABELS[id],
      emoji: COSMETIC_EMOJI[id],
    });
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* Feeding                                                             */
/* ------------------------------------------------------------------ */

export type FeedResult = {
  xpGained: number;
  oldLevel: number;
  newLevel: number;
  oldProgress: number;
  newProgress: number;
  leveledUp: boolean;
  formChanged: boolean;
  newFormLabel: string;
  unlocked: CosmeticInstance[];
};

export function computeFeed(oldXp: number, xpGained: number): FeedResult {
  const before = levelFromXp(oldXp);
  const after = levelFromXp(oldXp + xpGained);
  const beforeCos = cosmeticsForLevel(before.level);
  const afterCos = cosmeticsForLevel(after.level);
  const oldForm = formForLevel(before.level);
  const newForm = formForLevel(after.level);
  return {
    xpGained,
    oldLevel: before.level,
    newLevel: after.level,
    oldProgress: before.progress,
    newProgress: after.progress,
    leveledUp: after.level > before.level,
    formChanged: newForm !== oldForm,
    newFormLabel: newForm,
    unlocked: afterCos.slice(beforeCos.length),
  };
}
