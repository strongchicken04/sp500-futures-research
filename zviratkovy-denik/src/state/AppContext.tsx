import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import type { ActivityId } from '@/config/activities';
import { PERSONAL } from '@/config/personal';
import { genId } from '@/lib/id';
import { deletePhotoFile } from '@/lib/photos';
import { loadJSON, saveJSON, STORAGE_KEYS } from '@/lib/storage';
import { entryPhotos, type Entry, type PetState, type Settings } from '@/lib/types';
import { computeFeed, cosmeticsForLevel, levelFromXp, XP_PER_ENTRY, type FeedResult } from '@/lib/xp';

const DEFAULT_PET: PetState = {
  name: PERSONAL.defaultPetName,
  xp: 0,
  level: 0,
  unlockedCosmetics: [],
};

const DEFAULT_SETTINGS: Settings = { onboarded: false };

export type NewEntryInput = {
  id?: string;
  activityId: ActivityId;
  note: string;
  photoUris?: string[];
  fields?: Record<string, string>;
};

export type EntryPatch = {
  note: string;
  photoUris?: string[];
  fields?: Record<string, string>;
};

type AppContextValue = {
  hydrated: boolean;
  entries: Entry[];
  pet: PetState;
  settings: Settings;
  getEntry: (id: string) => Entry | undefined;
  addEntry: (input: NewEntryInput) => Promise<FeedResult>;
  updateEntry: (id: string, patch: EntryPatch) => Promise<void>;
  deleteEntry: (id: string) => Promise<void>;
  renamePet: (name: string) => void;
  completeOnboarding: (petName: string) => void;
};

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [hydrated, setHydrated] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [pet, setPet] = useState<PetState>(DEFAULT_PET);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);

  // Refs mirror the latest committed values so async actions never race renders.
  const entriesRef = useRef(entries);
  const petRef = useRef(pet);
  const settingsRef = useRef(settings);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [e, p, s] = await Promise.all([
        loadJSON<Entry[]>(STORAGE_KEYS.entries, []),
        loadJSON<PetState>(STORAGE_KEYS.pet, DEFAULT_PET),
        loadJSON<Settings>(STORAGE_KEYS.settings, DEFAULT_SETTINGS),
      ]);
      if (cancelled) return;
      const sorted = [...e].sort((a, b) => b.createdAt - a.createdAt);
      // Self-heal derived fields in case the app logic evolved between runs.
      const level = levelFromXp(p.xp ?? 0).level;
      const healedPet: PetState = {
        ...DEFAULT_PET,
        ...p,
        level,
        unlockedCosmetics: cosmeticsForLevel(level).map((c) => c.key),
      };
      entriesRef.current = sorted;
      petRef.current = healedPet;
      settingsRef.current = { ...DEFAULT_SETTINGS, ...s };
      setEntries(sorted);
      setPet(healedPet);
      setSettings(settingsRef.current);
      setHydrated(true);
    })().catch((err) => {
      console.warn('hydration failed', err);
      if (!cancelled) setHydrated(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const commitEntries = useCallback((next: Entry[]) => {
    entriesRef.current = next;
    setEntries(next);
    void saveJSON(STORAGE_KEYS.entries, next);
  }, []);

  const commitPet = useCallback((next: PetState) => {
    petRef.current = next;
    setPet(next);
    void saveJSON(STORAGE_KEYS.pet, next);
  }, []);

  const commitSettings = useCallback((next: Settings) => {
    settingsRef.current = next;
    setSettings(next);
    void saveJSON(STORAGE_KEYS.settings, next);
  }, []);

  const getEntry = useCallback((id: string) => entriesRef.current.find((e) => e.id === id), []);

  const addEntry = useCallback(
    async (input: NewEntryInput): Promise<FeedResult> => {
      const photoUris = input.photoUris && input.photoUris.length > 0 ? input.photoUris : undefined;
      const entry: Entry = {
        id: input.id ?? genId(),
        activityId: input.activityId,
        note: input.note.trim(),
        photoUris,
        photoUri: photoUris?.[0],
        fields: input.fields && Object.keys(input.fields).length > 0 ? input.fields : undefined,
        createdAt: Date.now(),
      };
      commitEntries([entry, ...entriesRef.current]);

      const prevPet = petRef.current;
      const feed = computeFeed(prevPet.xp, XP_PER_ENTRY);
      commitPet({
        ...prevPet,
        xp: prevPet.xp + XP_PER_ENTRY,
        level: feed.newLevel,
        unlockedCosmetics: cosmeticsForLevel(feed.newLevel).map((c) => c.key),
      });
      return feed;
    },
    [commitEntries, commitPet]
  );

  const updateEntry = useCallback(
    async (id: string, patch: EntryPatch): Promise<void> => {
      const old = entriesRef.current.find((e) => e.id === id);
      if (!old) return;
      const nextPhotos = patch.photoUris ?? [];
      for (const p of entryPhotos(old)) {
        if (!nextPhotos.includes(p)) deletePhotoFile(p);
      }
      const next = entriesRef.current.map((e) =>
        e.id === id
          ? {
              ...e,
              note: patch.note.trim(),
              photoUris: nextPhotos.length > 0 ? nextPhotos : undefined,
              photoUri: nextPhotos[0],
              fields: patch.fields && Object.keys(patch.fields).length > 0 ? patch.fields : undefined,
            }
          : e
      );
      commitEntries(next);
    },
    [commitEntries]
  );

  const deleteEntry = useCallback(
    async (id: string): Promise<void> => {
      const old = entriesRef.current.find((e) => e.id === id);
      if (old) entryPhotos(old).forEach((p) => deletePhotoFile(p));
      commitEntries(entriesRef.current.filter((e) => e.id !== id));
      // XP stays with the pet on purpose — deleting a memory never punishes her.
    },
    [commitEntries]
  );

  const renamePet = useCallback(
    (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) return;
      commitPet({ ...petRef.current, name: trimmed.slice(0, 24) });
    },
    [commitPet]
  );

  const completeOnboarding = useCallback(
    (petName: string) => {
      const trimmed = petName.trim();
      commitPet({ ...petRef.current, name: (trimmed || PERSONAL.defaultPetName).slice(0, 24) });
      commitSettings({ ...settingsRef.current, onboarded: true });
    },
    [commitPet, commitSettings]
  );

  const value = useMemo<AppContextValue>(
    () => ({
      hydrated,
      entries,
      pet,
      settings,
      getEntry,
      addEntry,
      updateEntry,
      deleteEntry,
      renamePet,
      completeOnboarding,
    }),
    [hydrated, entries, pet, settings, getEntry, addEntry, updateEntry, deleteEntry, renamePet, completeOnboarding]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}
