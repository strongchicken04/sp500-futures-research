/**
 * 🏝️ Activity islands — the whole home screen is driven by this array.
 * Adding a new island = adding one object here (plus nothing else).
 */
/** 'zasilka' is legacy — its island was removed, the id stays only so any
 * previously stored entries still parse. */
export type ActivityId = 'jidlo' | 'zasilka' | 'skola' | 'judo' | 'spanek' | 'fotky';

export type ActivityField =
  | { key: string; label: string; type: 'text'; placeholder: string }
  | { key: string; label: string; type: 'picker'; options: string[] };

export type Activity = {
  id: ActivityId;
  name: string;
  emoji: string;
  /** vivid accent (buttons, highlights) */
  accent: string;
  /** darker accent for headings on soft backgrounds */
  accentDark: string;
  /** soft pastel — island card background */
  soft: string;
  /** extra pale — screen background of the island */
  pale: string;
  tagline: string;
  emptyTitle: string;
  emptyText: string;
  /** emoji that flies to the pet when an entry is saved */
  foodEmoji: string;
  addLabel: string;
  noteLabel: string;
  notePlaceholder: string;
  /** the Fotky island requires a photo (it IS a photo gallery) */
  photoRequired?: boolean;
  fields: ActivityField[];
};

export const ACTIVITIES: Activity[] = [
  {
    id: 'jidlo',
    name: 'Jídlo',
    emoji: '🍓',
    accent: '#EE7D96',
    accentDark: '#B84A64',
    soft: '#FBDAE2',
    pale: '#FEF2F5',
    tagline: 'Dobroty a mlsání',
    emptyTitle: 'Zatím tu nejsou žádné dobroty',
    emptyText: 'Napíšeš, co sis dnes dala dobrého? 🍓',
    foodEmoji: '🍓',
    addLabel: '+ Přidat zápisek',
    noteLabel: 'Důležité věci k jídlu 💭',
    notePlaceholder: 'Napiš pár slov jen pro sebe…',
    fields: [
      { key: 'co', label: 'Co sis dala dobrého?', type: 'text', placeholder: 'třeba palačinky s borůvkami' },
      { key: 'hodnoceni', label: 'A jaké to bylo?', type: 'picker', options: ['😋 Mňamka', '🙂 Dobré', '😕 Nic moc'] },
    ],
  },
  {
    id: 'skola',
    name: 'Škola',
    emoji: '📚',
    accent: '#5FA8D3',
    accentDark: '#33719A',
    soft: '#CFE8F5',
    pale: '#EFF8FC',
    tagline: 'Učení a objevy',
    emptyTitle: 'Prázdná lavice!',
    emptyText: 'Co nového ses dozvěděla? 📚',
    foodEmoji: '📖',
    addLabel: '+ Přidat zápisek',
    noteLabel: 'Důležité věci ke škole 💭',
    notePlaceholder: 'Napiš pár slov jen pro sebe…',
    fields: [
      { key: 'predmet', label: 'Předmět', type: 'text', placeholder: 'čeština, matika, přírodopis…' },
      { key: 'latka', label: 'Co ses učila?', type: 'text', placeholder: 'třeba vyjmenovaná slova' },
    ],
  },
  {
    id: 'judo',
    name: 'Judo trénink',
    emoji: '🥋',
    accent: '#7FB069',
    accentDark: '#527A40',
    soft: '#D8EACB',
    pale: '#F1F8EB',
    tagline: 'Síla a odvaha',
    emptyTitle: 'Tatami zatím čeká',
    emptyText: 'Jak bylo na tréninku? 🥋',
    foodEmoji: '🥋',
    addLabel: '+ Přidat zápisek',
    noteLabel: 'Důležité věci k tréninku 💭',
    notePlaceholder: 'Napiš pár slov jen pro sebe…',
    fields: [
      { key: 'delka', label: 'Jak dlouho?', type: 'text', placeholder: 'třeba 1,5 hodiny' },
      { key: 'co', label: 'Co jste trénovali?', type: 'text', placeholder: 'chvaty, pády, randori…' },
    ],
  },
  {
    id: 'spanek',
    name: 'Spánek',
    emoji: '😴',
    accent: '#9F8CC9',
    accentDark: '#6F5CA0',
    soft: '#E3DBF2',
    pale: '#F5F1FA',
    tagline: 'Sladké sny',
    emptyTitle: 'Ještě tu není žádný spánkový zápisek',
    emptyText: 'Jak se ti spalo? 😴',
    foodEmoji: '🌙',
    addLabel: '+ Přidat zápisek',
    noteLabel: 'Důležité věci ke spánku 💭',
    notePlaceholder: 'Napiš pár slov jen pro sebe…',
    fields: [
      { key: 'hodiny', label: 'Kolik hodin?', type: 'text', placeholder: 'třeba 8' },
      { key: 'kvalita', label: 'Jak ses vyspala?', type: 'picker', options: ['😌 Krásně', '🙂 Docela dobře', '🥱 Moc ne'] },
    ],
  },
  {
    id: 'fotky',
    name: 'Fotky',
    emoji: '📸',
    accent: '#F0906F',
    accentDark: '#B55E40',
    soft: '#FBDFD2',
    pale: '#FDF2EC',
    tagline: 'Galerie vzpomínek',
    emptyTitle: 'Galerie čeká na první fotku',
    emptyText: 'Přidáš nějakou hezkou vzpomínku? 📸',
    foodEmoji: '📸',
    addLabel: '+ Přidat fotku',
    noteLabel: 'Popisek ke vzpomínce 💭',
    notePlaceholder: 'Co je na fotce? Proč je ti milá?',
    photoRequired: true,
    fields: [],
  },
];

export const getActivity = (id?: string | string[]) => {
  const key = Array.isArray(id) ? id[0] : id;
  return ACTIVITIES.find((a) => a.id === key);
};
