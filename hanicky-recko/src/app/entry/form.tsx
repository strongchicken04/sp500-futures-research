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
import Animated, { FadeIn } from 'react-native-reanimated';

import { PhotoPickerField } from '@/components/PhotoPickerField';
import { Card, Chip, IconButton, PrimaryButton, Screen, T } from '@/components/ui';
import { getCategory } from '@/config/categories';
import { C, F } from '@/config/theme';
import { formatDateTime } from '@/lib/czech';
import { genId } from '@/lib/id';
import { persistPhoto } from '@/lib/photos';
import { entryPhotos } from '@/lib/types';
import { useApp } from '@/state/AppContext';

export default function EntryFormScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ categoryId?: string; entryId?: string }>();
  const { getEntry, addEntry, updateEntry } = useApp();

  const entryId = typeof params.entryId === 'string' ? params.entryId : undefined;
  const existing = entryId ? getEntry(entryId) : undefined;
  const category = getCategory(existing?.categoryId ?? params.categoryId);
  const isEdit = !!existing;

  const [note, setNote] = useState(existing?.note ?? '');
  const [fields, setFields] = useState<Record<string, string>>(existing?.fields ?? {});
  const [photos, setPhotos] = useState<string[]>(existing ? entryPhotos(existing) : []);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const newIdRef = useRef(genId());
  const nowRef = useRef(Date.now());
  // Photos the entry already had are persisted; everything else is freshly picked.
  const initialPhotosRef = useRef<Set<string>>(new Set(existing ? entryPhotos(existing) : []));

  const hasAnything =
    note.trim().length > 0 ||
    photos.length > 0 ||
    Object.values(fields).some((v) => v.trim().length > 0);

  const canSave = useMemo(() => {
    if (saving) return false;
    if (category?.photoRequired) return photos.length > 0;
    return hasAnything;
  }, [saving, category?.photoRequired, photos.length, hasAnything]);

  if (!category) return <Redirect href="/" />;

  const setField = (key: string, value: string) =>
    setFields((prev) => {
      const next = { ...prev };
      if (value.trim().length === 0) delete next[key];
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
      } else {
        await addEntry({ id, categoryId: category.id, note, photoUris: storedUris, fields: cleanFields });
      }
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      setSaved(true);
      setTimeout(() => router.back(), 750);
    } finally {
      setSaving(false);
    }
  };

  const hint = category.photoRequired && photos.length === 0 ? 'Vyber aspoň jednu fotku 📸' : null;

  return (
    <Screen bg={category.pale} edges={Platform.OS === 'android' ? ['top', 'bottom'] : ['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.headerRow}>
          <IconButton accessibilityLabel="Zavřít" onPress={() => router.back()}>
            <Text style={{ fontSize: 15 }}>✕</Text>
          </IconButton>
          <T v="title" color={category.accentDark}>
            {category.emoji} {isEdit ? 'Upravit' : category.name}
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

          {category.fields.map((f) => (
            <View key={f.key}>
              <T v="heading" style={styles.label}>
                {f.label}
              </T>
              {f.type === 'text' && (
                <TextInput
                  value={fields[f.key] ?? ''}
                  onChangeText={(v) => setField(f.key, v)}
                  placeholder={f.placeholder}
                  placeholderTextColor={C.inkFaint}
                  style={styles.textInput}
                />
              )}
              {f.type === 'number' && (
                <View style={styles.numberRow}>
                  <TextInput
                    value={fields[f.key] ?? ''}
                    onChangeText={(v) => setField(f.key, v.replace(/\D/g, '').slice(0, 5))}
                    placeholder={f.placeholder}
                    placeholderTextColor={C.inkFaint}
                    keyboardType="number-pad"
                    inputMode="numeric"
                    style={[styles.textInput, { flex: 1 }]}
                  />
                  <T v="bodyBold" color={C.inkSoft}>
                    {f.suffix}
                  </T>
                </View>
              )}
              {f.type === 'picker' && (
                <View style={styles.chipRow}>
                  {f.options.map((opt) => (
                    <Chip
                      key={opt}
                      label={opt}
                      accent={category.accent}
                      selected={fields[f.key] === opt}
                      onPress={() => setField(f.key, fields[f.key] === opt ? '' : opt)}
                    />
                  ))}
                </View>
              )}
            </View>
          ))}

          <T v="heading" style={styles.label}>
            {category.noteLabel}
          </T>
          <TextInput
            value={note}
            onChangeText={setNote}
            placeholder={category.notePlaceholder}
            placeholderTextColor={C.inkFaint}
            multiline
            style={styles.noteInput}
          />

          <T v="heading" style={styles.label}>
            {category.photoRequired ? 'Fotky 📸' : 'Fotky (nepovinné) 📸'}
          </T>
          <PhotoPickerField uris={photos} accent={category.accent} onChange={setPhotos} max={8} />

          <View style={{ marginTop: 26 }}>
            <PrimaryButton
              label={saving ? 'Ukládám…' : isEdit ? 'Uložit změny 💙' : 'Uložit 💙'}
              color={category.accent}
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

      {saved && (
        <Animated.View entering={FadeIn.duration(160)} style={styles.savedOverlay} pointerEvents="none">
          <View style={styles.savedCard}>
            <Text style={{ fontSize: 40 }}>💙</Text>
            <T v="title" center style={{ marginTop: 4 }}>
              Uloženo!
            </T>
          </View>
        </Animated.View>
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
    minHeight: 110,
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
  numberRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  savedOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFFCC',
  },
  savedCard: { alignItems: 'center' },
});
