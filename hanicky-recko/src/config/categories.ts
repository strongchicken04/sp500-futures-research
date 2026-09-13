/**
 * 🏛️ Categories — the whole app is driven by this array.
 * Adding a category = adding one object here.
 */
export type CategoryId = 'fotky' | 'jidlo' | 'pokemoni' | 'aktivita';

export type CategoryField =
  | { key: string; label: string; type: 'text'; placeholder: string }
  | { key: string; label: string; type: 'picker'; options: string[] }
  | { key: string; label: string; type: 'number'; placeholder: string; suffix: string };

export type Category = {
  id: CategoryId;
  name: string;
  emoji: string;
  /** vivid accent (buttons, highlights) */
  accent: string;
  /** darker accent for headings on soft backgrounds */
  accentDark: string;
  /** soft pastel — category card background */
  soft: string;
  /** extra pale — screen background */
  pale: string;
  tagline: string;
  emptyTitle: string;
  emptyText: string;
  addLabel: string;
  noteLabel: string;
  notePlaceholder: string;
  /** an entry needs at least a photo (photo gallery) */
  photoRequired?: boolean;
  fields: CategoryField[];
};

export const CATEGORIES: Category[] = [
  {
    id: 'fotky',
    name: 'Fotky',
    emoji: '📸',
    accent: '#2E8BC0',
    accentDark: '#1B5E85',
    soft: '#CDE9F7',
    pale: '#F0F9FD',
    tagline: 'Vzpomínky z Řecka',
    emptyTitle: 'Zatím tu není žádná fotka',
    emptyText: 'Přidáš první vzpomínku z Řecka? 📸',
    addLabel: '+ Přidat fotky',
    noteLabel: 'Popisek (nepovinný)',
    notePlaceholder: 'Co je na fotce? Kde to bylo?',
    photoRequired: true,
    fields: [],
  },
  {
    id: 'jidlo',
    name: 'Jídlo',
    emoji: '🍽️',
    accent: '#E07A5F',
    accentDark: '#A94F35',
    soft: '#FBDDD2',
    pale: '#FEF4F0',
    tagline: 'Dobroty a mlsání',
    emptyTitle: 'Zatím žádná dobrota',
    emptyText: 'Co sis dnes dala dobrého? 🥙',
    addLabel: '+ Přidat jídlo',
    noteLabel: 'Poznámka (nepovinná)',
    notePlaceholder: 'Jaké to bylo? S kým jsi jedla?',
    fields: [
      { key: 'co', label: 'Co jsi jedla?', type: 'text', placeholder: 'třeba gyros, salát, zmrzlina…' },
      { key: 'kalorie', label: 'Kalorie (nepovinné)', type: 'number', placeholder: 'třeba 450', suffix: 'kcal' },
    ],
  },
  {
    id: 'pokemoni',
    name: 'Pokémoni',
    emoji: '⚡',
    accent: '#F2B705',
    accentDark: '#9C7400',
    soft: '#FCEDBF',
    pale: '#FEFAEC',
    tagline: 'Lov na cestách',
    emptyTitle: 'Zatím žádný úlovek',
    emptyText: 'Chytila jsi dnes něco? ⚡',
    addLabel: '+ Přidat úlovek',
    noteLabel: 'Koho jsi chytila? (nepovinné)',
    notePlaceholder: 'třeba Pikachu u pláže…',
    fields: [
      {
        key: 'ulovek',
        label: 'Chytila jsi něco?',
        type: 'picker',
        options: ['✅ Jo, chytila!', '🫥 Nic extra'],
      },
    ],
  },
  {
    id: 'aktivita',
    name: 'Aktivita',
    emoji: '🏖️',
    accent: '#1EA896',
    accentDark: '#0F6E62',
    soft: '#C7EBE5',
    pale: '#EFFAF8',
    tagline: 'Co jsi dnes dělala',
    emptyTitle: 'Zatím tu nic není',
    emptyText: 'Co hezkého jsi dnes zažila? 🏖️',
    addLabel: '+ Přidat zápisek',
    noteLabel: 'Co jsi dělala?',
    notePlaceholder: 'Napiš, co se dnes dělo…',
    fields: [],
  },
];

export const getCategory = (id?: string | string[]) => {
  const key = Array.isArray(id) ? id[0] : id;
  return CATEGORIES.find((c) => c.id === key);
};
