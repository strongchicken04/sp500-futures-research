import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import type { CategoryId } from '@/config/categories';
import { genId } from '@/lib/id';
import { deletePhotoFile } from '@/lib/photos';
import { loadJSON, saveJSON, STORAGE_KEYS } from '@/lib/storage';
import { entryPhotos, type Entry } from '@/lib/types';

export type EntryInput = {
  id?: string;
  categoryId: CategoryId;
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
  getEntry: (id: string) => Entry | undefined;
  addEntry: (input: EntryInput) => Promise<void>;
  updateEntry: (id: string, patch: EntryPatch) => Promise<void>;
  deleteEntry: (id: string) => Promise<void>;
};

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [hydrated, setHydrated] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  // Mirrors the latest committed value so async actions never race renders.
  const entriesRef = useRef(entries);

  useEffect(() => {
    let cancelled = false;
    loadJSON<Entry[]>(STORAGE_KEYS.entries, [])
      .then((e) => {
        if (cancelled) return;
        const sorted = [...e].sort((a, b) => b.createdAt - a.createdAt);
        entriesRef.current = sorted;
        setEntries(sorted);
        setHydrated(true);
      })
      .catch((err) => {
        console.warn('hydration failed', err);
        if (!cancelled) setHydrated(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const commit = useCallback((next: Entry[]) => {
    entriesRef.current = next;
    setEntries(next);
    void saveJSON(STORAGE_KEYS.entries, next);
  }, []);

  const getEntry = useCallback((id: string) => entriesRef.current.find((e) => e.id === id), []);

  const addEntry = useCallback(
    async (input: EntryInput) => {
      const photoUris = input.photoUris && input.photoUris.length > 0 ? input.photoUris : undefined;
      const entry: Entry = {
        id: input.id ?? genId(),
        categoryId: input.categoryId,
        note: input.note.trim(),
        photoUris,
        fields: input.fields && Object.keys(input.fields).length > 0 ? input.fields : undefined,
        createdAt: Date.now(),
      };
      commit([entry, ...entriesRef.current]);
    },
    [commit]
  );

  const updateEntry = useCallback(
    async (id: string, patch: EntryPatch) => {
      const old = entriesRef.current.find((e) => e.id === id);
      if (!old) return;
      const nextPhotos = patch.photoUris ?? [];
      for (const p of entryPhotos(old)) {
        if (!nextPhotos.includes(p)) deletePhotoFile(p);
      }
      commit(
        entriesRef.current.map((e) =>
          e.id === id
            ? {
                ...e,
                note: patch.note.trim(),
                photoUris: nextPhotos.length > 0 ? nextPhotos : undefined,
                fields: patch.fields && Object.keys(patch.fields).length > 0 ? patch.fields : undefined,
              }
            : e
        )
      );
    },
    [commit]
  );

  const deleteEntry = useCallback(
    async (id: string) => {
      const old = entriesRef.current.find((e) => e.id === id);
      if (old) entryPhotos(old).forEach((p) => deletePhotoFile(p));
      commit(entriesRef.current.filter((e) => e.id !== id));
    },
    [commit]
  );

  const value = useMemo<AppContextValue>(
    () => ({ hydrated, entries, getEntry, addEntry, updateEntry, deleteEntry }),
    [hydrated, entries, getEntry, addEntry, updateEntry, deleteEntry]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}
