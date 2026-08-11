import type { ActivityId } from '@/config/activities';

export type Entry = {
  id: string;
  activityId: ActivityId;
  /** required note for activity entries; caption for photo entries */
  note: string;
  /** legacy single photo — newer builds keep it mirrored to photoUris[0] so
   * older app versions can still read entries */
  photoUri?: string;
  /** all persisted photo uris of the entry (newer builds) */
  photoUris?: string[];
  /** activity-specific optional fields */
  fields?: Record<string, string>;
  /** epoch ms */
  createdAt: number;
};

/** Photos of an entry regardless of which format it was saved in. */
export function entryPhotos(entry: Pick<Entry, 'photoUri' | 'photoUris'>): string[] {
  if (entry.photoUris && entry.photoUris.length > 0) return entry.photoUris;
  return entry.photoUri ? [entry.photoUri] : [];
}

export type PetState = {
  name: string;
  /** total xp — only ever grows */
  xp: number;
  /** derived from xp, uncapped */
  level: number;
  /** cosmetic keys like "bow:0" — derived from level, persisted for convenience */
  unlockedCosmetics: string[];
};

export type Settings = {
  onboarded: boolean;
};
