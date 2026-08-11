import * as Haptics from 'expo-haptics';
import { Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import React, { useMemo, useRef, useState } from 'react';
import {
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { FeedCelebration } from '@/components/FeedCelebration';
import { PhotoPickerField } from '@/components/PhotoPickerField';
import { Card, Chip, IconButton, PrimaryButton, Screen, T } from '@/components/ui';
import { getActivity } from '@/config/activities';
import { C, F } from '@/config/theme';
import { formatDateTime } from '@/lib/czech';
import { genId } from '@/lib/id';
import { persistPhoto } from '@/lib/photos';
import { entryPhotos } from '@/lib/types';
import type { FeedResult } from '@/lib/xp';
import { useApp } from '@/state/AppContext';

export default function EntryFormScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ activityId?: string; entryId?: string }>();
  const { getEntry, addEntry, updateEntry, pet } = useApp();

  const entryId = typeof params.entryId === 'string' ? params.entryId : undefined;
  const existing = entryId ? getEntry(entryId) : undefined;
  const activity = getActivity(existing?.activityId ?? params.activityId);
  const isEdit = !!existing;

  const [note, setNote] = useState(existing?.note ?? '');
  const [fields, setFields] = useState<Record<string, string>>(existing?.fields ?? {});
  const [photos, setPhotos] = useState<string[]>(existing ? entryPhotos(existing) : []);
  const [saving, setSaving] = useState(false);
  const [feed, setFeed] = useState<FeedResult | null>(null);
  const newIdRef = useRef(genId());
  const nowRef = useRef(Date.now());
  // Photos the entry already had — these are persisted, everything else is new.
  const initialPhotosRef = useRef<Set<string>>(new Set(existing ? entryPhotos(existing) : []));

  const canSave = useMemo(() => {
    if (saving) return false;
    if (note.trim().length === 0) return false;
    if (activity?.photoRequired && photos.length === 0) return false;
    return true;
  }, [note, photos.length, activity?.photoRequired, saving]);

  if (!activity) return <Redirect href="/" />;

  const setField = (key: string, value: string) =>
    setFields((prev) => {
      const next = { ...prev };
      const trimmedIsEmpty = value.trim().length === 0;
      if (trimmedIsEmpty) delete next[key];
      else next[key] = value;
      return next;
    });

  const handleSave = async () => {
    if (!canSave) return;
    setSaving(true);
    Keyboard.dismiss();
    try {
      const id = existing?.id ?? newIdRef.current;
      const storedUris: string[] = [];
      for (const p of photos) {
        storedUris.push(initialPhotosRef.current.has(p) ? p : await persistPhoto(p, id));
      }
      const cleanFields: Record<string, string> = {};
      for (const [k, v] of Object.entries(fields)) {
        if (v.trim().length > 0) cleanFields[k] = v.trim();
      }
      if (isEdit && existing) {
        await updateEntry(existing.id, { note, photoUris: storedUris, fields: cleanFields });
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
        router.back();
      } else {
        const result = await addEntry({
          id,
          activityId: activity.id,
          note,
          photoUris: storedUris,
          fields: cleanFields,
        });
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
        setFeed(result);
      }
    } finally {
      setSaving(false);
    }
  };

  const hint = !note.trim()
    ? `Nejdřív napiš pár slov — právě ta ${pet.name} živí 💛`
    : activity.photoRequired && photos.length === 0
      ? 'Ještě vyber aspoň jednu fotku 📸'
      : null;

  return (
    <Screen bg={activity.pale} edges={Platform.OS === 'android' ? ['top', 'bottom'] : ['bottom']}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.headerRow}>
          <IconButton accessibilityLabel="Zavřít" onPress={() => router.back()}>
            <Text style={{ fontSize: 15 }}>✕</Text>
          </IconButton>
          <T v="title" color={activity.accentDark}>
            {activity.emoji} {isEdit ? 'Upravit zápisek' : 'Nový zápisek'}
          </T>
          <View style={{ width: 42 }} />
        </View>

        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}>
          <Card style={styles.dateCard}>
            <T v="small" color={C.inkSoft}>
              🕰 {formatDateTime(existing?.createdAt ?? nowRef.current)}
            </T>
          </Card>

          {/* the heart of the app — her required note */}
          <T v="heading" style={styles.label}>
            {activity.noteLabel}
          </T>
          <TextInput
            value={note}
            onChangeText={setNote}
            placeholder={activity.notePlaceholder}
            placeholderTextColor={C.inkFaint}
            multiline
            style={styles.noteInput}
          />

          {activity.fields.map((f) => (
            <View key={f.key}>
              <T v="heading" style={styles.label}>
                {f.label}
              </T>
              {f.type === 'text' ? (
                <TextInput
                  value={fields[f.key] ?? ''}
                  onChangeText={(v) => setField(f.key, v)}
                  placeholder={f.placeholder}
                  placeholderTextColor={C.inkFaint}
                  style={styles.textInput}
                />
              ) : (
                <View style={styles.chipRow}>
                  {f.options.map((opt) => (
                    <Chip
                      key={opt}
                      label={opt}
                      accent={activity.accent}
                      selected={fields[f.key] === opt}
                      onPress={() => setField(f.key, fields[f.key] === opt ? '' : opt)}
                    />
                  ))}
                </View>
              )}
            </View>
          ))}

          <T v="heading" style={styles.label}>
            {activity.photoRequired ? 'Fotky 📸' : 'Fotky (nepovinné) 📸'}
          </T>
          <PhotoPickerField uris={photos} accent={activity.accent} onChange={setPhotos} />

          <View style={{ marginTop: 26 }}>
            <PrimaryButton
              label={saving ? 'Ukládám…' : isEdit ? 'Uložit změny 💛' : 'Uložit a nakrmit 💛'}
              color={activity.accent}
              disabled={!canSave}
              onPress={handleSave}
            />
            {hint && (
              <T v="tiny" center color={C.inkSoft} style={{ marginTop: 8 }}>
                {hint}
              </T>
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>

      {feed && (
        <FeedCelebration
          activity={activity}
          result={feed}
          petName={pet.name}
          onDone={() => {
            setFeed(null);
            router.back();
          }}
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 14,
  },
  scroll: { padding: 18, paddingBottom: 46 },
  dateCard: { paddingVertical: 10, marginBottom: 4 },
  label: { marginTop: 18, marginBottom: 8 },
  noteInput: {
    backgroundColor: C.card,
    borderRadius: 18,
    borderWidth: 1.5,
    borderColor: C.line,
    padding: 14,
    minHeight: 116,
    textAlignVertical: 'top',
    fontFamily: F.body,
    fontSize: 15.5,
    lineHeight: 22,
    color: C.ink,
  },
  textInput: {
    backgroundColor: C.card,
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: C.line,
    paddingVertical: 12,
    paddingHorizontal: 14,
    fontFamily: F.body,
    fontSize: 15,
    color: C.ink,
  },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
});
