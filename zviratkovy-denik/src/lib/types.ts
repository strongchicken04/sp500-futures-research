import type { ActivityId } from '@/config/activities';

export type Entry = {
  id: string;
  activityId: ActivityId;
  /** required note for activity entries; caption for photo entries */
  note: string;
  /** persisted local file uri (inside the app's document directory) */
  photoUri?: string;
  /** activity-specific optional fields */
  fields?: Record<string, string>;
  /** epoch ms */
  createdAt: number;
};

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
