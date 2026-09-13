import type { CategoryId } from '@/config/categories';

export type Entry = {
  id: string;
  categoryId: CategoryId;
  /** free-form note / caption (optional in this app) */
  note: string;
  /** all persisted photo uris of the entry */
  photoUris?: string[];
  /** category-specific optional fields */
  fields?: Record<string, string>;
  /** epoch ms */
  createdAt: number;
};

/** Photos of an entry, always as an array. */
export function entryPhotos(entry: Pick<Entry, 'photoUris'>): string[] {
  return entry.photoUris ?? [];
}

/** Calories stored on a food entry, or 0. */
export function entryCalories(entry: Pick<Entry, 'fields'>): number {
  const raw = entry.fields?.kalorie;
  if (!raw) return 0;
  const n = parseInt(raw.replace(/\D/g, ''), 10);
  return Number.isFinite(n) ? n : 0;
}
